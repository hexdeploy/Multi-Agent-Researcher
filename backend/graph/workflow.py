import os
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import TypedDict
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from tools.search_tools import (
    duckduckgo_search_tool,
    wikipedia_search_tool,
    arxiv_search_tool,
)

load_dotenv(override=True)


class ResearchState(TypedDict):
    topic: str
    research_plan: str
    raw_research: str
    fact_check_result: str
    confidence_score: str
    analysis: str
    final_report: str
    retry_count: int


def _get_groq_model_name() -> str:
    load_dotenv(override=True)
    raw = os.getenv("GROQ_MODEL_NAME", "groq/openai/gpt-oss-20b")
    return raw.replace("groq/", "") if raw.startswith("groq/") else raw


def _invoke_groq_safe(prompt: str, temperature: float = 0.2, max_tokens: int = 900) -> str:
    """Invokes Groq with compact prompts and automatic backoff on 429 TPM rate limits."""
    llm = ChatGroq(
        model=_get_groq_model_name(),
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=30,
        max_retries=1,
    )
    for attempt in range(4):
        try:
            response = llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            err_msg = str(e).lower()
            if ("rate_limit" in err_msg or "429" in err_msg or "rate limit" in err_msg) and attempt < 3:
                wait_sec = 18 * (attempt + 1)
                print(f"[GRAPH] Groq 8K TPM limit reached. Waiting {wait_sec}s before retry {attempt + 1}/3...", flush=True)
                time.sleep(wait_sec)
            else:
                raise


def _run_with_timeout(fn, *args, timeout_sec: int = 120):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn, *args)
        return future.result(timeout=timeout_sec)


def _gather_multi_source_data(topic: str) -> str:
    """Fetches and trims live results from DuckDuckGo, Wikipedia, and arXiv."""
    sections = []
    for label, tool in [
        ("DuckDuckGo", duckduckgo_search_tool),
        ("Wikipedia", wikipedia_search_tool),
        ("arXiv", arxiv_search_tool),
    ]:
        try:
            output = str(tool.run(topic))[:900]
            sections.append(f"[{label}]\n{output}")
        except Exception as e:
            sections.append(f"[{label}]\nUnavailable: {e}")
    return "\n\n".join(sections)


def planner_node(state: ResearchState) -> dict:
    """Generates an initial 4-point research plan for human review."""
    print(f"[GRAPH] Starting planner_node for topic: {state['topic']}", flush=True)
    try:
        prompt = (
            f"Topic: '{state['topic']}'. Output 4 concise bullet points outlining key technical, "
            "factual, and real-world research angles to investigate. No intro text."
        )
        plan_text = _invoke_groq_safe(prompt, temperature=0.3, max_tokens=300)
        print("[GRAPH] planner_node succeeded.", flush=True)
        return {"research_plan": plan_text}
    except Exception as e:
        print(f"[GRAPH ERROR] planner_node failed: {e}", flush=True)
        traceback.print_exc()
        return {
            "research_plan": (
                f"- Core technical architecture of {state['topic']}\n"
                f"- Recent 2025–2026 breakthroughs and deployments\n"
                f"- Key limitations and reliability challenges\n"
                f"- Comparative landscape and future outlook"
            )
        }


def researcher_node(state: ResearchState) -> dict:
    print(f"[GRAPH] Starting researcher_node for topic: {state['topic']}", flush=True)
    scraped_sources = _run_with_timeout(_gather_multi_source_data, state["topic"], timeout_sec=45)

    prompt = (
        f"You are Alpha (Senior Researcher). Topic: '{state['topic']}'.\n"
        f"Plan:\n{state.get('research_plan', '')[:400]}\n\n"
        f"Sources:\n{scraped_sources}\n\n"
        "Extract the most important facts, dates, metrics, and exact URLs in concise bullet points (max 300 words)."
    )
    raw_data = _run_with_timeout(_invoke_groq_safe, prompt, 0.1, 700, timeout_sec=120)
    time.sleep(14)  # Keep rolling 60s TPM window well below 8,000 tokens
    print("[GRAPH] researcher_node succeeded.", flush=True)
    return {"raw_research": raw_data[:1800]}


def fact_checker_node(state: ResearchState) -> dict:
    print("[GRAPH] Starting fact_checker_node...", flush=True)
    prompt = (
        f"You are Beta (Fact-Checker). Topic: '{state['topic']}'.\n"
        f"Notes:\n{state['raw_research'][:1500]}\n\n"
        "Verify source consistency in 4 short bullets (max 150 words). "
        "End with exactly 'CONFIDENCE: HIGH' or 'CONFIDENCE: LOW'."
    )
    fact_check = _run_with_timeout(_invoke_groq_safe, prompt, 0.1, 400, timeout_sec=120)
    confidence = "LOW" if "CONFIDENCE: LOW" in fact_check.upper() else "HIGH"
    retries = state.get("retry_count", 0)
    if confidence == "LOW":
        retries += 1
    time.sleep(14)  # Keep rolling 60s TPM window well below 8,000 tokens
    print(f"[GRAPH] fact_checker_node finished (Confidence: {confidence}).", flush=True)
    return {
        "fact_check_result": fact_check[:1000],
        "confidence_score": confidence,
        "retry_count": retries,
    }


def analyst_node(state: ResearchState) -> dict:
    print("[GRAPH] Starting analyst_node...", flush=True)
    prompt = (
        f"You are Gamma (Strategic Analyst). Topic: '{state['topic']}'.\n"
        f"Findings:\n{state['raw_research'][:1400]}\n"
        f"Audit:\n{state['fact_check_result'][:700]}\n\n"
        "Synthesize key patterns, comparative trade-offs, and strategic takeaways (max 300 words)."
    )
    analysis = _run_with_timeout(_invoke_groq_safe, prompt, 0.2, 700, timeout_sec=120)
    time.sleep(14)  # Keep rolling 60s TPM window well below 8,000 tokens
    print("[GRAPH] analyst_node finished.", flush=True)
    return {"analysis": analysis[:1800]}


def writer_node(state: ResearchState) -> dict:
    print("[GRAPH] Starting writer_node...", flush=True)
    prompt = (
        f"You are Delta (Technical Writer). Write a clean Markdown research report on '{state['topic']}'.\n\n"
        f"Analysis:\n{state['analysis'][:1500]}\n\n"
        f"Verified Notes & URLs:\n{state['fact_check_result'][:800]}\n\n"
        "Format with: # Title, ## Executive Summary, ## Key Findings & Architecture, "
        "## Strategic Insights & Challenges, and ## References (with URLs)."
    )
    report = _run_with_timeout(_invoke_groq_safe, prompt, 0.3, 1200, timeout_sec=120)
    print("[GRAPH] writer_node finished.", flush=True)
    return {"final_report": report}


def should_retry(state: ResearchState) -> str:
    if state.get("confidence_score") == "LOW" and state.get("retry_count", 0) < 2:
        return "researcher"
    return "analyst"


def build_research_graph():
    workflow = StateGraph(ResearchState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("fact_checker", fact_checker_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("writer", writer_node)

    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "researcher")
    workflow.add_edge("researcher", "fact_checker")
    workflow.add_conditional_edges(
        "fact_checker",
        should_retry,
        {
            "researcher": "researcher",
            "analyst": "analyst",
        },
    )
    workflow.add_edge("analyst", "writer")
    workflow.add_edge("writer", END)

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory, interrupt_before=["researcher"])