#!/usr/bin/env python3
"""
Flask web server for the Autonomous Research Agent.
Streams agent output in real-time via Server-Sent Events (SSE).
"""

import os
import json
import threading
import queue
import time
from datetime import datetime
from flask import Flask, render_template, request, Response, jsonify, stream_with_context
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Store active research jobs
active_jobs = {}


class StreamingAgent:
    """Wraps ResearchAgent with a message queue for SSE streaming."""
    
    def __init__(self, target: str, iterations: int):
        self.target = target
        self.iterations = iterations
        self.message_queue = queue.Queue()
        self.done = False
        self.report = None
        self.error = None

    def emit(self, type: str, data: dict):
        self.message_queue.put({"type": type, "data": data})

    def run(self):
        """Run agent in background thread."""
        try:
            from tools.search import search, search_news
            from tools.scraper import scrape
            from tools.memory import AgentMemory
            from llm.groq_client import plan_searches, extract_facts, should_continue, compile_report

            self.emit("status", {"message": f"🕷️ Initializing agent for: {self.target}", "phase": "init"})
            memory = AgentMemory(self.target)
            all_sources = set()

            for iteration in range(1, self.iterations + 1):
                memory.iteration = iteration
                self.emit("iteration", {"current": iteration, "total": self.iterations})

                # PLAN
                self.emit("phase", {"name": "PLANNING", "icon": "🧠"})
                queries = plan_searches(self.target, memory.get_summary(), iteration)
                if not queries:
                    self.emit("warning", {"message": "No queries generated"})
                    break
                for q in queries:
                    self.emit("query", {"text": q})

                # SEARCH
                self.emit("phase", {"name": "SEARCHING", "icon": "🔍"})
                urls_to_scrape = []
                snippet_facts = []

                for query in queries:
                    memory.add_search(query)
                    results = search(query, max_results=4)
                    if iteration == 1:
                        results += search_news(f"{self.target} CEO founder 2024", max_results=3)

                    for r in results:
                        url = r.get("url", "")
                        snippet = r.get("snippet", "")
                        title = r.get("title", "")
                        if snippet and len(snippet) > 50:
                            snippet_facts.append({
                                "category": "general",
                                "fact": f"{title}: {snippet}",
                                "source": url
                            })
                        if url and not memory.is_visited(url):
                            urls_to_scrape.append(url)
                            self.emit("url_found", {"title": title[:60], "url": url})

                if snippet_facts:
                    memory.add_facts(snippet_facts)
                    self.emit("facts_stored", {"count": len(snippet_facts), "type": "snippet"})

                # Deduplicate
                seen = set()
                unique_urls = []
                for url in urls_to_scrape:
                    if url not in seen and not memory.is_visited(url):
                        seen.add(url)
                        unique_urls.append(url)
                urls_to_scrape = unique_urls[:8]

                # SCRAPE
                self.emit("phase", {"name": "SCRAPING", "icon": "🕸️"})
                scraped_count = 0

                for url in urls_to_scrape:
                    if scraped_count >= 4:
                        break
                    if memory.is_visited(url):
                        continue

                    self.emit("scraping", {"url": url[:70]})
                    result = scrape(url)
                    memory.mark_visited(url)

                    if not result["success"]:
                        self.emit("scrape_failed", {"url": url[:50], "reason": result.get("reason", "?")})
                        continue

                    scraped_count += 1
                    self.emit("scraped", {"chars": result["char_count"], "title": result.get("title", "")[:50]})

                    if result["text"]:
                        extracted = extract_facts(result["text"], self.target, url)
                        facts = extracted.get("facts", [])
                        if facts:
                            memory.add_facts(facts)
                            all_sources.add(url)
                            self.emit("facts_extracted", {
                                "count": len(facts),
                                "relevance": extracted.get("relevance_score", "?"),
                                "url": url[:50]
                            })

                # Stats
                stats = memory.get_stats()
                self.emit("stats", {
                    "total_facts": stats["total_facts"],
                    "urls_visited": stats["urls_visited"],
                    "categories": list(stats["categories"].keys())
                })

                # REFLECT
                if iteration < self.iterations:
                    self.emit("phase", {"name": "REFLECTING", "icon": "🤔"})
                    decision = should_continue(memory.get_summary(), self.target, iteration, self.iterations)
                    self.emit("reflection", {
                        "continue": decision.get("continue", True),
                        "reason": decision.get("reason", ""),
                        "gaps": decision.get("missing_areas", [])
                    })
                    if not decision.get("continue", True):
                        break

                memory.save()
                time.sleep(0.5)

            # COMPILE
            self.emit("phase", {"name": "COMPILING REPORT", "icon": "📋"})
            all_facts = memory.facts
            self.emit("compiling", {"facts_count": len(all_facts)})

            report = compile_report(self.target, all_facts)
            report["sources"] = list(all_sources)
            report["metadata"] = {
                "target": self.target,
                "total_facts": len(all_facts),
                "iterations_run": memory.iteration,
                "urls_scraped": len(memory.visited_urls),
                "categories": dict(memory.get_stats()["categories"]),
                "generated_at": datetime.now().isoformat()
            }

            self.report = report
            self.emit("complete", {"report": report})

        except Exception as e:
            import traceback
            self.error = str(e)
            self.emit("error", {"message": str(e), "trace": traceback.format_exc()})
        finally:
            self.done = True
            self.emit("done", {})


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/research", methods=["POST"])
def start_research():
    data = request.get_json()
    target = data.get("target", "").strip()
    iterations = int(data.get("iterations", 3))

    if not target:
        return jsonify({"error": "Target name required"}), 400
    if not os.environ.get("GROQ_API_KEY"):
        return jsonify({"error": "GROQ_API_KEY not configured"}), 500

    job_id = f"{int(time.time())}_{target.replace(' ', '_')}"
    agent = StreamingAgent(target, iterations)
    active_jobs[job_id] = agent

    thread = threading.Thread(target=agent.run, daemon=True)
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/stream/<job_id>")
def stream(job_id):
    agent = active_jobs.get(job_id)
    if not agent:
        return jsonify({"error": "Job not found"}), 404

    def generate():
        while True:
            try:
                msg = agent.message_queue.get(timeout=30)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg["type"] == "done":
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                if agent.done:
                    break

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*"
        }
    )


@app.route("/api/jobs")
def list_jobs():
    return jsonify([
        {"job_id": jid, "target": a.target, "done": a.done}
        for jid, a in active_jobs.items()
    ])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)