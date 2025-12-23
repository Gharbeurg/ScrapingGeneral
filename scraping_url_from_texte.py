# Bibliothèques
import re
import os
from unidecode import unidecode
import urlexpander

import os
import pandas as pd
from datetime import datetime
from colorama import Fore, Back, Style

# variables
fichier_entree = "C:/DATA/github/.params/nouveau.txt"
fichier_sortie = "C:/DATA/github/.data/fichier_analyse.xlsx"
nbre_phrases_totales = 0
nbre_phrases_traitees = 0
nbre_phrases_erreur = 0
nbre_minimum_caractere_phrase = 20

link_regex = re.compile('((https?):((//)|(\\\\))+([\w\d:#@%/;$()~_?\+-=\\\.&](#!)?)*)', re.DOTALL)

df_table_phrases = pd.DataFrame(columns =  ['phrase', 'liens'])
df_table_phrases = df_table_phrases.reset_index(drop=True)
l_phrase = []
l_liens = []

# suppression et ecriture du fichier de sortie
print("{} - suppression du fichier de sortie".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
if os.path.exists(fichier_sortie):
    os.remove(fichier_sortie)

# Ouverture du fichier d'entrée
print("{} - Lecture du fichier d'entrée".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
with open(fichier_entree, 'r', encoding="utf-8") as f:
    for line in f:
        nbre_phrases_totales += 1
        sent_sans_sut_ligne = line.replace("\n","")  #sauts de lignes
        try:
            nbre_phrases_traitees +=1
            liste_liens = ''
            urls = re.findall(link_regex, line)
            l_phrase.append(line)
            if urls:
                for link in urls:
                    url_etendu = urlexpander.expand(link[0])
                    liste_liens += url_etendu + ', '
                
                l_liens.append(liste_liens[:-2])
            else:
                l_liens.append('')
            
            print ("[+] {} - {}".format(line[:100], liste_liens[:-2]))

        except:
            nbre_phrases_erreur += 1
            print(Fore.RED + "[+] Erreur sur la phrase : {}".format(line) + Fore.RESET)

    # creation du dataframe
    df_table_phrases['phrase'] = pd.Series(l_phrase)
    df_table_phrases['liens'] = pd.Series(l_liens)

# Comptage
print ("[+] Nombre de phrases totales : {}".format(nbre_phrases_totales))
print ("[+] Nombre de phrases traitées : {}".format(nbre_phrases_traitees))
print ("[+] Nombre de phrases en erreur : {}".format(nbre_phrases_erreur))
    
print("{} - Création du fichier de sortie".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
with open(fichier_sortie, 'w', encoding="utf-8") as f:
    df_table_phrases.to_excel(fichier_sortie)
    f.close()
print("{} - Fin du programme".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))

f.close()