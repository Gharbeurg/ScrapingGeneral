import requests
from bs4 import BeautifulSoup

# noms des fichiers
fichier_entree = "C:/DATA/code/.params/pagerselabo.txt"
fichier_sortie = "C:/DATA/code/.data/sortielaborse.txt"

with open(fichier_sortie, "w", encoding="utf-8") as sortie:
    with open(fichier_entree, "r", encoding="utf-8") as entree:
        for ligne in entree:
            url = ligne.strip()

            if not url:
                continue

            try:
                reponse = requests.get(url, timeout=10)

                if reponse.status_code == 200:
                    # parser le HTML
                    soup = BeautifulSoup(reponse.text, "html.parser")

                    # supprimer les éléments inutiles
                    for element in soup(["script", "style", "noscript"]):
                        element.decompose()

                    # récupérer uniquement le texte
                    texte = soup.get_text(separator="\n")

                    # nettoyer les lignes vides
                    lignes = [l.strip() for l in texte.splitlines() if l.strip()]
                    texte_propre = "\n".join(lignes)

                    sortie.write(f"\n\n===== CONTENU DE : {url} =====\n\n")
                    sortie.write(texte_propre)

                else:
                    sortie.write(f"\n\n===== PAGE NON DISPONIBLE : {url} =====\n\n")

            except Exception as e:
                sortie.write(f"\n\n===== ERREUR POUR : {url} =====\n")
                sortie.write(str(e))