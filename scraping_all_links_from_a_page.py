#bibliotheques
import os
from bs4 import BeautifulSoup

#variables
fichier_sortie = "C:/DATA/github/.data/liste_liens.txt"
fichier_entree = "C:/DATA/github/.data/linkedin_liste_oncologues.txt"

# suppression du fichier de sortie
if os.path.exists(fichier_sortie):
    os.remove(fichier_sortie)

# Ouverture du fichier de sortie
file_sortie = open(fichier_sortie, 'a')

# recuperation du contenu entre les tags
with open(fichier_entree, 'r', encoding='utf-8') as f:
    contents = f.read()
    soup = BeautifulSoup(contents, "html.parser")

    for a_href in soup.find_all("a", href=True):
        lien = a_href["href"]
        if "miniProfile" in lien:
            print(lien)
            file_sortie.write(lien)
            file_sortie.write('\n')