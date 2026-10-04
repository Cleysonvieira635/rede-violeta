from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from app.core.config import settings
from app.db.database import Base, engine
from app.api.api import api_router

Base.metadata.create_all(bind=engine)

# Migração leve e idempotente: bancos criados antes da coluna 'resumo_ia'/
# 'moderado_ia' existir no modelo não ganham essas colunas automaticamente
# via create_all (que só cria tabelas novas, não altera tabelas já
# existentes). Tentamos adicionar as colunas e ignoramos o erro caso elas
# já existam — funciona tanto em SQLite quanto em Postgres.
with engine.connect() as _conn:
    for _coluna_sql in (
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
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)

@app.get("/health", include_in_schema=False)
def healthcheck():
    return {"status": "ok", "projeto": "Fala Segura API"}

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
