-- ============================================================
-- SCHEMA COMPLET EPIMAD
-- ============================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- ============================================================
-- 1. TABLES DE REFERENCE
-- ============================================================

CREATE TABLE IF NOT EXISTS regions (
    id SERIAL PRIMARY KEY,
    code_region VARCHAR(10) UNIQUE NOT NULL,
    nom_region VARCHAR(100) UNIQUE NOT NULL,
    population_totale INTEGER NOT NULL,
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    type_zone VARCHAR(20),
    date_mise_a_jour TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS maladies (
    id SERIAL PRIMARY KEY,
    code_maladie VARCHAR(50) UNIQUE NOT NULL,
    nom_officiel VARCHAR(100) NOT NULL,
    agent_pathogene VARCHAR(100),
    type_maladie VARCHAR(50),
    frequence_surveillance VARCHAR(20),
    actif BOOLEAN DEFAULT TRUE,
    date_mise_a_jour TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sources_donnees (
    id SERIAL PRIMARY KEY,
    nom_source VARCHAR(100) NOT NULL,
    type_source VARCHAR(50),
    date_importation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 2. TABLES DE FAITS
-- ============================================================

CREATE TABLE IF NOT EXISTS cas_epidemiques (
    id SERIAL PRIMARY KEY,
    date_observation DATE NOT NULL,
    semaine_epidemio VARCHAR(10) NOT NULL,
    region_id INTEGER NOT NULL REFERENCES regions(id),
    maladie_id INTEGER NOT NULL REFERENCES maladies(id),
    source_id INTEGER REFERENCES sources_donnees(id),
    cas_nouveaux INTEGER DEFAULT 0,
    cas_cumules INTEGER DEFAULT 0,
    deces INTEGER DEFAULT 0,
    hospitalisations INTEGER DEFAULT 0,
    taux_incidence DECIMAL(10, 4),
    taux_letalite DECIMAL(5, 2),
    niveau_alerte VARCHAR(10),
    donnees_specifiques JSONB,
    date_insertion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date_observation, region_id, maladie_id)
);

CREATE TABLE IF NOT EXISTS alertes (
    id SERIAL PRIMARY KEY,
    date_alerte TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    region_id INTEGER NOT NULL REFERENCES regions(id),
    maladie_id INTEGER NOT NULL REFERENCES maladies(id),
    niveau_alerte VARCHAR(10) NOT NULL,
    indicateur_declencheur VARCHAR(50) NOT NULL,
    valeur_declencheuse DECIMAL(10, 4) NOT NULL,
    statut_traitement VARCHAR(20) DEFAULT 'nouvelle'
);

-- ============================================================
-- 3. TABLES POUR LE MODULE IA
-- ============================================================

CREATE TABLE IF NOT EXISTS previsions_ia (
    id SERIAL PRIMARY KEY,
    date_previson DATE NOT NULL,
    region_id INTEGER NOT NULL REFERENCES regions(id),
    maladie_id INTEGER NOT NULL REFERENCES maladies(id),
    horizon VARCHAR(10) NOT NULL,
    cas_prevus INTEGER NOT NULL,
    intervalle_confiance_min INTEGER,
    intervalle_confiance_max INTEGER,
    date_generation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS anomalies_detectees (
    id SERIAL PRIMARY KEY,
    date_detection TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    region_id INTEGER NOT NULL REFERENCES regions(id),
    maladie_id INTEGER NOT NULL REFERENCES maladies(id),
    type_anomalie VARCHAR(50),
    valeur_anormale DECIMAL(10, 4),
    score_anomalie DECIMAL(5, 4)
);

CREATE TABLE IF NOT EXISTS score_risque (
    id SERIAL PRIMARY KEY,
    date_calcul DATE NOT NULL,
    region_id INTEGER NOT NULL REFERENCES regions(id),
    maladie_id INTEGER NOT NULL REFERENCES maladies(id),
    score_global DECIMAL(5, 2),
    niveau_risque VARCHAR(10),
    details_calcul JSONB,
    date_insertion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 4. INDEX DE PERFORMANCE
-- ============================================================

CREATE INDEX idx_cas_region_maladie_date ON cas_epidemiques(region_id, maladie_id, date_observation DESC);
CREATE INDEX idx_alertes_date ON alertes(date_alerte DESC);
CREATE INDEX idx_cas_donnees_json ON cas_epidemiques USING GIN(donnees_specifiques);

-- ============================================================
-- 5. DONNÉES INITIALES
-- ============================================================

INSERT INTO maladies (code_maladie, nom_officiel, agent_pathogene, type_maladie, frequence_surveillance) VALUES
('covid19', 'COVID-19', 'SARS-CoV-2', 'Pandémique', 'quotidien'),
('paludisme', 'Paludisme', 'Plasmodium falciparum', 'Epidemique', 'hebdomadaire'),
('peste', 'Peste', 'Yersinia pestis', 'Endémique saisonnière', 'hebdomadaire'),
('rougeole', 'Rougeole', 'Virus de la rougeole', 'Endémique avec épidémies', 'hebdomadaire'),
('hepatite', 'Hépatite virale', 'VHB/VHC', 'Endémique', 'hebdomadaire'),
('tuberculose', 'Tuberculose', 'Mycobacterium tuberculosis', 'Endémique chronique', 'hebdomadaire')
ON CONFLICT (code_maladie) DO NOTHING;

INSERT INTO regions (code_region, nom_region, population_totale, latitude, longitude, type_zone) VALUES
('AN', 'Analamanga', 4290727, -18.9137, 47.5247, 'urbain'),
('VK', 'Vakinankaratra', 2462316, -19.8000, 47.0333, 'plateau'),
('IT', 'Itasy', 1063882, -19.0000, 46.5000, 'plateau'),
('BO', 'Bongolava', 794456, -18.5000, 46.0000, 'rural'),
('DI', 'Diana', 1053715, -13.0000, 49.5000, 'cotier'),
('SV', 'SAVA', 1330546, -14.3000, 49.8000, 'cotier'),
('AM', 'Amoron''i Mania', 991145, -20.5000, 47.5000, 'plateau'),
('AT', 'Atsimo-Atsinanana', 1220000, -23.0000, 47.5000, 'cotier'),
('FV', 'Fitovinany', 1011279, -22.0000, 48.2000, 'cotier'),
('HM', 'Haute Matsiatra', 1710391, -21.5000, 47.0000, 'plateau'),
('IH', 'Ihorombe', 494097, -22.5000, 46.5000, 'rural'),
('BE', 'Betsiboka', 465641, -17.0000, 46.0000, 'rural'),
('BY', 'Boeny', 1100305, -15.8000, 46.3000, 'cotier'),
('ME', 'Melaky', 365790, -17.5000, 45.0000, 'rural'),
('SF', 'Sofia', 1784988, -14.5000, 47.8000, 'rural'),
('AL', 'Alaotra-Mangoro', 1479918, -18.0000, 48.5000, 'rural'),
('AB', 'Ambatosoa', 652462, -17.8000, 48.8000, 'rural'),
('AJ', 'Analanjirofo', 864183, -17.0000, 49.5000, 'cotier'),
('AS', 'Atsinanana', 1750511, -19.0000, 48.8000, 'cotier'),
('AD', 'Androy', 1065878, -24.8000, 45.5000, 'rural'),
('AO', 'Anosy', 957916, -25.0000, 47.0000, 'cotier'),
('AR', 'Atsimo-Andrefana', 2128706, -23.5000, 44.5000, 'cotier'),
('MN', 'Menabe', 819876, -20.0000, 44.5000, 'cotier'),
('VV', 'Vatovavy', 576905, -21.0000, 48.5000, 'cotier')
ON CONFLICT (code_region) DO NOTHING;


CREATE TABLE IF NOT EXISTS utilisateurs (
    id SERIAL PRIMARY KEY,
    nom VARCHAR NOT NULL,
    prenom VARCHAR NOT NULL,
    email VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR NOT NULL,
    role VARCHAR DEFAULT 'En_attente' NOT NULL,
    est_verifie BOOLEAN DEFAULT FALSE,
    email_confirme BOOLEAN DEFAULT FALSE,
    date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    derniere_connexion TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS historique_imports (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES utilisateurs(id),
    nom_donnees VARCHAR NOT NULL,
    maladie_nom VARCHAR NOT NULL,
    type_import VARCHAR NOT NULL,
    donnees_brutes JSONB,
    statut VARCHAR DEFAULT 'Brouillon',
    date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    date_verification TIMESTAMP WITH TIME ZONE,
    date_import_etl TIMESTAMP WITH TIME ZONE
);

-- =====================================================
-- TABLE DES NOTIFICATIONS
-- =====================================================

CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    destinataire_id INTEGER NOT NULL,
    expediteur_id INTEGER,
    type VARCHAR(50) NOT NULL,
    titre VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    
    lu BOOLEAN DEFAULT FALSE NOT NULL,
    priorite VARCHAR(20) DEFAULT 'medium' NOT NULL,
    
    lien VARCHAR(500),
    date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    date_lecture TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT fk_destinataire 
        FOREIGN KEY (destinataire_id) 
        REFERENCES utilisateurs(id) 
        ON DELETE CASCADE,
        
    CONSTRAINT fk_expediteur 
        FOREIGN KEY (expediteur_id) 
        REFERENCES utilisateurs(id) 
        ON DELETE SET NULL
);


CREATE INDEX IF NOT EXISTS idx_notifications_destinataire_lu 
ON notifications(destinataire_id, lu);

CREATE INDEX IF NOT EXISTS idx_notifications_date_creation 
ON notifications(date_creation DESC);

CREATE INDEX IF NOT EXISTS idx_notifications_type 
ON notifications(type);