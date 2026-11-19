from __future__ import annotations

import re
import base64
from dataclasses import dataclass
from typing import Optional, Tuple, List
from github import Github, GithubException
from config import GITHUB_TOKEN, MAX_FILE_CHARS


@dataclass
class PRFile:
    filename: str
    status: str
    patch: Optional[str]
    content: Optional[str]
    additions: int
    deletions: int


def parse_pr_url(pr_url: str) -> Tuple[str, str, int]:
    """Extract owner, repo, and PR number from a GitHub PR URL."""
    pattern = r"github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.search(pattern, pr_url)
    if not match:
        raise ValueError(f"Invalid GitHub PR URL: {pr_url}")
    owner, repo, pr_number = match.groups()
    return owner, repo, int(pr_number)


def fetch_pr_files(pr_url: str) -> Tuple[str, str, List[PRFile]]:
    """
    Fetch changed .cs files and their diffs for a given PR URL.
    Returns (pr_title, pr_description, list[PRFile]).
    """
    gh = Github(GITHUB_TOKEN) if GITHUB_TOKEN else Github()
    owner, repo_name, pr_number = parse_pr_url(pr_url)

    try:
        repo = gh.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(pr_number)
        files = pr.get_files()
    except GithubException as e:
        raise RuntimeError(f"GitHub API error: {e.status} {e.data}") from e

    pr_files: List[PRFile] = []
    for f in files:
        if f.status == "removed":
            continue
        if not f.filename.endswith((".cs", ".csproj")):
            continue

        content = None
        if f.status in ("added", "modified", "renamed"):
            try:
                file_obj = repo.get_contents(f.filename, ref=pr.head.sha)
                raw = base64.b64decode(file_obj.content).decode("utf-8", errors="replace")
                content = raw[:MAX_FILE_CHARS]
                if len(raw) > MAX_FILE_CHARS:
                    content += f"\n\n... [truncated at {MAX_FILE_CHARS} chars] ..."
            except GithubException:
                content = None

        pr_files.append(PRFile(
            filename=f.filename,
            status=f.status,
            patch=f.patch,
            content=content,
            additions=f.additions,
            deletions=f.deletions,
        ))

    return pr.title, pr.body or "", pr_files


def fetch_repo_files(repo_url: str, branch: str = "") -> Tuple[str, str, List[PRFile]]:
    """
    Fetch all .cs/.csproj files from a repository branch for a full repo review.
    Returns (title, description, list[PRFile]) — files are treated as 'added'.
    """
    pattern = r"github\.com/([^/]+)/([^/]+)"
    match = re.search(pattern, repo_url)
    if not match:
        raise ValueError(f"Invalid GitHub repository URL: {repo_url}")
    owner, repo_name = match.groups()
    repo_name = repo_name.rstrip("/")

    gh = Github(GITHUB_TOKEN) if GITHUB_TOKEN else Github()
    try:
        repo = gh.get_repo(f"{owner}/{repo_name}")
    except GithubException as e:
        raise RuntimeError(f"GitHub API error: {e.status} {e.data}") from e

    ref = branch or repo.default_branch
    title = f"{owner}/{repo_name} @ {ref}"
    description = f"Full repository review of branch `{ref}`"

    # Walk the tree recursively — single API call, much faster than traversing dirs
    try:
        tree = repo.get_git_tree(ref, recursive=True)
    except GithubException as e:
        raise RuntimeError(f"Could not read repository tree: {e.status} {e.data}") from e

    cs_paths = [
        item.path for item in tree.tree
        if item.type == "blob" and item.path.endswith((".cs", ".csproj"))
    ]

    pr_files: List[PRFile] = []
    for path in cs_paths:
        content = None
        try:
            file_obj = repo.get_contents(path, ref=ref)
            raw = base64.b64decode(file_obj.content).decode("utf-8", errors="replace")
            content = raw[:MAX_FILE_CHARS]
            if len(raw) > MAX_FILE_CHARS:
                content += f"\n\n... [truncated at {MAX_FILE_CHARS} chars] ..."
        except GithubException:
            content = None

        pr_files.append(PRFile(
            filename=path,
            status="added",
            patch=None,         # no diff in repo mode — full content is available
            content=content,
            additions=0,
            deletions=0,
        ))

    return title, description, pr_files


def post_pr_review(pr_url: str, reviews: List[dict], missing_tests: dict) -> str:
    """
    Post a structured review comment to the GitHub PR.
    Uses COMMENT event so the agent never blocks a merge — human decides.
    Returns the URL of the created review.
    """
    gh = Github(GITHUB_TOKEN)
    owner, repo_name, pr_number = parse_pr_url(pr_url)
    repo = gh.get_repo(f"{owner}/{repo_name}")
    pr = repo.get_pull(pr_number)

    body = _build_review_body(reviews, missing_tests)
    review = pr.create_review(body=body, event="COMMENT")
    return review.html_url


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_SEVERITY_EMOJI = {"CRITICAL": "🔴", "WARNING": "🟡", "SUGGESTION": "🔵"}
_CATEGORY_LABEL = {
    "FORMATTING":     "📐 Formatting",
    "BEST_PRACTICES": "⚙️ Best Practices",
    "SOLID":          "🧱 SOLID",
    "CLEAN_CODE_DRY": "🧹 Clean Code / DRY",
    "UNIT_TESTS":     "🧪 Unit Tests",
}


def _build_review_body(reviews: List[dict], missing_tests: dict) -> str:
    sections: List[str] = ["# 🤖 AI Code Review\n"]

    for review in reviews:
        filename = review.get("filename", "unknown")
        summary = review.get("summary", "")
        findings = review.get("findings", [])
        scores = review.get("score", {})
        test_info = review.get("test_coverage_assessment", {})

        sections.append(f"## `{filename}`")
        sections.append(f"> {summary}\n")

        # Score table
        if scores:
            sections.append("| Category | Score |")
            sections.append("|---|:---:|")
            for key, label in [
                ("formatting",     "📐 Formatting"),
                ("best_practices", "⚙️ Best Practices"),
                ("solid",          "🧱 SOLID"),
                ("clean_code_dry", "🧹 Clean Code / DRY"),
                ("unit_tests",     "🧪 Unit Tests"),
            ]:
                val = scores.get(key, "N/A")
                badge = f"**{val}/10**" if isinstance(val, int) else str(val)
                sections.append(f"| {label} | {badge} |")
            sections.append("")

        # Test coverage badge
        if test_info:
            cov_ok = test_info.get("coverage_ok")
            badge = "✅ Coverage OK" if cov_ok is True else "❌ Below 85% threshold" if cov_ok is False else "Coverage unknown"
            est = test_info.get("estimated_coverage", "")
            notes = test_info.get("notes", "")
            sections.append(f"**Coverage:** {badge} {est}  \n{notes}\n")

        if not findings:
            sections.append("✅ No issues found.\n")
            continue

        for f in findings:
            sev = f.get("severity", "SUGGESTION")
            cat = f.get("category", "")
            icon = _SEVERITY_EMOJI.get(sev, "⚪")
            cat_label = _CATEGORY_LABEL.get(cat, cat)
            line_ref = f" — line {f['line']}" if f.get("line") else ""

            sections.append(f"### {icon} {f.get('title', '')}")
            sections.append(f"**{sev}** · {cat_label}{line_ref}  ")
            sections.append(f"**Finding:** {f.get('description', '')}  ")
            sections.append(f"**Suggested fix:** {f.get('suggestion', '')}  ")
            sections.append("")

    # Missing tests — advisory only, human decides
    missing = missing_tests.get("missing_tests", [])
    if missing:
        sections.append("---")
        sections.append("## ⚠️ Missing Test Coverage\n")
        sections.append(
            "> The following scenarios have no test coverage. "
            "**Human reviewer: please assess whether tests are required before merging.**\n"
        )
        sections.append("| File | Scenario | Why it matters |")
        sections.append("|---|---|---|")
        for item in missing:
            sections.append(
                f"| `{item.get('file', '')}` | {item.get('scenario', '')} | {item.get('reason', '')} |"
            )
        sections.append("")

    sections.append("---")
    sections.append(
        "*This review was generated by an AI agent. "
        "All findings are advisory — a human reviewer makes the final merge decision.*"
    )
    return "\n".join(sections)
