from fastapi import APIRouter, HTTPException, Query

from app.services.arima_prediction import charger_et_predire

router = APIRouter(prefix="/api/previsions", tags=["Prévisions ARIMA"])


@router.get("/arima")
def get_previsions_arima(
    region_id: int = Query(..., description="ID de la région"),
    maladie_id: int = Query(..., description="ID de la maladie"),
    horizon: int = Query(4, description="Nombre de semaines à prédire")
):
    """
    Génère des prévisions ARIMA pour une région et une maladie donnée,
    en interrogeant le service ai-models.
    """
    try:
        previsions = charger_et_predire(region_id, maladie_id, horizon)
        return {
            "status": "success",
            "region_id": region_id,
            "maladie_id": maladie_id,
            "horizon_semaines": horizon,
            "data": previsions
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur interne du serveur: {str(e)}")