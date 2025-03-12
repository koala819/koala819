import logging
from typing import Any
import pathlib
import requests
import re
from datetime import datetime
import sys
import json

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
        
        # Parse JSON response
        articles = response.json()
        logging.info(f"Nombre d'articles récupérés: {len(articles)}")
        
        # Format the dates
        formatted_articles = []
        for article in articles:
            # Skip articles without required fields
            if not article.get('title') or not article.get('url'):
                continue
                
            # Format the date if present
            formatted_date = ""
            if article.get('date'):
                try:
                    # Handle ISO date format
                    date = datetime.fromisoformat(article['date'].replace('Z', '+00:00'))
                    formatted_date = date.strftime(DEFAULT_DATE_FORMAT)
                except Exception as e:
                    logging.error(f"Erreur lors du formatage de la date: {e}")
                    formatted_date = article['date']
            
            # Add to formatted articles
            formatted_articles.append({
                "title": article.get('title', 'No Title'),
                "url": article.get('url', ''),
                "date": formatted_date,
                "summary": article.get('summary', '')
            })
        
        return formatted_articles[:DEFAULT_N]
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Erreur lors de la récupération du flux: {e}")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"Erreur lors du décodage JSON: {e}")
        logging.error(f"Contenu de la réponse: {response.text[:200]}...")
        return []
    except Exception as e:
        logging.error(f"Erreur inattendue: {e}")
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
