import logging
from typing import Any
import pathlib
import requests
import re
from datetime import datetime

DEFAULT_N = 5
DEFAULT_DATE_FORMAT = "%Y-%m-%d"

root = pathlib.Path(__file__).parent.resolve()

def fetch_posts(url: str) -> list[dict[str, str]]:
    try:
        response = requests.get(url)
        response.raise_for_status()
        posts = response.json()
        if not posts:
            logging.error("Malformed response: no posts found")
            return []
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching the posts: {e}")
        return []
    except Exception as e:
        logging.error(f"Error processing the posts: {e}")
        return []

    return [
        {
            "title": post["title"],
            "url": post["url"],
            "date": format_post_date(post),
        }
        for post in posts[:DEFAULT_N]
    ]

def format_post_entry(entry: dict[str, str]) -> str:
    title = entry.get("title", "No Title")
    link = entry.get("url", "")
    date = entry.get("date", "")

    return f"[{title}]({link}) - {date}"

def format_post_date(post: Any, date_format: str = DEFAULT_DATE_FORMAT) -> str:
    if "publishedDate" in post:
        published_time = datetime.fromisoformat(post["publishedDate"])
        return published_time.strftime(date_format)
    return ""

def replace_chunk(content, marker, chunk, inline=False):
    pattern = f"<!-- {marker} start -->.*<!-- {marker} end -->"
    r = re.compile(pattern, re.DOTALL)
    
    if not inline:
        chunk = f"\n{chunk}\n"
        
    return r.sub(f"<!-- {marker} start -->{chunk}<!-- {marker} end -->", content)


if __name__ == "__main__":
    readme = root / "README.md"
    url = "https://www.dix31.com/api/atoms"
    posts = fetch_posts(url)
    posts_md = "\n\n".join([format_post_entry(post) for post in posts])
    readme_contents = readme.read_text()
    rewritten = replace_chunk(readme_contents, "blog", posts_md)
    readme.write_text(rewritten)
    print(posts_md)
