import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are an autonomous research agent specialized in gathering comprehensive information about founders and CEOs.
Your job is to plan targeted searches, extract relevant facts from web content, and synthesize information into structured insights.
Always respond in valid JSON when asked for structured output.
Prioritize credible sources (LinkedIn, Crunchbase, Forbes, TechCrunch, official company sites, Wikipedia).
"""

def chat(messages: list, response_format: str = "text") -> str:
    kwargs = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "temperature": 0.3,
        "max_tokens": 2048,
    }
    if response_format == "json":
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content

def plan_searches(target: str, context: str = "", iteration: int = 0) -> list:
    prompt = f"""You are researching: "{target}"
Current context gathered so far:
{context if context else "None yet - this is the first search."}
Iteration: {iteration}
Generate 3-5 highly targeted search queries to find comprehensive information about this person.
Focus on: early life, education, Stanford dropout, Loopt founding, Y Combinator presidency, OpenAI founding and leadership, net worth, personal life, controversies like the November 2023 board firing, notable quotes and vision for AI.
{"Since this is not the first iteration, focus on gaps in the context above." if iteration > 0 else "Start with broad biographical queries."}
Respond with JSON: {{"queries": ["query1", "query2", ...]}}"""
    response = chat([{"role": "user", "content": prompt}], response_format="json")
    data = json.loads(response)
    return data.get("queries", [])

def extract_facts(content: str, target: str, url: str) -> dict:
    prompt = f"""Extract all relevant facts about "{target}" from this web content.
URL: {url}
Content (truncated):
{content[:3000]}
Extract and categorize facts. Respond with JSON:
{{
  "facts": [
    {{"category": "education|career|company|achievement|personal|quote|financial", "fact": "...", "source": "{url}"}}
  ],
  "relevant_links": [],
  "relevance_score": 0
}}
Only include facts directly about {target}."""
    response = chat([{"role": "user", "content": prompt}], response_format="json")
    try:
        return json.loads(response)
    except:
        return {"facts": [], "relevant_links": [], "relevance_score": 0}

def should_continue(memory_summary: str, target: str, iteration: int, max_iterations: int) -> dict:
    prompt = f"""Research status for "{target}":
Iteration: {iteration}/{max_iterations}
Summary of what we know so far:
{memory_summary}
Should we continue researching or do we have enough to write a comprehensive report?
Respond with JSON: {{"continue": true, "reason": "...", "missing_areas": ["area1"]}}"""
    response = chat([{"role": "user", "content": prompt}], response_format="json")
    try:
        return json.loads(response)
    except:
        return {"continue": iteration < max_iterations, "reason": "Parsing error", "missing_areas": []}

def compile_report(target: str, all_facts: list) -> dict:
    facts_text = "\n".join([f"[{f.get('category','general').upper()}] {f.get('fact','')} (Source: {f.get('source','')})" for f in all_facts])
    prompt = f"""You have researched "{target}" and gathered these facts:
{facts_text}
Compile a comprehensive report. Respond with JSON:
{{
  "name": "Full name",
  "title": "Current title/role",
  "summary": "2-3 sentence executive summary",
  "sections": {{
    "early_life_education": "Detailed paragraph",
    "career_journey": "Detailed paragraph",
    "entrepreneurial_ventures": "Companies founded or led",
    "key_achievements": ["achievement1", "achievement2"],
    "leadership_style": "Analysis paragraph",
    "notable_quotes": ["quote1", "quote2"],
    "controversies_challenges": "Paragraph",
    "net_worth_financials": "Financial details",
    "personal_life": "Personal details",
    "vision_philosophy": "Vision paragraph"
  }},
  "sources": [],
  "confidence_score": 80,
  "research_gaps": ["gap1"]
}}"""
    response = chat([{"role": "user", "content": prompt}], response_format="json")
    try:
        return json.loads(response)
    except Exception as e:
        return {"error": str(e), "raw": response}
