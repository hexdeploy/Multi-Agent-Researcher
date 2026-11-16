import json
import arxiv
import wikipedia
from crewai.tools import tool
from duckduckgo_search import DDGS


def _clean_query(query: str) -> str:
    """Helper to clean LLM inputs if it accidentally passes JSON strings."""
    if not isinstance(query, str):
        return str(query)
    query = query.strip()
    if query.startswith("{") and query.endswith("}"):
        try:
            parsed = json.loads(query)
            if isinstance(parsed, dict):
                for key in ["query", "q", "search"]:
                    if key in parsed:
                        return str(parsed[key])
        except Exception:
            pass
    if (query.startswith('"') and query.endswith('"')) or (query.startswith("'") and query.endswith("'")):
        query = query[1:-1]
    return query


@tool("DuckDuckGo Web Search")
def duckduckgo_search_tool(query: str) -> str:
    """
    Search the web using DuckDuckGo for current news, articles, documentation, and general facts.
    Returns formatted titles, source URLs, and snippets.
    """
    clean_q = _clean_query(query)
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(clean_q, max_results=2))  # Reduced to 2 to save tokens
        
        if not results:
            return f"No web results found for '{clean_q}'."

        formatted_results = []
        for idx, res in enumerate(results, start=1):
            title = res.get("title", "No Title")
            url = res.get("href", "No URL")
            body = res.get("body", "No Snippet")[:300]  # Trim snippet length
            formatted_results.append(
                f"[Web {idx}] Title: {title}\nURL: {url}\nSummary: {body}"
            )
        return "\n\n---\n\n".join(formatted_results)
    except Exception as e:
        return f"Web search note for '{clean_q}': {str(e)}. Proceeding with Wikipedia and arXiv knowledge."


@tool("Wikipedia Knowledge Search")
def wikipedia_search_tool(query: str) -> str:
    """
    Search Wikipedia for foundational knowledge, definitions, history, and established facts.
    Returns the top matching page title, Wikipedia URL, and summary.
    """
    clean_q = _clean_query(query)
    try:
        search_titles = wikipedia.search(clean_q, results=2)
        if not search_titles:
            return f"No Wikipedia articles found for '{clean_q}'."

        formatted_results = []
        for idx, title in enumerate(search_titles[:1], start=1):  # Top 1 result to save tokens
            try:
                page = wikipedia.page(title, auto_suggest=False)
                summary = wikipedia.summary(title, sentences=3, auto_suggest=False)
                formatted_results.append(
                    f"[Wiki {idx}] Title: {page.title}\nURL: {page.url}\nSummary: {summary}"
                )
            except Exception:
                continue

        return (
            "\n\n---\n\n".join(formatted_results)
            if formatted_results
            else f"Could not retrieve Wikipedia details for '{clean_q}'."
        )
    except Exception as e:
        return f"Wikipedia search error for '{clean_q}': {str(e)}"


@tool("arXiv Academic Paper Search")
def arxiv_search_tool(query: str) -> str:
    """
    Search arXiv for peer-reviewed preprints, scientific studies, AI/ML papers, and technical research.
    Returns paper titles, authors, publication dates, arXiv PDF/abstract URLs, and abstracts.
    """
    clean_q = _clean_query(query)
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=clean_q,
            max_results=2,  # Reduced to 2 to save tokens
            sort_by=arxiv.SortCriterion.Relevance,
        )
        results = list(client.results(search))
        if not results:
            return f"No arXiv academic papers found for '{clean_q}'."

        formatted_results = []
        for idx, paper in enumerate(results, start=1):
            authors = ", ".join(author.name for author in paper.authors[:2])
            published = paper.published.strftime("%Y-%m-%d") if paper.published else "Unknown"
            abstract = paper.summary.replace("\n", " ").strip()[:300]  # Trim abstract
            formatted_results.append(
                f"[arXiv {idx}] Title: {paper.title}\n"
                f"Authors: {authors} | Published: {published}\n"
                f"URL: {paper.entry_id}\n"
                f"Abstract: {abstract}..."
            )
        return "\n\n---\n\n".join(formatted_results)
    except Exception as e:
    
        return f"arXiv search error for '{clean_q}': {str(e)}"