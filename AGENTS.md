# Codex Instructions (folio-enrich)

## Project Conventions
- Backend: Python/FastAPI in `backend/`, venv at `backend/.venv/`
- Run tests: `cd backend && .venv/bin/python -m pytest tests/ -v`
- Run server: `cd backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8731 --reload`
- Frontend: Single-file `frontend/index.html` (vanilla JS, no build step)

## UX
- When discussing UI/UX topics, always apply UX best practices (accessibility, consistency, feedback, error prevention, progressive disclosure, proximity, hierarchy, contrast, etc.) without being asked.
