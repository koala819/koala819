import logging
from typing import Any
import pathlib
import feedparser
import requests
import re
from datetime import datetime
DEFAULT_N = 5
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
root = pathlib.Path(file).parent.resolve()
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
        published_time = datetime(entry.updated_parsed[:6])
        return published_time.strftime(date_format)
    return ""
def replace_chunk(content, marker, chunk, inline=False):
    pattern = f"<!-- {marker} start -->.<!-- {marker} end -->"
    r = re.compile(pattern, re.DOTALL)

    if not inline:
        chunk = f"\n{chunk}\n"

    return r.sub(f"<!-- {marker} start -->{chunk}<!-- {marker} end -->", content)
if name == "main":
    readme = root / "README.md"
    url = "https://www.dix31.com/api/atoms"
    feeds = fetch_feed(url)
    feeds_md = "\n\n".join([format_feed_entry(feed) for feed in feeds])
    readme_contents = readme.read_text()
    rewritten = replace_chunk(readme_contents, "blog", feeds_md)
    readme.write_text(rewritten)
    print(feeds_md)
