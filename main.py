#!/usr/bin/env python3
"""
C# Code Review Agent

Usage:
    # Review a pull request
    python main.py https://github.com/owner/repo/pull/42

    # Review an entire repository branch
    python main.py --repo https://github.com/owner/repo
    python main.py --repo https://github.com/owner/repo --branch develop

    # Output options  (can combine with comma or repeat the flag)
    python main.py --repo URL --output console,md,html
    python main.py --repo URL --output md --output html
    python main.py --repo URL --output html --out-dir ./reports
"""
import sys
import argparse
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from agent.core import build_agent
from agent.state import ReviewState
from output.console import print_report

VALID_OUTPUTS = {"console", "md", "html"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI-powered C# code review agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("pr_url", nargs="?", metavar="PR_URL",
                       help="GitHub pull request URL to review")
    group.add_argument("--repo", metavar="REPO_URL",
                       help="GitHub repository URL for a full branch review")
    parser.add_argument("--branch", metavar="BRANCH", default="",
                        help="Branch to review (default: repo default branch). Only used with --repo.")
    parser.add_argument(
        "--output", "-o", metavar="FORMAT", action="append", default=[],
        help=(
            "Output format(s): console, md, html. "
            "Repeat or comma-separate for multiple. "
            "Default: console. "
            "Example: --output md,html"
        ),
    )
    parser.add_argument(
        "--out-dir", metavar="DIR", default=".",
        help="Directory for file outputs (md/html). Default: current directory.",
    )
    return parser.parse_args()


def _resolve_outputs(raw: list[str]) -> set[str]:
    """Flatten comma-separated values and validate."""
    outputs: set[str] = set()
    for token in raw:
        for part in token.split(","):
            part = part.strip().lower()
            if part not in VALID_OUTPUTS:
                print(f"⚠️  Unknown output format '{part}' — ignored. Valid: {', '.join(sorted(VALID_OUTPUTS))}")
            else:
                outputs.add(part)
    return outputs or {"console"}


def _stem(state: ReviewState) -> str:
    """Safe filename stem from the reviewed target."""
    import re
    target = state.repo_url or state.pr_url or "review"
    # keep only alphanumeric + dash/dot, strip leading slashes
    stem = re.sub(r"https?://", "", target)
    stem = re.sub(r"[^\w.\-]", "_", stem)
    stem = stem.strip("_").strip(".")
    return stem[:80] or "review"


def main() -> None:
    args = parse_args()
    outputs = _resolve_outputs(args.output)
    out_dir = Path(args.out_dir)

    agent = build_agent()

    if args.repo:
        branch_label = f" ({args.branch})" if args.branch else ""
        print(f"\n🔍 Reviewing repository: {args.repo}{branch_label}")
        print("⏳ Fetching all C# files and running AI review (may take a minute)...\n")
        state = ReviewState(repo_url=args.repo, branch=args.branch)
    else:
        print(f"\n🔍 Reviewing PR: {args.pr_url}")
        print("⏳ Running AI code review (this may take 30–60 seconds)...\n")
        state = ReviewState(pr_url=args.pr_url)

    final_state_raw = agent.invoke(state)
    # LangGraph returns a dict — reconstruct the dataclass for the report
    if isinstance(final_state_raw, dict):
        final_state = ReviewState(**{k: v for k, v in final_state_raw.items() if k in ReviewState.__dataclass_fields__})
    else:
        final_state = final_state_raw

    # Always print to console
    print_report(final_state)

    # File outputs
    if "md" in outputs or "html" in outputs:
        stem = _stem(final_state)
        print()  # blank line before file-save messages

    if "md" in outputs:
        from output.md_writer import write_md
        write_md(final_state, out_dir / f"{stem}.md")

    if "html" in outputs:
        from output.html_writer import write_html
        write_html(final_state, out_dir / f"{stem}.html")


if __name__ == "__main__":
    main()
