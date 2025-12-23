#bibliotheques
from bs4 import BeautifulSoup
import time
import os
import re
from unidecode import unidecode

#suppression des warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

from urllib.parse import urljoin, urlparse

from unidecode import unidecode
from tabulate import tabulate

from datetime import datetime
from colorama import Fore, Back, Style

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

#fichiers
fichier_entree = "C:/DATA/code/.data/liste_actus.txt"
fichier_brut = "C:/DATA/code/.data/contenu_actus_brut.txt"
fichier_sortie = "C:/DATA/code/.data/contenu_actus.txt"

#variables
compteur = 0
nbre_pages_erreur = 0
liste_pages_web = []

temporisation = 3
taille_minimum_lien = 40

#driver chrome
chrome_options = Options()
chrome_options.add_argument("--log-level=3")  # 0=ALL, 1=INFO, 2=WARNING, 3=ERROR
service = Service("C:/DATA/code/drivers/chromedriver.exe")
driver = webdriver.Chrome(service=service, options=chrome_options)

# === FONCTIONS ===
def est_ligne_actualite(ligne):
    """Détecte si une ligne est probablement une phrase d'actualité"""
    ligne = ligne.strip()
    if not ligne:
        return False
    
    ligne_sans_accents = unidecode(ligne.lower())

    # Mots qui indiquent qu'on doit supprimer la ligne
    mots_exclus = [
        "cookie", "s'abonner", "menu", "recherche", "politique de confidentialité",
        "partager", "envoyer", "facebook", "linkedin", "email", "commenter", 
        "publicité", "sponsorisé", "annonce", "newsletter", "podcast", "vidéo",
        "paramétrer", "accepté", "refuser", "enregistrer", "se connecter", "s'inscrire",
        "mot de passe", "compte", "connexion", "mentions légales", "contact", "édition", "source", "journal", "live", "club abonnés", "diverto", "notre fondation", "avis de décès"
    ]
    if any(mot in ligne_sans_accents for mot in mots_exclus):
        return False

    # Lignes très courtes sans sens
    if len(ligne) < 30:
        return False

    # Doit contenir des mots et pas que des chiffres / symboles
    if not re.search(r'[a-zA-Z]', ligne):
        return False

    # Bonus : doit avoir au moins une ponctuation naturelle
    if not re.search(r'[\.!?]', ligne):
        # Optionnel, mais ça nettoie beaucoup mieux
        return False

    return True

def nettoyer_texte_fichier(fichier_entree, fichier_sortie):
    with open(fichier_entree, 'r', encoding='utf-8') as fe:
        lignes = fe.readlines()

    lignes_filtrees = [ligne for ligne in lignes if est_ligne_actualite(ligne)]

    with open(fichier_sortie, 'w', encoding='utf-8') as fs:
        fs.writelines(lignes_filtrees)

    print(f"Nettoyage terminé : {len(lignes) - len(lignes_filtrees)} lignes supprimées.")

def supprimer_lignes_doublons(nom_fichier):
    with open(nom_fichier, 'r', encoding='utf-8') as fss:
        lignes = fss.readlines()

    # Supprimer les doublons tout en conservant l'ordre
    lignes_uniques = list(dict.fromkeys(lignes))

    with open(nom_fichier, 'w', encoding='utf-8') as fss:
        fss.writelines(lignes_uniques)

def detect_and_accept_cookies(driver):
    print("{} - Essaie de détecter et de cliquer sur un bouton de consentement".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
    try:
        possible_keywords = ['Accepter', 'Accept', 'Tout accepter', 'J’accepte', 'OK', 'Oui', 'Agree', 'Allow', 'Autoriser', 'Enregistrer']
        buttons = driver.find_elements(By.TAG_NAME, 'button')
        for button in buttons:
            for keyword in possible_keywords:
                if keyword.lower() in button.text.lower():
                    print(f"→ Bouton détecté : {button.text.strip()}")
                    button.click()
                    time.sleep(2)
                    return True
    except Exception as e:
        print("[+]Erreur pendant la détection/clic du consentement :", e)
    return False

def is_consent_page(html):
    print("{} - Teste si le HTML contient des indices de page de consentement".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text().lower()
    return any(kw in text for kw in ['cookies', 'consentement', 'cookie settings', 'your privacy', 'gdpr', 'Tout accepter''Autoriser', 'Enregistrer', 'Tout enregistrer'])


# === Extraction du texte d'un article ===
def extraire_texte_depuis_url(url):
    try:
        #recuperation de la page
        driver.get(url)
        time.sleep(temporisation)

        #Detection du consentement
        html = driver.page_source
        if is_consent_page(html):
            print("{} - Consentement détecté. Tentative d acceptation…".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
            accepted = detect_and_accept_cookies(driver)
            if accepted:
                print("[+] Consentement accepté.")
            else:
                print("[+] Consentement non accepté automatiquement.")

                # Étape 2 : récupérer le vrai contenu de la page
        
        time.sleep(temporisation)
        final_html = driver.page_source
        soup_contenu = BeautifulSoup(final_html, 'html.parser')

        # Nettoyer le HTML
        for balise in soup_contenu(['script', 'style', 'noscript', 'header', 'footer', 'aside']):
            balise.decompose()

        texte = soup_contenu.get_text(separator='\n', strip=True)

        # Nettoyer le texte
        texte = texte.replace('\xa0', ' ')       # NBSP

        #mise en minuscule
        texte_min = texte.lower()

        #ecriture du texte
        if '2025' in texte_min:
            with open(fichier_brut, 'a', encoding='utf-8') as fs:
                    fs.write(f"URL: {url}\n\n{texte_min}\n")
                    fs.write("---------------------\n")

                    #article ajouté
                    compteur +=1

                    print("{} - URL - {}".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S"), url))

    except Exception as e:
        print(Fore.RED + "[+] Erreur sur cette URL - {}".format(url) + Fore.RESET)


# DEBUT DU PROGRAMME
print("{} - Début du programme".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))

# suppression du fichier de sortie
if os.path.exists(fichier_sortie):
    os.remove(fichier_sortie)

# Collecte des actualites
print("{} - Ouverture du fichier des sites actus".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
with open(fichier_entree, 'r', encoding="utf-8") as fe:
    for line in fe:
   
        try:
            print(Fore.GREEN + "{} - ACTU - {}".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S"), line) + Fore.RESET)
            extraire_texte_depuis_url(line)
  
        except:
            print(Fore.RED + "[+] Erreur sur ce fichir - {}".format(line) + Fore.RESET)

#nettoyage du texte pour ne garder que les actualités
nettoyer_texte_fichier(fichier_brut, fichier_sortie)

#suppression du fichier brut
if os.path.exists(fichier_brut):
    os.remove(fichier_brut)

print("{} - Fin de la collecte des actualités".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
print("[+] Nombe de pages  en erreur : ", nbre_pages_erreur)

print("{} - Suppression des lignes en doublon".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
supprimer_lignes_doublons(fichier_sortie)

#fermeture
driver.quit()

print("{} - Nombre total des articles - {}".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S"), compteur))
print("{} - Fin du programme".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))