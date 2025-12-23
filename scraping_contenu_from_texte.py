# Bibliothèques
import re
import os
from unidecode import unidecode

from nltk.tokenize import sent_tokenize

import os
import pandas as pd
import openai
from datetime import datetime
from colorama import Fore, Back, Style

# variables
fichier_entree = "C:/DATA/github/.params/nouveau.txt"
fichier_sortie = "C:/DATA/github/.data/fichier_analyse.xlsx"
nbre_phrases_totales = 0
nbre_phrases_traitees = 0
nbre_phrases_erreur = 0
nbre_minimum_caractere_phrase = 20

df_table_phrases = pd.DataFrame(columns =  ['phrase'])
df_table_phrases = df_table_phrases.reset_index(drop=True)
l_phrase = []

# suppression et ecriture du fichier de sortie
print("{} - suppression du fichier de sortie".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
if os.path.exists(fichier_sortie):
    os.remove(fichier_sortie)

# Ouverture du fichier d'entrée
print("{} - Lecture du fichier d'entrée".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
with open(fichier_entree, 'r', encoding="utf-8") as f:
    for line in f:
        try:
            # Tokenisation
            sentence_tokens = sent_tokenize(line)

            # Nettoyage des caractères spéciaux
            for sent in sentence_tokens:
                nbre_phrases_totales += 1
                sent = unidecode(sent) #accents
                sent = re.sub('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*\(\),]|''(?:%[0-9a-fA-F][0-9a-fA-F]))+','', sent)  #filtrage des URLs
                sent = re.sub("(@[A-Za-z0-9_]+)","", sent)  #@username
                sent_sans_icone = sent.encode('ascii', 'ignore').decode('ascii')  #icones
                sent_sans_icone = sent_sans_icone.replace("\n","")  #sauts de lignes
                sent_sans_icone = sent_sans_icone.strip()  #espaces
                sent_sans_icone = sent_sans_icone.lower()

                # Ajout de la phrase si elle fait une taille minimale
                if len(sent_sans_icone) > nbre_minimum_caractere_phrase:
                    nbre_phrases_traitees +=1
                    l_phrase.append(sent_sans_icone)

        except:
            nbre_phrases_erreur += 1
            print(Fore.RED + "[+] Erreur sur la phrase : {}".format(sent) + Fore.RESET)

    # creation du dataframe
    df_table_phrases['phrase'] = pd.Series(l_phrase)

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