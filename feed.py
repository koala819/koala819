import logging
from typing import Any
import pathlib
import requests
import re
from datetime import datetime
import json

DEFAULT_N = 5
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
root = pathlib.Path(__file__).parent.resolve()

def fetch_feed(url: str) -> list[dict[str, str]]:
    # Add a cache-busting parameter to the URL
    cache_buster = datetime.now().timestamp()
    url_with_cache_buster = f"{url}?cache_buster={cache_buster}"
    
    try:
        response = requests.get(url_with_cache_buster)
        response.raise_for_status()
        
        # Traiter le contenu comme du texte brut, car ce n'est pas un flux RSS standard
        content = response.text
        
        # Parser le contenu texte personnalisé
        # Format attendu: titre - dateURL description
        articles = []
        lines = content.strip().split('\n')
        
        # Première ligne = info du blog, on la saute
        for i in range(1, len(lines), 2):
            if i + 1 < len(lines):
                # Ligne impaire: titre, date et URL
                title_line = lines[i]
                
                # Extraire le titre, la date et l'URL
                # Format attendu: TITRE URL DATE
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
        
        # Prendre les N premiers articles
        return articles[:DEFAULT_N]
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching the feed: {e}")
        return []
    except Exception as e:
        logging.error(f"Error processing the feed: {e}")
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
        
    return r.sub(f"<!-- {marker} start -->{chunk}<!-- {marker} end -->", content)

if __name__ == "__main__":
    readme = root / "README.md"
    url = "https://www.dix31.com/api/atoms"
    feeds = fetch_feed(url)
    feeds_md = "\n\n".join([format_feed_entry(feed) for feed in feeds])
    readme_contents = readme.read_text()
    rewritten = replace_chunk(readme_contents, "blog", feeds_md)
    readme.write_text(rewritten)
    print(feeds_md)
