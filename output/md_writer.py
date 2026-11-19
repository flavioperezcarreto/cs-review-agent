"""
Markdown report writer.

Produces a single .md file with:
- Table of contents (one anchor per file)
- Per-file section with score table, findings, test coverage
- Summary and missing-test advisory
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from agent.state import ReviewState

SEVERITY_ICON = {"CRITICAL": "🔴", "WARNING": "🟡", "SUGGESTION": "🔵"}
SEVERITY_BADGE = {
    "CRITICAL":   "![CRITICAL](https://img.shields.io/badge/CRITICAL-red)",
    "WARNING":    "![WARNING](https://img.shields.io/badge/WARNING-yellow)",
    "SUGGESTION": "![SUGGESTION](https://img.shields.io/badge/SUGGESTION-blue)",
}
CATEGORY_LABEL = {
    "FORMATTING":     "📐 Formatting",
    "BEST_PRACTICES": "⚙️ Best Practices",
    "SOLID":          "🧱 SOLID",
    "CLEAN_CODE_DRY": "🧹 Clean Code / DRY",
    "UNIT_TESTS":     "🧪 Unit Tests",
}
SCORE_KEYS = [
    ("formatting",     "📐 Formatting"),
    ("best_practices", "⚙️ Best Practices"),
    ("solid",          "🧱 SOLID"),
    ("clean_code_dry", "🧹 Clean Code / DRY"),
    ("unit_tests",     "🧪 Unit Tests"),
]


def _slug(text: str) -> str:
    """GitHub-compatible heading anchor slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text)
    return text


def _score_bar(val: int, out_of: int = 10) -> str:
    filled = round(val * 10 / out_of)
    return "█" * filled + "░" * (10 - filled) + f" {val}/{out_of}"


def write_md(state: ReviewState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    title = state.pr_title or state.repo_url or state.pr_url

    lines += [
        f"# 🤖 AI Code Review — {title}",
        "",
    ]
    if state.pr_url:
        lines.append(f"> **PR:** {state.pr_url}  ")
    if state.repo_url:
        branch_note = f" (branch: `{state.branch}`)" if state.branch else ""
        lines.append(f"> **Repo:** {state.repo_url}{branch_note}  ")
    lines.append("")

    if state.error:
        lines += [f"> ⛔ **Error:** {state.error}", ""]
        _write(path, lines)
        return

    if not state.reviews:
        lines += ["> ⚠️ No reviewable C# files found.", ""]
        _write(path, lines)
        return

    all_findings = [f for r in state.reviews for f in r.get("findings", [])]
    criticals   = sum(1 for f in all_findings if f.get("severity") == "CRITICAL")
    warnings    = sum(1 for f in all_findings if f.get("severity") == "WARNING")
    suggestions = sum(1 for f in all_findings if f.get("severity") == "SUGGESTION")

    lines += [
        "## 📊 Summary",
        "",
        f"| Files | 🔴 Critical | 🟡 Warnings | 🔵 Suggestions |",
        f"|------:|------------:|------------:|---------------:|",
        f"| {len(state.reviews)} | {criticals} | {warnings} | {suggestions} |",
        "",
    ]

    # Table of contents
    lines += ["## 📁 Files Reviewed", ""]
    for review in state.reviews:
        fname = review.get("filename", "unknown")
        slug = _slug(fname)
        file_findings = review.get("findings", [])
        fc = sum(1 for f in file_findings if f.get("severity") == "CRITICAL")
        fw = sum(1 for f in file_findings if f.get("severity") == "WARNING")
        fs = sum(1 for f in file_findings if f.get("severity") == "SUGGESTION")
        badges = []
        if fc: badges.append(f"🔴 {fc}")
        if fw: badges.append(f"🟡 {fw}")
        if fs: badges.append(f"🔵 {fs}")
        badge_str = " · ".join(badges) if badges else "✅ clean"
        lines.append(f"- [{fname}](#{slug}) — {badge_str}")
    lines.append("")

    # Per-file sections
    lines.append("---")
    lines.append("")
    for review in state.reviews:
        fname    = review.get("filename", "unknown")
        summary  = review.get("summary", "")
        findings = review.get("findings", [])
        scores   = review.get("score", {})
        test_info = review.get("test_coverage_assessment", {})

        lines += [f"## {fname}", ""]
        if summary:
            lines += [f"_{summary}_", ""]

        if scores:
            lines += [
                "### Scores",
                "",
                "| Category | Score | Bar |",
                "|----------|------:|-----|",
            ]
            for key, label in SCORE_KEYS:
                val = scores.get(key, "N/A")
                bar = _score_bar(val) if isinstance(val, int) else "N/A"
                lines.append(f"| {label} | {val}/10 | `{bar}` |")
            lines.append("")

        if test_info:
            cov_ok = test_info.get("coverage_ok")
            badge = "✅ Coverage OK" if cov_ok is True else \
                    "❌ Below 85% threshold" if cov_ok is False else "⚠️ Coverage unknown"
            est   = test_info.get("estimated_coverage", "")
            notes = test_info.get("notes", "")
            lines += [
                "### Test Coverage",
                "",
                f"**{badge}**" + (f"  •  {est}" if est else "") + (f"  \n{notes}" if notes else ""),
                "",
            ]

        if not findings:
            lines += ["### Findings", "", "✅ No issues found.", ""]
        else:
            lines += ["### Findings", "", "| # | Severity | Category | Line | Title |", "|---|----------|----------|------|-------|"]
            for i, f in enumerate(findings, 1):
                sev      = f.get("severity", "SUGGESTION")
                cat      = CATEGORY_LABEL.get(f.get("category", ""), f.get("category", ""))
                icon     = SEVERITY_ICON.get(sev, "⚪")
                line_no  = f.get("line", "—")
                title    = f.get("title", "")
                lines.append(f"| {i} | {icon} {sev} | {cat} | {line_no} | {title} |")
            lines.append("")

            # Detail blocks
            for i, f in enumerate(findings, 1):
                sev     = f.get("severity", "SUGGESTION")
                icon    = SEVERITY_ICON.get(sev, "⚪")
                title   = f.get("title", "")
                desc    = f.get("description", "")
                suggest = f.get("suggestion", "")
                line_no = f.get("line")
                lines += [
                    f"#### {i}. {icon} {title}",
                    "",
                ]
                if line_no:
                    lines.append(f"**Line:** `{line_no}`  ")
                lines += [
                    f"**Severity:** {sev}  ",
                    f"**Category:** {CATEGORY_LABEL.get(f.get('category',''), f.get('category',''))}",
                    "",
                    desc,
                    "",
                    f"> 💡 **Suggestion:** {suggest}",
                    "",
                ]

        lines += ["---", ""]

    # Missing tests advisory
    missing = state.missing_tests.get("missing_tests", [])
    if missing:
        lines += [
            "## ⚠️ Missing Test Coverage Advisory",
            "",
            "> These findings are advisory — a human reviewer should make the final decision.",
            "",
            "| File | Scenario | Reason |",
            "|------|----------|--------|",
        ]
        for item in missing:
            f   = item.get("file", "").replace("|", "\\|")
            sc  = item.get("scenario", "").replace("|", "\\|")
            rsn = item.get("reason", "").replace("|", "\\|")
            lines.append(f"| `{f}` | {sc} | {rsn} |")
        lines.append("")

    if state.post_review_url:
        if state.post_review_url.startswith("ERROR:"):
            lines += [f"> ⚠️ Could not post GitHub review: {state.post_review_url}", ""]
        else:
            lines += [f"> ✅ Review posted to GitHub: {state.post_review_url}", ""]

    _write(path, lines)
    print(f"  📄 Markdown report saved: {path}")


def _write(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines), encoding="utf-8")
