import logging
from typing import Any
import pathlib
import feedparser
import requests
import re
import json
from datetime import datetime
import os

DEFAULT_N = 5
DEFAULT_DATE_FORMAT = "%Y-%m-%d"

# Fix: Use __file__ to get the current file's path
root = pathlib.Path(__file__).parent.resolve()

def fetch_feed(url: str) -> list[dict[str, str]]:
    """Fallback method to fetch RSS feed (not used in main flow)"""
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
    """Format a feed entry as markdown"""
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
    """Format date for RSS entries (fallback method)"""
    if hasattr(entry, "updated_parsed"):
        # Fix: Create datetime object properly from time_struct
        published_time = datetime(*entry.updated_parsed[:6])
        return published_time.strftime(date_format)
    return ""

def replace_chunk(content, marker, chunk, inline=False):
    """Replace a chunk of content in a markdown file"""
    pattern = f"<!-- {marker} start -->.*?<!-- {marker} end -->"
    r = re.compile(pattern, re.DOTALL)
    if not inline:
        chunk = f"\n{chunk}\n"
    return r.sub(f"<!-- {marker} start -->{chunk}<!-- {marker} end -->", content)

def process_json_response(json_content):
    """Process the JSON response from the API"""
    try:
        # Attempt to parse as JSON
        articles = json.loads(json_content)
        
        # Check if response is a list of articles
        if isinstance(articles, list) and len(articles) > 0:
            # Format dates in the articles
            for article in articles:
                if "date" in article and article["date"]:
                    try:
                        date_obj = datetime.fromisoformat(article["date"].replace('Z', '+00:00'))
                        article["date"] = date_obj.strftime(DEFAULT_DATE_FORMAT)
                    except Exception as e:
                        logging.warning(f"Could not parse date '{article['date']}': {e}")
            
            # Return the first N articles
            return articles[:DEFAULT_N]
        else:
            logging.error(f"Expected a list of articles, got: {type(articles)}")
            return []
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON: {e}")
        return []
    except Exception as e:
        logging.error(f"Error processing JSON response: {e}")
        return []

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    readme = root / "README.md"
    url = "https://www.dix31.com/api/atoms"
    
    try:
        # Fetch content from the API
        response = requests.get(url)
        response.raise_for_status()
        content = response.text
        
        # Process as JSON
        feeds = process_json_response(content)
        logging.info(f"Found {len(feeds)} articles from JSON")
        
        # Format the feeds as markdown
        if feeds:
            feeds_md = "\n".join([format_feed_entry(feed) for feed in feeds])
            
            # Update README.md
            readme_contents = readme.read_text()
            rewritten = replace_chunk(readme_contents, "blog", feeds_md)
            readme.write_text(rewritten)
            logging.info("README.md updated successfully")
            
            # Print the content for log visibility
            print("\nGenerated content:\n")
            print(feeds_md)
        else:
            logging.error("No articles found to update README")
            print("No content generated")
            exit(1)
            
    except Exception as e:
        logging.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
