import sys
import os
import json
import pandas as pd
from datetime import datetime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import Column, Integer, String, Date, Numeric, JSON, ForeignKey
from sqlalchemy.orm import declarative_base
from app.database import engine, SessionLocal

Base = declarative_base()

class Region(Base):
    __tablename__ = "regions"
    id = Column(Integer, primary_key=True)
    nom_region = Column(String(100), unique=True)

class Maladie(Base):
    __tablename__ = "maladies"
    id = Column(Integer, primary_key=True)
    code_maladie = Column(String(50), unique=True)

class CasEpidemique(Base):
    __tablename__ = "cas_epidemiques"
    id = Column(Integer, primary_key=True)
    date_observation = Column(Date, nullable=False)
    semaine_epidemio = Column(String(10), nullable=False)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    maladie_id = Column(Integer, ForeignKey("maladies.id"), nullable=False)
    cas_nouveaux = Column(Integer, default=0)
    deces = Column(Integer, default=0)
    gueris = Column(Integer, default=0)
    hospitalisations = Column(Integer, default=0)
    taux_incidence = Column(Numeric(10, 4))
    taux_letalite = Column(Numeric(6, 2))
    niveau_alerte = Column(String(10))
    donnees_specifiques = Column(JSON)

def safe_int(value, default=0):
    if pd.isna(value) or value is None:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default

def safe_float(value, default=0.0):
    if pd.isna(value) or value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def get_id(db, model, column_name, value):
    column = getattr(model, column_name)
    result = db.query(model).filter(column == value).first()
    return result.id if result else None

def calculer_niveau_alerte(taux_incidence, code_maladie, seuils_config, row=None):
    config_seuils_maladie = seuils_config.get(code_maladie)
    if not config_seuils_maladie:
        return 'Vert'

    niveaux = config_seuils_maladie.get('niveaux')
    if not niveaux:
        return 'Vert'

    regles = config_seuils_maladie.get('regles_speciales', {})
    indicateur = taux_incidence

    regle_saison = regles.get('saisonnalite')
    if regle_saison and row is not None and 'saison' in row:
        if row.get('saison') == 'pluies':
            indicateur = indicateur * regle_saison.get('facteur_multiplicateur', 1.0)

    ordre_niveaux = ['Vert', 'Jaune', 'Orange', 'Rouge']
    niveau_trouve = 'Vert'
    for nom_niveau in ordre_niveaux:
        bornes = niveaux.get(nom_niveau)
        if not bornes:
            continue
        mini = bornes.get('min', 0)
        maxi = bornes.get('max')
        if indicateur >= mini and (maxi is None or indicateur < maxi):
            niveau_trouve = nom_niveau

    regle_enfants = regles.get('alerte_enfants')
    if regle_enfants and row is not None and 'incidence_enfants_5_ans' in row:
        try:
            incidence_enfants = float(row.get('incidence_enfants_5_ans', 0))
            action = regle_enfants.get('action', '')
            if incidence_enfants > 50:
                if 'minimum' in action.lower():
                    niveau_minimum = action.replace('Alerte', '').replace('minimum', '').strip()
                    if niveau_minimum in ordre_niveaux:
                        if ordre_niveaux.index(niveau_trouve) < ordre_niveaux.index(niveau_minimum):
                            niveau_trouve = niveau_minimum
                elif 'escalade' in action.lower():
                    idx = min(ordre_niveaux.index(niveau_trouve) + 1, len(ordre_niveaux) - 1)
                    niveau_trouve = ordre_niveaux[idx]
        except (ValueError, TypeError):
            pass

    return niveau_trouve

def charger_maladie(config_maladie, project_root, seuils_config):
    code = config_maladie['metadata']['maladie_id']
    nom = config_maladie['metadata']['nom']
    fichier_csv = os.path.join(project_root, config_maladie['source']['fichier_brut'])

    colonnes_specifiques = []
    for categorie, cols in config_maladie['colonnes_source']['colonnes_utiles'].items():
        if categorie not in ['temporelles', 'geographiques', 'cas', 'deces', 'gueris', 'hospitalisations']:
            colonnes_specifiques.extend(cols)

    print(f"\n{'='*50}")
    print(f"Chargement de : {nom} ({code})")
    print(f"Fichier : {fichier_csv}")
    print(f"{'='*50}")

    if not os.path.exists(fichier_csv):
        print(f"Fichier introuvable : {fichier_csv}")
        return

    df = pd.read_csv(fichier_csv)
    df.columns = df.columns.str.strip()
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.strip()

    print(f"{len(df)} lignes lues et nettoyees.")

    db = SessionLocal()
    try:
        maladie_id = get_id(db, Maladie, 'code_maladie', code)
        if not maladie_id:
            print(f"Maladie '{code}' non trouvee en base.")
            return

        nb_inseres = 0
        nb_erreurs = 0
        records_to_insert = []

        for index, row in df.iterrows():
            try:
                region_id = get_id(db, Region, 'nom_region', row['region'])
                if not region_id:
                    nb_erreurs += 1
                    continue

                date_str = str(row.get('date', '2020-01-01'))
                date_obj = pd.to_datetime(date_str)
                semaine_epi = date_obj.strftime('%Y-W%V')

                cas_nouveaux = safe_int(row.get('new_cases', row.get('cas_confirmes', row.get('cas_totaux', row.get('cas_signalés', row.get('nouveaux_diagnostics_aghbs', row.get('nouveaux_cas', 0)))))))
                deces = safe_int(row.get('new_deaths', row.get('deces', 0)))
                gueris = safe_int(row.get('new_recoveries', row.get('patients_gueris', 0)))
                hosp = safe_int(row.get('hosp_patients', row.get('cas_graves', 0)))

                taux_inc = safe_float(row.get('taux_incidence', row.get('new_cases_per_million', 0)))
                taux_let = safe_float(row.get('taux_letalite', 0))
                alerte = calculer_niveau_alerte(taux_inc, code, seuils_config, row)

                json_data = {}
                for col in colonnes_specifiques:
                    if col in df.columns:
                        val = row[col]
                        json_data[col] = None if pd.isna(val) else val

                record = {
                    'date_observation': date_obj.date(),
                    'semaine_epidemio': semaine_epi,
                    'region_id': region_id,
                    'maladie_id': maladie_id,
                    'cas_nouveaux': cas_nouveaux,
                    'deces': deces,
                    'gueris': gueris,
                    'hospitalisations': hosp,
                    'taux_incidence': taux_inc,
                    'taux_letalite': taux_let,
                    'niveau_alerte': alerte,
                    'donnees_specifiques': json_data
                }
                records_to_insert.append(record)
                nb_inseres += 1

            except Exception as e:
                nb_erreurs += 1
                if nb_erreurs <= 3:
                    print(f"Erreur ligne {index}: {e}")

        if records_to_insert:
            taille_lot = 1000
            for i in range(0, len(records_to_insert), taille_lot):
                lot = records_to_insert[i:i + taille_lot]
                stmt = insert(CasEpidemique).values(lot)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['date_observation', 'region_id', 'maladie_id'],
                    set_=dict(
                        semaine_epidemio=stmt.excluded.semaine_epidemio,
                        cas_nouveaux=stmt.excluded.cas_nouveaux,
                        deces=stmt.excluded.deces,
                        gueris=stmt.excluded.gueris,
                        hospitalisations=stmt.excluded.hospitalisations,
                        taux_incidence=stmt.excluded.taux_incidence,
                        taux_letalite=stmt.excluded.taux_letalite,
                        niveau_alerte=stmt.excluded.niveau_alerte,
                        donnees_specifiques=stmt.excluded.donnees_specifiques
                    )
                )
                db.execute(stmt)

            db.commit()
            print(f"SUCCES : {nb_inseres} lignes traitees, {nb_erreurs} erreurs.")

    except Exception as e:
        db.rollback()
        print(f"ERREUR FATALE : {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("DEMARRAGE DU PIPELINE ETL GENERIQUE...")

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)

    chemin_json = os.path.join(BASE_DIR, "config", "maladies.json")
    with open(chemin_json, 'r', encoding='utf-8') as f:
        config = json.load(f)

    chemin_seuils = os.path.join(BASE_DIR, "config", "seuils_alerte.json")
    with open(chemin_seuils, 'r', encoding='utf-8') as f:
        seuils_config = json.load(f)

    for code_maladie, config_maladie in config.items():
        charger_maladie(config_maladie, PROJECT_ROOT, seuils_config)
    print("\nFIN DU PIPELINE ETL !")