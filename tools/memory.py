import json
import os
from datetime import datetime
from collections import defaultdict


class AgentMemory:
    """
    Agent memory system with:
    - Fact storage (categorized)
    - URL visit tracking (avoid re-scraping)
    - Session persistence (save/load JSON)
    """

    def __init__(self, target: str, session_dir: str = "sessions"):
        self.target = target
        self.session_dir = session_dir
        self.facts: list[dict] = []
        self.visited_urls: set[str] = set()
        self.queued_urls: list[str] = []
        self.search_history: list[str] = []
        self.categories: dict[str, list] = defaultdict(list)
        self.iteration = 0
        self.created_at = datetime.now().isoformat()

        os.makedirs(session_dir, exist_ok=True)
        self.session_file = os.path.join(session_dir, f"{self._safe_name(target)}.json")

    def _safe_name(self, name: str) -> str:
        return "".join(c if c.isalnum() else "_" for c in name).lower()

    def add_facts(self, facts: list[dict]):
        """Add new facts, avoid duplicates."""
        for fact in facts:
            fact_text = fact.get("fact", "")
            # Simple dedup: skip if very similar fact exists
            existing_facts = [f["fact"] for f in self.facts]
            if fact_text and not any(
                self._similarity(fact_text, existing) > 0.8
                for existing in existing_facts
            ):
                fact["added_at"] = datetime.now().isoformat()
                self.facts.append(fact)
                category = fact.get("category", "general")
                self.categories[category].append(fact)

    def _similarity(self, a: str, b: str) -> float:
        """Simple word overlap similarity."""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        overlap = words_a & words_b
        return len(overlap) / max(len(words_a), len(words_b))

    def mark_visited(self, url: str):
        self.visited_urls.add(url)

    def is_visited(self, url: str) -> bool:
        return url in self.visited_urls

    def add_to_queue(self, urls: list[str]):
        """Add URLs to scraping queue, skip already visited."""
        for url in urls:
            if url not in self.visited_urls and url not in self.queued_urls:
                self.queued_urls.append(url)

    def pop_from_queue(self) -> str | None:
        """Get next URL to scrape."""
        if self.queued_urls:
            return self.queued_urls.pop(0)
        return None

    def add_search(self, query: str):
        self.search_history.append(query)

    def get_summary(self) -> str:
        """Generate a text summary of what we know."""
        if not self.facts:
            return "No facts gathered yet."

        lines = [f"Facts about {self.target}:", f"Total facts: {len(self.facts)}", ""]
        
        for category, facts in self.categories.items():
            lines.append(f"=== {category.upper()} ({len(facts)} facts) ===")
            for f in facts[:5]:  # show max 5 per category
                lines.append(f"  • {f['fact']}")
            if len(facts) > 5:
                lines.append(f"  ... and {len(facts) - 5} more")
            lines.append("")

        return "\n".join(lines)

    def get_stats(self) -> dict:
        return {
            "total_facts": len(self.facts),
            "categories": {k: len(v) for k, v in self.categories.items()},
            "urls_visited": len(self.visited_urls),
            "urls_queued": len(self.queued_urls),
            "searches_done": len(self.search_history),
            "iteration": self.iteration,
        }

    def save(self):
        """Persist memory to JSON."""
        data = {
            "target": self.target,
            "created_at": self.created_at,
            "saved_at": datetime.now().isoformat(),
            "facts": self.facts,
            "visited_urls": list(self.visited_urls),
            "search_history": self.search_history,
            "iteration": self.iteration,
        }
        with open(self.session_file, "w") as f:
            json.dump(data, f, indent=2)

    def load(self) -> bool:
        """Load previous session if exists."""
        if not os.path.exists(self.session_file):
            return False
        try:
            with open(self.session_file) as f:
                data = json.load(f)
            self.facts = data.get("facts", [])
            self.visited_urls = set(data.get("visited_urls", []))
            self.search_history = data.get("search_history", [])
            self.iteration = data.get("iteration", 0)
            # Rebuild categories
            for fact in self.facts:
                self.categories[fact.get("category", "general")].append(fact)
            return True
        except Exception as e:
            print(f"[Memory] Failed to load session: {e}")
            return False