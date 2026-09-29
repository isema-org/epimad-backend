import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import List, Optional
from datetime import timedelta

from app.models import CasEpidemique, Region, Maladie

from app.database import get_db
from app.models import CasEpidemique, Region
from app.schemas import CasEpidemiqueRead

router = APIRouter()

@router.get("/cas", response_model=List[CasEpidemiqueRead], tags=["Cas Épidémiques"])
def get_all_cas(
    skip: int = 0,
    limit: int = 100,
    maladie_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Récupère tous les cas épidémiques avec pagination et filtrage par maladie."""
    query = db.query(CasEpidemique)
    
    if maladie_id is not None:
        query = query.filter(CasEpidemique.maladie_id == maladie_id)
    
    cas = query.order_by(CasEpidemique.date_observation.desc()).offset(skip).limit(limit).all()
    return cas

FENETRE_SEMAINES_PAR_MALADIE = {
    'covid19': None,
    'paludisme': 52,
}

@router.get("/carto", tags=["Cartographie"])
def get_carto_data(
    maladie_id: Optional[int] = Query(None, description="ID de la maladie a afficher"),
    db: Session = Depends(get_db)
):
    try:
        code_maladie = None
        if maladie_id is not None:
            maladie_row = db.query(Maladie.code_maladie).filter(Maladie.id == maladie_id).first()
            if maladie_row:
                code_maladie = maladie_row.code_maladie

        fenetre_semaines = FENETRE_SEMAINES_PAR_MALADIE.get(code_maladie, 52)
        print(f"DEBUG: maladie_id={maladie_id}, code_maladie={code_maladie}, fenetre_semaines={fenetre_semaines}")

        ordre_case = case(
            (CasEpidemique.niveau_alerte == 'Rouge', 4),
            (CasEpidemique.niveau_alerte == 'Orange', 3),
            (CasEpidemique.niveau_alerte == 'Jaune', 2),
            (CasEpidemique.niveau_alerte == 'Vert', 1),
            else_=0
        )

        date_limite = None
        if fenetre_semaines is not None:
            date_max_sous_requete = db.query(func.max(CasEpidemique.date_observation))
            if maladie_id is not None:
                date_max_sous_requete = date_max_sous_requete.filter(CasEpidemique.maladie_id == maladie_id)
            date_reference = date_max_sous_requete.scalar()
            date_limite = date_reference - timedelta(weeks=fenetre_semaines) if date_reference else None

        pire_niveau_sous_requete = db.query(
            CasEpidemique.region_id,
            func.max(ordre_case).label('pire_score')
        )
        if maladie_id is not None:
            pire_niveau_sous_requete = pire_niveau_sous_requete.filter(CasEpidemique.maladie_id == maladie_id)
        if date_limite is not None:
            pire_niveau_sous_requete = pire_niveau_sous_requete.filter(CasEpidemique.date_observation >= date_limite)
        pire_niveau_sous_requete = pire_niveau_sous_requete.group_by(CasEpidemique.region_id).subquery()

        mapping_score_niveau = {4: 'Rouge', 3: 'Orange', 2: 'Jaune', 1: 'Vert', 0: 'Vert'}

        query = db.query(
            Region.id,
            Region.nom_region,
            Region.latitude,
            Region.longitude,
            Region.population_totale,
            func.coalesce(func.sum(CasEpidemique.cas_nouveaux), 0).label('total_cas'),
            func.coalesce(func.sum(CasEpidemique.deces), 0).label('total_deces'),
            func.coalesce(func.sum(CasEpidemique.gueris), 0).label('total_gueris'),
            pire_niveau_sous_requete.c.pire_score
        )

        query = query.join(CasEpidemique, Region.id == CasEpidemique.region_id)
        query = query.outerjoin(pire_niveau_sous_requete, Region.id == pire_niveau_sous_requete.c.region_id)

        if maladie_id is not None:
            query = query.filter(CasEpidemique.maladie_id == maladie_id)

        query = query.group_by(
            Region.id,
            Region.nom_region,
            Region.latitude,
            Region.longitude,
            Region.population_totale,
            pire_niveau_sous_requete.c.pire_score
        )

        results = query.all()

        resultats = []
        for r in results:
            niveau_brut = mapping_score_niveau.get(r.pire_score, 'Vert').lower()
            mapping_niveau = {
                'vert': 'stable',
                'jaune': 'modere',
                'orange': 'eleve',
                'rouge': 'critique'
            }
            niveau = mapping_niveau.get(niveau_brut, 'stable')

            resultats.append({
                "id": r.id,
                "nom": r.nom_region,
                "lat": float(r.latitude) if r.latitude else 0.0,
                "lng": float(r.longitude) if r.longitude else 0.0,
                "cas": int(r.total_cas or 0),
                "deces": int(r.total_deces or 0),
                "gueris": int(r.total_gueris or 0),
                "pop": int(r.population_totale or 0),
                "niveau": niveau
            })

        return resultats

    except Exception as e:
        print(f"ERREUR CRITIQUE BACKEND /carto: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))