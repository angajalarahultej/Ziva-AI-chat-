import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Orb } from "./components/Orb";
import { LastExchange } from "./components/Transcript";
import { useVoiceSocket } from "./hooks/useVoiceSocket";

const SUGGESTIONS = [
  { tag: "తెలుగు", title: "Talk in Telugu", text: "Let's talk in Telugu. నాతో తెలుగులో మాట్లాడు.", tint: "rgba(125,211,252,0.08)", chip: "bg-sky-200 text-slate-900" },
  { tag: "English", title: "Chat in English", text: "Let's continue in English.", tint: "rgba(252,165,165,0.08)", chip: "bg-rose-200 text-slate-900" },
  { tag: "Mixed", title: "Surprise me", text: "Tell me something interesting, mix Telugu and English.", tint: "rgba(187,247,208,0.08)", chip: "bg-green-200 text-slate-900" },
];

const LANGS = ["AUTO", "ENGLISH", "TELUGU", "HINDI"];

export default function App() {
  const v = useVoiceSocket();
  const [text, setText] = useState("");
  const offline = v.state === "OFFLINE" || v.state === "ERROR";

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#07080c] text-slate-100">
      <div className="astra-grid pointer-events-none absolute inset-0" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_40%,rgba(0,0,0,0.6)_100%)]" />

      <div className="relative flex min-h-screen">
        {/* top-right status — pinned to the screen's right edge */}
        <main className="mx-auto flex w-full max-w-3xl flex-col items-center px-5 pb-10 pt-6">
          <div className="absolute right-4 top-5">
            <div className="glass-bar flex items-center gap-2 rounded-full px-4 py-1.5 text-xs text-slate-300">
              <span
                className={`h-2 w-2 rounded-full ${offline ? "" : "pulse-dot"}`}
                style={{ background: offline ? "#525c73" : "#2dd4bf" }}
              />
              {offline ? "Ziva offline" : v.inCall ? `On call · ${v.state.toLowerCase()}` : `Online · ${v.state.toLowerCase()}`}
              {v.hearingYou && <span className="text-emerald-300">· hearing you…</span>}
            </div>
          </div>

          {/* entity */}
          <div className="mt-2">
            <Orb state={v.state} level={v.level} />
          </div>

          {/* last exchange only */}
          <div className="mt-4 min-h-[110px]">
            <LastExchange messages={v.messages} />
          </div>

          {/* suggestion cards */}
          <AnimatePresence>
            {!offline && !v.inCall && v.messages.length === 0 && (
              <motion.div
                initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                className="mt-6 grid w-full grid-cols-1 gap-3 sm:grid-cols-3"
              >
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s.title}
                    onClick={() => v.sendText(s.text)}
                    className="rounded-2xl border border-white/5 p-4 text-left transition hover:border-teal-300/30"
                    style={{ background: s.tint }}
                  >
                    <span className={`inline-block rounded-md px-2.5 py-1 text-xs font-semibold ${s.chip}`}>{s.tag}</span>
                    <div className="mt-2 text-sm text-slate-400">{s.title}</div>
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── control bar ── */}
          <div className="glass-bar mt-6 w-full rounded-2xl p-3">
            {offline ? (
              <button
                onClick={v.connect}
                className="w-full rounded-xl bg-teal-300 py-3.5 text-sm font-bold tracking-[0.25em] text-slate-950 transition hover:bg-teal-200"
              >
                ACTIVATE ZIVA
              </button>
            ) : (
              <div className="flex flex-col gap-2">
                <div className="flex flex-col gap-2 sm:flex-row">
                  {v.inCall ? (
                    <button
                      onClick={v.endCall}
                      className="flex-1 rounded-xl bg-red-400/90 py-3 text-sm font-bold tracking-widest text-slate-950 transition hover:bg-red-300"
                    >
                      ⏹ END CALL
                    </button>
                  ) : (
                    <button
                      onClick={v.startCall}
                      className="flex-1 rounded-xl bg-teal-300 py-3 text-sm font-bold tracking-widest text-slate-950 transition hover:bg-teal-200"
                    >
                      📞 START CALL
                    </button>
                  )}
                  <select
                    value={v.voiceName}
                    onChange={(e) => v.setVoiceName(e.target.value)}
                    title="Voice"
                    className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none"
                  >
                    {["Female", "Male"].map((x) => <option key={x} value={x} className="bg-slate-900">{x}</option>)}
                  </select>
                  <select
                    value={v.langPref}
                    onChange={(e) => v.setLangPref(e.target.value)}
                    title="Language"
                    className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none"
                  >
                    {LANGS.map((l) => <option key={l} value={l} className="bg-slate-900">{l}</option>)}
                  </select>
                  <button
                    onClick={v.speakTest}
                    title="Test speaker — if this is silent, the device has no usable voice"
                    className="rounded-xl border border-white/10 px-4 py-3 text-sm transition hover:border-white/25"
                  >
                    🔊
                  </button>
                  <button
                    onClick={() => { if (v.inCall) v.endCall(); v.disconnect(); }}
                    className="rounded-xl border border-white/10 px-5 py-3 text-sm text-slate-300 transition hover:border-white/25"
                  >
                    Deactivate
                  </button>
                </div>
                <form
                  className="flex gap-2"
                  onSubmit={(e) => { e.preventDefault(); v.sendText(text); setText(""); }}
                >
                  <input
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="Ask me anything…"
                    className="flex-1 rounded-xl border border-white/10 bg-black/30 px-4 py-2.5 text-sm outline-none placeholder:text-slate-600 focus:border-teal-300/40"
                  />
                  <button className="rounded-xl bg-teal-300 px-4 text-lg font-bold text-slate-950">↑</button>
                </form>
              </div>
            )}
          </div>

          <p className="mt-4 text-center text-xs text-slate-600">
            {v.inCall
              ? "Hands-free — just speak. Talk over her to interrupt."
              : offline
                ? "Activate, then start a call — Telugu, English, or mixed."
                : "Tip: START CALL is hands-free like a phone call."}
          </p>
        </main>
      </div>
    </div>
  );
}
