"""
scorer.py — Scoring thématique et nettoyage du corpus
Lit mots_cles.txt, score chaque page crawlée, supprime les non pertinentes.
Fonctionne indépendamment de crawler.py sur la même base SQLite et le même corpus.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH    = Path(r"C:/PYTHON/.data/Resultatscrawling/crawler.db")              # Chemin de la base SQLite
OUTPUT_DIR = Path(r"C:/PYTHON/.data/Resultatscrawling")                         # Répertoire de sortie des fichiers
MOTS_CLES_FILE = Path(r"C:/PYTHON/.entree/SitesSources/Filtre_motcle_IA.txt")   # Fichier de seeds, une URL par ligne
SEUIL           = 0.5                                                           # Score minimum pour conserver une page (0 à 1)

# Filtres structurels — pages non-article
MIN_MOTS_PARAGRAPHE = 20    # Longueur moyenne minimale des paragraphes (en mots)
MIN_MOTS_TOTAL      = 200   # Nombre minimum de mots dans la page

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scorer")

# ---------------------------------------------------------------------------
# Lecture de la configuration
# ---------------------------------------------------------------------------

def lire_mots_cles(filepath: str) -> list[str]:
    """
    Lit le fichier de mots clés.
    Retourne une liste de mots clés en minuscules.
    Les lignes vides et commentaires (#) sont ignorés.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Fichier mots clés introuvable : {filepath}")
    mots = []
    with open(path, encoding="utf-8") as f:
        for ligne in f:
            mot = ligne.strip().lower()
            if mot and not mot.startswith("#"):
                mots.append(mot)
    if not mots:
        raise ValueError(f"Aucun mot clé trouvé dans {filepath}")
    return mots

# ---------------------------------------------------------------------------
# Base de données
# ---------------------------------------------------------------------------

def connecter_db(db_path: str) -> sqlite3.Connection:
    """Ouvre la connexion SQLite et migre le schéma si nécessaire."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Accès aux colonnes par nom

    # Migration : ajouter les colonnes score et mots_cles_trouves si absentes
    colonnes = [row[1] for row in conn.execute("PRAGMA table_info(pages)")]
    if "score" not in colonnes:
        conn.execute("ALTER TABLE pages ADD COLUMN score REAL")
        log.info("Colonne 'score' ajoutée à la table pages")
    if "mots_cles_trouves" not in colonnes:
        conn.execute("ALTER TABLE pages ADD COLUMN mots_cles_trouves TEXT")
        log.info("Colonne 'mots_cles_trouves' ajoutée à la table pages")
    conn.commit()
    return conn


def lire_pages_a_scorer(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """
    Retourne toutes les pages dont le score est NULL.
    Cela permet de relancer le scorer sans re-scorer les pages déjà traitées.
    """
    return conn.execute("""
        SELECT uuid, url, domaine, type, profondeur
        FROM pages
        WHERE score IS NULL
        ORDER BY date_crawl ASC
    """).fetchall()


def mettre_a_jour_score(
    conn: sqlite3.Connection,
    uuid: str,
    score: float,
    mots_trouves: list[str],
) -> None:
    """Met à jour le score et les mots clés trouvés pour une page."""
    conn.execute(
        """
        UPDATE pages
        SET score = ?, mots_cles_trouves = ?
        WHERE uuid = ?
        """,
        (score, ", ".join(mots_trouves), uuid),
    )
    conn.commit()


def supprimer_page_db(conn: sqlite3.Connection, uuid: str) -> None:
    """Supprime une page de la table pages."""
    conn.execute("DELETE FROM pages WHERE uuid = ?", (uuid,))
    conn.commit()

# ---------------------------------------------------------------------------
# Extraction du texte
# ---------------------------------------------------------------------------

def extraire_texte_html(contenu: bytes) -> str:
    """Extrait le texte brut d'un fichier HTML via BeautifulSoup."""
    from bs4 import BeautifulSoup
    try:
        try:
            texte = contenu.decode("utf-8")
        except UnicodeDecodeError:
            texte = contenu.decode("latin-1", errors="replace")
        soup = BeautifulSoup(texte, "html.parser")
        # Supprimer les balises script et style
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True).lower()
    except Exception as e:
        log.warning(f"Erreur extraction HTML : {e}")
        return ""


def extraire_texte_pdf(contenu: bytes) -> str:
    """Extrait le texte brut d'un fichier PDF via pymupdf."""
    import fitz  # pymupdf
    try:
        doc = fitz.open(stream=contenu, filetype="pdf")
        textes = []
        for page in doc:
            textes.append(page.get_text())
        doc.close()
        return " ".join(textes).lower()
    except Exception as e:
        log.warning(f"Erreur extraction PDF : {e}")
        return ""


def extraire_texte_txt(contenu: bytes) -> str:
    """Extrait le texte brut d'un fichier texte."""
    try:
        try:
            return contenu.decode("utf-8").lower()
        except UnicodeDecodeError:
            return contenu.decode("latin-1", errors="replace").lower()
    except Exception as e:
        log.warning(f"Erreur extraction TXT : {e}")
        return ""


def extraire_texte(contenu: bytes, type_fichier: str) -> str:
    """
    Dispatche vers le bon extracteur selon le type de fichier.
    Retourne le texte en minuscules pour faciliter la comparaison.
    """
    if type_fichier == "pdf":
        return extraire_texte_pdf(contenu)
    if type_fichier in ("doc", "docx"):
        return extraire_texte_txt(contenu)
    if type_fichier == "txt":
        return extraire_texte_txt(contenu)
    return extraire_texte_html(contenu)

# ---------------------------------------------------------------------------
# Filtre structurel — détection des pages non-article
# ---------------------------------------------------------------------------

def est_article(contenu: bytes, type_fichier: str) -> tuple[bool, str]:
    """
    Détecte si une page est un vrai article ou une page de navigation/liste.
    Retourne (True, "") si c'est un article, (False, raison) sinon.

    Critères pour les pages HTML :
    - Longueur moyenne des paragraphes >= MIN_MOTS_PARAGRAPHE
    - Nombre total de mots >= MIN_MOTS_TOTAL

    Les PDF et fichiers texte sont toujours considérés comme des articles
    car ils n'ont pas de structure HTML navigationnelle.
    """
    # PDF et texte — pas de structure HTML à analyser, on considère article
    if type_fichier in ("pdf", "txt", "doc", "docx"):
        return True, ""

    # HTML — analyse structurelle
    from bs4 import BeautifulSoup
    try:
        try:
            texte_brut = contenu.decode("utf-8")
        except UnicodeDecodeError:
            texte_brut = contenu.decode("latin-1", errors="replace")

        soup = BeautifulSoup(texte_brut, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # Critère 1 — nombre total de mots
        texte_total = soup.get_text(separator=" ", strip=True)
        nb_mots = len(texte_total.split())
        if nb_mots < MIN_MOTS_TOTAL:
            return False, f"trop court ({nb_mots} mots < {MIN_MOTS_TOTAL})"

        # Critère 2 — longueur moyenne des paragraphes
        paras = [p.get_text(strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
        if paras:
            longueurs = [len(p.split()) for p in paras]
            moy = sum(longueurs) / len(longueurs)
            if moy < MIN_MOTS_PARAGRAPHE:
                return False, f"paragraphes trop courts (moy={moy:.1f} mots < {MIN_MOTS_PARAGRAPHE})"

        return True, ""

    except Exception as e:
        log.warning(f"Erreur analyse structurelle : {e}")
        return True, ""  # En cas d'erreur, on laisse passer pour ne pas supprimer par erreur

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def scorer(texte: str, mots_cles: list[str]) -> tuple[float, list[str]]:
    """
    Calcule un score de pertinence thématique par comptage de mots clés.

    Principe :
    - Pour chaque mot clé, on vérifie sa présence dans le texte
    - On compte le nombre d'occurrences de chaque mot clé trouvé
    - Le score est le ratio : mots_cles_presents / total_mots_cles
    - Bonus : les mots clés présents plusieurs fois augmentent le score

    Retourne (score entre 0 et 1, liste des mots clés trouvés).
    """
    if not texte:
        return 0.0, []

    mots_trouves = []
    score_brut = 0.0

    for mot in mots_cles:
        occurrences = texte.count(mot)
        if occurrences > 0:
            mots_trouves.append(mot)
            # Bonus logarithmique pour les occurrences multiples
            # 1 occurrence = 1.0, 2 = 1.3, 5 = 1.6, 10 = 2.0
            import math
            score_brut += 1.0 + math.log(occurrences)

    if not mots_cles:
        return 0.0, []

    # Normalisation : score max théorique = nb_mots_cles * (1 + log(occurrences_max))
    # On normalise simplement par le nombre de mots clés pour avoir 0-1
    score = min(score_brut / len(mots_cles), 1.0)

    return round(score, 4), mots_trouves

# ---------------------------------------------------------------------------
# Suppression fichier
# ---------------------------------------------------------------------------

def supprimer_fichier(output_dir: str, uuid: str, type_fichier: str) -> None:
    """Supprime le fichier du répertoire corpus."""
    chemin = Path(output_dir) / f"{uuid}.{type_fichier}"
    if chemin.exists():
        chemin.unlink()
    else:
        log.warning(f"Fichier introuvable pour suppression : {chemin}")

# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------

def main() -> None:
    """Point d'entrée principal du scorer."""

    # Chargement de la configuration
    mots_cles = lire_mots_cles(MOTS_CLES_FILE)
    log.info(f"Mots clés chargés : {len(mots_cles)}")
    for mot in mots_cles:
        log.info(f"  → {mot}")

    conn = connecter_db(DB_PATH)
    pages = lire_pages_a_scorer(conn)
    log.info(f"{len(pages)} page(s) à scorer")

    if not pages:
        log.info("Rien à scorer — toutes les pages ont déjà un score.")
        conn.close()
        return

    # Statistiques
    stats = {"analysees": 0, "conservees": 0, "supprimees": 0, "erreurs": 0}
    debut = datetime.now()

    for page in pages:
        uuid      = page["uuid"]
        url       = page["url"]
        type_fic  = page["type"]

        # Lire le fichier
        chemin = Path(OUTPUT_DIR) / f"{uuid}.{type_fic}"
        if not chemin.exists():
            log.warning(f"[FICHIER MANQUANT] {url}")
            supprimer_page_db(conn, uuid)
            stats["erreurs"] += 1
            continue

        contenu = chemin.read_bytes()

        # Extraire le texte
        texte = extraire_texte(contenu, type_fic)
        if not texte:
            log.warning(f"[TEXTE VIDE] {url}")
            supprimer_fichier(OUTPUT_DIR, uuid, type_fic)
            supprimer_page_db(conn, uuid)
            stats["erreurs"] += 1
            continue

        # Filtre structurel — rejeter les pages non-article
        article_ok, raison = est_article(contenu, type_fic)
        if not article_ok:
            supprimer_fichier(OUTPUT_DIR, uuid, type_fic)
            supprimer_page_db(conn, uuid)
            log.info(f"[NON-ARTICLE] {raison} — {url}")
            stats["supprimees"] += 1
            continue

        # Scorer
        score, mots_trouves = scorer(texte, mots_cles)
        stats["analysees"] += 1

        if score >= SEUIL:
            mettre_a_jour_score(conn, uuid, score, mots_trouves)
            log.info(f"[CONSERVÉE] score={score:.2f} mots={mots_trouves[:3]} {url}")
            stats["conservees"] += 1
        else:
            supprimer_fichier(OUTPUT_DIR, uuid, type_fic)
            supprimer_page_db(conn, uuid)
            log.info(f"[SUPPRIMÉE] score={score:.2f} {url}")
            stats["supprimees"] += 1

    # Résumé
    duree = (datetime.now() - debut).total_seconds()
    log.info("=" * 50)
    log.info("RÉSUMÉ DU SCORING")
    log.info("=" * 50)
    log.info(f"Pages analysées  : {stats['analysees']}")
    log.info(f"Pages conservées : {stats['conservees']}")
    log.info(f"Pages supprimées : {stats['supprimees']}")
    log.info(f"Erreurs          : {stats['erreurs']}")
    log.info(f"Durée            : {duree:.1f} secondes")
    log.info("=" * 50)

    conn.close()


if __name__ == "__main__":
    main()