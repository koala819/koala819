import logging
from typing import Any
import pathlib
import feedparser
import requests
import re
from datetime import datetime
import os

DEFAULT_N = 5
DEFAULT_DATE_FORMAT = "%Y-%m-%d"

# Fix: Use __file__ to get the current file's path
root = pathlib.Path(__file__).parent.resolve()

def fetch_feed(url: str) -> list[dict[str, str]]:
    # Add a cache-busting parameter to the URL
    cache_buster = datetime.now().timestamp()
    url_with_cache_buster = f"{url}?cache_buster={cache_buster}"
    try:
        response = requests.get(url_with_cache_buster)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        if not feed.entries:
            logging.error("Malformed feed: no entries found")
            return []
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching the feed: {e}")
        return []
    except Exception as e:
        logging.error(f"Error processing the feed: {e}")
        return []
    return [
        {
            "title": entry.title,
            "url": entry.link,
            "date": format_entry_date(entry),
            "summary": entry.summary,
        }
        for entry in feed.entries[:DEFAULT_N]
    ]

def format_feed_entry(entry: dict[str, str]) -> str:
    title = entry.get("title", "No Title")
    link = entry.get("url", "")
    date = entry.get("date", "")
    summary = entry.get("summary", "")
    
    # S'assurer que les valeurs ne sont pas vides
    if not title:
        title = "No Title"
    if not link:
        link = "#"
    if not date:
        date = ""
    if not summary:
        summary = ""
        
    # Formater l'entrée en Markdown
    return f"### [{title}]({link})\n*{date}*\n\n{summary}\n"

def format_entry_date(entry: Any, date_format: str = DEFAULT_DATE_FORMAT) -> str:
    if hasattr(entry, "updated_parsed"):
        # Fix: Create datetime object properly from time_struct
        published_time = datetime(*entry.updated_parsed[:6])
        return published_time.strftime(date_format)
    return ""

def replace_chunk(content, marker, chunk, inline=False):
    pattern = f"<!-- {marker} start -->.*?<!-- {marker} end -->"
    r = re.compile(pattern, re.DOTALL)
    if not inline:
        chunk = f"\n{chunk}\n"
    return r.sub(f"<!-- {marker} start -->{chunk}<!-- {marker} end -->", content)

def process_json_feed(json_content):
    """Process the JSON-like feed from your URL."""
    articles = []
    try:
        # D'abord, supprimons la première ligne "donne" si elle existe
        content = json_content.strip()
        if content.startswith("donne"):
            content = content[5:].strip()
            
        # Initialisons un index pour suivre les articles
        article_index = 0
        while True:
            # Cherchons le début du prochain article
            title_start = content.find(str(article_index) + 'title"')
            if title_start == -1:
                break
                
            # Créer un nouvel article
            article = {}
            
            # Extraire le titre
            title_start = content.find('"', title_start) + 1
            title_end = content.find('"', title_start)
            article['title'] = content[title_start:title_end]
            
            # Extraire l'URL
            url_start = content.find('url"', title_end) + 4
            url_start = content.find('"', url_start) + 1
            url_end = content.find('"', url_start)
            article['url'] = content[url_start:url_end]
            
            # Extraire la date
            date_start = content.find('date"', url_end) + 5
            date_start = content.find('"', date_start) + 1
            date_end = content.find('"', date_start)
            date_str = content[date_start:date_end]
            try:
                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                article['date'] = date_obj.strftime(DEFAULT_DATE_FORMAT)
            except:
                article['date'] = date_str
            
            # Extraire le résumé
            summary_start = content.find('summary"', date_end) + 8
            summary_start = content.find('"', summary_start) + 1
            summary_end = content.find('"', summary_start)
            article['summary'] = content[summary_start:summary_end]
            
            # Ajouter l'article à la liste
            articles.append(article)
            
            # Passer à l'article suivant
            article_index += 1
            
            # Limiter le nombre d'articles
            if article_index >= DEFAULT_N:
                break
                
        return articles
    except Exception as e:
        logging.error(f"Error processing JSON-like feed: {e}")
        return []

if __name__ == "__main__":
    readme = root / "README.md"
    url = "https://www.dix31.com/api/atoms"
    
    try:
        # Configurer le logging pour voir les problèmes
        logging.basicConfig(level=logging.DEBUG)
        
        # Fetching the content as text rather than parsing as RSS
        response = requests.get(url)
        response.raise_for_status()
        content = response.text
        
        # Log the first part of the content for debugging
        logging.debug(f"Content preview: {content[:200]}")
        
        # Process the custom JSON-like feed
        feeds = process_json_feed(content)
        logging.info(f"Found {len(feeds)} articles")
        
        if not feeds:
            logging.warning("No feed entries found, trying regular feed parser")
            feeds = fetch_feed(url)
            
        # Log the feed entries for debugging
        for i, feed in enumerate(feeds):
            logging.debug(f"Feed {i}: {feed}")
            
        # Format the feeds as markdown
        feeds_md = "\n".join([format_feed_entry(feed) for feed in feeds])
        
        # Make sure we have content to update
        if not feeds_md.strip():
            logging.error("No formatted content to update README with")
            print("No content generated")
            exit(1)
            
        try:
            logging.info(f"Updating README at {readme}")
            readme_contents = readme.read_text()
            rewritten = replace_chunk(readme_contents, "blog", feeds_md)
            readme.write_text(rewritten)
            print("README.md updated successfully")
            # Print the formatted Markdown so it's visible in the action logs
            print("\nGenerated content:\n" + feeds_md)
        except Exception as e:
            logging.error(f"Error updating README: {e}")
            # Print the feed content anyway
            print(feeds_md)
            
    except Exception as e:
        logging.error(f"Failed to fetch or process URL content: {e}")
        import traceback
        traceback.print_exc()
