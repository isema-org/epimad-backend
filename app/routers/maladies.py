import sys
from pathlib import Path
from sqlalchemy import text
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Maladie
from app.schemas import MaladieRead

router = APIRouter(prefix="/api", tags=["Maladies"])

@router.get("/maladies", response_model=List[MaladieRead])
def get_all_maladies(db: Session = Depends(get_db)):
    """
    Récupère toutes les maladies.
    """
    maladies = db.query(Maladie).order_by(Maladie.nom_officiel).all()
    if not maladies:
        raise HTTPException(status_code=404, detail="Aucune maladie trouvée.")
    return maladies

@router.get("/maladies/overview", tags=["Maladies - Statistiques"])
def get_maladies_overview(db: Session = Depends(get_db)):
    """
    Retourne la liste des maladies avec leurs statistiques calculées à la volée.
    """
    maladies = db.query(Maladie).order_by(Maladie.nom_officiel).all()
    current_year = datetime.now().year
    result = []

    for m in maladies:
        stats_query = text("""
            SELECT 
                MIN(date_observation) as min_date,
                MAX(date_observation) as max_date,
                SUM(CASE WHEN EXTRACT(YEAR FROM date_observation) = :year THEN COALESCE(cas_nouveaux, 0) ELSE 0 END) as total_year
            FROM cas_epidemiques
            WHERE maladie_id = :mid
        """)
        stats = db.execute(stats_query, {"year": current_year, "mid": m.id}).fetchone()

        min_date = stats.min_date
        max_date = stats.max_date
        total_year = stats.total_year or 0

        periode = "Aucune donnée"
        derniere_maj = "-"
        if min_date and max_date:
            periode = f"{min_date.strftime('%b %Y')} - {max_date.strftime('%b %Y')}"
            derniere_maj = max_date.strftime('%d/%m/%Y')

    
        trend_query = text("""
            SELECT date_observation, SUM(cas_nouveaux) as total_cases
            FROM cas_epidemiques
            WHERE maladie_id = :mid
            GROUP BY date_observation
            ORDER BY date_observation DESC
            LIMIT 8
        """)
        weekly_data = db.execute(trend_query, {"mid": m.id}).fetchall()

        tendance = "stable"
        icone_tendance = "➡️"
        periode_1_total = 0 
        periode_2_total = 0  
        variation_pct = 0.0
        
        if len(weekly_data) >= 8:
            periode_1_total = sum([row.total_cases for row in weekly_data[4:8]])
            
            periode_2_total = sum([row.total_cases for row in weekly_data[0:4]])
            if periode_1_total > 0:
                variation_pct = ((periode_2_total - periode_1_total) / periode_1_total) * 100
            
            if variation_pct > 10:
                tendance = "hausse"
                icone_tendance = "📈"
            elif variation_pct < -10:
                tendance = "baisse"
                icone_tendance = "📉"
            else:
                tendance = "stable"
                icone_tendance = "➡️"
                
        elif len(weekly_data) > 0:
            tendance = "nouvelle"
            icone_tendance = "✨"
            periode_1_total = sum([row.total_cases for row in weekly_data])

        est_actif = getattr(m, "actif", True)
        result.append({
            "id": m.id,
            "nom": m.nom_officiel,
            "code": m.code_maladie,
            "actif": est_actif,
            "periode": periode,
            "derniere_maj": derniere_maj,
            "tendance": tendance,
            "icone_tendance": icone_tendance,
            "total_cas_annee": total_year,
            "periode_1_total": periode_1_total,
            "periode_2_total": periode_2_total,
            "variation_pct": round(variation_pct, 1)
        })
        
    return result