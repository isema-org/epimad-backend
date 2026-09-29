from database import engine
from sqlalchemy import text

# Remet les données uniformes initiales pour toutes les maladies
requete_sql = text("""
    UPDATE cas_epidemiques
    SET 
        cas_nouveaux = 68853,
        deces = 1428,
        hospitalisations = 0
    WHERE maladie_id IN (1, 2, 3, 4, 5, 6);
""")

try:
    with engine.connect() as conn:
        result = conn.execute(requete_sql)
        conn.commit()
        print(f" Succès ! {result.rowcount} lignes ont été réinitialisées.")
        print("Tes données sont revenues à leur état initial.")
except Exception as e:
    print(f" Erreur : {e}")