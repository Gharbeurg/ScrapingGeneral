#bibliotheques
import pandas as pd
import time
import bs4
import random
import requests
import os
import pickle
import unicodedata
import re, string
from tabulate import tabulate
from datetime import datetime

#variables
fichier_sortie = "C:/DATA/github/.data/mehmo_content.txt"
fichier_entree = "C:/DATA/github/.data/adresses_google.txt"
extensions = [".html", ".htm", ".php", ".php3", ".jsp", ".asp", ".aspx", ".xhtml", "/", "kjsp", ""]
l_contenu = []
liste_lignes = []
nbre_pages_erreur = 0
regex = re.compile(r'[\n\r\t]')
compteur = 0

# Collecte des pages à travailler
def get_pages(token):
    pages = []
    with open(token, 'r') as f:
        for line in f:
            # suppression des caractères spéciaux
            line = regex.sub("", line)
            pages.append(line)
    f.close()
    return pages

print("{} - Lecture du fichier d'entrée".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
pages = get_pages(fichier_entree)

# parsing de chaque page web
print("{} - Parsing de chaque page".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
for i in pages:
    if i.lower().endswith(tuple(extensions)):
        l_contenu.append(i)
        compteur += 1
        try:
            
            print("[+] page {} : {}".format(compteur, i))

            # recuperation du contenu entre les tags
            response = requests.get(i)
            soup = bs4.BeautifulSoup(response.text, 'lxml')
            tag = soup.findAll(["h1"])
            for el in tag:

                # suppression des accents et majuscules
                chaine = unicodedata.normalize('NFKD', el.text).encode('ASCII', 'ignore')
                chaine = str(chaine, "utf-8").lower()
                   
                # suppression des caracteres inutiles
                chaine = re.sub('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*\(\),]|''(?:%[0-9a-fA-F][0-9a-fA-F]))+','', chaine)
                chaine = re.sub("(@[A-Za-z0-9_]+)","", chaine)
                chaine = chaine.replace("\\n","")
                if chaine !="":
                    l_contenu.append(chaine)
        
        except:
            print("[+] Erreur sur la page : {}".format(i))
            nbre_pages_erreur += 1

print("[+] Nombe de pages  en erreur : ", nbre_pages_erreur )

# Suppression des lignes en doubles
print("{} - Suppression des doublons".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
for line in l_contenu:
    # copier la ligne dans la liste si elle n'y est pas déjà
    if line not in liste_lignes:
        liste_lignes.append(line)

# ecriture du fichier de sortie
print("{} - Ecriture du fichier de sortie".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
if os.path.exists(fichier_sortie):
    os.remove(fichier_sortie)

with open(fichier_sortie, "w", encoding="utf-8") as f:
    for item in liste_lignes:
        f.write(f'{item}\n')