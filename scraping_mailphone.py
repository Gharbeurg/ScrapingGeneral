#bibliotheques
import pandas as pd
import os
import requests
from datetime import datetime
from pytz import timezone
import re, string

#variables
fichier_sortie = "C:/DATA/github/.data/coordonnees_collectes.xls"
fichier_entree = "C:/DATA/github/.data/www.opusline.fr_internal_links.txt"
nbre_pages_erreur = 0
regex_french_phone = r"\d{10}|\+33\d{9}|\+33\s\d{1}\s\d{2}\s\d{2}\s\d{2}\s\d{2}|\d{2}\s\d{2}\s\d{2}\s\d{2}\s\d{2}"
regex_mail = r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)"
df_mails = pd.DataFrame(columns =  ['mail', 'phone', 'lien'])
l_mail = []
l_lien = []
l_phone = []
compteur = 0

# Collecte des pages à travailler
def get_pages(token):
    pages = []
    with open(token, 'r', encoding="utf-8") as f:
        for line in f:
            # suppression des caractères spéciaux
            pages.append(line)
    f.close()
    return pages

pages = get_pages(fichier_entree)

# expression reguliere pour localiser un mail dans une page
# parsing de chaque page web
for i in pages:
    compteur += 1
    try:
        # recuperation du contenu entre les tags
        response = requests.get(i)
        mail_list = re.findall(regex_mail, response.text)
        phone_list = re.findall(regex_french_phone, response.text)
        
        # mails
        print(l_mail)
        if mail_list:
            l_mail += mail_list
        else:
            l_mail.append(" ")

        # phone
        if phone_list:
            l_phone += phone_list
        else:
            l_phone.append("aucun telephone")

        l_lien.append(response.url)

        print("{} - lien : {} - mails trouvés : {} - Téléphones trouvés : {}".format(compteur, response.url, mail_list, phone_list))

    except:
        nbre_pages_erreur += 1

print("Nombe de pages  en erreur : ", nbre_pages_erreur )

df_mails['mail'] = l_mail
df_mails['lien'] = pd.Series(l_lien)
df_mails['phone'] = pd.Series(l_phone)

# ecriture du fichier de sortie
if os.path.exists(fichier_sortie):
    os.remove(fichier_sortie)

df_mails.to_excel(fichier_sortie)