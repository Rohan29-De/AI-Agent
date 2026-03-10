import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Domains to skip (login walls, social media, paywalls)
SKIP_DOMAINS = {
    "twitter.com", "x.com", "facebook.com", "instagram.com",
    "tiktok.com", "reddit.com", "youtube.com", "login",
    "wsj.com", "nytimes.com", "ft.com"
}

# High-value domains for a founder/CEO research
HIGH_VALUE_DOMAINS = {
    "linkedin.com", "crunchbase.com", "forbes.com", "techcrunch.com",
    "bloomberg.com", "businessinsider.com", "wired.com", "inc.com",
    "entrepreneur.com", "wikipedia.org", "investopedia.com"
}


def is_skippable(url: str) -> bool:
    """Check if URL should be skipped."""
    try:
        domain = urlparse(url).netloc.lower()
        return any(skip in domain for skip in SKIP_DOMAINS)
    except:
        return True


def scrape(url: str, timeout: int = 10) -> dict:
    """
    Scrape a URL and return cleaned text + extracted links.
    Returns: {url, text, links, title, success}
    """
    if is_skippable(url):
        return {"url": url, "text": "", "links": [], "title": "", "success": False, "reason": "skipped domain"}

    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return {"url": url, "text": "", "links": [], "title": "", "success": False, "reason": "non-HTML content"}

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove noise elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "advertisement", "iframe"]):
            tag.decompose()

        # Extract title
        title = soup.find("title")
        title_text = title.get_text(strip=True) if title else ""

        # Extract main content (prefer article/main tags)
        main_content = (
            soup.find("article") or
            soup.find("main") or
            soup.find(class_=re.compile(r"content|article|post|story", re.I)) or
            soup.find("body")
        )

        # Clean text
        raw_text = main_content.get_text(separator="\n", strip=True) if main_content else ""
        lines = [line.strip() for line in raw_text.split("\n") if len(line.strip()) > 40]
        text = "\n".join(lines[:100])  # cap at 100 meaningful lines

        # Extract links
        links = []
        base_domain = urlparse(url).netloc
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            absolute_url = urljoin(url, href)
            link_domain = urlparse(absolute_url).netloc

            # Only keep http/https links
            if not absolute_url.startswith(("http://", "https://")):
                continue

            # Prioritize high-value external links, skip same-domain navigation
            if link_domain != base_domain or any(hv in link_domain for hv in HIGH_VALUE_DOMAINS):
                link_text = a_tag.get_text(strip=True)
                if len(link_text) > 3:  # skip icon-only links
                    links.append({"url": absolute_url, "text": link_text})

        # Deduplicate links
        seen = set()
        unique_links = []
        for link in links:
            if link["url"] not in seen:
                seen.add(link["url"])
                unique_links.append(link["url"])

        time.sleep(0.3)  # polite delay

        return {
            "url": url,
            "title": title_text,
            "text": text,
            "links": unique_links[:20],  # top 20 links
            "success": True,
            "char_count": len(text)
        }

    except requests.exceptions.Timeout:
        return {"url": url, "text": "", "links": [], "title": "", "success": False, "reason": "timeout"}
    except requests.exceptions.HTTPError as e:
        return {"url": url, "text": "", "links": [], "title": "", "success": False, "reason": f"HTTP {e.response.status_code}"}
    except Exception as e:
        return {"url": url, "text": "", "links": [], "title": "", "success": False, "reason": str(e)}