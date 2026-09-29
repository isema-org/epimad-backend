import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import SQLALCHEMY_DATABASE_URL, ENV_PATH

print(f"Backend utilise le fichier .env : {ENV_PATH}")
print(f"Backend DATABASE_URL : {SQLALCHEMY_DATABASE_URL}")