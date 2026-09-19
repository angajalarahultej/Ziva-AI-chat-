# ASTRA — Real-Time Multilingual AI Voice Companion

English + Telugu (+ optional Hindi), voice-first, with memory + knowledge + free-LLM fallback.

## 1. Setup (2 min)

```bash
cd astra
cp .env.example .env   # ← ONE env file for everything
```

Open `.env` and paste your free-model key (you'll give this next):

```ini
OPENROUTER_API_KEY=sk-or-v1-...     # ← paste here
LLM_MODEL=tngtech/deepseek-r1t2-chimera:free   # change to any free model, anytime
LLM_FALLBACK_MODEL=meta-llama/llama-3.3-70b-instruct:free
```

No key needed for voice: STT = local Whisper, TTS = Edge-TTS (te-IN + en-IN) with browser-speech fallback.

## 2. Run

```bash
bash run.sh
# backend → http://localhost:8000  (docs: /docs, health: /health)
# frontend → http://localhost:5173
```

Or manually:

```bash
pip install -r backend/requirements.txt
pytest backend/tests -q
cd backend && uvicorn app.main:app --port 8000
cd frontend && npm install && npm run dev
```

## 3. Talk to ASTRA

1. Open http://localhost:5173 → **ACTIVATE ASTRA**
2. **Hold TALK**, speak (“Naku Python gurinchi simple ga explain cheyyi”), release
3. ASTRA transcribes → thinks (memory + knowledge + LLM) → speaks back
4. **INTERRUPT** stops her mid-speech (barge-in). Typing also works (no mic needed).

## 4. Test cases

- English: “Hello ASTRA.” / “Tell me a joke.” / “What is Python?”
- Telugu: “హాయ్ ఆస్ట్రా” / “నువ్వు ఎలా ఉన్నావు?” / “Python అంటే ఏంటి?”
- Mixed: “Naku Python nerchukovali, ekkada start cheyyali?” / “Machine learning ni simple ga Telugu lo explain cheyyi.”
- Memory: “Remember that I prefer Python.” → later “What programming language do I prefer?”
- No-key behavior: without `OPENROUTER_API_KEY`, ASTRA replies with a clear error instead of crashing.

## 5. Structure

```
astra/
├── .env / .env.example      # single config (keys, voices, models)
├── backend/app/
│   ├── api/routes.py        # REST: conversations, memories, documents, settings, chat/text
│   ├── websocket/voice.py   # /ws/voice real-time loop + barge-in
│   ├── services/llm|stt|tts # swappable providers (OpenRouter / Whisper / Edge-TTS)
│   ├── services/memory|knowledge|conversation
│   └── core/astra_prompt.py # personality (editable)
└── frontend/src/            # React + Tailwind + Framer Motion dashboard
```

## 6. Swapping later

- New LLM: just change `LLM_MODEL` in `.env` — no code change.
- Local model / new provider: add a class implementing `LLMProvider.chat()`.
- New STT/TTS: implement `STTProvider.transcribe()` / `TTSProvider.synthesize()`.
- Vector memory: replace `long_term.search()` / `knowledge.retrieve()` with pgvector.
