import requests
import argparse
from urllib.request import urlparse, urljoin
from bs4 import BeautifulSoup
import colorama

# init the colorama module
colorama.init()

GREEN = colorama.Fore.GREEN
GRAY = colorama.Fore.LIGHTBLACK_EX
RESET = colorama.Fore.RESET

# initialize the set of links (unique links)
internal_urls = set()
external_urls = set()
external_urls_domain = set()
chaine_domaines = ""

total_urls_visited = 0


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extraction des liens du site")
    parser.add_argument("url", help="The URL to extract links from.")
    parser.add_argument("-m", "--max-urls", help="Nombre maximum d'adresses à crawler, defaut 30.", default=30, type=int)
    
    args = parser.parse_args()
    url = args.url
    max_urls = args.max_urls

    crawl(url, max_urls=max_urls)

    print("[+] Total de liens internes:", len(internal_urls))
    print("[+] Total de liens externes:", len(external_urls))
    print("[+] Total des URLs:", len(external_urls) + len(internal_urls))

    domain_name = urlparse(url).netloc

    # save the internal links to a file
    with open(f"C:/DATA/github/.data/{domain_name}_internal_links.txt", "w", encoding="utf-8") as f:
        for internal_link in internal_urls:
            print(internal_link.strip(), file=f)

    # save the external links to a file
    with open(f"C:/DATA/github/.data/{domain_name}_external_links.txt", "w", encoding="utf-8") as f:
        for external_link in external_urls:
            print(external_link.strip(), file=f)
    
    # save external domain names
    external_urls_domain = list(dict.fromkeys(external_urls_domain))

        # save the external links to a file
    with open(f"C:/DATA/github/.data/{domain_name}_external_domains.txt", "w", encoding="utf-8") as f:
        for external_domain in external_urls_domain:
            if "@" not in external_domain:
                chaine_domaines += external_domain.strip() + ", "
        
        f.write(chaine_domaines)