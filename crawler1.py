"""
crawler.py — Crawler web thématique
Architecture : asyncio + curl_cffi + BeautifulSoup4 + SQLite
"""

import asyncio
import logging
import random
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEEDS_FILE = Path(r"C:/PYTHON/.entree/SitesSources/sites_actus_labos.txt")           # Fichier de seeds, une URL par ligne
PATTERNS        = [                     # Patterns d'URL à sauvegarder
    "/abs/",          # arxiv
    "/pdf/",          # arxiv, documents
    "/article/",      # presse
    "/fr/",           # INRIA pages en français
    "/en/",           # INRIA pages en anglais
    "/publication",   # publications génériques
    "/research/",     # recherche générique
    "/blog/",         # blogs pour hugging face
    "/blog.google/",  # blog deepmind
    "/news/",         # stanford
    "/the-decoder.com/", # the decoder
    "/www.lemonde.fr/", # le monde
    "/www.technologyreview.com/", # MIT tech review
    "/www.therundown.ai/", # the rundown
    "/partnershiponai.org/", #parternership on AI
]

OUTPUT_DIR = Path(r"C:/PYTHON/.data/Resultatscrawling")                         # Répertoire de sortie des fichiers
DB_PATH    = Path(r"C:/PYTHON/.data/Resultatscrawling/crawler.db")                         # Chemin de la base SQLite

DELAY_MIN       = 1                    # Délai minimum entre requêtes (secondes)
DELAY_MAX       = 3                    # Délai maximum entre requêtes (secondes)
MAX_CONCURRENT  = 5                    # Nombre de workers parallèles
MAX_RETRIES     = 1                    # Nombre de retries en cas d'erreur
MAX_DEPTH       = 1                    # Profondeur max de crawl
TIMEOUT         = 30                   # Timeout par requête (secondes)
MAX_FILE_SIZE   = 50 * 1024 * 1024    # Taille max de fichier (50 MB)
TYPES_AUTORISES = [                    # Extensions de fichiers autorisées
    ".html",
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("crawler")

# ---------------------------------------------------------------------------
# Base de données
# ---------------------------------------------------------------------------

def init_db(db_path: str) -> sqlite3.Connection:
    """Initialise la base SQLite et crée les tables si elles n'existent pas."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")  # Meilleure concurrence en écriture
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pages (
            uuid        TEXT PRIMARY KEY,
            url         TEXT NOT NULL UNIQUE,
            domaine     TEXT NOT NULL,
            type        TEXT NOT NULL,
            date_crawl  TEXT NOT NULL,
            profondeur  INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS erreurs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            url         TEXT NOT NULL,
            domaine     TEXT NOT NULL,
            code_http   TEXT,
            message     TEXT,
            date        TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_pages_url     ON pages(url);
        CREATE INDEX IF NOT EXISTS idx_pages_domaine ON pages(domaine);
    """)
    conn.commit()
    return conn


def url_deja_visitee(conn: sqlite3.Connection, url: str) -> bool:
    """Retourne True si l'URL a déjà été crawlée ou a déjà échoué."""
    row = conn.execute(
        "SELECT 1 FROM pages WHERE url = ?", (url,)
    ).fetchone()
    if row:
        return True
    row = conn.execute(
        "SELECT 1 FROM erreurs WHERE url = ?", (url,)
    ).fetchone()
    return row is not None


def sauvegarder_page(
    conn: sqlite3.Connection,
    url: str,
    domaine: str,
    type_fichier: str,
    profondeur: int,
    file_uuid: str,
) -> None:
    """Enregistre une page crawlée dans la table pages."""
    conn.execute(
        """
        INSERT OR IGNORE INTO pages (uuid, url, domaine, type, date_crawl, profondeur)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (file_uuid, url, domaine, type_fichier, datetime.utcnow().isoformat(), profondeur),
    )
    conn.commit()


def sauvegarder_erreur(
    conn: sqlite3.Connection,
    url: str,
    domaine: str,
    code_http: str | None,
    message: str,
) -> None:
    """Enregistre une erreur dans la table erreurs."""
    conn.execute(
        """
        INSERT INTO erreurs (url, domaine, code_http, message, date)
        VALUES (?, ?, ?, ?, ?)
        """,
        (url, domaine, code_http, message, datetime.utcnow().isoformat()),
    )
    conn.commit()

# ---------------------------------------------------------------------------
# Utilitaires URL
# ---------------------------------------------------------------------------

def extraire_domaine(url: str) -> str:
    """Retourne le domaine (netloc) d'une URL."""
    return urlparse(url).netloc


def meme_domaine(url: str, domaine_seed: str) -> bool:
    """Retourne True si l'URL appartient au même domaine que la seed."""
    return extraire_domaine(url) == domaine_seed


def url_matche_pattern(url: str, patterns: list[str]) -> bool:
    """Retourne True si l'URL contient au moins un des patterns."""
    return any(pattern in url for pattern in patterns)


def extension_autorisee(url: str, types_autorises: list[str]) -> bool:
    """
    Retourne True si l'URL pointe vers un type de fichier autorisé,
    ou si elle n'a pas d'extension (page HTML sans .html explicite).
    """
    path = urlparse(url).path.lower()
    if "." not in Path(path).suffix:
        return True  # Pas d'extension → probablement du HTML
    return Path(path).suffix in types_autorises


def detecter_type(url: str, content_type: str) -> str:
    """Détecte le type de fichier à partir de l'URL ou du Content-Type."""
    path = urlparse(url).path.lower()
    if path.endswith(".pdf") or "pdf" in content_type:
        return "pdf"
    if path.endswith(".docx") or "docx" in content_type:
        return "docx"
    if path.endswith(".doc"):
        return "doc"
    if path.endswith(".txt") or "text/plain" in content_type:
        return "txt"
    return "html"


def normaliser_url(url: str, base_url: str) -> str | None:
    """
    Convertit une URL relative en URL absolue.
    Retourne None si l'URL n'est pas valide ou non HTTP(S).
    Filtre les URLs malformées (templates non résolus, espaces, etc.)
    """
    try:
        url = url.strip()

        # Ignorer les templates non résolus ex: {{live_url}}, {url}, %7B%7B
        if "{{" in url or "}}" in url or "{%" in url or "%}" in url:
            return None

        # Ignorer les URLs avec des espaces non encodés
        if " " in url:
            return None

        url_abs = urljoin(base_url, url)
        parsed = urlparse(url_abs)
        if parsed.scheme not in ("http", "https"):
            return None
        # Supprimer les fragments (#section)
        return parsed._replace(fragment="").geturl()
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Téléchargement HTTP
# ---------------------------------------------------------------------------

async def telecharger(
    url: str,
    session,
    timeout: int = TIMEOUT,
    max_retries: int = MAX_RETRIES,
) -> tuple[bytes | None, str, str | None]:
    """
    Télécharge une URL avec curl_cffi en impersonnant Chrome.
    Retourne (contenu, content_type, message_erreur).
    - contenu        : bytes du fichier, ou None si erreur
    - content_type   : valeur du header Content-Type, ou ""
    - message_erreur : None si succès, sinon description de l'erreur
    Gère les retries avec délai exponentiel.
    Gère le 429 avec délai adaptatif (Retry-After ou 60s par défaut).
    La session curl_cffi est partagée et passée en paramètre.
    """
    tentative = 0
    dernier_message = None

    while tentative <= max_retries:
        try:
            response = await session.get(
                url,
                timeout=timeout,
                impersonate="chrome",  # Contourne les anti-bots TLS
                allow_redirects=True,
            )

            # 429 Too Many Requests — délai adaptatif
            if response.status_code == 429:
                dernier_message = "HTTP 429 Too Many Requests"
                # Respecter le header Retry-After si présent, sinon 60s par défaut
                retry_after = response.headers.get("Retry-After")
                try:
                    attente = int(retry_after) if retry_after else 60
                except ValueError:
                    attente = 60
                log.warning(f"[429] {url} — rate limité, attente {attente}s avant retry")
                await asyncio.sleep(attente)
                tentative += 1
                continue

            # Autres erreurs HTTP (4xx, 5xx)
            if response.status_code >= 400:
                dernier_message = f"HTTP {response.status_code}"
                tentative += 1
                if tentative <= max_retries:
                    attente = 2 ** tentative  # Délai exponentiel : 2s, 4s...
                    log.warning(f"[RETRY {tentative}/{max_retries}] {url} — {dernier_message} — attente {attente}s")
                    await asyncio.sleep(attente)
                continue

            # Vérification taille avant de lire le contenu
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_FILE_SIZE:
                return None, "", f"Fichier trop lourd : {int(content_length) // (1024*1024)} MB"

            contenu = response.content
            if len(contenu) > MAX_FILE_SIZE:
                return None, "", f"Fichier trop lourd : {len(contenu) // (1024*1024)} MB"

            content_type = response.headers.get("Content-Type", "")
            return contenu, content_type, None

        except asyncio.TimeoutError:
            dernier_message = f"Timeout après {timeout}s"
        except Exception as e:
            dernier_message = str(e)

        tentative += 1
        if tentative <= max_retries:
            attente = 2 ** tentative
            log.warning(f"[RETRY {tentative}/{max_retries}] {url} — {dernier_message} — attente {attente}s")
            await asyncio.sleep(attente)

    return None, "", dernier_message

# ---------------------------------------------------------------------------
# Extraction des liens
# ---------------------------------------------------------------------------

def extraire_liens(html: bytes, base_url: str) -> list[str]:
    """
    Parse le HTML et extrait tous les liens <a href>.
    Retourne une liste d'URLs absolues normalisées, sans doublons.
    Les PDFs et autres fichiers liés via <a href> sont inclus.
    """
    from bs4 import BeautifulSoup

    try:
        # Décodage UTF-8 avec fallback latin-1
        try:
            texte = html.decode("utf-8")
        except UnicodeDecodeError:
            texte = html.decode("latin-1", errors="replace")

        soup = BeautifulSoup(texte, "html.parser")

        liens = set()
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()

            # Ignorer les liens vides, mailto, javascript, tel
            if not href or href.startswith(("mailto:", "javascript:", "tel:", "#")):
                continue

            url_absolue = normaliser_url(href, base_url)
            if url_absolue:
                liens.add(url_absolue)

        return list(liens)

    except Exception as e:
        log.warning(f"Erreur extraction liens depuis {base_url} : {e}")
        return []

# ---------------------------------------------------------------------------
# Stockage fichier
# ---------------------------------------------------------------------------

def sauvegarder_fichier(
    contenu: bytes,
    output_dir: str,
    file_uuid: str,
    type_fichier: str,
) -> Path:
    """
    Sauvegarde le contenu brut dans le répertoire de sortie.
    Nom du fichier : <uuid>.<type>
    Retourne le chemin du fichier créé.
    """
    chemin = Path(output_dir) / f"{file_uuid}.{type_fichier}"
    chemin.write_bytes(contenu)
    return chemin

# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

async def worker(
    queue: asyncio.Queue,
    conn: sqlite3.Connection,
    semaphore: asyncio.Semaphore,
    stats: dict,
    domaine_seed: str,
    db_lock: asyncio.Lock,
) -> None:
    """
    Worker async. Consomme des URLs depuis la queue et les traite.
    Chaque item de la queue est un tuple (url, profondeur).
    La session HTTP est créée une fois par worker et réutilisée.
    """
    from curl_cffi.requests import AsyncSession

    async with AsyncSession() as session:
        while True:
            try:
                url, profondeur = await asyncio.wait_for(queue.get(), timeout=5)
            except asyncio.TimeoutError:
                break

            async with semaphore:
                await traiter_url(url, profondeur, queue, conn, stats, domaine_seed, session, db_lock)
                await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

            queue.task_done()


async def traiter_url(
    url: str,
    profondeur: int,
    queue: asyncio.Queue,
    conn: sqlite3.Connection,
    stats: dict,
    domaine_seed: str,
    session,
    db_lock: asyncio.Lock,
) -> None:
    """
    Traite une URL :
    - vérifie si déjà visitée
    - vérifie le domaine
    - vérifie l'extension
    - télécharge
    - vérifie la taille
    - sauvegarde si pattern matché
    - extrait les liens si profondeur < MAX_DEPTH
    """

    # 1. Déjà visitée ? (lecture SQLite — pas besoin de verrou)
    if url_deja_visitee(conn, url):
        log.debug(f"[IGNORÉE — déjà visitée] {url}")
        stats["ignorees"] += 1
        return

    # 2. Même domaine que la seed ?
    if not meme_domaine(url, domaine_seed):
        log.debug(f"[IGNORÉE — hors domaine] {url}")
        stats["ignorees"] += 1
        return

    # 3. Extension autorisée ?
    if not extension_autorisee(url, TYPES_AUTORISES):
        log.debug(f"[IGNORÉE — extension non autorisée] {url}")
        stats["ignorees"] += 1
        return

    # 4. Téléchargement
    log.info(f"[CRAWL] profondeur={profondeur} {url}")
    contenu, content_type, erreur = await telecharger(url, session)

    if erreur or contenu is None:
        log.warning(f"[ERREUR] {url} — {erreur}")
        async with db_lock:
            sauvegarder_erreur(conn, url, domaine_seed, None, erreur or "contenu vide")
        stats["erreurs"] += 1
        return

    # 5. Détecter le type de fichier
    type_fichier = detecter_type(url, content_type)

    # 6. Sauvegarder si pattern matché
    if url_matche_pattern(url, PATTERNS):
        file_uuid = str(uuid.uuid4())
        chemin = sauvegarder_fichier(contenu, OUTPUT_DIR, file_uuid, type_fichier)
        async with db_lock:
            sauvegarder_page(conn, url, domaine_seed, type_fichier, profondeur, file_uuid)
        log.info(f"[SAUVEGARDÉE] {url} → {chemin.name}")
        stats["sauvegardees"] += 1
    else:
        log.debug(f"[IGNORÉE — pattern non matché] {url}")
        stats["ignorees"] += 1

    # 7. Extraire les liens si profondeur < MAX_DEPTH
    # On extrait les liens même si la page n'est pas sauvegardée
    # (une page index peut ne pas matcher le pattern mais contenir des liens utiles)
    if profondeur < MAX_DEPTH and "html" in content_type:
        liens = extraire_liens(contenu, url)
        nouveaux = 0
        for lien in liens:
            if not url_deja_visitee(conn, lien):
                await queue.put((lien, profondeur + 1))
                nouveaux += 1
        if nouveaux:
            log.debug(f"[LIENS] {nouveaux} nouveau(x) lien(s) ajouté(s) depuis {url}")

# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def lire_seeds(seeds_file: str) -> list[str]:
    """Lit le fichier de seeds et retourne une liste d'URLs."""
    path = Path(seeds_file)
    if not path.exists():
        raise FileNotFoundError(f"Fichier seeds introuvable : {seeds_file}")
    seeds = []
    with open(path, encoding="utf-8") as f:
        for ligne in f:
            url = ligne.strip()
            if url and not url.startswith("#"):
                seeds.append(url)
    return seeds


def afficher_resume(stats: dict, duree: float) -> None:
    """Affiche le résumé final dans le terminal."""
    log.info("=" * 50)
    log.info("RÉSUMÉ DU CRAWL")
    log.info("=" * 50)
    log.info(f"Pages sauvegardées : {stats['sauvegardees']}")
    log.info(f"Pages ignorées     : {stats['ignorees']}")
    log.info(f"Erreurs            : {stats['erreurs']}")
    log.info(f"Durée              : {duree:.1f} secondes")
    log.info("=" * 50)


async def main() -> None:
    """Point d'entrée principal du crawler."""

    # Initialisation
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    conn = init_db(DB_PATH)
    seeds = lire_seeds(SEEDS_FILE)

    log.info(f"Démarrage du crawl — {len(seeds)} seed(s) chargée(s)")
    for seed in seeds:
        log.info(f"  → {seed}")

    # Statistiques globales partagées entre tous les workers
    stats = {"sauvegardees": 0, "ignorees": 0, "erreurs": 0}

    # Regrouper les seeds par domaine
    # Chaque domaine a sa propre queue et ses propres workers
    # Cela garantit que chaque worker connaît son domaine_seed
    domaines: dict[str, list[str]] = {}
    for seed_url in seeds:
        domaine = extraire_domaine(seed_url)
        domaines.setdefault(domaine, []).append(seed_url)

    debut = asyncio.get_event_loop().time()

    # Lancer un groupe de workers par domaine en parallèle
    async def crawl_domaine(domaine: str, seed_urls: list[str]) -> None:
        """Crawl un domaine avec son propre groupe de workers."""
        queue: asyncio.Queue = asyncio.Queue()
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        db_lock = asyncio.Lock()  # Verrou pour les écritures SQLite

        # Remplissage initial de la queue avec les seeds du domaine
        for seed_url in seed_urls:
            await queue.put((seed_url, 0))

        log.info(f"[DOMAINE] {domaine} — {len(seed_urls)} seed(s)")

        workers = [
            asyncio.create_task(
                worker(queue, conn, semaphore, stats, domaine, db_lock)
            )
            for _ in range(MAX_CONCURRENT)
        ]

        await queue.join()

        for w in workers:
            w.cancel()

        log.info(f"[DOMAINE TERMINÉ] {domaine}")

    # Lancer tous les domaines en parallèle
    await asyncio.gather(*[
        crawl_domaine(domaine, seed_urls)
        for domaine, seed_urls in domaines.items()
    ])

    duree = asyncio.get_event_loop().time() - debut
    afficher_resume(stats, duree)
    conn.close()


if __name__ == "__main__":
    asyncio.run(main())