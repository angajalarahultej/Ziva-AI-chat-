#!/bin/bash
# Run ASTRA locally: backend :8000 + frontend :5173
set -e
cd "$(dirname "$0")"
cp -n .env.example .env 2>/dev/null || true
echo "→ backend deps…"
python3 -m pip install -q -r backend/requirements.txt
echo "→ tests…"
python3 -m pytest backend/tests -q
echo "→ starting backend :8000…"
cd backend && python3 -m uvicorn app.main:app --port 8000 &
BACK_PID=$!
cd ../frontend
if [ ! -d node_modules ]; then echo "→ npm install…"; npm install; fi
echo "→ starting frontend :5173…"
npm run dev &
wait $BACK_PID
