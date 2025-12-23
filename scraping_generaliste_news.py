# Bibliotheque
import time
import pandas as pd
import time
import bs4
import re

from datetime import datetime
from colorama import Fore, Back, Style
from selenium import webdriver

# variables
temporisation = 5
nombre_requete = 0

adresse_driver_chrome = "C:/DATA/github/drivers/chromedriver.exe"
adresse_generaliste_news = "https://www.legeneraliste.fr/actu-medicale"
adresse_generaliste = "https://www.legeneraliste.fr"
fichier_generaliste_sortie = "C:/DATA/github/.data/sante_news.csv"
fichier_log = "C:/DATA/github/.logs/log_execution.txt"
journal = 'GENERALISTE'

df_news = pd.DataFrame(columns =  ['journal', 'date', 'categorie', 'auteur', 'titre', 'description', 'lien', 'commente', 'partage'])
df_news = df_news.reset_index(drop=True)
l_journal = []
l_date = []
l_categorie = []
l_titre = []
l_auteur = []
l_description = []
l_lien = []
l_commente = []
l_partage = []

# ouverture du fichier de logs
f_log = open(fichier_log, 'a', encoding='utf8')
f_log.write("{} - Lancement du programme - scraping_generaliste_news.py\n".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))

# Ouverture du Browser
f_log.write("{} - Ouverture du browser\n".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))

options = webdriver.ChromeOptions() 
options.add_experimental_option("excludeSwitches", ["enable-logging"])
driver = webdriver.Chrome(options=options, executable_path=adresse_driver_chrome)

# ouverture de la page
f_log.write("{} - Ouverture de la page\n".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
try:
    driver.get(adresse_generaliste_news)
    time.sleep(temporisation)

    #Recuperation du contenu
    f_log.write("{} - Recuperation du contenu\n".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
    contenu = driver.page_source.encode('utf8')
    soup_contenu = bs4.BeautifulSoup(contenu, 'html.parser')

    #récuperation des articles
    result_block = soup_contenu.find_all("div", {"class":"article-listing mb-3"})

    if result_block:
        try:
            for result in result_block:
                nombre_requete += 1
        
                #journal_article
                journal_article = journal

                #categorie
                categorie_article = ''
                if result.find("div", {"class":"surtitre myriad font-size-15 font-size-13-m line-height-1-2 mb-0 text-gray-700"}):
                    categorie_article = result.find("div", {"class":"surtitre myriad font-size-15 font-size-13-m line-height-1-2 mb-0 text-gray-700"}).text.strip()
                else:
                    categorie_article = ''

                #description
                if result.find("div", {"class":"text-chapo font-size-16 line-height-1-3 d-inline"}):
                    description_article = result.find("div", {"class":"text-chapo font-size-16 line-height-1-3 d-inline"}).text.strip()
                else:
                    description_article = ''

                #date
                if result.find("div", {"class":"font-size-16 text-uppercase text-gray-500 d-none d-md-inline"}):
                    date_article = result.find("div", {"class":"font-size-16 text-uppercase text-gray-500 d-none d-md-inline"}).text.strip()
                    date_article = date_article[:-2]
                else:
                    date_article = ''

                #lien, titre
                if result.find("a"):
                    lien_article = adresse_generaliste + result.find("a").get('href')
                    titre_article = result.find("a").get('title')
                else:
                    lien_article = ''
                    titre_article = ''

                #commente
                if result.find("span", {"class":"nb-com"}):
                    commente_article = result.find("span", {"class":"nb-com"}).text.strip()
                else:
                    commente_article = ''

                #partage
                partage_article = ''

                #auteur
                auteur_article = ''

                #ajout dans la liste
                l_journal.append(journal_article)
                l_date.append(date_article)
                l_categorie.append(categorie_article)
                l_titre.append(titre_article)
                l_auteur.append(auteur_article)
                l_description.append(description_article)
                l_lien.append(lien_article)
                l_commente.append(commente_article)
                l_partage.append(partage_article)

                f_log.write("[+] - {} - {}\n".format(nombre_requete, titre_article.rstrip()))
        
        except:
            f_log.write(Fore.RED + "[+] - Erreur docteur, ligne {}\n".format(nombre_requete) + Fore.RESET)

except:
    f_log.write(Fore.RED + "[+] - Mince ca deconne\n" + Fore.RESET)

# creation du dataframe
f_log.write("{} - Création du dataframe\n".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
df_news['journal'] = l_journal
df_news['date'] = l_date
df_news['categorie'] = l_categorie
df_news['titre'] = l_titre
df_news['auteur'] = l_auteur
df_news['description'] = l_description
df_news['lien'] = l_lien
df_news['commente'] = l_commente
df_news['partage'] = l_partage

# ecriture des fichiers de sortie
f_log.write("{} - Ecriture du fichier de sortie\n".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
df_news.to_csv(fichier_generaliste_sortie, mode='a', sep=';', index=False, header=False)

#fermeture
driver.quit()
f_log.close

#fin du programme
f_log.write("{} - Fin du programme - scraping_generaliste_news.py\n".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
f_log.write("****************************************************\n")   