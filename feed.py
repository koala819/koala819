import logging
from typing import Any
import pathlib
import requests
import re
from datetime import datetime
import sys

DEFAULT_N = 5
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
root = pathlib.Path(__file__).parent.resolve()

# Configuration du logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_feed(url: str) -> list[dict[str, str]]:
    logging.info(f"Récupération du flux depuis {url}")
    # Add a cache-busting parameter to the URL
    cache_buster = datetime.now().timestamp()
    url_with_cache_buster = f"{url}?cache_buster={cache_buster}"
    
    try:
        response = requests.get(url_with_cache_buster)
        response.raise_for_status()
        
        logging.info(f"Statut de la réponse: {response.status_code}")
        logging.info(f"Taille de la réponse: {len(response.text)} caractères")
        
        # Traiter le contenu comme du texte brut, car ce n'est pas un flux RSS standard
        content = response.text
        
        # Parser le contenu texte personnalisé
        articles = []
        lines = content.strip().split('\n')
        
        logging.info(f"Nombre de lignes dans la réponse: {len(lines)}")
        
        # Première ligne = info du blog, on la saute
        for i in range(1, len(lines), 2):
            if i + 1 < len(lines):
                # Ligne impaire: titre, date et URL
                title_line = lines[i]
                
                # Extraire le titre, la date et l'URL
                title_parts = title_line.split('https://')
                if len(title_parts) > 1:
                    title = title_parts[0].strip()
                    url_date_part = 'https://' + title_parts[1]
                    
                    # Trouver la date (format ISO) dans la ligne
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)', url_date_part)
                    if date_match:
                        date_str = date_match.group(1)
                        # Convertir la date ISO en objet datetime
                        date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        formatted_date = date.strftime(DEFAULT_DATE_FORMAT)
                        
                        # Extraire l'URL (tout ce qui est avant la date)
                        url = url_date_part.split(date_str)[0].strip()
                        
                        # Ligne paire: description
                        description = lines[i + 1] if i + 1 < len(lines) else ""
                        
                        articles.append({
                            "title": title,
                            "url": url,
                            "date": formatted_date,
                            "summary": description
                        })
        
        logging.info(f"Nombre d'articles extraits: {len(articles)}")
        
        # Prendre les N premiers articles
        return articles[:DEFAULT_N]
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Erreur lors de la récupération du flux: {e}")
        return []
    except Exception as e:
        logging.error(f"Erreur lors du traitement du flux: {e}")
        return []

def format_feed_entry(entry: dict[str, str]) -> str:
    title = entry.get("title", "No Title")
    link = entry.get("url", "")
    date = entry.get("date", "")
    summary = entry.get("summary", "")
    return f"[{title}]({link}) - {date}\n{summary}"

def replace_chunk(content, marker, chunk, inline=False):
    pattern = f"<!-- {marker} start -->.*<!-- {marker} end -->"
    r = re.compile(pattern, re.DOTALL)
    
    if not inline:
        chunk = f"\n{chunk}\n"
    
    # Vérifier si le pattern existe dans le contenu
    if not r.search(content):
        logging.error(f"Le motif '<!-- {marker} start -->.*<!-- {marker} end -->' n'a pas été trouvé dans le README.")
        logging.error("Vérifiez que les balises existent exactement sous cette forme.")
        return content
        
    return r.sub(f"<!-- {marker} start -->{chunk}<!-- {marker} end -->", content)

if __name__ == "__main__":
    logging.info("Démarrage du script")
    
    # Récupérer le chemin du README
    readme = root / "README.md"
    logging.info(f"Chemin du README: {readme.absolute()}")
    
    # Vérifier si le fichier existe
    if not readme.exists():
        logging.error(f"ERREUR: Le fichier README.md n'existe pas à l'emplacement {readme.absolute()}")
        sys.exit(1)
    
    # Lire le contenu du README
    try:
        readme_contents = readme.read_text(encoding='utf-8')
        logging.info(f"Contenu du README lu avec succès ({len(readme_contents)} caractères)")
    except Exception as e:
        logging.error(f"Erreur lors de la lecture du README: {e}")
        sys.exit(1)
    
    # Vérifier la présence des balises
    if "<!-- blog start -->" not in readme_contents or "<!-- blog end -->" not in readme_contents:
        logging.error("Les balises '<!-- blog start -->' et/ou '<!-- blog end -->' sont absentes du README")
        logging.info("Contenu du README:")
        logging.info(readme_contents)
        sys.exit(1)
    
    # Récupérer les articles
    url = "https://www.dix31.com/api/atoms"
    feeds = fetch_feed(url)
    
    if not feeds:
        logging.error("Aucun article récupéré. Vérifiez l'URL et le format de la réponse.")
        sys.exit(1)
    
    # Formater les articles
    feeds_md = "\n\n".join([format_feed_entry(feed) for feed in feeds])
    logging.info(f"Articles formatés ({len(feeds_md)} caractères)")
    
    # Remplacer le bloc dans le README
    rewritten = replace_chunk(readme_contents, "blog", feeds_md)
    
    # Vérifier si le contenu a changé
    if rewritten == readme_contents:
        logging.warning("Le contenu n'a pas été modifié après le remplacement.")
        # Vérifier plus en détail
        blog_start_idx = readme_contents.find("<!-- blog start -->")
        blog_end_idx = readme_contents.find("<!-- blog end -->")
        if blog_start_idx != -1 and blog_end_idx != -1:
            current_content = readme_contents[blog_start_idx:blog_end_idx + len("<!-- blog end -->")]
            logging.info(f"Contenu actuel entre les balises: {repr(current_content)}")
    else:
        logging.info("Le contenu a été modifié avec succès.")
    
    # Écrire le nouveau contenu dans le README
    try:
        readme.write_text(rewritten, encoding='utf-8')
        logging.info("Fichier README.md mis à jour avec succès!")
    except Exception as e:
        logging.error(f"Erreur lors de l'écriture du fichier: {e}")
        sys.exit(1)
    
    # Afficher un résumé des articles pour vérification
    print("\n=== Articles ajoutés au README ===")
    for i, feed in enumerate(feeds, 1):
        print(f"{i}. {feed['title']} - {feed['date']}")
    
    logging.info("Script terminé avec succès")
