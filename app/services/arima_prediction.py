import os
import requests

AI_MODELS_URL = os.getenv("AI_MODELS_URL", "http://localhost:8001")


def charger_et_predire(region_id: int, maladie_id: int, horizon: int = 4):
    """Appelle le service ai-models pour obtenir les prévisions ARIMA."""
    url = f"{AI_MODELS_URL}/predict/arima"
    params = {"region_id": region_id, "maladie_id": maladie_id, "horizon": horizon}

    print(f" Appel du service ai-models : {url} avec {params}")

    try:
        response = requests.get(url, params=params, timeout=30)
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            f"Impossible de contacter le service ai-models à {AI_MODELS_URL}. "
            f"Vérifiez qu'il est démarré."
        )

    if response.status_code == 404:
        raise FileNotFoundError(
            f"Aucun modèle trouvé pour la Région {region_id} et la Maladie {maladie_id}."
        )
    response.raise_for_status()

    data = response.json()
    previsions_brutes = data["previsions"]

    resultats = []
    for p in previsions_brutes:
        resultats.append({
            "date": p["date_previson"],
            "cas_prevus": int(round(p["cas_prevus"])),
            "min_confiance": int(round(max(0, p["intervalle_confiance_min"]))),
            "max_confiance": int(round(max(0, p["intervalle_confiance_max"])))
        })

    print(f" {len(resultats)} prévisions ARIMA reçues depuis ai-models.")
    return resultats