import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os

from datetime import datetime
from colorama import Fore, Back, Style

# variables
fichier_sites_actus = "C:/DATA/code/.params/sites_actus_labos.txt"
fichier_sortie = "C:/DATA/code/.data/Actualites_laboratoires2_21042025.txt"
nombre_articles = 0
ANNEE = "2025"

# fonctions

# === Supprimer les lignes en doublon ===
def supprimer_lignes_doublons(nom_fichier):
    with open(nom_fichier, 'r', encoding='utf-8') as f:
        lignes = f.readlines()

    # Supprimer les doublons tout en conservant l'ordre
    lignes_uniques = list(dict.fromkeys(lignes))

    with open(nom_fichier, 'w', encoding='utf-8') as f:
        f.writelines(lignes_uniques)

# === Heuristique pour filtrer les liens ===
def est_lien_possiblement_article(lien, texte, separation):
    # Écarte les liens peu pertinents
    if '#' in lien or lien.endswith(('.jpg', '.png', '.css', '.js', '.pdf', '.zip')):
        return False
    if not texte or len(texte.strip()) < 30:
        return False
    # Profondeur d'URL : un article a souvent plusieurs segments
    if len(urlparse(lien).path.strip('/').split('/')) >= int(separation):
        return True
    return False

# === Extraction des liens candidats ===
def extraire_liens_possibles(url_page,separation):
    try:
        reponse = requests.get(url_page)
        reponse.raise_for_status()
        soup = BeautifulSoup(reponse.text, 'html.parser')

        liens = set()
        for a in soup.find_all('a', href=True):
            texte = a.get_text(strip=True)
            lien_complet = urljoin(url_page, a['href'])
            domaine = urlparse(url_page).netloc

            if urlparse(lien_complet).netloc == domaine and est_lien_possiblement_article(lien_complet, texte,separation):
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

        if ANNEE in texte_min:
            with open(fichier_sortie, 'a', encoding='utf-8') as fs:
                fs.write(f"URL: {url}\n\n{texte_min}\n")
                fs.write("---------------------\n")

                print("{} - URL - {}".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S"), url))
        else:
            print("❌ Pas la bonne année")

    except Exception as e:
        print(Fore.RED + "[+] Erreur sur cette URL - {}".format(url) + Fore.RESET)

# === Script principal ===
def traitement_complet(url_page,separation):
    n=0
    liens = extraire_liens_possibles(url_page,separation)
    print("{} - {} liens articles potentiels trouvés.".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S"),len(liens)))
    for lien in liens:
        extraire_texte_depuis_url(lien)

# Début du programme
print("{} - Début du programme".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))

# suppression du fichier de sortie
if os.path.exists(fichier_sortie):
    os.remove(fichier_sortie)

# Collecte des sites
print("{} - Ouverture du fichier des sites actus".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
with open(fichier_sites_actus, 'r', encoding="utf-8") as f:
    for line in f:

        lien_url, separations = line.split(';', 1)
        
        try:
            print(Fore.GREEN + "{} - SITE - {}".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S"), line) + Fore.RESET)
            traitement_complet(lien_url,separations)
  
        except:
            print(Fore.RED + "[+] Erreur sur ce fichir - {}".format(line) + Fore.RESET)

print("{} - Suppression des lignes en doublon".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
supprimer_lignes_doublons(fichier_sortie)

#compter nombre des articles
with open(fichier_sortie, "r", encoding="utf-8") as f:
    for line in f:
        if "URL:" in line:
            nombre_articles += 1

# Fin du programme
print("{} - Nombre total des articles - {}".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S"), nombre_articles))
print("{} - Fin du programme".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))