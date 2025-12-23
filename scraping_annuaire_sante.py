# Bibliotheque
import os
import time

from datetime import datetime
from parsel import Selector
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException

# variables
nbre_pages_erreur=0
temporisation = 15
chrome_driver_install_rep = "C:\DATA\gitHub\drivers\chromedriver.exe"
adresse_annuaire = "https://annuaire.sante.fr/web/site-pro/"

# variables
fichier_medecins = "C:/DATA/github/.params/liste_medecins.txt"
fichier_adresses_medecins = "C:/DATA/github/.data/adresses_medecins.txt"

# démarrage du browser
chrome_options = webdriver.ChromeOptions()
chrome_options.binary_location = "C:\Program Files\Google\Chrome\Application\chrome.exe"
prefs = {"profile.default_content_setting_values.notifications" : 2}
chrome_options.add_experimental_option("prefs",prefs)
driver = webdriver.Chrome(chrome_driver_install_rep, chrome_options=chrome_options)

# Accès à l'annuaire
print("{} - Accès à l'annuaire".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
driver.get(adresse_annuaire)

# récupération de la liste de noms et lieux des médecins
with open(fichier_medecins) as f:
    for line in f:
        line_split = line.split(";") 
        print("{} - Médecin : {}".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S"), line_split[1]))
       
        # trouver le formulaire de recherche
        #time.sleep(temporisation)
        search_input = driver.find_element_by_xpath("//input[@title='Recherche Qui Quoi']").clear()
        search_input = driver.find_element_by_xpath("//input[@title='Recherche Où']").clear()
        search_input = driver.find_element_by_xpath("//input[@title='Recherche Qui Quoi']")
        search_input.send_keys(line_split[1])
        search_input = driver.find_element_by_xpath("//input[@title='Recherche Où']")
        search_input.send_keys(line_split[0])
        search_input.send_keys(Keys.ENTER)

        # Impression des éléments
        time.sleep(temporisation)
        nom_medecin = driver.find_element_by_xpath("//div[@class='nom_prenom'][1]").text
        professions = driver.find_elements_by_xpath("//div[@class='profession'][1]")
        profession = ""
        for e in professions:
            profession += e.text + " " 
        adresse_medecin = driver.find_element_by_xpath("//div[@class='adresse'][1]").text
        adresse_medecin = ' '.join([line.strip() for line in adresse_medecin.strip().splitlines()])
        try:
            tel_medecin = driver.find_element_by_xpath("//div[@class='tel'][1]").text
        except NoSuchElementException:
            tel_medecin = "phone vide"
        try:
            mel_medecin = driver.find_element_by_xpath("//div[@class='mssante'][1]").text
        except NoSuchElementException:
            mel_medecin = "mail vide"
        
        # ecriture du fichier de résultats
        with open(fichier_adresses_medecins, 'a+', encoding="utf-8") as f:
            f.write(f'{nom_medecin};{line_split[0]};{profession};{adresse_medecin};{tel_medecin};{mel_medecin}\n')

driver.quit()
f.close()