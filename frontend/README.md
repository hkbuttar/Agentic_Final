# Frontend

React (Vite) UI for the voice-to-voice product discovery assistant. Calls
[../src/api](../src/api) — see the top-level README's
[Interface](../README.md#interface) section for the feature/component mapping.

```bash
npm install
cp .env.example .env   # set VITE_API_BASE_URL if the API isn't on localhost:8080
npm run dev
```

Requires the backend API (`src/api/app.py`) running separately.

## Structure

- `src/App.jsx` — orchestrates record/type → transcribe → query → answer
- `src/api.js` — `fetch` wrappers for `/transcribe`, `/query`, `/speak`
- `src/components/` — `Recorder`, `AgentTrace`, `ComparisonTable`, `AnswerPanel`
