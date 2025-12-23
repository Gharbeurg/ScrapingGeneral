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
from bs4 import BeautifulSoup
from tabulate import tabulate

#variables
fichier_contenu = "C:/DATA/github/.data/liste_hashtags.txt"
fichier_entree = "C:/DATA/github/.data/hash.html"
l_contenu = []
nbre_pages_erreur = 0
regex = re.compile(r'[\n\r\t]')
compteur = 0

# recuperation du contenu entre les tags
with open(fichier_entree, 'r', encoding='utf-8') as f:
    contents = f.read()
    soup = BeautifulSoup(contents, 'lxml')

tag = soup.findAll(["h1", "h2", "h3", "p", "a", "div", "span", "li", "tr", "td"])
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
    
# ecriture du fichier contenu
if os.path.exists(fichier_contenu):
    os.remove(fichier_contenu)

with open(fichier_contenu, "w", encoding="utf-8") as f:
    for item in l_contenu:
        f.write(f'{item}\n')