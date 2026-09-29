# EpiMad — Backend

API FastAPI pour la surveillance épidémiologique à Madagascar. Gère l'authentification, les données épidémiques, l'import de données (ETL intégré) et sert de point d'entrée pour les prévisions IA (déléguées au service `ai-models`).

## Prérequis

- Python 3.12
- Docker et Docker Compose
- Un service `ai-models` accessible (voir dépôt séparé)

## Installation locale

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copiez `.env.example` vers `.env` et renseignez les valeurs :

```powershell
Copy-Item .env.example .env
```

## Lancer la base de données

```powershell
docker compose up -d db
```

Le schéma initial (`database/schema.sql`) est appliqué automatiquement au premier démarrage du volume.

## Lancer le backend en local

```powershell
uvicorn main:app --reload
```

L'API est disponible sur `http://127.0.0.1:8000`, documentation interactive sur `/docs`.

## Variables d'environnement

| Variable | Description |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Identifiants de la base |
| `POSTGRES_HOST`, `POSTGRES_PORT` | Adresse de la base (`localhost`/`5437` en local, `db`/`5432` en Docker Compose) |
| `ADMIN_1_EMAIL`, `ADMIN_1_PASSWORD` | Compte administrateur créé au premier démarrage si aucun n'existe |
| `AI_MODELS_URL` | URL du service ai-models (ex: `http://localhost:8001` en local, `http://ai-models:8001` en réseau Docker) |

## Build et run en conteneur isolé

```powershell
docker build -t epimad-api .
docker run --rm -p 8000:8000 --env-file .env -e POSTGRES_HOST=host.docker.internal -e AI_MODELS_URL=http://host.docker.internal:8001 --add-host=host.docker.internal:host-gateway epimad-api
```

## Docker Compose complet (backend + db + pgadmin)

```powershell
docker compose up -d
```

Le service `ai-models` n'est pas inclus dans ce compose : il tourne sur un environnement séparé. Ajustez `AI_MODELS_URL` en conséquence.

## Architecture

- `app/routers/` — endpoints de l'API, groupés par domaine
- `app/models.py`, `app/database.py` — ORM SQLAlchemy et connexion
- `ETL/` — pipeline d'import des données sources (exécuté manuellement ou via `/api/import/upload`)
- `database/schema.sql` — schéma complet de la base, source de vérité

## Communication avec ai-models

Le backend ne contient aucun code de machine learning. Toutes les prédictions (ARIMA, XGBoost) et les entraînements sont délégués au service `ai-models` via HTTP (`AI_MODELS_URL`). Voir le dépôt `entrainement_modele` pour son fonctionnement.