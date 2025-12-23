# bibliotheques
import csv
import pandas as pd
import os
import requests
import argparse
from urllib.request import urlparse, urljoin
from bs4 import BeautifulSoup
import colorama
from time import sleep
from datetime import datetime

# init the colorama module
colorama.init()

GREEN = colorama.Fore.GREEN
GRAY = colorama.Fore.LIGHTBLACK_EX
RESET = colorama.Fore.RESET

# variables
fichier_entree = "C:/DATA/github/.data/entree.txt"
fichier_sortie = "C:/DATA/github/.data/liste_graphe.txt"

# ecriture des fichiers de sortie
if os.path.exists(fichier_sortie):
    os.remove(fichier_sortie)

# initialize the set of links (unique links)
internal_urls = set()
external_urls = set()
external_urls_domain = set()
chaine_domaines = ""
total_urls_visited = 0

#fonctions
def is_valid(url):
    """
    Checks whether `url` is a valid URL.
    """
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)


def get_all_website_links(url):
    """
    Returns all URLs that is found on `url` in which it belongs to the same website
    """
    # all URLs of `url`
    urls = set()
    # domain name of the URL without the protocol
    domain_name = urlparse(url).netloc
    soup = BeautifulSoup(requests.get(url).content, "html.parser", from_encoding="iso-8859-1")
    for a_tag in soup.findAll("a"):
        href = a_tag.attrs.get("href")
        if href == "" or href is None or "javascript" in href or "mailto" in href:
            # href empty tag
            continue
        # join the URL if it's relative (not absolute link)
        href = urljoin(url, href)
        parsed_href = urlparse(href)
        # remove URL GET parameters, URL fragments, etc.
        href = parsed_href.scheme + "://" + parsed_href.netloc + parsed_href.path
        if not is_valid(href):
            # not a valid URL
            continue
        if href in internal_urls:
            # already in the set
            continue
        if domain_name not in href:
            # external link
            if href not in external_urls:
                print(f"{GRAY}Externe : {href}{RESET}")
                external_urls.add(href)
                external_urls_domain.add(urlparse(href).netloc)
            continue
        print(f"{GREEN}Interne: {href}{RESET}")
        urls.add(href)
        internal_urls.add(href)
    return urls

# crawl de la page, extraction des liens
def crawl(url, max_urls=50):
    global total_urls_visited
    total_urls_visited += 1
    links = get_all_website_links(url)
    for link in links:
        if total_urls_visited > max_urls:
            break
        crawl(link, max_urls=max_urls)


# Ouverture du fichier de domaines
print("{} - Ouverture du fichier de domaines".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
with open(fichier_entree, 'r', encoding='utf8') as f:
    for line in f:
        if line.find("http") == -1:
            line = 'https://' + line.rstrip()
        else:
            line = line.rstrip()

        crawl(line)

        print("[+] Total de liens internes:", len(internal_urls))
        print("[+] Total de liens externes:", len(external_urls))
        print("[+] Total des URLs:", len(external_urls) + len(internal_urls))
        
        domain_name = urlparse(line).netloc

        # save external domain names
        external_urls_domain = list(dict.fromkeys(external_urls_domain))

        # save the external links to a file
        print("{} - Ecriture du fichier de sorties".format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
        with open(fichier_sortie, "a", encoding="utf-8") as f:
            chaine_domaines = domain_name + "\nLIENS : "
            for external_domain in external_urls_domain:
                if "@" not in external_domain:
                    chaine_domaines += external_domain.strip() + ", "
            chaine_domaines = chaine_domaines[:-2] + "\n"
            f.write(chaine_domaines)
        
        external_urls_domain = set()
        chaine_domaines = ""