import os
import requests
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["predictions"])

AI_MODELS_URL = os.getenv("AI_MODELS_URL", "http://localhost:8001")


def _appeler_ai_models(method: str, path: str, **kwargs):
    """Fonction utilitaire pour appeler le service ai-models et gérer les erreurs de façon homogène."""
    url = f"{AI_MODELS_URL}{path}"
    try:
        response = requests.request(method, url, timeout=60, **kwargs)
    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=503,
            detail=f"Impossible de contacter le service ai-models à {AI_MODELS_URL}. Vérifiez qu'il est démarré."
        )

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail=response.json().get("detail", "Ressource introuvable."))
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Erreur ai-models."))

    return response.json()


@router.get("/predictions/all")
async def get_all_predictions(horizon: int = 4):
    if horizon < 1 or horizon > 12:
        raise HTTPException(status_code=400, detail="L'horizon doit être entre 1 et 12 semaines")

    models_data = _appeler_ai_models("GET", "/models")
    results = {}

    for entry in models_data["data"]:
        disease = entry["disease"]
        try:
            pred = _appeler_ai_models("GET", "/predict/xgboost", params={"disease": disease, "horizon": horizon})
            results[disease] = {
                "predictions": pred["previsions"],
                "model_file": entry["model_file"],
            }
        except HTTPException as e:
            results[disease] = {"error": e.detail, "model_file": entry["model_file"]}

    return {"status": "success", "horizon": horizon, "total_diseases": len(results), "data": results}


@router.get("/predictions/{disease}")
async def get_disease_predictions(disease: str, horizon: int = 4):
    if horizon < 1 or horizon > 12:
        raise HTTPException(status_code=400, detail="L'horizon doit être entre 1 et 12 semaines")

    try:
        pred = _appeler_ai_models("GET", "/predict/xgboost", params={"disease": disease, "horizon": horizon})
    except HTTPException as e:
        if e.status_code == 404:
            print(f"\n Modèle '{disease}' non trouvé. Tentative d'entraînement...")
            _appeler_ai_models("POST", f"/train/{disease}", params={"horizon": horizon})
            pred = _appeler_ai_models("GET", "/predict/xgboost", params={"disease": disease, "horizon": horizon})
        else:
            raise

    return {
        "status": "success",
        "disease": pred["disease"],
        "horizon": pred["horizon"],
        "total_predictions": len(pred["previsions"]),
        "data": pred["previsions"],
    }


@router.get("/models")
async def get_available_models():
    return _appeler_ai_models("GET", "/models")


@router.post("/train/{disease}")
async def trigger_training(disease: str, horizon: int = 4):
    print(f"\n Demande d'entraînement manuel pour '{disease}'")
    return _appeler_ai_models("POST", f"/train/{disease}", params={"horizon": horizon})