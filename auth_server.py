"""Backend entry point — runs on port 8001."""

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.utils.auth import router as auth_router
from src.utils.chat import router as chat_router
from src.utils.extract import router as extract_router
from src.utils.sessions import router as sessions_router
from src.utils.database import init_db

load_dotenv()

app = FastAPI(title="Sentinel AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(extract_router)
app.include_router(sessions_router)

init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("auth_server:app", host="0.0.0.0", port=8001, reload=True)
