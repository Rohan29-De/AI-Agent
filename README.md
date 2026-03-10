# ARCANE — Autonomous Research & Context Acquisition Network Engine

> An OpenClaw-inspired autonomous agent that researches founders and CEOs using LLM-driven planning, web scraping, and iterative reflection. **Zero cost** — runs entirely on Groq's free tier + DuckDuckGo.

---

## What It Does

Given a target name (e.g. `"Sam Altman"`), ARCANE autonomously:
1. **Plans** targeted search queries using an LLM
2. **Searches** DuckDuckGo and extracts snippet facts immediately
3. **Scrapes** the most relevant web pages
4. **Extracts** structured facts (categorized by type) via LLM
5. **Reflects** — decides whether to keep researching or stop
6. **Compiles** a comprehensive JSON + Markdown report

Results include: early life, career journey, companies founded, achievements, controversies, net worth, personal life, notable quotes, and vision/philosophy — with a confidence score and source list.

---

## Project Structure

```
AI-Agent/
├── main.py               # CLI entry point
├── app.py                # Flask web server with real-time SSE streaming
├── agent.py              # ResearchAgent — core agentic loop
├── llm/
│   └── groq_client.py    # Groq API wrapper (plan, extract, reflect, compile)
├── tools/
│   ├── search.py         # DuckDuckGo search (text + news)
│   ├── scraper.py        # HTTP scraper with BeautifulSoup content extraction
│   └── memory.py         # AgentMemory — facts, URL dedup, session persistence
├── output/
│   └── formatter.py      # Saves reports as JSON and Markdown
├── templates/
│   └── index.html        # ARCANE web UI — dark terminal aesthetic, live log stream
├── sessions/             # Saved research sessions (gitignored)
├── output/               # Generated reports (gitignored)
├── requirements.txt
├── Procfile              # For deployment (e.g. Render/Railway)
└── .env                  # Put your GROQ_API_KEY here (gitignored)
```

---

## Setup

### 1. Clone & create virtualenv

```bash
git clone https://github.com/Rohan29-De/AI-Agent
cd AI-Agent
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Get a free Groq API key

Sign up at [console.groq.com](https://console.groq.com) — it's free.

### 4. Create `.env`

```bash
echo "GROQ_API_KEY=your_key_here" > .env
```

---

## Usage

### CLI

```bash
# Basic research
python main.py "Sam Altman"

# More iterations = deeper research
python main.py "Jensen Huang" --iterations 5

# Resume a previous session
python main.py "Elon Musk" --resume

# Custom output directory
python main.py "Sundar Pichai" --output-dir results/
```

**CLI flags:**

| Flag | Default | Description |
|---|---|---|
| `--iterations` / `-i` | 3 | Number of research iterations |
| `--urls-per-iter` / `-u` | 4 | Max URLs to scrape per iteration |
| `--resume` / `-r` | off | Resume from saved session |
| `--output-dir` / `-o` | `output/` | Where to save reports |
| `--no-markdown` | off | Skip markdown report |

### Web UI (ARCANE)

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000). Enter a name, choose iterations, click **DEPLOY**. The terminal panel streams the agent's log in real-time; the report appears on the right when complete. Supports JSON and Markdown download.

---

## Output

Reports are saved to `output/` as both JSON and Markdown:

```
output/
├── sam_altman_20260310_161052.json
└── sam_altman_20260310_161052.md
```

**JSON report structure:**

```json
{
  "name": "Samuel H. Altman",
  "title": "CEO of OpenAI",
  "summary": "...",
  "sections": {
    "early_life_education": "...",
    "career_journey": "...",
    "entrepreneurial_ventures": "...",
    "key_achievements": ["..."],
    "leadership_style": "...",
    "notable_quotes": ["..."],
    "controversies_challenges": "...",
    "net_worth_financials": "...",
    "personal_life": "...",
    "vision_philosophy": "..."
  },
  "sources": ["https://..."],
  "confidence_score": 85,
  "research_gaps": ["..."],
  "metadata": {
    "target": "Sam Altman",
    "total_facts": 47,
    "iterations_run": 3,
    "urls_scraped": 8,
    "categories": {"career": 18, "personal": 6}
  }
}
```

---

## Architecture

### Agentic Loop (per iteration)

```
PLAN  →  SEARCH  →  SCRAPE  →  EXTRACT  →  REFLECT
  ↑                                             |
  └─────────── (loop until done) ───────────────┘
                                                |
                                           COMPILE REPORT
```

### Key Design Decisions

- **Snippet-first fact gathering**: search result snippets are stored as facts immediately, even if the page can't be scraped. This ensures data is gathered even when sites block scrapers.
- **LLM-structured JSON**: all LLM calls request JSON output with a defined schema via `response_format={"type":"json_object"}`.
- **Fuzzy deduplication**: `AgentMemory` uses word-overlap similarity (>80% threshold) to avoid storing near-identical facts.
- **Domain filtering**: known paywalls/social media (WSJ, NYT, Twitter, etc.) are skipped. High-value domains (Wikipedia, Forbes, Crunchbase, TechCrunch) are prioritized.
- **Session persistence**: each research session is saved to `sessions/<target>.json` and can be resumed with `--resume`.
- **SSE streaming** (web UI): the Flask app runs the agent in a background thread and pushes structured events to the browser via Server-Sent Events.

### LLM Functions (`llm/groq_client.py`)

| Function | Purpose |
|---|---|
| `plan_searches(target, context, iteration)` | Generate 3–5 targeted search queries |
| `extract_facts(text, target, url)` | Extract & categorize facts from scraped content |
| `should_continue(summary, target, iteration, max)` | Decide whether to keep researching |
| `compile_report(target, all_facts)` | Synthesize final structured report |

All functions use a shared `chat()` helper that injects a `SYSTEM_PROMPT` and supports `response_format="json"`.

---

## Known Issues & Planned Improvements

### Current Limitations

1. **DuckDuckGo regional/irrelevant results**: Short names can match unrelated topics (e.g. "SAM" matches Meta's Segment Anything Model). Mitigated with `region='wt-wt'` and more specific query phrasing.
2. **JS-rendered pages return 0 chars**: Sites like MSN and Benzinga are React apps — `requests` + BeautifulSoup can't execute JavaScript. Fix: integrate Playwright.
3. **Repeated URLs across iterations**: When DuckDuckGo returns the same URLs every iteration, later iterations scrape nothing new. Fix: always include Wikipedia as a first-pass source, and inject direct URLs for well-known people.

### Planned Next Steps

- [ ] Add Playwright for JS-rendered page scraping
- [ ] Always scrape Wikipedia directly as first source
- [ ] Wrap target name in quotes in search queries (e.g. `"Sam Altman" biography`)
- [ ] Swappable LLM backend (OpenAI, Ollama, Gemini)
- [ ] PDF export using WeasyPrint
- [ ] Batch mode: research multiple targets in one run
- [ ] Deploy to Render/Railway (Procfile is already set up)

---

## Dependencies

| Package | Purpose |
|---|---|
| `groq` | LLM inference (llama-3.3-70b-versatile, free tier) |
| `duckduckgo-search` | Web search without API key |
| `requests` + `beautifulsoup4` + `lxml` | Web scraping |
| `rich` | Terminal UI (panels, tables, colored output) |
| `flask` | Web server for ARCANE UI |
| `python-dotenv` | Load `GROQ_API_KEY` from `.env` |

---

## Cost

**Zero.** Groq's free tier provides generous rate limits for `llama-3.3-70b-versatile`. DuckDuckGo requires no API key.

---

*Inspired by OpenClaw autonomous agent architecture.*
