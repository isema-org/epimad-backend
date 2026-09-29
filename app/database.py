import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
from app.models import Base 

BACKEND_ROOT = Path(__file__).resolve().parent.parent
env_path = BACKEND_ROOT / ".env"

load_dotenv(dotenv_path=env_path)

DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "postgres")

SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
print(f" DEBUG: .env chargé depuis : {env_path}")
print(f" DEBUG: Connexion BDD -> {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Crée automatiquement les tables manquantes dans la base de données."""
    Base.metadata.create_all(bind=engine)
    print("✅ [SÉCURITÉ DB] Vérification des tables terminée. Aucune table manquante.")

# Garde l'initialisation des tables
init_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()