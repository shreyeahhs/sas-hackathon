# NightOut Planner (sas-hackathon)

A fast event/venue planner with a nightly cache, GPT-aided recommendations, and a modern Vite + React TypeScript frontend.

## Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- Optional: Google Places API key, OpenAI key (if you enable GPT and venue details as in the backend)

## Backend (FastAPI)

1) Install dependencies

```cmd
pip install -r requirements.txt
```

2) Run the server (default http://localhost:8000)

**Important:** Run uvicorn from the project root (d:\sas-hackathon), not from inside the backend/ folder.

```cmd
uvicorn backend.backend3:app --reload --port 8000
```

Or if you have a venv inside backend/:

```cmd
backend\venv\Scripts\python.exe -m uvicorn backend.backend3:app --reload --port 8000
```

3) Useful endpoints
- POST /api/events/live — returns events (uses cached CSV), accepts category, venue, today_only
- GET  /api/events/refresh — refreshes CSV cache on demand
- GET  /api/events/categories — returns category list
- GET  /api/recommendations/marquee — returns curated marquee items (title @ venue) from recent events
- POST /chat — chatbot endpoint for conversational planning (requires session_id and message)

Make sure CORS is enabled (already done in the backend code) so the frontend can call these endpoints.

## Frontend (Vite + React + TypeScript)

The frontend lives in `frontend/`.

1) Install dependencies

```cmd
cd frontend
npm install
```

2) Run the dev server

- Recommended on Windows: use Command Prompt (cmd), not PowerShell.

```cmd
npm run dev
```

Vite will print a URL like http://localhost:5173

If you are using PowerShell and see a policy error like “npm.ps1 cannot be loaded because running scripts is disabled”, you have three options:

- Easiest: call npm via the cmd shim

```powershell
npm.cmd run dev
```

- Or adjust your PowerShell execution policy for the current user

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
```

- Or simply run the command in a Command Prompt terminal instead of PowerShell.

3) Build for production

```cmd
npm run build
```

Static files will be emitted to `frontend/dist/`.

## Configuration

- The frontend talks to the backend at `http://localhost:8000` (see `frontend/src/api.ts`). If your backend runs elsewhere, update `API_BASE` accordingly.
- **AI Mode**: Now uses a chat interface instead of a wizard modal. Click "Try AI Mode" or "AI Mode" button to open a conversational planner.
  - The AI asks preliminary questions (mood, group size, budget) and adapts to your responses.
  - You can chat naturally to refine your requirements; the AI will update recommendations dynamically.
  - Recommendations (events and venues) appear inline in the chat with images, links, and map locations.
  - Each chat session maintains state via a unique `session_id` sent to the backend.

## Troubleshooting

- If events look out of date, hit `/api/events/refresh` in the browser to refresh the CSV cache.
- If images don’t show, the source page might not have images for that event; we surface `image_url` when available.
- If the frontend can’t reach the backend, confirm ports, CORS, and that `API_BASE` points to your server.
