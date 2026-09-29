from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from sqlalchemy.orm import Session
from sqlalchemy import text
import pandas as pd
import io
import os
import threading
import requests

from app.database import get_db, engine

router = APIRouter(prefix="/api/import", tags=["Import ETL & IA"])

AI_MODELS_URL = os.getenv("AI_MODELS_URL", "http://localhost:8001")


def _declencher_entrainement_arriere_plan(disease: str):
    """Appelle les routes de training d'ai-models en arrière-plan, sans bloquer la réponse HTTP."""
    def _run():
        try:
            requests.post(f"{AI_MODELS_URL}/train/{disease}", params={"horizon": 4}, timeout=300)
            print(f" Entraînement XGBoost déclenché pour '{disease}'.")
        except Exception as e:
            print(f" Erreur lors du déclenchement de l'entraînement XGBoost : {e}")

        try:
            requests.post(f"{AI_MODELS_URL}/train/arima", params={"horizon": 4}, timeout=600)
            print(f" Entraînement ARIMA déclenché.")
        except Exception as e:
            print(f" Erreur lors du déclenchement de l'entraînement ARIMA : {e}")

    threading.Thread(target=_run, daemon=True).start()


@router.post("/upload")
async def import_and_train(
    file: UploadFile = File(...),
    maladie_nom: str = Form(...),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith(('.csv', '.xlsx')):
        raise HTTPException(status_code=400, detail="Format non supporté.")

    try:
        maladie_nom_clean = maladie_nom.strip().title()

        check_maladie = text("SELECT id FROM maladies WHERE nom_officiel = :nom")
        result = db.execute(check_maladie, {"nom": maladie_nom_clean}).fetchone()

        if result:
            maladie_id = result[0]
            maladie_status = f"Maladie existante '{maladie_nom_clean}' mise à jour."
        else:
            code_maladie = maladie_nom_clean[:3].upper()
            insert_maladie = text("""
                INSERT INTO maladies (nom_officiel, code_maladie, agent_pathogene, type_maladie, frequence_surveillance, actif, date_mise_a_jour)
                VALUES (:nom, :code, 'À définir', 'Virale', 'Hebdomadaire', true, CURRENT_TIMESTAMP)
                RETURNING id
            """)
            new_id_result = db.execute(insert_maladie, {"nom": maladie_nom_clean, "code": code_maladie})
            maladie_id = new_id_result.fetchone()[0]
            db.commit()
            maladie_status = f"Nouvelle maladie '{maladie_nom_clean}' créée avec l'ID {maladie_id}."

        content = await file.read()
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))

        required_cols = ['date', 'region', 'nouveaux_cas_confirmes']
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise HTTPException(status_code=400, detail=f"Colonnes manquantes: {missing}")

        regions_query = text("SELECT id, nom_region FROM regions")
        regions_df = pd.read_sql(regions_query, engine)
        region_map = {str(row['nom_region']).strip().lower(): row['id'] for _, row in regions_df.iterrows()}

        inserted = 0
        updated = 0
        errors = []

        for index, row in df.iterrows():
            try:
                region_name = str(row.get('region', '')).strip().lower()
                region_id = region_map.get(region_name)

                if not region_id:
                    errors.append(f"Ligne {index+2}: Région '{row.get('region')}' introuvable.")
                    continue

                date_obs = pd.to_datetime(row['date'], errors='coerce')
                if pd.isna(date_obs):
                    errors.append(f"Ligne {index+2}: Date invalide.")
                    continue

                semaine_epidemio = int(date_obs.isocalendar().week)
                cas_nouveaux = int(float(row.get('nouveaux_cas_confirmes', 0)))
                cas_cumules = int(float(row.get('cas_confirmes', cas_nouveaux)))

                check_sql = text("""
                    SELECT id FROM cas_epidemiques
                    WHERE region_id = :rid AND maladie_id = :mid AND date_observation = :d
                """)
                exists = db.execute(check_sql, {"rid": region_id, "mid": maladie_id, "d": date_obs}).fetchone()

                if exists:
                    update_sql = text("""
                        UPDATE cas_epidemiques
                        SET semaine_epidemio = :semaine, cas_nouveaux = :cn, cas_cumules = :cc
                        WHERE region_id = :rid AND maladie_id = :mid AND date_observation = :d
                    """)
                    db.execute(update_sql, {
                        "semaine": semaine_epidemio, "cn": cas_nouveaux, "cc": cas_cumules,
                        "rid": region_id, "mid": maladie_id, "d": date_obs
                    })
                    updated += 1
                else:
                    insert_sql = text("""
                        INSERT INTO cas_epidemiques (region_id, maladie_id, date_observation, semaine_epidemio, cas_nouveaux, cas_cumules)
                        VALUES (:rid, :mid, :d, :semaine, :cn, :cc)
                    """)
                    db.execute(insert_sql, {
                        "rid": region_id, "mid": maladie_id, "d": date_obs,
                        "semaine": semaine_epidemio, "cn": cas_nouveaux, "cc": cas_cumules
                    })
                    inserted += 1

            except Exception as e:
                errors.append(f"Ligne {index+2}: Erreur ({str(e)})")
                db.rollback()

        db.commit()

        # ============================================================
        # DÉCLENCHEMENT de l'entraînement automatique via le service ai-models
        # ============================================================
        ia_status = "Entraînement XGBoost et ARIMA déclenchés en arrière-plan sur le service ai-models."
        try:
            _declencher_entrainement_arriere_plan(maladie_nom_clean)
        except Exception as e:
            ia_status = f"Erreur lors du déclenchement de l'entraînement : {str(e)}"

        return {
            "status": "success",
            "maladie_status": maladie_status,
            "maladie_id": maladie_id,
            "inserted": inserted,
            "updated": updated,
            "errors": errors[:5],
            "ia_status": ia_status,
            "message": f"Import terminé : {inserted} nouvelles données, {updated} mises à jour."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))