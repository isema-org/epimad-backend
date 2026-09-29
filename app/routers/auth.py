from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt # type: ignore
import bcrypt # type: ignore
import re
from typing import List

from app.database import get_db
from app.models import User
from app.schemas import UserRegister, UserResponse

router = APIRouter(prefix="/api/auth", tags=["Authentification"])


SECRET_KEY = "votre_cle_secrete_tres_longue_et_aleatoire_ici"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Récupère l'utilisateur connecté depuis le token JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_admin(current_user: User = Depends(get_current_user)):
    """Vérifie que l'utilisateur est Admin."""
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs"
        )
    return current_user



def is_valid_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if user.role == "En_attente" or not user.est_verifie:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre compte est en attente de validation par l'administrateur."
        )
    
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role, "user_id": user.id}
    )
    
    user.derniere_connexion = datetime.utcnow()
    db.commit()
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "nom": user.nom,
            "prenom": user.prenom,
            "email": user.email,
            "role": user.role
        }
    }

@router.post("/register")
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    if len(user_data.password) < 6:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 6 caractères.")
    
    if user_data.password != user_data.password_confirm:
        raise HTTPException(status_code=400, detail="Les mots de passe ne correspondent pas.")
    
    if not is_valid_email(user_data.email):
        raise HTTPException(status_code=400, detail="Format d'email invalide.")
    
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé.")
    
    hashed_password = bcrypt.hashpw(
        user_data.password.encode('utf-8'), 
        bcrypt.gensalt()
    ).decode('utf-8')
    
    new_user = User(
        nom=user_data.nom.upper().strip(),
        prenom=user_data.prenom.capitalize().strip(),
        email=user_data.email.lower().strip(),
        hashed_password=hashed_password,
        role="En_attente",
        est_verifie=False,
        email_confirme=False
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "message": "Compte créé avec succès. En attente de validation.",
        "user_id": new_user.id
    }


@router.get("/users", response_model=List[UserResponse])
def get_all_users(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Liste tous les utilisateurs (Admin uniquement)."""
    users = db.query(User).order_by(User.date_creation.desc()).all()
    return users

@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    new_role: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Change le rôle d'un utilisateur (Admin uniquement)."""
    valid_roles = ["Admin", "Epidemiologiste", "Saisisseur", "Lecteur", "En_attente"]
    
    if new_role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Rôle invalide. Choices: {valid_roles}")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    user.role = new_role
    user.est_verifie = True
    
    db.commit()
    db.refresh(user)
    
    return {
        "message": f"Rôle de {user.prenom} {user.nom} mis à jour vers {new_role}",
        "user_id": user.id
    }

@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Supprime un utilisateur (Admin uniquement)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte")
    
    db.delete(user)
    db.commit()
    
    return {"message": f"Utilisateur {user.prenom} {user.nom} supprimé"}