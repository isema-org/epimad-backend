import sys
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import CasEpidemique, Region

router = APIRouter()

@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    # 1. Calculer les sommes totales
    totals = db.query(
        func.sum(CasEpidemique.cas_nouveaux).label('total_cas'),
        func.sum(CasEpidemique.deces).label('total_deces'),
        func.sum(CasEpidemique.gueris).label('total_gueris'),
        func.sum(CasEpidemique.hospitalisations).label('total_hosp'),
    ).first()

    regions_actives = db.query(Region.id).join(CasEpidemique).distinct().count()

    return {
        "total_cas": totals.total_cas or 0,
        "total_deces": totals.total_deces or 0,
        "total_gueris": totals.total_gueris or 0,
        "total_hospitalisations": totals.total_hosp or 0,
        "regions_actives": regions_actives
    }