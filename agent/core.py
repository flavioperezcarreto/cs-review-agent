import json
import concurrent.futures
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from agent.state import ReviewState
from tools.github_tool import fetch_pr_files, fetch_repo_files, post_pr_review
from prompts.review_prompts import SYSTEM_PROMPT, FILE_REVIEW_PROMPT, NO_TESTS_PROMPT
from config import MODEL_NAME, POST_GITHUB_REVIEW, PORTKEY_API_KEY, PORTKEY_BASE_URL


llm = ChatOpenAI(
    model=MODEL_NAME,
    base_url=PORTKEY_BASE_URL,
    api_key=PORTKEY_API_KEY,
    temperature=0,
    default_headers={"Authorization": f"Bearer {PORTKEY_API_KEY}"},
)

_TEST_SUFFIXES = ("Test.cs", "Tests.cs", "Spec.cs")


# ---------------------------------------------------------------------------
# LLM call with retry
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _invoke_llm(messages: list) -> str:
    response = llm.invoke(messages)
    return response.content.strip()


def _strip_fences(raw: str) -> str:
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")]
    return raw.strip()


def _safe_parse(raw: str, fallback: dict) -> dict:
    cleaned = _strip_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {**fallback, "raw_response": cleaned}


def _normalize_scores(review: dict) -> dict:
    """Clamp all score values to 0–10; replace missing keys with 0."""
    scores = review.get("score", {})
    keys = ["formatting", "best_practices", "solid", "clean_code_dry", "unit_tests"]
    review["score"] = {
        k: max(0, min(10, int(scores[k]))) if isinstance(scores.get(k), (int, float)) else 0
        for k in keys
    }
    return review


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def fetch_pr(state: ReviewState) -> ReviewState:
    try:
        if state.repo_url:
            title, description, files = fetch_repo_files(state.repo_url, state.branch)
            state.pr_title = title
            state.pr_description = description
            state.files = files
        else:
            title, description, files = fetch_pr_files(state.pr_url)
            state.pr_title = title
            state.pr_description = description
            state.files = files
    except Exception as e:
        state.error = str(e)
    return state


def _review_single_file(f) -> dict:
    """Review one file; runs in a thread pool worker."""
    prompt = FILE_REVIEW_PROMPT.format(
        filename=f.filename,
        status=f.status,
        patch=f.patch or "(no diff available)",
        content=f.content or "(full content unavailable — reviewing diff only)",
    )
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]
    try:
        raw = _invoke_llm(messages)
    except Exception as e:
        return {
            "filename": f.filename,
            "summary": f"Review failed after retries: {e}",
            "findings": [],
            "score": {},
            "test_coverage_assessment": {},
        }

    review = _safe_parse(raw, {"filename": f.filename, "summary": "Could not parse model response.", "findings": []})
    return _normalize_scores(review)


def review_files(state: ReviewState) -> ReviewState:
    if state.error or not state.files:
        return state

    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = list(executor.map(_review_single_file, state.files))

    state.reviews = results
    return state


def check_missing_tests(state: ReviewState) -> ReviewState:
    if state.error or not state.reviews:
        return state

    production_files = [
        r["filename"] for r in state.reviews
        if not r["filename"].endswith(_TEST_SUFFIXES)
        and not r["filename"].endswith(".csproj")
    ]
    test_files = [
        r["filename"] for r in state.reviews
        if r["filename"].endswith(_TEST_SUFFIXES)
    ]

    # Flag production files that have no corresponding test file in the PR
    uncovered = [
        pf for pf in production_files
        if not any(pf.replace(".cs", "") in tf for tf in test_files)
    ]

    if uncovered:
        prompt = NO_TESTS_PROMPT.format(filenames="\n".join(uncovered))
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        try:
            raw = _invoke_llm(messages)
        except Exception as e:
            state.missing_tests = {"error": str(e)}
            return state

        state.missing_tests = _safe_parse(raw, {})

    return state


def post_review(state: ReviewState) -> ReviewState:
    if state.error or not state.reviews or not POST_GITHUB_REVIEW:
        return state
    if state.repo_url:
        # Repo mode has no PR to post to — console report only
        return state
    try:
        url = post_pr_review(state.pr_url, state.reviews, state.missing_tests)
        state.post_review_url = url
    except Exception as e:
        state.post_review_url = f"ERROR: {e}"
    return state


def should_abort(state: ReviewState) -> str:
    return "abort" if state.error else "review"


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_agent():
    graph = StateGraph(ReviewState)

    graph.add_node("fetch_pr", fetch_pr)
    graph.add_node("review_files", review_files)
    graph.add_node("check_missing_tests", check_missing_tests)
    graph.add_node("post_review", post_review)

    graph.set_entry_point("fetch_pr")
    graph.add_conditional_edges(
        "fetch_pr",
        should_abort,
        {"review": "review_files", "abort": END},
    )
    graph.add_edge("review_files", "check_missing_tests")
    graph.add_edge("check_missing_tests", "post_review")
    graph.add_edge("post_review", END)

    return graph.compile()
