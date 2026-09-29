import sys
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Region
from app.schemas import RegionRead

router = APIRouter()

@router.get("/regions", response_model=List[RegionRead], tags=["Régions"])
def get_all_regions(db: Session = Depends(get_db)):
    """
    Récupère toutes les 24 régions de Madagascar.
    """
    regions = db.query(Region).order_by(Region.nom_region).all()
    if not regions:
        raise HTTPException(status_code=404, detail="Aucune région trouvée.")
    return regions

@router.get("/regions/{region_id}", response_model=RegionRead, tags=["Régions"])
def get_region_by_id(region_id: int, db: Session = Depends(get_db)):
    """
    Récupère les détails d'une région spécifique.
    """
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Région non trouvée.")
    return region
