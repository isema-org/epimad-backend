import json

with open('maladies.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f" JSON valide !")
print(f" Nombre de maladies : {len(data)}")
print(f" Maladies configurées : {list(data.keys())}")

for maladie_id, config in data.items():
    print(f"\n• {config['metadata']['nom']}")
    print(f"  - Type : {config['metadata']['type']}")
    print(f"  - Fréquence : {config['metadata']['frequence_donnees']}")
    print(f"  - Fichier source : {config['source']['fichier_brut']}")