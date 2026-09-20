import { useEffect, useRef, useState } from "react";
import { API, WS_URL } from "../config";
import type { AstraState, ChatMsg } from "../types";

/** Speak via browser (fallback when server has no TTS audio). Picks te-IN voice when available. */
function browserSpeak(text: string, lang: string) {
  try {
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    const voices = speechSynthesis.getVoices();
    const want = lang === "te" || lang === "mixed" ? ["te-IN", "te"] : ["en-IN", "en"];
    for (const prefix of want) {
      const v = voices.find((x) => x.lang.startsWith(prefix));
      if (v) { u.voice = v; u.lang = v.lang; break; }
    }
    speechSynthesis.speak(u);
  } catch { /* ignore */ }
}

export function useVoiceSocket() {
  const [state, setState] = useState<AstraState>("OFFLINE");
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [langPref, setLangPref] = useState("AUTO");
  const [level, setLevel] = useState(0); // mic level for the orb
  const ws = useRef<WebSocket | null>(null);
  const media = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const audioEl = useRef<HTMLAudioElement | null>(null);
  const audioQueue = useRef<string[]>([]);
  const playing = useRef(false);
  const speechQueue = useRef<{ text: string; lang: string }[]>([]);
  const speaking = useRef(false);
  const watchdog = useRef<ReturnType<typeof setTimeout> | null>(null);
  const micLevels = useRef<number[]>([]);

  const push = (m: ChatMsg) => setMessages((p) => [...p, m]);
  const appendDelta = (d: string) =>
    setMessages((p) => {
      if (p.length === 0 || p[p.length - 1].role !== "assistant") return [...p, { role: "assistant", text: d }];
      const last = p[p.length - 1];
      return [...p.slice(0, -1), { role: "assistant", text: last.text + d }];
    });

  const connect = () => {
    setState("INITIALIZING");
    setMessages([]);          // never resume stale words from a previous session
    setConversationId(null);  // backend starts a brand-new conversation
    try {
      // Warm up the OS voice list early — getVoices() is async and often
      // empty on first call, which is one reason speech comes out silent.
      speechSynthesis.getVoices();
      speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices();
    } catch { /* */ }
    fetch(`${API}/api/session/start`, { method: "POST" }).catch(() => null);
    const sock = new WebSocket(WS_URL);
    ws.current = sock;
    sock.onopen = () => {
      setState("ONLINE");
      sock.send(JSON.stringify({ event: "config", language_preference: langPref,
        conversation_id: conversationId, voice: "browser" }));
    };
    sock.onmessage = async (ev) => {
      const m = JSON.parse(ev.data);
      switch (m.event) {
        case "config":
          if (m.conversation_id) setConversationId(m.conversation_id);
          break;
        case "state_change":
          setState(m.state === "ONLINE" ? "ONLINE" : m.state);
          if (m.state === "SPEAKING") speakStart.current = Date.now();
          if (m.state === "INTERRUPTED") stopAudio();
          break;
        case "transcription":
          break; // shown via user_message
        case "user_message":
          push({ role: "user", text: m.text });
          break;
        case "assistant_text":
          if (m.partial) push({ role: "assistant", text: "" });
          else if (m.text) {
            // final full text replaces the streamed partial
            setMessages((p) => {
              if (p.length && p[p.length - 1].role === "assistant")
                return [...p.slice(0, -1), { role: "assistant", text: m.text }];
              return [...p, { role: "assistant", text: m.text }];
            });
          }
          break;
        case "assistant_text_delta":
          appendDelta(m.delta || "");
          break;
        case "assistant_audio":
          if (m.final) break;
          if (m.audio_b64) enqueueAudio(`data:audio/mpeg;base64,${m.audio_b64}`);
          else if (m.audio_url) enqueueAudio(`${API}${m.audio_url}`);
          else if (m.text) enqueueSpeech(m.text, m.language);
          break;
        case "error":
          push({ role: "assistant", text: `⚠️ ${m.message}` });
          break;
      }
    };
    sock.onclose = () => setState("OFFLINE");
    sock.onerror = () => {
      setState("ERROR");
      push({ role: "assistant", text: "⚠️ Can't reach Ziva's backend on this machine — is it running (port 8000)?" });
    };
  };

  const disconnect = () => {
    // Fresh session next time: mic closed, queues cleared, no old words leak in.
    teardownCall();
    stopAudio();
    ws.current?.close();
    ws.current = null;
    setMessages([]);
    setConversationId(null);
    setState("OFFLINE");
  };

  const playNext = () => {
    if (playing.current) return;
    const next = audioQueue.current.shift();
    if (!next) return;
    playing.current = true;
    const a = new Audio(next);
    audioEl.current = a;
    a.onended = () => { playing.current = false; audioEl.current = null; playNext(); };
    a.onerror = () => { playing.current = false; audioEl.current = null; playNext(); };
    a.play().catch(() => { playing.current = false; playNext(); });
  };
  const enqueueAudio = (url: string) => { audioQueue.current.push(url); playNext(); };

  const speakNext = () => {
    if (speaking.current) return;
    const next = speechQueue.current.shift();
    if (!next) return;
    try {
      speaking.current = true;
      speechSynthesis.resume(); // Chrome pauses speech in background tabs
      const u = new SpeechSynthesisUtterance(next.text);
      const voices = speechSynthesis.getVoices();
      const want = next.lang === "te" || next.lang === "mixed" ? ["te-IN", "te"] : ["en-IN", "en"];
      u.lang = want[0]; // always set — without this Telugu text may stay silent
      for (const prefix of want) {
        const v = voices.find((x) => x.lang.startsWith(prefix));
        if (v) { u.voice = v; u.lang = v.lang; break; }
      }
      u.rate = 1.0;
      const done = () => {
        if (watchdog.current) clearTimeout(watchdog.current);
        speaking.current = false;
        speakNext();
      };
      u.onend = done;
      u.onerror = done;
      // Watchdog: if the OS never fires onend (blocked/no-voice), unstick the queue
      watchdog.current = setTimeout(() => {
        try { speechSynthesis.cancel(); } catch { /* */ }
        speaking.current = false;
        speakNext();
      }, Math.min(20000, 3000 + next.text.length * 120));
      speechSynthesis.speak(u);
    } catch { speaking.current = false; }
  };
  const enqueueSpeech = (text: string, lang: string) => { speechQueue.current.push({ text, lang }); speakNext(); };

  /** One-tap voice self-test: speaks immediately inside the click gesture.
   *  If THIS is silent, the OS/browser has no usable voice (not our pipeline). */
  const speakTest = () => {
    try {
      speechSynthesis.cancel();
      speaking.current = false;
      if (watchdog.current) clearTimeout(watchdog.current);
      const lang = langPref === "TELUGU" ? "te" : langPref === "HINDI" ? "hi" : "en";
      enqueueSpeech(
        lang === "te" ? "హే బాస్, నేను జివాని. నా మాట వినిపిస్తోందా?"
        : "Hey Boss, Ziva here. Can you hear me?",
        lang);
    } catch { /* speech unsupported */ }
  };

  const stopAudio = () => {
    audioQueue.current = [];
    speechQueue.current = [];
    playing.current = false;
    speaking.current = false;
    if (watchdog.current) clearTimeout(watchdog.current);
    try { speechSynthesis.cancel(); } catch { /* */ }
    audioEl.current?.pause();
    audioEl.current = null;
  };

  const interrupt = () => {
    stopAudio();
    ws.current?.send(JSON.stringify({ event: "interrupt" }));
  };

  /** Hold-to-talk: start/stop mic recording, send one audio_chunk per utterance. */
  const startTalk = async () => {
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch {
      push({ role: "assistant", text: "🎙 Microphone blocked — click the lock icon in the address bar, Allow the mic, then reload." });
      return;
    }
    const rec = new MediaRecorder(stream, { mimeType: "audio/webm" });
    media.current = rec;
    chunks.current = [];
    micLevels.current = [];
    const ctx = new AudioContext();
    const src = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    src.connect(analyser);
    const data = new Uint8Array(new ArrayBuffer(analyser.frequencyBinCount));
    const tick = () => {
      if (media.current !== rec) { ctx.close(); return; }
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (const v of data) sum += Math.abs(v - 128);
      const lv = Math.min(1, sum / data.length / 40);
      micLevels.current.push(lv);
      setLevel(lv);
      requestAnimationFrame(tick);
    };
    tick();
    rec.ondataavailable = (e) => { if (e.data.size) chunks.current.push(e.data); };
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      setLevel(0);
      setState("PROCESSING");
      // Noise gate: if the mic barely moved, it was silence/background hum —
      // don't waste 5s transcribing it, tell the user right away.
      const lv = micLevels.current;
      const avg = lv.length ? lv.reduce((a, b) => a + b, 0) / lv.length : 0;
      const peak = lv.length ? Math.max(...lv) : 0;
      const tooShort = lv.length < 20; // <~0.4s hold
      if ((avg < 0.008 && peak < 0.03) || tooShort) {
        push({ role: "assistant", text: "🔇 I didn't hear anything — hold TALK and speak up." });
        setState(ws.current?.readyState === WebSocket.OPEN ? "LISTENING" : "OFFLINE");
        return;
      }
      const blob = new Blob(chunks.current, { type: "audio/webm" });
      const reader = new FileReader();
      reader.onload = () => {
        const b64 = (reader.result as string).split(",")[1];
        ws.current?.send(JSON.stringify({ event: "audio_chunk", audio_b64: b64, mime: "audio/webm" }));
      };
      reader.readAsDataURL(blob);
    };
    rec.start();
    setState("LISTENING");
  };
  const stopTalk = () => { media.current?.stop(); media.current = null; };

  const sendText = (text: string) => {
    if (!text.trim()) return;
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify({ event: "text_message", text }));
    else {
      // No socket: REST fallback (same pipeline, no audio)
      fetch(`${API}/api/chat/text`, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, conversation_id: conversationId, language_preference: langPref }) })
        .then((r) => r.json()).then((d) => {
          setConversationId(d.conversation_id);
          push({ role: "user", text });
          push({ role: "assistant", text: d.reply });
          browserSpeak(d.reply, d.language);
        });
    }
  };

  useEffect(() => () => { ws.current?.close(); }, []);

  // ── CALL MODE: one tap → continuous listen ⇄ speak loop, like a phone call ──
  const [inCall, setInCall] = useState(false);
  const [hearingYou, setHearingYou] = useState(false);
  const call = useRef<{
    stream: MediaStream; ctx: AudioContext; analyser: AnalyserNode; data: Uint8Array<ArrayBuffer>;
    rec: MediaRecorder | null; chunks: Blob[]; capturing: boolean;
    loud: number; lastVoice: number; startedAt: number;
  } | null>(null);
  const stateRef = useRef(state);
  stateRef.current = state;
  const speakStart = useRef(0); // when ASTRA last started speaking (echo guard)

  const sendBlob = (blob: Blob) => {
    const reader = new FileReader();
    reader.onload = () => {
      const b64 = (reader.result as string).split(",")[1];
      ws.current?.send(JSON.stringify({ event: "audio_chunk", audio_b64: b64, mime: "audio/webm" }));
    };
    reader.readAsDataURL(blob);
  };

  const startCall = async () => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) connect();
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch {
      push({ role: "assistant", text: "🎙 Microphone blocked — click the lock icon in the address bar, Allow the mic, then reload." });
      return;
    }
    const ctx = new AudioContext();
    const src = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 2048;
    src.connect(analyser);
    call.current = { stream, ctx, analyser, data: new Uint8Array(new ArrayBuffer(analyser.frequencyBinCount)),
      rec: null, chunks: [], capturing: false, loud: 0, lastVoice: 0, startedAt: 0 };
    setInCall(true);
    setState("LISTENING");

    const level = () => {
      const c = call.current!;
      c.analyser.getByteTimeDomainData(c.data);
      let sum = 0;
      for (const v of c.data) sum += Math.abs(v - 128);
      const lv = Math.min(1, sum / c.data.length / 40);
      setLevel(lv);
      return lv;
    };
    const beginCapture = () => {
      const c = call.current!;
      // Barge-in, SPEAKING only: user is deliberately talking over ASTRA.
      if (stateRef.current === "SPEAKING") {
        stopAudio();
        ws.current?.send(JSON.stringify({ event: "interrupt" }));
      }
      const rec = new MediaRecorder(c.stream, { mimeType: "audio/webm" });
      c.rec = rec;
      c.chunks = [];
      c.capturing = true;
      c.lastVoice = performance.now();
      c.startedAt = performance.now();
      setHearingYou(true);
      rec.ondataavailable = (e) => { if (e.data.size) c.chunks.push(e.data); };
      rec.onstop = () => {
        const blob = new Blob(c.chunks, { type: "audio/webm" });
        c.rec = null;
        c.capturing = false;
        setHearingYou(false);
        if (blob.size > 2000) sendBlob(blob); // else: blip, ignore
      };
      rec.start();
    };
    const endCapture = () => {
      const c = call.current;
      if (c?.rec && c.rec.state !== "inactive") {
        setState("PROCESSING");
        c.rec.stop();
      }
    };
    const tick = () => {
      const c = call.current;
      if (!c) return;
      const lv = level();
      const now = performance.now();
      if (!c.capturing) {
        if (stateRef.current === "SPEAKING") {
          // She is talking: her own voice bleeds into the mic and bikes/fans
          // rumble on. So: ignore the first second entirely, then demand LOUD
          // sustained voice (a real person cutting in) before interrupting.
          const inGrace = Date.now() - speakStart.current < 1000;
          c.loud = !inGrace && lv > 0.14 ? c.loud + 1 : 0;
          if (c.loud >= 15) { c.loud = 0; beginCapture(); }
        } else {
          c.loud = lv > 0.07 ? c.loud + 1 : 0;   // sustained voice, not a door slam
          if (c.loud >= 5) { c.loud = 0; beginCapture(); }
        }
      } else {
        // Capturing: refresh the voice clock on any sound, end the turn only
        // after a full 1.2s of quiet — pauses between words/sentences stay
        // in ONE turn instead of splitting into two questions.
        if (lv >= 0.035) c.lastVoice = now;
        const quietFor = now - c.lastVoice;
        const tooLong = now - c.startedAt > 25000;
        if (quietFor >= 1200 || tooLong) endCapture();
      }
      requestAnimationFrame(tick);
    };
    tick();
  };

  const endCall = () => {
    teardownCall();
    setInCall(false);
    setHearingYou(false);
    stopAudio();
    setState("ONLINE");
  };

  // Shared teardown for END CALL and DEACTIVATE (also used mid-call).
  function teardownCall() {
    const c = call.current;
    call.current = null;
    setInCall(false);
    setHearingYou(false);
    setLevel(0);
    try {
      if (c?.rec && c.rec.state !== "inactive") c.rec.stop();
      c?.stream.getTracks().forEach((t) => t.stop());
      c?.ctx.close();
    } catch { /* */ }
  }

  return { state, messages, connect, disconnect, startTalk, stopTalk, sendText, interrupt,
    langPref, setLangPref, level, inCall, hearingYou, startCall, endCall, speakTest };
}
