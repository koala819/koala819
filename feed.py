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
    return f"[{title}]({link}) - {date}\n{summary}"

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
        # Parse the JSON-like format
        lines = json_content.strip().split('\n')
        current_article = {}
        
        for line in lines:
            if line.startswith(('0', '1', '2', '3', '4')) and 'title' in line:
                # New article starts
                if current_article and 'title' in current_article:
                    articles.append(current_article)
                current_article = {}
                
            if 'title' in line and '"' in line:
                parts = line.split('title')
                if len(parts) > 1:
                    title_part = parts[1].strip()
                    title = title_part.split('"')[1]
                    current_article['title'] = title
            
            if 'url' in line and '"' in line:
                parts = line.split('url')
                if len(parts) > 1:
                    url_part = parts[1].strip()
                    url = url_part.split('"')[1]
                    current_article['url'] = url
            
            if 'date' in line and '"' in line:
                parts = line.split('date')
                if len(parts) > 1:
                    date_part = parts[1].strip()
                    date = date_part.split('"')[1]
                    # Convert to desired format
                    try:
                        date_obj = datetime.fromisoformat(date.replace('Z', '+00:00'))
                        current_article['date'] = date_obj.strftime(DEFAULT_DATE_FORMAT)
                    except:
                        current_article['date'] = date
            
            if 'summary' in line and '"' in line:
                parts = line.split('summary')
                if len(parts) > 1:
                    summary_part = parts[1].strip()
                    summary = summary_part.split('"')[1]
                    current_article['summary'] = summary
        
        # Add the last article
        if current_article and 'title' in current_article:
            articles.append(current_article)
            
        return articles[:DEFAULT_N]
    except Exception as e:
        logging.error(f"Error processing JSON-like feed: {e}")
        return []

if __name__ == "__main__":
    readme = root / "README.md"
    url = "https://www.dix31.com/api/atoms"
    
    try:
        # Fetching the content as text rather than parsing as RSS
        response = requests.get(url)
        response.raise_for_status()
        content = response.text
        
        # Process the custom JSON-like feed
        feeds = process_json_feed(content)
        
        if not feeds:
            logging.warning("No feed entries found, trying regular feed parser")
            feeds = fetch_feed(url)
            
        feeds_md = "\n\n".join([format_feed_entry(feed) for feed in feeds])
        
        try:
            readme_contents = readme.read_text()
            rewritten = replace_chunk(readme_contents, "blog", feeds_md)
            readme.write_text(rewritten)
            print("README.md updated successfully")
        except Exception as e:
            logging.error(f"Error updating README: {e}")
            # Print the feed content anyway
            print(feeds_md)
            
    except Exception as e:
        logging.error(f"Failed to fetch or process URL content: {e}")
