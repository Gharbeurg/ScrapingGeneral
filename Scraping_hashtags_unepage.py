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
from datetime import datetime

#variables
fichier_hashtags = "C:/DATA/github/.data/hashtagss.txt"
fichier_entree = "C:/DATA/github/.data/liste_hashtags.txt"
liste_hashtag = []
nbre_pages_erreur = 0
compteur = 0

# OUverture du fichier
print("{} - Ouverture du fichier".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
with open(fichier_entree, 'r', encoding="utf-8") as file_entree:

    # lire le fichier ligne par ligne
    for line in file_entree:

        #Test de la présence des mots clés dans la chaîne et d'une ligne non existante
        Hashtags = re.findall(r'(?:^|\s)(\#\w+)',line)
        if Hashtags:
            for item in Hashtags:
                liste_hashtag.append(item)
    
# ecriture du fichier contenu
print("{} - Ecriture du fichier de sortie".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
if os.path.exists(fichier_hashtags):
    os.remove(fichier_hashtags)

with open(fichier_hashtags, "w", encoding="utf-8") as f:
    for item in liste_hashtag:
        print(item)
        f.write(f'{item}\n')