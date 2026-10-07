from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import Denuncia
from app.schemas.schemas import DenunciaCreate, DenunciaOut

router = APIRouter(prefix="/denuncias", tags=["Denúncia"])

@router.post("/", response_model=DenunciaOut)
def criar_denuncia(dados: DenunciaCreate, db: Session = Depends(get_db)):
    denuncia = Denuncia(**dados.model_dump())
    db.add(denuncia)
    db.commit()
    db.refresh(denuncia)
    return denuncia
