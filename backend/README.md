# Backend (FastAPI)

## 起動（uv）

```bash
cd backend
uv sync
uv run --env-file .env uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
