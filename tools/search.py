from duckduckgo_search import DDGS
import time

def search(query: str, max_results: int = 5) -> list:
    results = []
    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results, region='wt-wt'))
            for r in raw:
                url = r.get("href", "")
                if not url:
                    continue
                results.append({
                    "title": r.get("title", ""),
                    "url": url,
                    "snippet": r.get("body", "")
                })
        time.sleep(1)
    except Exception as e:
        print(f"  [Search Error] {e}")
    return results

def search_news(query: str, max_results: int = 5) -> list:
    results = []
    try:
        with DDGS() as ddgs:
            raw = list(ddgs.news(query, max_results=max_results, region='wt-wt'))
            for r in raw:
                url = r.get("url", "")
                if not url:
                    continue
                results.append({
                    "title": r.get("title", ""),
                    "url": url,
                    "snippet": r.get("body", ""),
                    "date": r.get("date", "")
                })
        time.sleep(1)
    except Exception as e:
        print(f"  [News Error] {e}")
    return results
