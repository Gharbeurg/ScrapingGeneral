#bibliotheques
import bs4
import requests
import os
import unicodedata
import re
import PyPDF4

from tabulate import tabulate
from datetime import datetime
from colorama import Fore, Back, Style

#fichiers
fichier_entree = "C:/DATA/github/.params/nouveau.txt"
fichier_sortie = "C:/DATA/github/.data/hemo.txt"
fichier_pdf = 'C:/DATA/github/.data/fichier_pdf.pdf'

#variables
pages = []
l_contenu = []
liste_lignes = []
nbre_pages_erreur = 0
regex = re.compile(r'[\n\r\t]')
compteur = 0
texte_pdf = ""

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
        pages.append(line)

f.close()

# parsing de chaque page web
print("{} - Parsing de chaque page".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
for i in pages:
    file_sortie.write(i + "\n") 
    compteur += 1

    try:

        #ecuperation de la page
        response = requests.get(i, stream = True)
        content_type = response.headers.get('content-type')

        if 'application/pdf' in content_type:
            with open(fichier_pdf,"wb") as pdf:
                for chunk in response.iter_content(chunk_size=1024):
                    # writing one chunk at a time to pdf file
                    if chunk:
                        pdf.write(chunk)
            
            #recuperation du contenu
            pdfFileObj = open(fichier_pdf, 'rb') 
    
            # creating a pdf reader object 
            pdfReader = PyPDF4.PdfFileReader(pdfFileObj)
            nombre_pages = pdfReader.numPages

            #creating a page object
            pageObj = pdfReader.getPage(0)
            
            for n in range(nombre_pages):
                texte_pdf +=pdfReader.getPage(n).extractText()

            #fermeture du fichier 
            pdfFileObj.close()

            file_sortie.write(texte_pdf)
            print("[+] doc {} : {} - {} - {} pages".format(compteur, content_type, i, nombre_pages))
            
        else:
            soup = bs4.BeautifulSoup(response.text, 'lxml')
            tag = soup.findAll(["h1", "h2", "h3", "p", "a", "div", "span", "li", "tr", "td"])
            for el in tag:
                # suppression des accents et majuscules
                chaine = unicodedata.normalize('NFKD', el.text).encode('ASCII', 'ignore')
                chaine = str(chaine, "utf-8").lower()
                if chaine !="":
                    file_sortie.write(chaine)
            
            file_sortie.write("\n") 
            print("[+] page {} : {} - {}".format(compteur, content_type, i))

    except:
        print(Fore.RED + "[+] Erreur sur la page : {} - {}".format(i, content_type) + Fore.RESET)
        nbre_pages_erreur += 1

print("{} - Fin du parsing".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
print("[+] Nombe de pages  en erreur : ", nbre_pages_erreur )