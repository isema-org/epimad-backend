from pydantic import BaseModel, ConfigDict
from typing import List, Dict, Any, Optional
from datetime import date,datetime
from typing import Optional
from pydantic import BaseModel

class RegionBase(BaseModel):
    code_region: str
    nom_region: str
    population_totale: int
    
class RegionRead(RegionBase):
    id: int
    latitude: float
    longitude: float
    
    model_config = ConfigDict(from_attributes=True)
    
###  Schemas pour les maladies
class MaladieBase(BaseModel):
    code_maladie: str
    nom_officiel: str

class MaladieRead(MaladieBase):
    id: int
    agent_pathogene: Optional[str] = None
    type_maladie: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

### Schemas pour les cas épidémiques
class CasEpidemiqueBase(BaseModel):
    date_observation: date
    semaine_epidemio: str
    cas_nouveaux: int = 0
    deces: int = 0
    hospitalisations: float= 0
    taux_incidence: float = 0.0
    taux_letalite: float = 0.0
    niveau_alerte: str
  
##Schemas pour les cas épidémiques avec relations    
class CasEpidemiqueRead(CasEpidemiqueBase):
    id: int
    region_id: int
    maladie_id: int
    donnees_specifiques: Optional[Dict[str, Any]] = None
    region: "RegionRead"
    maladie: "MaladieRead"
    
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

## Schemas pour les utilisateurs
class UserRegister(BaseModel):
    nom: str
    prenom: str
    email: str
    password: str
    password_confirm: str

class UserResponse(BaseModel):
    id: int
    nom: str
    prenom: str
    email: str
    role: str
    est_verifie: bool
    email_confirme: bool
    date_creation: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ImportDraftRequest(BaseModel):
    nom_donnees: str
    maladie_nom: str
    type_import: str
    donnees: List[Dict[str, Any]]  # Les lignes de données

class ImportVerifyRequest(BaseModel):
    donnees_corrigees: List[Dict[str, Any]]

class HistoriqueImportResponse(BaseModel):
    id: int
    nom_donnees: str
    maladie_nom: str
    type_import: str
    statut: str
    date_creation: datetime
    date_verification: Optional[datetime] = None
    date_import_etl: Optional[datetime] = None
    lignes_count: int
    
    # Champs pour l'Admin
    saisisseur_nom: Optional[str] = None
    saisisseur_email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
    
### =====================================================
### Schemas pour les Notifications
### =====================================================

class NotificationBase(BaseModel):
    """Champs de base pour une notification"""
    type: str                          # 'INSCRIPTION_USER', 'ALERTE_IA', 'SEUIL_DEPASSE', etc.
    titre: str                         # Titre court
    message: str                       # Message détaillé
    lien: Optional[str] = None         # Lien optionnel vers la ressource
    priorite: str = "medium"           # 'low', 'medium', 'high', 'critical'

class NotificationCreate(NotificationBase):
    """Schéma pour créer une nouvelle notification"""
    destinataire_id: int               # ID de l'utilisateur destinataire
    expediteur_id: Optional[int] = None  # ID de l'expéditeur (optionnel, par défaut l'utilisateur connecté)

class NotificationResponse(NotificationBase):
    """Schéma de réponse complète pour une notification"""
    id: int
    destinataire_id: int
    expediteur_id: Optional[int] = None
    lu: bool
    date_creation: datetime
    date_lecture: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class NotificationUpdate(BaseModel):
    """Schéma pour mettre à jour une notification (marquer comme lue)"""
    lu: bool

class NotificationCountResponse(BaseModel):
    """Schéma pour le compteur de notifications non lues (badge)"""
    non_lues: int

class NotificationListResponse(BaseModel):
    """Schéma pour la liste paginée de notifications"""
    notifications: List[NotificationResponse]
    total: int
    non_lues: int