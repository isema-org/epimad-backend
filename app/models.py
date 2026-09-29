from sqlalchemy import Column, Integer, String, Date, Numeric, JSON, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

# Base commune de modèles
Base = declarative_base()

class Region(Base):
    __tablename__ = "regions"
    
    id = Column(Integer, primary_key=True, index=True)
    code_region = Column(String(10), unique=True, index=True)
    nom_region = Column(String(100), unique=True, index=True)
    population_totale = Column(Integer)
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    
class Maladie(Base):
    __tablename__ = "maladies"
    
    id = Column(Integer, primary_key=True, index=True)
    code_maladie = Column(String(50), unique=True, index=True)
    nom_officiel = Column(String(100))
    agent_pathogene = Column(String(100))
    type_maladie = Column(String(50))
    
class CasEpidemique(Base):
    __tablename__ = "cas_epidemiques"
    
    id = Column(Integer, primary_key=True, index=True)
    date_observation = Column(Date, index=True)
    semaine_epidemio = Column(String(10))
    
    region_id = Column(Integer, ForeignKey("regions.id"))
    maladie_id = Column(Integer, ForeignKey("maladies.id"))
    
    cas_nouveaux = Column(Integer, default=0)
    deces = Column(Integer, default=0)
    gueris = Column(Integer, default=0)
    hospitalisations = Column(Integer, default=0)
    taux_incidence = Column(Numeric(10, 4))
    taux_letalite = Column(Numeric(6, 2))
    niveau_alerte = Column(String(20))
    donnees_specifiques = Column(JSON)
    
    region = relationship("Region")
    maladie = relationship("Maladie")

class User(Base):
    __tablename__ = "utilisateurs"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    prenom = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="En_attente", nullable=False) 
    est_verifie = Column(Boolean, default=False)
    email_confirme = Column(Boolean, default=False)
    
    date_creation = Column(DateTime(timezone=True), server_default=func.now())
    derniere_connexion = Column(DateTime(timezone=True), nullable=True)

    notifications_recues = relationship("Notification", foreign_keys="Notification.destinataire_id", back_populates="destinataire")
    notifications_envoyees = relationship("Notification", foreign_keys="Notification.expediteur_id", back_populates="expediteur")
class HistoriqueImport(Base):
    __tablename__ = "historique_imports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("utilisateurs.id"), nullable=False)
    
    nom_donnees = Column(String, nullable=False)
    maladie_nom = Column(String, nullable=False)
    type_import = Column(String, nullable=False)
    
    
    donnees_brutes = Column(JSONB, nullable=True) 
    
    statut = Column(String, default="Brouillon")
    
    date_creation = Column(DateTime(timezone=True), server_default=func.now())
    date_verification = Column(DateTime(timezone=True), nullable=True)
    date_import_etl = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")

class SourceDonnees(Base):
    __tablename__ = "sources_donnees"
    
    id = Column(Integer, primary_key=True, index=True)
    nom_source = Column(String(100), nullable=False)
    type_source = Column(String(50))
    date_importation = Column(DateTime(timezone=True), server_default=func.now())


class Alerte(Base):
    __tablename__ = "alertes"
    
    id = Column(Integer, primary_key=True, index=True)
    date_alerte = Column(DateTime(timezone=True), server_default=func.now())
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    maladie_id = Column(Integer, ForeignKey("maladies.id"), nullable=False)
    niveau_alerte = Column(String(10), nullable=False)
    indicateur_declencheur = Column(String(50), nullable=False)
    valeur_declencheuse = Column(Numeric(10, 4), nullable=False)
    statut_traitement = Column(String(20), default="nouvelle")
    
    region = relationship("Region")
    maladie = relationship("Maladie")


class PrevisionIA(Base):
    __tablename__ = "previsions_ia"
    
    id = Column(Integer, primary_key=True, index=True)
    date_previson = Column(Date, nullable=False)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    maladie_id = Column(Integer, ForeignKey("maladies.id"), nullable=False)
    horizon = Column(String(10), nullable=False)
    cas_prevus = Column(Integer, nullable=False)
    intervalle_confiance_min = Column(Integer)
    intervalle_confiance_max = Column(Integer)
    date_generation = Column(DateTime(timezone=True), server_default=func.now())
    
    region = relationship("Region")
    maladie = relationship("Maladie")


class AnomalieDetectee(Base):
    __tablename__ = "anomalies_detectees"
    
    id = Column(Integer, primary_key=True, index=True)
    date_detection = Column(DateTime(timezone=True), server_default=func.now())
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    maladie_id = Column(Integer, ForeignKey("maladies.id"), nullable=False)
    type_anomalie = Column(String(50))
    valeur_anormale = Column(Numeric(10, 4))
    score_anomalie = Column(Numeric(5, 4))
    
    region = relationship("Region")
    maladie = relationship("Maladie")


class ScoreRisque(Base):
    __tablename__ = "score_risque"
    
    id = Column(Integer, primary_key=True, index=True)
    date_calcul = Column(Date, nullable=False)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    maladie_id = Column(Integer, ForeignKey("maladies.id"), nullable=False)
    score_global = Column(Numeric(5, 2))
    niveau_risque = Column(String(10))
    details_calcul = Column(JSONB)
    date_insertion = Column(DateTime(timezone=True), server_default=func.now())
    
    region = relationship("Region")
    maladie = relationship("Maladie")
    
class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Clés étrangères vers la table utilisateurs
    destinataire_id = Column(Integer, ForeignKey("utilisateurs.id"), nullable=False)
    expediteur_id = Column(Integer, ForeignKey("utilisateurs.id"), nullable=True)
    
    # Contenu de la notification
    type = Column(String(50), nullable=False)      
    titre = Column(String(200), nullable=False)     
    message = Column(String, nullable=False)        
    
    # État et priorité
    lu = Column(Boolean, default=False, nullable=False)
    priorite = Column(String(20), default="medium", nullable=False)
    
    # Liens et dates
    lien = Column(String(500), nullable=True)
    date_creation = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    date_lecture = Column(DateTime(timezone=True), nullable=True)
    
    # Relations avec User
    destinataire = relationship("User", foreign_keys=[destinataire_id], back_populates="notifications_recues")
    expediteur = relationship("User", foreign_keys=[expediteur_id], back_populates="notifications_envoyees")