# Dev Setup — How to Run the Application

## 2 Servers (both must be running)

### 1. Vite Dev Server (port 5173) — React Frontend
**This is the URL users open in the browser.**
```bash
export PATH="/Users/its-dev2/my-agent-app/.node/bin:$PATH"
cd /Users/its-dev2/my-agent-app/frontend
npm run dev
```
- node/npm location: `/Users/its-dev2/my-agent-app/.node/bin/`
- URL: http://localhost:5173

### 2. Chainlit Backend (port 8000) — WebSocket/API + Auth + Media
```bash
source /Users/its-dev2/my-agent-app/venv/bin/activate
cd /Users/its-dev2/my-agent-app
PYTHONPATH=/Users/its-dev2/my-agent-app chainlit run app.py --host 0.0.0.0 --port 8000
```
- venv location: `/Users/its-dev2/my-agent-app/venv/`
- **MUST run `app.py`** (NOT `backend/handlers/chat.py`) — app.py registers all HTTP endpoints:
  - `GET /api/media/{file_path}` — serves generated images, videos, attachments
  - `POST /api/auth/login`, `/verify`, `/logout` — authentication
  - `GET /api/auth/login-url` — System81 OAuth login URL
  - `POST /api/upload` — file upload
  - CORS middleware
- URL: http://localhost:8000 (DO NOT open in browser — this is Chainlit's own UI)

## Vite Proxy Configuration

`frontend/vite.config.ts` routes all `/api/*` to port 8000 (Chainlit):
- `/api/auth/*` → port 8000
- `/api/media/*` → port 8000
- `/api/upload` → port 8000
- `/ws/*` → port 8000 (WebSocket)
- `/project/*` → port 8000
- `/public/*` → port 8000

## Critical Rules

- **NEVER open port 8000 in the browser** — that's Chainlit's own UI, not our React app
- **ALWAYS open http://localhost:5173** for the user
- **MUST run `app.py`** not `backend/handlers/chat.py` — app.py has all HTTP endpoints
- node/npm are NOT in the default PATH — must export from `.node/bin/`
