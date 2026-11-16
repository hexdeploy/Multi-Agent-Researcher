import os
from dotenv import load_dotenv
from crewai import Agent, LLM

load_dotenv(override=True)


def get_groq_llm(temperature: float = 0.2) -> LLM:
    load_dotenv(override=True)
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is missing in your .env file.")

    model_name = os.getenv("GROQ_MODEL_NAME", "groq/openai/gpt-oss-20b")

    return LLM(
        model=model_name,
        api_key=api_key,
        temperature=temperature,
        max_tokens=1000,
        num_retries=3,
    )


def create_researcher_agent() -> Agent:
    return Agent(
        role="Senior Multi-Source Researcher",
        goal=(
            "Extract concise, concrete facts, metrics, and source URLs on '{topic}' "
            "from the gathered multi-source search results."
        ),
        backstory=(
            "You are an investigative research specialist skilled at distilling raw search "
            "dumps into dense, accurate bullet points with URLs."
        ),
        llm=get_groq_llm(temperature=0.1),
        verbose=True,
        allow_delegation=False,
        max_iter=1,
    )


def create_fact_checker_agent() -> Agent:
    return Agent(
        role="Rigorous Fact-Checker & Verification Auditor",
        goal=(
            "Cross-verify claims on '{topic}' across the provided sources and assign "
            "an objective confidence rating."
        ),
        backstory=(
            "You are a skeptical editorial fact-checker who verifies consistency across sources."
        ),
        llm=get_groq_llm(temperature=0.1),
        verbose=True,
        allow_delegation=False,
        max_iter=1,
    )


def create_analyst_agent() -> Agent:
    return Agent(
        role="Strategic Research Analyst",
        goal=(
            "Synthesize verified facts on '{topic}' into core trends, comparisons, "
            "and strategic insights."
        ),
        backstory=(
            "You are a principal intelligence analyst who turns verified evidence into structured clarity."
        ),
        llm=get_groq_llm(temperature=0.2),
        verbose=True,
        allow_delegation=False,
        max_iter=1,
    )


def create_writer_agent() -> Agent:
    return Agent(
        role="Technical Research Report Writer",
        goal=(
            "Produce a clear, publication-ready Markdown research report on '{topic}' with "
            "structured sections, inline citations, and a References list."
        ),
        backstory=(
            "You are an expert technical writer who crafts readable reports backed by verified URLs."
        ),
        llm=get_groq_llm(temperature=0.3),
        verbose=True,
        allow_delegation=False,
        max_iter=1,
    )