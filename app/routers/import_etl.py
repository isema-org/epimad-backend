from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import List, Dict, Any
from sqlalchemy.dialects.postgresql import insert
from app.database import get_db
from app.models import User, HistoriqueImport, CasEpidemique, Maladie, Region
from app.schemas import ImportDraftRequest, ImportVerifyRequest, HistoriqueImportResponse
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/import", tags=["Import ETL"])

def parse_date(date_str: str) -> date:
    """Convertir une chaîne de caractères en objet date, peu importe le format."""
    if not date_str:
        return datetime.utcnow().date()
    
    date_str = str(date_str).strip()
    
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        try:
            return datetime.strptime(date_str, "%Y/%m/%d").date()
        except ValueError:
            return date.fromisoformat(date_str)
@router.post("/draft", status_code=status.HTTP_201_CREATED)
def creer_brouillon(
    payload: ImportDraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Étape 1 : Sauvegarde les données en tant que brouillon."""
    if current_user.role not in ["Admin", "Saisisseur"]:
        raise HTTPException(status_code=403, detail="Accès refusé.")

    nouvel_import = HistoriqueImport(
        user_id=current_user.id,
        nom_donnees=payload.nom_donnees,
        maladie_nom=payload.maladie_nom,
        type_import=payload.type_import,
        donnees_brutes=payload.donnees,
        statut="Brouillon"
    )
    db.add(nouvel_import)
    db.commit()
    db.refresh(nouvel_import)
    
    return {"id": nouvel_import.id, "message": "Brouillon sauvegardé avec succès."}


@router.put("/{import_id}/verify")
def verifier_donnees(
    import_id: int,
    payload: ImportVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Étape 2 : L'utilisateur corrige les données et valide."""
    import_record = db.query(HistoriqueImport).filter(HistoriqueImport.id == import_id).first()
    if not import_record:
        raise HTTPException(status_code=404, detail="Import non trouvé.")
    
    if import_record.user_id != current_user.id and current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Non autorisé à modifier cet import.")

    if import_record.statut != "Brouillon":
        raise HTTPException(status_code=400, detail="Cet import n'est plus en statut Brouillon.")

    import_record.donnees_brutes = payload.donnees_corrigees
    import_record.statut = "Verifie"
    import_record.date_verification = datetime.utcnow()
    
    db.commit()
    return {"message": "Données vérifiées et prêtes pour l'ETL."}


@router.post("/{import_id}/submit-etl")
def soumettre_etl(
    import_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Étape 3 : Traitement ETL réel. Insère les données dans les tables de production."""
    import_record = db.query(HistoriqueImport).filter(HistoriqueImport.id == import_id).first()
    if not import_record:
        raise HTTPException(status_code=404, detail="Import non trouvé.")

    if import_record.statut != "Verifie":
        raise HTTPException(status_code=400, detail="Les données doivent être vérifiées avant soumission ETL.")

    try:
        # 1. Trouver ou créer la Maladie
        maladie = db.query(Maladie).filter(Maladie.nom_officiel.ilike(import_record.maladie_nom)).first()
        if not maladie:
            maladie = Maladie(
                code_maladie=f"MAL-{datetime.utcnow().strftime('%Y%m%d%H%M')}",
                nom_officiel=import_record.maladie_nom,
                agent_pathogene="Inconnu",
                type_maladie="Épidémique"
            )
            db.add(maladie)
            db.commit()
            db.refresh(maladie)

        records_to_upsert = []
        
        for row in import_record.donnees_brutes:
            
            cas_nouveaux = int(row.get("cas_notifies") or row.get("nouveaux_cas_confirmes") or row.get("cas") or 0)
            deces = int(row.get("deces") or row.get("nouveaux_deces") or 0)
            gueris = int(row.get("guerisons") or row.get("gueris") or 0)
            hospitalisations = int(row.get("hospitalisations") or row.get("hospitalises") or 0)
            
            taux_incidence = 0.0
            if row.get("taux_positivite"):
                try:
                    taux_incidence = float(row.get("taux_positivite"))
                except:
                    pass

            
            region_nom = row.get("region", "Inconnue")
            region = db.query(Region).filter(Region.nom_region.ilike(region_nom)).first()
            if not region:
                region = Region(code_region=f"REG-{len(region_nom)}", nom_region=region_nom, population_totale=0)
                db.add(region)
                db.commit()
                db.refresh(region)

            
            records_to_upsert.append({
                "date_observation": parse_date(row.get("date", datetime.utcnow().strftime("%Y-%m-%d"))),
                "semaine_epidemio": f"S{datetime.utcnow().isocalendar()[1]}",
                "region_id": region.id,
                "maladie_id": maladie.id,
                "cas_nouveaux": cas_nouveaux,
                "deces": deces,
                "gueris": gueris,
                "hospitalisations": hospitalisations,
                "taux_incidence": taux_incidence,
                "taux_letalite": 0.0,
                "niveau_alerte": "Normal"
            })

        stmt = insert(CasEpidemique).values(records_to_upsert)
        
        stmt = stmt.on_conflict_do_update(
            index_elements=['date_observation', 'region_id', 'maladie_id'],
            set_=dict(
                cas_nouveaux=stmt.excluded.cas_nouveaux,
                deces=stmt.excluded.deces,
                gueris=stmt.excluded.gueris,
                hospitalisations=stmt.excluded.hospitalisations,
                taux_incidence=stmt.excluded.taux_incidence,
                semaine_epidemio=stmt.excluded.semaine_epidemio,
                niveau_alerte=stmt.excluded.niveau_alerte
            )
        )
        
        db.execute(stmt)
        cas_crees = len(records_to_upsert)

        import_record.statut = "Importe"
        import_record.date_import_etl = datetime.utcnow()
        
        db.commit()
        return {"message": f"ETL réussi : {cas_crees} cas insérés avec succès.", "cas_crees": cas_crees}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement ETL : {str(e)}")


@router.get("/history", response_model=List[HistoriqueImportResponse])
def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Récupère l'historique des imports (filtré par rôle)."""
    
    # Requête de base
    query = db.query(HistoriqueImport).join(User, HistoriqueImport.user_id == User.id)
    
    # Difference de role
    if current_user.role != "Admin":
        query = query.filter(HistoriqueImport.user_id == current_user.id)
    
    imports = query.order_by(HistoriqueImport.date_creation.desc()).all()
    
    # Formater la réponse
    result = []
    for imp in imports:
        result.append(HistoriqueImportResponse(
            id=imp.id,
            nom_donnees=imp.nom_donnees,
            maladie_nom=imp.maladie_nom,
            type_import=imp.type_import,
            statut=imp.statut,
            date_creation=imp.date_creation,
            date_verification=imp.date_verification,
            date_import_etl=imp.date_import_etl,
            lignes_count=len(imp.donnees_brutes) if imp.donnees_brutes else 0,
            saisisseur_nom=f"{imp.user.prenom} {imp.user.nom}",
            saisisseur_email=imp.user.email
        ))
    
    return result
@router.get("/regions-list", tags=["Import ETL"])
def get_regions_for_import(db: Session = Depends(get_db)):
    """Récupère la liste des régions spécifiquement pour l'interface d'import."""
    regions = db.query(Region).order_by(Region.nom_region).all()
   
    return [{"id": r.id, "nom_region": r.nom_region} for r in regions]

@router.delete("/history/{import_id}", status_code=status.HTTP_200_OK)
def delete_import(
    import_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Supprime un historique d'import (Réservé aux Administrateurs)."""
    
    if current_user.role.lower() != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé. Seuls les administrateurs peuvent supprimer des imports.")
    
    import_record = db.query(HistoriqueImport).filter(HistoriqueImport.id == import_id).first()
    if not import_record:
        raise HTTPException(status_code=404, detail="Historique d'import non trouvé.")
    
    db.delete(import_record)
    db.commit()
    
    return {"message": "Historique d'import supprimé avec succès."}