#bibliotheques
import os
import re
import time
from tabulate import tabulate
from datetime import datetime
from colorama import Fore, Back, Style
import pandas as pd

import pdfplumber
from unidecode import unidecode

from nltk.tokenize import sent_tokenize

from selenium import webdriver
from selenium.webdriver import Chrome, ChromeOptions

#fichiers
fichier_liste_pdfs = "C:/DATA/github/.params/nouveau.txt"
repertoire_download = "C:/DATA/github/.download/"
fichier_sortie = "C:/DATA/github/.data/texte_pdf.xlsx"

nbre_phrases_totales = 0
nbre_phrases_traitees = 0
nbre_phrases_erreur = 0
nbre_minimum_caractere_phrase = 20
nbre_fichiers = 0
nbre_fichiers_erreur = 0
nbre_pages = 0
nbre_pages_erreur = 0

temporisation = 5

df_table_phrases = pd.DataFrame(columns =  ['phrase', 'page', 'fichier'])
df_table_phrases = df_table_phrases.reset_index(drop=True)
l_phrase = []
l_fichier = []
l_page = []

# options de chrome pour la récupération des PDFs
options = ChromeOptions()
chrome_prefs = {
    "download.prompt_for_download": False,
    "plugins.always_open_pdf_externally": True,
    "download.open_pdf_in_system_reader": False,
    "profile.default_content_settings.popups": 0,
    # add location preference...
    "download.default_directory": "C:\\DATA\\github\\.download"
}
options.add_experimental_option("prefs", chrome_prefs)
driver = webdriver.Chrome("C:/DATA/github/drivers/chromedriver.exe", options=options)


# suppression des fichiers du répertoire de download
print("{} - Suppression des fichiers du download".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
for f in os.listdir(repertoire_download):
    os.remove(os.path.join(repertoire_download, f))

# suppression du fichier de sortie
print("{} - Suppression du fichier de sortie".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
if os.path.exists(fichier_sortie):
    os.remove(fichier_sortie)

# téléchargement des fichiers à travailler
print("{} - Lecture du fichier d'entrée et téléchargement".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
with open(fichier_liste_pdfs, 'r') as f:
    for line in f:
        try:
            driver.get(line)
            time.sleep(temporisation)
            print("[+] fichier récupéré : {} ".format(os.path.basename(line.strip().lower())))
        except:
            print(Fore.RED + "[+] Erreur de chargement du fichier : {}".format(i) + Fore.RESET)
#fermeture
f.close()
driver.quit()

# parsing de chaque fichier
print("{} - Récupération du contenu de chaque fichier".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
for i in os.listdir(repertoire_download):
    filepath = os.path.join(repertoire_download, i)
    with pdfplumber.open(filepath) as pdf:
        pages = pdf.pages
        number_of_pages = len(pdf.pages)

        print("[+] fichier : {} - nombre de pages {} ".format(i, number_of_pages))
        for numero_page in range(0, number_of_pages):
            try:
                #extraction du texte de la page
                pageobj = pdf.pages[numero_page]
                text = pageobj.extract_text()

                try:
                    # Tokenisation
                    sentence_tokens = sent_tokenize(text)


                    # Nettoyage des caractères spéciaux
                    for sent in sentence_tokens:
                        nbre_phrases_totales += 1
                        sent = unidecode(sent) #accents
                        sent = re.sub('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*\(\),]|''(?:%[0-9a-fA-F][0-9a-fA-F]))+','', sent)
                        sent = re.sub("(@[A-Za-z0-9_]+)","", sent)
                        sent_sans_icone = sent.encode('ascii', 'ignore').decode('ascii')
                        sent_sans_icone = sent_sans_icone.replace("\n","")
                        sent_sans_icone = sent_sans_icone.strip()
                        sent_sans_icone = sent_sans_icone.lower()

                        # Ajout de la phrase si elle fait une taille minimale
                        if len(sent_sans_icone) > nbre_minimum_caractere_phrase:
                            nbre_phrases_traitees +=1
                            l_phrase.append(sent_sans_icone)
                            l_fichier.append(i)
                            l_page.append(numero_page)
                        else:
                            nbre_phrases_erreur += 1

                except:
                    print(Fore.RED + "[+] Erreur sur la page : {}".format(numero_page) + Fore.RESET)
                    nbre_pages_erreur += 1

            except:
                print(Fore.RED + "[+] Erreur sur le fichier : {}".format(i) + Fore.RESET)
                nbre_fichiers_erreur += 1

        print("{} - Fin du parsing du fichier".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
        print("[+] Nombe de pages  en erreur : ", nbre_pages_erreur)

# creation du dataframe
print("{} - Fin du parsing, creation du dataframe".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
df_table_phrases['phrase'] = pd.Series(l_phrase)
df_table_phrases['page'] = pd.Series(l_page)
df_table_phrases['fichier'] = pd.Series(l_fichier)

# Comptage
print ("[+] Nombre de phrases totales : {}".format(nbre_phrases_totales))
print ("[+] Nombre de phrases traitées : {}".format(nbre_phrases_traitees))
print ("[+] Nombre de phrases en erreur : {}".format(nbre_phrases_erreur))
    
print("{} - Création du fichier de sortie".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
with open(fichier_sortie, 'w', encoding="utf-8") as fs:
    df_table_phrases.to_excel(fichier_sortie)
    fs.close()

print("{} - Fin du programme".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))