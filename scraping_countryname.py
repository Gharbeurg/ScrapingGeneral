# Bibliotheque
import os
import time
import pandas as pd
import time
import bs4
import requests

from tabulate import tabulate
from datetime import datetime
from colorama import Fore, Back, Style

from geopy.geocoders import Nominatim
 

# variables
fichier_lieux = "C:/DATA/github/.data/lieux.txt"
fichier_lieux_sortie = "C:/DATA/github/.data/lieux_pays.xlsx"

temporisation = 2
df_liste_lieux = pd.DataFrame(columns =  ['lieu', 'pays'])
df_liste_lieux = df_liste_lieux.reset_index(drop=True)
l_lieux = []
l_pays = []

# parsing de chaque compte
print("{} - Ouverture du fichier des lieux".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
with open(fichier_lieux, 'r', encoding="utf-8") as f:
    for line in f:

        try:
            print("[+] Traitement du lieux : ", line)

            geolocator = Nominatim(user_agent = "geoapiExercises")
            location = geolocator.geocode(line)
            l_pays.append(location)

            #lieux
            l_lieux.append(line)

            print("{} - Lieu : {} - pays : {}".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S"), line, location))

        except:
            print(Fore.RED + "[+] Erreur sur ce lieu" + Fore.RESET)


# creation du dataframe
print("{} - Création du dataframe".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
df_liste_lieux['lieu'] = l_lieux
df_liste_lieux['pays'] = l_pays

# ecriture du fichier de sortie
if os.path.exists(fichier_lieux_sortie):
    os.remove(fichier_lieux_sortie)

print("{} - Ecriture du fichier de sortie".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
df_liste_lieux.to_excel(fichier_lieux_sortie)

f.close()