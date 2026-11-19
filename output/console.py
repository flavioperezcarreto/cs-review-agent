from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from agent.state import ReviewState

console = Console()

SEVERITY_STYLE = {
    "CRITICAL":   ("red",    "🔴"),
    "WARNING":    ("yellow", "🟡"),
    "SUGGESTION": ("blue",   "🔵"),
}

CATEGORY_LABEL = {
    "FORMATTING":     "📐 Formatting",
    "BEST_PRACTICES": "⚙️  Best Practices",
    "SOLID":          "🧱 SOLID",
    "CLEAN_CODE_DRY": "🧹 Clean Code / DRY",
    "UNIT_TESTS":     "🧪 Unit Tests",
}


def print_report(state: ReviewState) -> None:
    console.print()
    console.rule(f"[bold cyan]AI Code Review — {state.pr_title}[/bold cyan]")
    console.print(f"[dim]PR:[/dim] {state.pr_url}\n")

    if state.error:
        console.print(Panel(f"[red]{state.error}[/red]", title="Error"))
        return

    if not state.reviews:
        console.print("[yellow]No reviewable C# files found in this PR.[/yellow]")
        return

    for review in state.reviews:
        filename  = review.get("filename", "unknown")
        summary   = review.get("summary", "")
        findings  = review.get("findings", [])
        scores    = review.get("score", {})
        test_info = review.get("test_coverage_assessment", {})

        console.print(Panel(
            f"[bold]{filename}[/bold]\n[dim]{summary}[/dim]",
            style="cyan", box=box.ROUNDED,
        ))

        if scores:
            tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold magenta")
            tbl.add_column("Category")
            tbl.add_column("Score", justify="center")
            for key, label in [
                ("formatting",     "📐 Formatting"),
                ("best_practices", "⚙️  Best Practices"),
                ("solid",          "🧱 SOLID"),
                ("clean_code_dry", "🧹 Clean Code / DRY"),
                ("unit_tests",     "🧪 Unit Tests"),
            ]:
                val = scores.get(key, "N/A")
                colour = "green"  if isinstance(val, int) and val >= 8 else \
                         "yellow" if isinstance(val, int) and val >= 5 else "red"
                tbl.add_row(label, f"[{colour}]{val}/10[/{colour}]")
            console.print(tbl)

        if test_info:
            cov_ok = test_info.get("coverage_ok")
            badge = "[green]✅ Coverage OK[/green]"          if cov_ok is True  else \
                    "[red]❌ Below 85% threshold[/red]"       if cov_ok is False else \
                    "[dim]Coverage unknown[/dim]"
            console.print(
                f"  {badge}  [dim]{test_info.get('estimated_coverage', '')}[/dim]  "
                f"{test_info.get('notes', '')}\n"
            )

        if not findings:
            console.print("  [green]✅ No issues found.[/green]\n")
            continue

        for f in findings:
            sev        = f.get("severity", "SUGGESTION")
            cat        = f.get("category", "")
            style, icon = SEVERITY_STYLE.get(sev, ("white", "⚪"))
            line_info  = f"  line {f['line']}" if f.get("line") else ""
            cat_label  = CATEGORY_LABEL.get(cat, cat)

            t = Text()
            t.append(f"{icon} [{sev}]", style=f"bold {style}")
            t.append(f"  {cat_label}{line_info}", style="dim")
            console.print(t)
            console.print(f"  [bold]{f.get('title', '')}[/bold]")
            console.print(f"  {f.get('description', '')}")
            console.print(f"  [italic cyan]Suggestion:[/italic cyan] {f.get('suggestion', '')}")
            console.print()

    missing = state.missing_tests.get("missing_tests", [])
    if missing:
        console.rule("[bold yellow]⚠️  Missing Test Coverage[/bold yellow]")
        for item in missing:
            console.print(f"  [yellow]•[/yellow] [bold]{item.get('file', '')}[/bold]")
            console.print(f"    Scenario : {item.get('scenario', '')}")
            console.print(f"    Reason   : {item.get('reason', '')}\n")

    all_findings = [f for r in state.reviews for f in r.get("findings", [])]
    criticals   = sum(1 for f in all_findings if f.get("severity") == "CRITICAL")
    warnings    = sum(1 for f in all_findings if f.get("severity") == "WARNING")
    suggestions = sum(1 for f in all_findings if f.get("severity") == "SUGGESTION")

    console.rule("[bold]Summary[/bold]")
    console.print(
        f"  Files reviewed : [bold]{len(state.reviews)}[/bold]  |  "
        f"[red]🔴 Critical: {criticals}[/red]  |  "
        f"[yellow]🟡 Warnings: {warnings}[/yellow]  |  "
        f"[blue]🔵 Suggestions: {suggestions}[/blue]"
    )

    if state.post_review_url:
        if state.post_review_url.startswith("ERROR:"):
            console.print(f"\n  [red]⚠️  Could not post GitHub review: {state.post_review_url}[/red]")
        else:
            console.print(f"\n  [green]✅ Review posted to GitHub:[/green] {state.post_review_url}")

    console.print()
