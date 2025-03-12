import logging
from typing import Any
import pathlib
import feedparser
import requests
import re
from datetime import datetime
import os
import sys
import xml.etree.ElementTree as ET

DEFAULT_N = 5
DEFAULT_DATE_FORMAT = "%Y-%m-%d"

# Use __file__ to get the current file's path
root = pathlib.Path(__file__).parent.resolve()

def fetch_feed(url: str) -> list[dict[str, str]]:
    """Fetch and parse an RSS feed"""
    try:
        # Add a cache-busting parameter to the URL
        cache_buster = datetime.now().timestamp()
        url_with_cache_buster = f"{url}?cache_buster={cache_buster}"
        
        # Log the URL being fetched
        logging.info(f"Fetching feed from: {url_with_cache_buster}")
        
        # Make the request with proper headers for RSS
        headers = {
            'Accept': 'application/rss+xml, application/xml, text/xml',
            'User-Agent': 'Mozilla/5.0 (compatible; RSSFeedParser/1.0)'
        }
        response = requests.get(url_with_cache_buster, headers=headers)
        response.raise_for_status()
        
        # Try to parse with feedparser
        logging.info("Parsing with feedparser...")
        feed = feedparser.parse(response.content)
        
        # Check if the feed has entries
        if not feed.entries:
            logging.warning("No entries found with feedparser, trying XML parsing...")
            return parse_rss_manually(response.text)
            
        # Process entries with feedparser
        result = []
        for entry in feed.entries[:DEFAULT_N]:
            item = {
                "title": entry.title if hasattr(entry, "title") else "No title",
                "url": entry.link if hasattr(entry, "link") else "",
                "date": format_entry_date(entry),
                "summary": entry.description if hasattr(entry, "description") else ""
            }
            result.append(item)
            
        logging.info(f"Successfully parsed {len(result)} entries with feedparser")
        return result
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching the feed: {e}")
        return []
    except Exception as e:
        logging.error(f"Error processing the feed: {e}")
        logging.error(f"Exception type: {type(e).__name__}")
        return []

def parse_rss_manually(xml_content: str) -> list[dict[str, str]]:
    """Parse RSS feed manually using ElementTree"""
    try:
        logging.info("Attempting manual XML parsing...")
        
        # Parse the XML
        root = ET.fromstring(xml_content)
        
        # Find all item elements (may need to adjust for namespace)
        # Try different possible paths for items
        items = []
        possible_paths = [
            './/item',                   # Standard RSS
            './channel/item',            # Standard RSS with explicit channel
            './/{http://www.w3.org/2005/Atom}entry'  # Atom
        ]
        
        for path in possible_paths:
            items = root.findall(path)
            if items:
                logging.info(f"Found {len(items)} items using path: {path}")
                break
                
        if not items:
            logging.error("Could not find any items in the XML")
            return []
            
        # Process items
        result = []
        for item in items[:DEFAULT_N]:
            # Extract title, link, pubDate, and description
            # Handle both RSS and Atom formats
            
            # For title
            title_element = item.find('./title') or item.find('.//{http://www.w3.org/2005/Atom}title')
            title = title_element.text if title_element is not None else "No title"
            
            # For link
            link = ""
            link_element = item.find('./link') or item.find('.//{http://www.w3.org/2005/Atom}link')
            if link_element is not None:
                if link_element.text:
                    link = link_element.text
                elif link_element.get('href'):  # For Atom
                    link = link_element.get('href')
            
            # For date
            date = ""
            date_element = (
                item.find('./pubDate') or 
                item.find('.//{http://www.w3.org/2005/Atom}published') or
                item.find('.//{http://www.w3.org/2005/Atom}updated')
            )
            if date_element is not None and date_element.text:
                try:
                    # Parse the date
                    date_str = date_element.text
                    dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
                    date = dt.strftime(DEFAULT_DATE_FORMAT)
                except Exception as e:
                    logging.warning(f"Could not parse date: {date_element.text} - {e}")
                    try:
                        # Try alternative format
                        dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S GMT")
                        date = dt.strftime(DEFAULT_DATE_FORMAT)
                    except:
                        pass
            
            # For description/summary
            summary = ""
            summary_element = (
                item.find('./description') or 
                item.find('.//{http://www.w3.org/2005/Atom}summary') or
                item.find('.//{http://www.w3.org/2005/Atom}content')
            )
            if summary_element is not None:
                summary = summary_element.text or ""
            
            result.append({
                "title": title,
                "url": link,
                "date": date,
                "summary": summary
            })
            
        logging.info(f"Successfully parsed {len(result)} entries with manual XML parsing")
        return result
        
    except ET.ParseError as e:
        logging.error(f"XML parsing error: {e}")
        return []
    except Exception as e:
        logging.error(f"Error in manual RSS parsing: {e}")
        logging.error(f"Exception type: {type(e).__name__}")
        return []

def format_entry_date(entry: Any, date_format: str = DEFAULT_DATE_FORMAT) -> str:
    """Format the date from a feedparser entry"""
    # Try different date fields
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            published_time = datetime(*entry.published_parsed[:6])
            return published_time.strftime(date_format)
        except:
            pass
            
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            updated_time = datetime(*entry.updated_parsed[:6])
            return updated_time.strftime(date_format)
        except:
            pass
    
    # As a last resort, try to find any string date and parse it
    for attr in ["published", "updated", "pubDate"]:
        if hasattr(entry, attr) and getattr(entry, attr):
            try:
                date_str = getattr(entry, attr)
                dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
                return dt.strftime(date_format)
            except:
                try:
                    # Try alternative format
                    dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S GMT")
                    return dt.strftime(date_format)
                except:
                    pass
    
    return ""

def format_feed_entry(entry: dict[str, str]) -> str:
    """Format a feed entry as markdown"""
    title = entry.get("title", "No Title")
    link = entry.get("url", "")
    date = entry.get("date", "")
    summary = entry.get("summary", "")
    
    # Ensure values are not empty
    if not title:
        title = "No Title"
    if not link:
        link = "#"
    if not date:
        date = ""
    if not summary:
        summary = ""
        
    # Format the entry as Markdown
    return f"### [{title}]({link})\n*{date}*\n\n{summary}\n"

def replace_chunk(content, marker, chunk, inline=False):
    """Replace a chunk of content in a markdown file"""
    pattern = f"<!-- {marker} start -->.*?<!-- {marker} end -->"
    r = re.compile(pattern, re.DOTALL)
    if not inline:
        chunk = f"\n{chunk}\n"
    return r.sub(f"<!-- {marker} start -->{chunk}<!-- {marker} end -->", content)

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Get README path
    readme = root / "README.md"
    
    # RSS feed URL - Utiliser la nouvelle URL
    url = "https://www.dix31.com/api/rss"
    
    try:
        logging.info(f"Starting feed update process for URL: {url}")
        
        # Fetch and parse the feed
        feeds = fetch_feed(url)
        
        if not feeds:
            logging.error("No entries found in the feed")
            print("No entries found in the feed")
            sys.exit(1)
            
        logging.info(f"Successfully fetched {len(feeds)} entries")
        
        # Format as markdown
        feeds_md = "\n".join([format_feed_entry(feed) for feed in feeds])
        
        # Update README
        try:
            readme_contents = readme.read_text()
            rewritten = replace_chunk(readme_contents, "blog", feeds_md)
            readme.write_text(rewritten)
            logging.info(f"Successfully updated README at {readme}")
            
            # Print for log visibility
            print("\nGenerated content:\n")
            print(feeds_md)
            print("\nREADME.md updated successfully")
            
        except Exception as e:
            logging.error(f"Error updating README: {e}")
            # Still print content in case of README update failure
            print("\nGenerated content (README update failed):\n")
            print(feeds_md)
            sys.exit(1)
            
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
