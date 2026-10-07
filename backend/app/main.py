from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import text
from app.core.config import settings
from app.db.database import Base, engine
from app.api.api import api_router

Base.metadata.create_all(bind=engine)

# Migração leve e idempotente: create_all não altera tabelas existentes.
# Adicionamos colunas introduzidas por versões novas do modelo, preservando
# os registros já armazenados.
with engine.connect() as _conn:
    for _coluna_sql in (
        "ALTER TABLE alertas_comunitarios ADD COLUMN urgencia VARCHAR DEFAULT 'media'",
        "ALTER TABLE alertas_comunitarios ADD COLUMN confirmacoes INTEGER DEFAULT 0",
        "ALTER TABLE alertas_comunitarios ADD COLUMN resumo_ia TEXT",
        "ALTER TABLE alertas_comunitarios ADD COLUMN moderado_ia BOOLEAN DEFAULT 0",
    ):
        try:
            _conn.execute(text(_coluna_sql))
            _conn.commit()
        except Exception:
            _conn.rollback()

app = FastAPI(title=settings.app_name)

FRONTEND_DIR = Path(__file__).resolve().parents[2]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)

@app.get("/health", include_in_schema=False)
def healthcheck():
    return {"status": "ok", "projeto": "Fala Segura API"}

PUBLIC_FILES = {
    "index.html", "app.js", "language.js", "chat-widget.js", "style.css",
    "manifest.webmanifest", "service-worker.js",
}
PUBLIC_DIRS = ("img", "video")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/{caminho:path}", include_in_schema=False)
def arquivo_publico(caminho: str):
    alvo = (FRONTEND_DIR / caminho).resolve()
    permitido = caminho in PUBLIC_FILES or (
        caminho.split("/")[0] in PUBLIC_DIRS and FRONTEND_DIR.resolve() in alvo.parents
    )
    if not permitido or not alvo.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(alvo)
