from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
import time

from llm.groq_client import plan_searches, extract_facts, should_continue, compile_report
from tools.search import search, search_news
from tools.scraper import scrape
from tools.memory import AgentMemory

console = Console()

class ResearchAgent:
    def __init__(self, target: str, max_iterations: int = 4, max_urls_per_iter: int = 4, resume: bool = False):
        self.target = target
        self.max_iterations = max_iterations
        self.max_urls_per_iter = max_urls_per_iter
        self.memory = AgentMemory(target)
        if resume and self.memory.load():
            console.print(f"[green]Resumed: {len(self.memory.facts)} facts already gathered[/green]")
        self.all_sources = set()

    def _log(self, symbol, color, msg):
        console.print(f"  [{color}]{symbol}[/{color}] {msg}")

    def run(self) -> dict:
        console.print(Panel.fit(
            f"[bold]Target:[/bold] [cyan]{self.target}[/cyan]\n"
            f"[bold]Max Iterations:[/bold] {self.max_iterations}\n"
            f"[bold]Strategy:[/bold] Search → Snippet Facts → Scrape → Extract → Reflect → Report",
            title="[bold magenta]🕷️ AUTONOMOUS RESEARCH AGENT[/bold magenta]",
            border_style="magenta"
        ))

        for iteration in range(1, self.max_iterations + 1):
            self.memory.iteration = iteration
            console.print(f"\n{'═'*60}\n[bold magenta]ITERATION {iteration}/{self.max_iterations}[/bold magenta]\n{'═'*60}")

            # PLAN
            console.print(f"\n[bold blue]▶ PLANNING[/bold blue]")
            queries = plan_searches(self.target, self.memory.get_summary(), iteration)
            if not queries:
                self._log("⚠", "yellow", "No queries generated, stopping.")
                break
            for q in queries:
                console.print(f"  [dim]• {q}[/dim]")

            # SEARCH + collect URLs and snippet facts
            console.print(f"\n[bold blue]▶ SEARCHING[/bold blue]")
            urls_to_scrape = []
            snippet_facts = []

            for query in queries:
                self.memory.add_search(query)
                results = search(query, max_results=4)
                if iteration == 1:
                    results += search_news(f"{self.target} CEO founder 2024", max_results=3)

                for r in results:
                    url = r.get("url", "")
                    snippet = r.get("snippet", "")
                    title = r.get("title", "")

                    # Use snippet as a fact directly — always works
                    if snippet and len(snippet) > 50:
                        snippet_facts.append({
                            "category": "general",
                            "fact": f"{title}: {snippet}",
                            "source": url
                        })

                    if url and not self.memory.is_visited(url):
                        urls_to_scrape.append(url)
                        self._log("→", "cyan", f"{title[:60]}")

            # Store snippet facts immediately
            if snippet_facts:
                self.memory.add_facts(snippet_facts)
                self._log("✓", "green", f"Stored {len(snippet_facts)} snippet facts")

            # Deduplicate URLs
            seen = set()
            unique_urls = []
            for url in urls_to_scrape:
                if url not in seen and not self.memory.is_visited(url):
                    seen.add(url)
                    unique_urls.append(url)
            urls_to_scrape = unique_urls[:self.max_urls_per_iter * 2]

            # SCRAPE
            console.print(f"\n[bold blue]▶ SCRAPING[/bold blue] ({min(len(urls_to_scrape), self.max_urls_per_iter)} URLs)")
            scraped_count = 0

            for url in urls_to_scrape:
                if scraped_count >= self.max_urls_per_iter:
                    break
                if self.memory.is_visited(url):
                    continue

                self._log("→", "cyan", f"Scraping: {url[:70]}")
                result = scrape(url)
                self.memory.mark_visited(url)

                if not result["success"]:
                    self._log("⚠", "yellow", f"Failed ({result.get('reason','?')}): {url[:50]}")
                    continue

                scraped_count += 1
                self._log("✓", "green", f"{result['char_count']} chars: {result.get('title','')[:50]}")

                if result["text"]:
                    extracted = extract_facts(result["text"], self.target, url)
                    facts = extracted.get("facts", [])
                    if facts:
                        self.memory.add_facts(facts)
                        self.all_sources.add(url)
                        self._log("✓", "green", f"Extracted {len(facts)} facts (relevance: {extracted.get('relevance_score','?')}/10)")
                    for link in extracted.get("relevant_links", [])[:3]:
                        if not self.memory.is_visited(link):
                            self.memory.add_to_queue([link])

            # STATS
            stats = self.memory.get_stats()
            table = Table(box=box.SIMPLE)
            table.add_column("Metric", style="dim")
            table.add_column("Value", style="cyan")
            table.add_row("Facts gathered", str(stats["total_facts"]))
            table.add_row("URLs scraped", str(stats["urls_visited"]))
            table.add_row("Categories", ", ".join(stats["categories"].keys()) or "none")
            console.print(table)

            # REFLECT
            if iteration < self.max_iterations:
                console.print(f"\n[bold blue]▶ REFLECTING[/bold blue]")
                decision = should_continue(self.memory.get_summary(), self.target, iteration, self.max_iterations)
                if not decision.get("continue", True):
                    self._log("✓", "green", f"Stopping early: {decision.get('reason','')}")
                    break
                else:
                    self._log("→", "cyan", f"Continuing. Gaps: {', '.join(decision.get('missing_areas', []))}")

            self.memory.save()
            time.sleep(1)

        # COMPILE REPORT
        console.print(f"\n{'═'*60}\n[bold green]COMPILING FINAL REPORT[/bold green]\n{'═'*60}")
        all_facts = self.memory.facts
        console.print(f"  [dim]Synthesizing {len(all_facts)} facts...[/dim]")

        report = compile_report(self.target, all_facts)
        report["sources"] = list(self.all_sources)
        report["metadata"] = {
            "target": self.target,
            "total_facts": len(all_facts),
            "iterations_run": self.memory.iteration,
            "urls_scraped": len(self.memory.visited_urls),
            "categories": dict(self.memory.get_stats()["categories"])
        }
        return report
