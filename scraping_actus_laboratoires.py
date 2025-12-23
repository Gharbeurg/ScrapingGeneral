import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os

from datetime import datetime
from colorama import Fore, Back, Style

# variables
reportoire_pages = "C:/DATA/code/.params/actusgooglelabos/"
fichier_sortie = "C:/DATA/code/.data/actualites_laboratoires_21042025.txt"
nombre_articles = 0
compteur = 10
seuil_lignes = 15

# fonctions

def supprimer_lignes_courtes(nom_fichier, seuil):
    with open(nom_fichier, 'r', encoding='utf-8') as f:
        lignes = f.readlines()

    lignes_filtrees = [ligne for ligne in lignes if len(ligne.strip()) >= seuil]

    with open(nom_fichier, 'w', encoding='utf-8') as f:
        f.writelines(lignes_filtrees)


# === Supprimer les lignes en doublon ===
def supprimer_lignes_doublons(nom_fichier):
    with open(nom_fichier, 'r', encoding='utf-8') as f:
        lignes = f.readlines()

    # Supprimer les doublons tout en conservant l'ordre
    lignes_uniques = list(dict.fromkeys(lignes))

    with open(nom_fichier, 'w', encoding='utf-8') as f:
        f.writelines(lignes_uniques)

# === Heuristique pour filtrer les liens ===
def est_lien_possiblement_article(lien, texte):
    # Écarte les liens peu pertinents
    if '#' in lien or lien.endswith(('.jpg', '.png', '.css', '.js', '.pdf', '.zip')):
        return False
    if not texte or len(texte.strip()) < 30:
        return False
    # Profondeur d'URL : un article a souvent plusieurs segments
    if len(urlparse(lien).path.strip('/').split('/')) >= 2:
        return True
    return False

# === Extraction des liens candidats ===
def extraire_liens_possibles(chemin_fichier_html):
    try:
        with open(chemin_fichier_html, "r", encoding="utf-8") as f:
            contenu_html = f.read()

        soup = BeautifulSoup(contenu_html, 'html.parser')

        liens = set()
        for a in soup.find_all('a', href=True):
            texte = a.get_text(strip=True)
            lien_complet = a['href']

            # ici on ne peut pas utiliser urljoin() car ce n'est pas une vraie URL, mais c'est suffisant
            if est_lien_possiblement_article(lien_complet, texte):
                liens.add(lien_complet)

        return list(liens)

    except Exception as e:
        print(f"[!] Erreur lors de l'extraction des liens : {e}")
        return []

# === Extraction du texte d'un article ===
def extraire_texte_depuis_url(url):
    try:
        reponse = requests.get(url, timeout=10)
        reponse.raise_for_status()
        soup = BeautifulSoup(reponse.text, 'html.parser')

        # Nettoyer le HTML
        for balise in soup(['script', 'style', 'noscript', 'header', 'footer', 'aside']):
            balise.decompose()

        texte = soup.get_text(separator='\n', strip=True)

        #mise en minuscule
        texte_min = texte.lower()

        with open(fichier_sortie, 'a', encoding='utf-8') as fs:
            fs.write(f"URL: {url}\n\n{texte_min}\n")
            fs.write("---------------------\n")

            print("{} - URL - {}".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S"), url))

    except Exception as e:
        print(Fore.RED + "[+] Erreur sur cette URL - {}".format(url) + Fore.RESET)

# === Script principal ===
def traitement_complet(url_page):
    liens = extraire_liens_possibles(url_page)
    print("{} - {} liens articles potentiels trouvés.".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S"),len(liens)))
    for lien in liens:
        extraire_texte_depuis_url(lien)

# Début du programme
print("{} - Début du programme".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))

# suppression du fichier de sortie
if os.path.exists(fichier_sortie):
    os.remove(fichier_sortie)

# Collecte des pages
print("{} - Lecture des pages actus".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))

for i in range(1, compteur):
    nom_fichier = reportoire_pages + "page" + str(i) + ".htm"
       
    try:
        print(Fore.GREEN + "{} - Page - {}".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S"), nom_fichier) + Fore.RESET)
        traitement_complet(nom_fichier)
  
    except:
        print(Fore.RED + "[+] Erreur sur ce fichier - {}".format(nom_fichier) + Fore.RESET)

#suppression des doublons
print("{} - Suppression des lignes en doublon".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
supprimer_lignes_doublons(fichier_sortie)

#suppression des lignes courtes
print("{} - Suppression des lignes courtes".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
supprimer_lignes_courtes(fichier_sortie,seuil_lignes)

#compter nombre des articles
with open(fichier_sortie, "r", encoding="utf-8") as f:
    for line in f:
        if "URL:" in line:
            nombre_articles += 1

# Fin du programme
print("{} - Nombre total des articles - {}".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S"), nombre_articles))
print("{} - Fin du programme".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))