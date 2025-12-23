from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import time

def detect_and_accept_cookies(driver):
    """Essaie de détecter et de cliquer sur un bouton de consentement"""
    try:
        possible_keywords = ['Accepter', 'Accept', 'Tout accepter', 'J’accepte', 'OK', 'Oui', 'Agree', 'Allow']
        buttons = driver.find_elements(By.TAG_NAME, 'button')
        for button in buttons:
            for keyword in possible_keywords:
                if keyword.lower() in button.text.lower():
                    print(f"→ Bouton détecté : {button.text.strip()}")
                    button.click()
                    time.sleep(2)
                    return True
    except Exception as e:
        print("Erreur pendant la détection/clic du consentement :", e)
    return False

def is_consent_page(html):
    """Teste si le HTML contient des indices de page de consentement"""
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text().lower()
    return any(kw in text for kw in ['cookies', 'consentement', 'cookie settings', 'your privacy', 'gdpr'])

def scrape_website(url):
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)

    try:
        driver.get(url)
        time.sleep(3)

        # Étape 1 : détecter consentement
        html = driver.page_source
        if is_consent_page(html):
            print("Consentement détecté. Tentative d’acceptation…")
            accepted = detect_and_accept_cookies(driver)
            if accepted:
                print("Consentement accepté.")
            else:
                print("Consentement non accepté automatiquement.")

        # Étape 2 : récupérer le vrai contenu de la page
        time.sleep(2)
        final_html = driver.page_source
        soup = BeautifulSoup(final_html, 'html.parser')
        print("Titre de la page :", soup.title.string.strip() if soup.title else "Sans titre")

        # À ce stade, tu peux faire du scraping :
        # Exemple :
        paragraphs = soup.find_all('p')
        for p in paragraphs[:5]:  # on limite à 5 paragraphes pour l'exemple
            print("-", p.get_text(strip=True))

    finally:
        driver.quit()

# Exemple d’usage
scrape_website("https://www.lemonde.fr")  # ou tout autre site