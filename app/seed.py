import os

import bcrypt
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import User


def seed_admin_user():
    """Crée le compte administrateur initial à partir des variables d'environnement."""
    admin_email = os.getenv("ADMIN_1_EMAIL")
    admin_password = os.getenv("ADMIN_1_PASSWORD")

    if not admin_email or not admin_password:
        print(" ADMIN_1_EMAIL / ADMIN_1_PASSWORD non définis : aucun compte administrateur créé.")
        return

    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == admin_email).first():
            print(f" Le compte Administrateur ({admin_email}) existe déjà. Rien à faire.")
            return

        hashed_pw = bcrypt.hashpw(admin_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        db.add(User(
            nom="Administrateur",
            prenom="Système",
            email=admin_email,
            hashed_password=hashed_pw,
            role="Admin",
            est_verifie=True,
            email_confirme=True,
        ))
        db.commit()
        print(f" Compte Administrateur créé : {admin_email}")

    except IntegrityError:
        db.rollback()
        print(" Le compte Administrateur existe déjà. Rien à faire.")
    except Exception as e:
        db.rollback()
        print(f" Erreur inattendue lors de la création de l'Admin : {e}")
    finally:
        db.close()