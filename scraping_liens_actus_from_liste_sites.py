#bibliotheques
import bs4
from bs4 import BeautifulSoup
import time
import os

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
fichier_entree = "C:/DATA/code/.params/sites_actus_pneumo.txt"
fichier_sortie = "C:/DATA/code/.data/liste_actus.txt"

#variables
compteur = 0
nbre_pages_erreur = 0
liste_pages_web = []

temporisation = 3
taille_minimum_lien = 100
nombre_articles = 0

#driver chrome
#driver chrome
chrome_options = Options()
chrome_options.add_argument("--log-level=3")  # 0=ALL, 1=INFO, 2=WARNING, 3=ERROR
service = Service("C:/DATA/code/drivers/chromedriver.exe")
driver = webdriver.Chrome(service=service, options=chrome_options)

# === FONCTIONS ===
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
        possible_keywords = ['Accepter', 'Accept', 'Tout accepter', 'J’accepte', 'OK', 'Oui', 'Agree', 'Allow']
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
    return any(kw in text for kw in ['cookies', 'consentement', 'cookie settings', 'your privacy', 'gdpr', 'Tout accepter'])

# === Heuristique pour filtrer les liens ===
def est_lien_possiblement_article(lien):
    # Écarte les liens peu pertinents
    if '#' in lien or lien.endswith(('.jpg', '.png', '.css', '.js', '.pdf', '.zip')):
        return False
    elif len(lien) < taille_minimum_lien:
        return False
    else:
        return True

# DEBUT DU PROGRAMME

# suppression du fichier de sortie
print("{} - Suppression du fichier de sortie".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
if os.path.exists(fichier_sortie):
    os.remove(fichier_sortie)

# Collecte des pages à travailler
print("{} - Lecture du fichier d'entrée".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
with open(fichier_entree, 'r') as f:
    for line in f:
        # suppression des caractères spéciaux
        line = line.strip().lower()
        liste_pages_web.append(line)

f.close()

# parsing de chaque page web
print("{} - Récupération des liens de chaque page".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
for i in liste_pages_web:
    try:
        #recuperation de la page
        driver.get(i)
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

        print("[+] page : {} ".format(i))

        #recuperation des liens
        try:
            for a in soup_contenu.find_all('a', href=True):
                lien_complet = urljoin(i, a['href'])

                if est_lien_possiblement_article(lien_complet):
                    compteur += 1
                    print("[+] lien : {} ".format(lien_complet))

                    #ecriture dans le fichier de sortie
                    with open(fichier_sortie, 'a', encoding='utf-8') as fs:
                        fs.write(lien_complet + '\n')

        except Exception as e:
            print(Fore.RED + "[+] Erreur sur les liens de cette page : {}".format(i) + Fore.RESET)

    except:
            print(Fore.RED + "[+] Erreur sur la page : {}".format(i) + Fore.RESET)
            nbre_pages_erreur += 1

print("{} - Fin du parsing des pages".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
print("[+] Nombe de pages  en erreur : ", nbre_pages_erreur)

print("{} - Suppression des lignes en doublon".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
supprimer_lignes_doublons(fichier_sortie)

#fermeture
driver.quit()

#compter nombre des articles
with open(fichier_sortie, "r", encoding="utf-8") as fc:
    for line in fc:
        if "URL:" in line:
            nombre_articles += 1

# Fin du programme
print("{} - Nombre total des articles - {}".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S"), nombre_articles))
print("{} - Fin du programme".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))