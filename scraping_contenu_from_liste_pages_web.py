#bibliotheques
import bs4
import time
import os
import unicodedata
from unidecode import unidecode
import re
from tabulate import tabulate
from datetime import datetime
from colorama import Fore, Back, Style
import pandas as pd

from nltk.tokenize import sent_tokenize

from selenium import webdriver
from selenium.webdriver import Chrome, ChromeOptions

#fichiers
fichier_entree = "C:/DATA/code/.params/nouveau.txt"
fichier_sortie = "C:/DATA/code/.data/texte_html.xlsx"

#variables
nbre_phrases_totales = 0
nbre_phrases_traitees = 0
nbre_phrases_erreur = 0
nbre_minimum_caractere_phrase = 20
nbre_pages = 0
nbre_pages_erreur = 0
liste_pages_web = []

temporisation = 5

df_table_phrases = pd.DataFrame(columns =  ['phrase', 'page', 'fichier', 'balise'])
df_table_phrases = df_table_phrases.reset_index(drop=True)
l_phrase = []
l_fichier = []
l_page = []
l_balise = []

#driver chrome
driver = webdriver.Chrome("C:/DATA/github/drivers/chromedriver.exe")

# suppression du fichier de sortie
print("{} - Suppression du fichier de sortie".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
if os.path.exists(fichier_sortie):
    os.remove(fichier_sortie)

file_sortie = open(fichier_sortie, 'a', encoding='utf-8')

# Collecte des pages à travailler
print("{} - Lecture du fichier d'entrée".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
with open(fichier_entree, 'r') as f:
    for line in f:
        # suppression des caractères spéciaux
        line = line.strip().lower()
        liste_pages_web.append(line)

f.close()

# parsing de chaque page web
print("{} - Récupération du contenu de chaque page".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
for i in liste_pages_web:
    try:
        #recuperation de la page
        driver.get(i)
        time.sleep(temporisation)
        contenu = driver.page_source.encode('utf8')
        soup_contenu = bs4.BeautifulSoup(contenu, 'html.parser')

        print("[+] page : {} ".format(i))

        #recuperation de la metadescription
        print("{} - Récupération des metas..phores".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))

        meta_description = soup_contenu.find("meta",  {"property":"og:description"})
        if meta_description:
            try:
                # Tokenisation
                sentence_tokens = sent_tokenize(meta_description["content"])

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
                        l_page.append(1)
                        l_balise.append('meta')
                    else:
                        nbre_phrases_erreur += 1
            except:
                    print(Fore.RED + "[+] Erreur de meta description" + Fore.RESET)
                    nbre_pages_erreur += 1



        #recuperation des titres (H1, H2, H3)
        print("{} - Récupération des titres...de séjour".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
        
        liste_titres = soup_contenu.find_all(["h1", "h2", "h3"])
        if liste_titres:
            for titre in liste_titres:
                try:
                    # Tokenisation
                    sentence_tokens = sent_tokenize(titre.text.strip())

                    # Nettoyage des caractères spéciaux
                    for sent in sentence_tokens:
                        nbre_phrases_totales += 1
                        sent = re.sub('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*\(\),]|''(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', sent)
                        sent = re.sub("(@[A-Za-z0-9_]+)", "", sent)
                        sent = sent.replace("\n", "")
                        sent = sent.lower()
                        sent = sent.strip()

                        # Ajout de la phrase si elle fait une taille minimale
                        if len(sent) > nbre_minimum_caractere_phrase:
                            nbre_phrases_traitees += 1

                            l_phrase.append(sent)
                            l_fichier.append(i)
                            l_page.append(1)
                            l_balise.append('titre')
                        else:
                            nbre_phrases_erreur += 1
                except:
                    print(Fore.RED + "[+] Erreur de récupération de titre" + Fore.RESET)
                    nbre_pages_erreur += 1

        #recuperation des textes
        print("{} - Récupération des textes...de lois".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
        liste_textes = soup_contenu.find_all(["p", "div", "span"])
        if liste_textes:
            for texte in liste_textes:
                try:
                    # Tokenisation
                    sentence_tokens = sent_tokenize(texte.text.strip())

                    # Nettoyage des caractères spéciaux
                    for sent in sentence_tokens:
                        nbre_phrases_totales += 1
                        sent = re.sub('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*\(\),]|''(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', sent)
                        sent = re.sub("(@[A-Za-z0-9_]+)", "", sent)
                        sent = sent.replace("\n", "")
                        sent = sent.lower()
                        sent = sent.strip()

                        # Ajout de la phrase si elle fait une taille minimale
                        if len(sent) > nbre_minimum_caractere_phrase:
                            nbre_phrases_traitees += 1

                            l_phrase.append(sent)
                            l_fichier.append(i)
                            l_page.append(1)
                            l_balise.append('texte')
                        else:
                            nbre_phrases_erreur += 1
                except:
                    print(Fore.RED + "[+] Erreur de récupération de textes" + Fore.RESET)
                    nbre_pages_erreur += 1

        #recuperation des listes
        print("{} - Récupération des listes...de courses".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))

        liste_textes = soup_contenu.find_all(["li"])
        if liste_textes:
            for texte in liste_textes:
                try:
                    # Tokenisation
                    sentence_tokens = sent_tokenize(texte.text.strip())

                    # Nettoyage des caractères spéciaux
                    for sent in sentence_tokens:
                        nbre_phrases_totales += 1
                        sent = re.sub('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*\(\),]|''(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', sent)
                        sent = re.sub("(@[A-Za-z0-9_]+)", "", sent)
                        sent = sent.replace("\n", "")
                        sent = sent.lower()
                        sent = sent.strip()

                        # Ajout de la phrase si elle fait une taille minimale
                        if len(sent) > nbre_minimum_caractere_phrase:
                            nbre_phrases_traitees += 1

                            l_phrase.append(sent)
                            l_fichier.append(i)
                            l_page.append(1)
                            l_balise.append('li')
                        else:
                            nbre_phrases_erreur += 1
                except:
                    print(Fore.RED + "[+] Erreur de listes" + Fore.RESET)
                    nbre_pages_erreur += 1

    except:
            print(Fore.RED + "[+] Erreur sur la page : {}".format(i) + Fore.RESET)
            nbre_pages_erreur += 1

print("{} - Fin du parsing des pages".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
print("[+] Nombe de pages  en erreur : ", nbre_pages_erreur)

# creation du dataframe
print("{} - Fin du parsing, creation du dataframe".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
df_table_phrases['phrase'] = pd.Series(l_phrase)
df_table_phrases['page'] = pd.Series(l_page)
df_table_phrases['fichier'] = pd.Series(l_fichier)
df_table_phrases['balise'] = pd.Series(l_balise)

# Comptage
print("[+] Nombe de pages  en erreur : ", nbre_pages_erreur )
print ("[+] Nombre de phrases totales : {}".format(nbre_phrases_totales))
print ("[+] Nombre de phrases traitées : {}".format(nbre_phrases_traitees))
print ("[+] Nombre de phrases en erreur : {}".format(nbre_phrases_erreur))
    
print("{} - Création du fichier de sortie".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
with open(fichier_sortie, 'w', encoding="utf-8") as fs:
    df_table_phrases.to_excel(fichier_sortie)

#fermeture
driver.quit()
fs.close()

print("{} - Fin du programme".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))