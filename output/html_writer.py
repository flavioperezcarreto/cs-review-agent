"""
HTML report writer.

Produces a single self-contained .html file with:
- Inline CSS (no external dependencies)
- Fixed sidebar navigation with anchors per file
- Collapsible finding cards
- Summary banner
- Full-text search bar (JS, no library)
"""
from __future__ import annotations

import re
import html as htmllib
from pathlib import Path
from datetime import datetime, timezone

from agent.state import ReviewState

SEVERITY_COLOR = {
    "CRITICAL":   ("#c0392b", "#fdf0ef"),
    "WARNING":    ("#d68910", "#fefdf0"),
    "SUGGESTION": ("#1a6fa8", "#f0f5fd"),
}
SEVERITY_ICON = {"CRITICAL": "🔴", "WARNING": "🟡", "SUGGESTION": "🔵"}

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


def _e(text: str) -> str:
    return htmllib.escape(str(text))


def _slug(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text)
    return text


def _score_color(val: int) -> str:
    if val >= 8: return "#27ae60"
    if val >= 5: return "#d68910"
    return "#c0392b"


def _score_bar_html(val: int) -> str:
    pct = val * 10
    color = _score_color(val)
    return (
        f'<div class="score-bar-track">'
        f'<div class="score-bar-fill" style="width:{pct}%;background:{color}"></div>'
        f'</div>'
        f'<span class="score-label" style="color:{color}">{val}/10</span>'
    )


CSS = """
:root {
  --bg: #f8f9fa; --surface: #ffffff; --border: #dee2e6;
  --text: #212529; --muted: #6c757d;
  --primary: #0d6efd; --sidebar-w: 280px;
  --radius: 6px; --shadow: 0 1px 3px rgba(0,0,0,.1);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       font-size: 14px; color: var(--text); background: var(--bg);
       display: flex; min-height: 100vh; }

/* Sidebar */
#sidebar {
  width: var(--sidebar-w); min-height: 100vh; background: #1e2432;
  color: #c9d1d9; position: fixed; top: 0; left: 0; overflow-y: auto;
  padding: 0 0 40px; z-index: 100;
}
#sidebar h2 { font-size: 11px; text-transform: uppercase; letter-spacing: .1em;
              color: #8b949e; padding: 20px 16px 8px; }
#sidebar .toc-link {
  display: block; padding: 6px 16px; color: #c9d1d9; text-decoration: none;
  font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  border-left: 3px solid transparent; transition: all .15s;
}
#sidebar .toc-link:hover, #sidebar .toc-link.active {
  background: #262d3d; color: #fff; border-left-color: var(--primary);
}
#sidebar .toc-badge { float: right; font-size: 10px; }
#sidebar-header { padding: 16px; border-bottom: 1px solid #30363d; }
#sidebar-header h1 { font-size: 13px; color: #fff; }
#sidebar-header p  { font-size: 11px; color: #8b949e; margin-top: 4px; }

/* Main */
#main { margin-left: var(--sidebar-w); padding: 32px 40px; flex: 1; max-width: 960px; }

/* Search */
#search-wrap { margin-bottom: 24px; }
#search { width: 100%; padding: 10px 14px; border: 1px solid var(--border);
          border-radius: var(--radius); font-size: 14px; background: var(--surface); }

/* Summary banner */
.summary-banner { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 32px; }
.stat-card { flex: 1; min-width: 120px; background: var(--surface);
             border: 1px solid var(--border); border-radius: var(--radius);
             padding: 16px; text-align: center; box-shadow: var(--shadow); }
.stat-card .num { font-size: 32px; font-weight: 700; }
.stat-card .lbl { font-size: 12px; color: var(--muted); margin-top: 4px; }

/* File section */
.file-section { background: var(--surface); border: 1px solid var(--border);
                border-radius: var(--radius); margin-bottom: 32px;
                box-shadow: var(--shadow); overflow: hidden; }
.file-header { padding: 14px 20px; background: #f1f3f5; border-bottom: 1px solid var(--border);
               display: flex; justify-content: space-between; align-items: center; }
.file-name { font-family: 'SFMono-Regular', Consolas, monospace; font-size: 13px; font-weight: 600; }
.file-badges { display: flex; gap: 6px; }
.badge { padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; color: #fff; }
.badge.crit { background: #c0392b; }
.badge.warn { background: #d68910; }
.badge.sugg { background: #1a6fa8; }

.file-body { padding: 20px; }
.summary-text { color: var(--muted); font-style: italic; margin-bottom: 16px; }

/* Scores */
.scores-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
               gap: 10px; margin-bottom: 20px; }
.score-item { display: flex; flex-direction: column; gap: 4px; }
.score-item .cat-name { font-size: 12px; color: var(--muted); }
.score-bar-track { height: 6px; background: #e9ecef; border-radius: 3px; }
.score-bar-fill  { height: 100%; border-radius: 3px; }
.score-label { font-size: 12px; font-weight: 600; }

/* Finding card */
.finding-card { border: 1px solid var(--border); border-radius: var(--radius);
                margin-bottom: 10px; overflow: hidden; }
.finding-card summary { list-style: none; cursor: pointer; padding: 10px 14px;
                        display: flex; gap: 10px; align-items: center;
                        user-select: none; }
.finding-card summary::-webkit-details-marker { display: none; }
.finding-card summary .toggle-icon { margin-left: auto; color: var(--muted); font-size: 12px; }
.finding-body { padding: 12px 16px; border-top: 1px solid var(--border);
                background: #fafbfc; font-size: 13px; line-height: 1.6; }
.finding-body .suggestion { margin-top: 8px; padding: 8px 12px;
                            background: #e8f4fd; border-left: 3px solid var(--primary);
                            border-radius: 0 var(--radius) var(--radius) 0; }
.sev-label { font-size: 11px; font-weight: 700; padding: 2px 6px;
             border-radius: 3px; color: #fff; }
.cat-pill  { font-size: 11px; color: var(--muted); background: #e9ecef;
             padding: 2px 7px; border-radius: 10px; }
.line-pill  { font-size: 11px; color: var(--muted); font-family: monospace; }

/* Missing tests */
.advisory { background: #fff8e1; border: 1px solid #ffe082;
            border-radius: var(--radius); padding: 20px; margin-bottom: 32px; }
.advisory h3 { margin-bottom: 12px; }
.advisory table { width: 100%; border-collapse: collapse; font-size: 13px; }
.advisory th { text-align: left; padding: 6px 10px; background: #fff3cd;
               border-bottom: 2px solid #ffe082; }
.advisory td { padding: 6px 10px; border-bottom: 1px solid #ffe082; vertical-align: top; }

/* Utility */
.clean-badge { color: #27ae60; font-size: 13px; padding: 10px 0; }
h2.section-title { font-size: 20px; margin-bottom: 16px; }
.meta { font-size: 12px; color: var(--muted); margin-bottom: 24px; }
.meta a { color: var(--primary); }
.hidden { display: none !important; }
"""

JS = """
// Live search
const searchInput = document.getElementById('search');
searchInput.addEventListener('input', () => {
  const q = searchInput.value.toLowerCase();
  document.querySelectorAll('.file-section').forEach(sec => {
    const text = sec.textContent.toLowerCase();
    sec.classList.toggle('hidden', q.length > 1 && !text.includes(q));
  });
});

// Sidebar active state on scroll
const sections = document.querySelectorAll('.file-section[id]');
const links    = document.querySelectorAll('.toc-link[href^="#"]');
const observer = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      links.forEach(l => l.classList.toggle('active', l.getAttribute('href') === '#' + e.target.id));
    }
  });
}, { rootMargin: '-20% 0px -70% 0px' });
sections.forEach(s => observer.observe(s));
"""


def write_html(state: ReviewState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    title = _e(state.pr_title or state.repo_url or state.pr_url)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    all_findings = [f for r in state.reviews for f in r.get("findings", [])]
    criticals   = sum(1 for f in all_findings if f.get("severity") == "CRITICAL")
    warnings    = sum(1 for f in all_findings if f.get("severity") == "WARNING")
    suggestions = sum(1 for f in all_findings if f.get("severity") == "SUGGESTION")

    # --- Sidebar TOC ---
    toc_items: list[str] = []
    for review in state.reviews:
        fname = review.get("filename", "unknown")
        slug  = _slug(fname)
        file_findings = review.get("findings", [])
        fc = sum(1 for f in file_findings if f.get("severity") == "CRITICAL")
        fw = sum(1 for f in file_findings if f.get("severity") == "WARNING")
        fs = sum(1 for f in file_findings if f.get("severity") == "SUGGESTION")
        badges_html = ""
        if fc: badges_html += f'<span style="color:#c0392b">🔴{fc}</span> '
        if fw: badges_html += f'<span style="color:#d68910">🟡{fw}</span> '
        if fs: badges_html += f'<span style="color:#1a6fa8">🔵{fs}</span>'
        toc_items.append(
            f'<a class="toc-link" href="#{slug}" title="{_e(fname)}">'
            f'{_e(fname)}'
            f'<span class="toc-badge">{badges_html}</span>'
            f'</a>'
        )

    # --- File sections ---
    file_sections: list[str] = []
    for review in state.reviews:
        fname    = review.get("filename", "unknown")
        slug     = _slug(fname)
        summary  = review.get("summary", "")
        findings = review.get("findings", [])
        scores   = review.get("score", {})
        test_info = review.get("test_coverage_assessment", {})

        fc = sum(1 for f in findings if f.get("severity") == "CRITICAL")
        fw = sum(1 for f in findings if f.get("severity") == "WARNING")
        fs = sum(1 for f in findings if f.get("severity") == "SUGGESTION")

        badges = ""
        if fc: badges += f'<span class="badge crit">🔴 {fc}</span>'
        if fw: badges += f'<span class="badge warn">🟡 {fw}</span>'
        if fs: badges += f'<span class="badge sugg">🔵 {fs}</span>'
        if not findings: badges = '<span style="color:#27ae60">✅ clean</span>'

        # Scores
        scores_html = ""
        if scores:
            items = ""
            for key, label in SCORE_KEYS:
                val = scores.get(key, "N/A")
                bar = _score_bar_html(val) if isinstance(val, int) else "<em>N/A</em>"
                items += (
                    f'<div class="score-item">'
                    f'<span class="cat-name">{_e(label)}</span>'
                    f'{bar}'
                    f'</div>'
                )
            scores_html = f'<div class="scores-grid">{items}</div>'

        # Coverage
        cov_html = ""
        if test_info:
            cov_ok = test_info.get("coverage_ok")
            badge  = "✅ Coverage OK" if cov_ok is True else \
                     "❌ Below 85% threshold" if cov_ok is False else "⚠️ Coverage unknown"
            est    = test_info.get("estimated_coverage", "")
            notes  = _e(test_info.get("notes", ""))
            cov_html = (
                f'<p style="margin-bottom:12px"><strong>{badge}</strong>'
                + (f' &nbsp;·&nbsp; {_e(est)}' if est else "")
                + (f'<br><small>{notes}</small>' if notes else "")
                + '</p>'
            )

        # Findings
        if not findings:
            findings_html = '<p class="clean-badge">✅ No issues found.</p>'
        else:
            cards = ""
            for i, f in enumerate(findings, 1):
                sev      = f.get("severity", "SUGGESTION")
                cat      = f.get("category", "")
                icon     = SEVERITY_ICON.get(sev, "⚪")
                fc_color, fc_bg = SEVERITY_COLOR.get(sev, ("#555", "#fafafa"))
                title    = _e(f.get("title", ""))
                desc     = _e(f.get("description", ""))
                suggest  = _e(f.get("suggestion", ""))
                cat_lbl  = _e(CATEGORY_LABEL.get(cat, cat))
                line_no  = f.get("line")
                line_html = f'<span class="line-pill">line {_e(str(line_no))}</span>' if line_no else ""
                cards += (
                    f'<details class="finding-card" style="border-color:{fc_color}">'
                    f'<summary style="background:{fc_bg}">'
                    f'<span class="sev-label" style="background:{fc_color}">{icon} {_e(sev)}</span>'
                    f'<span style="margin-left:6px;font-weight:500">{title}</span>'
                    f'<span class="cat-pill" style="margin-left:8px">{cat_lbl}</span>'
                    f'{line_html}'
                    f'<span class="toggle-icon">▼</span>'
                    f'</summary>'
                    f'<div class="finding-body">'
                    f'<p>{desc}</p>'
                    f'<div class="suggestion">💡 <strong>Suggestion:</strong> {suggest}</div>'
                    f'</div>'
                    f'</details>'
                )
            findings_html = cards

        file_sections.append(
            f'<div class="file-section" id="{slug}">'
            f'  <div class="file-header">'
            f'    <span class="file-name">{_e(fname)}</span>'
            f'    <div class="file-badges">{badges}</div>'
            f'  </div>'
            f'  <div class="file-body">'
            + (f'<p class="summary-text">{_e(summary)}</p>' if summary else "")
            + scores_html
            + cov_html
            + findings_html
            + f'</div></div>'
        )

    # Missing tests
    advisory_html = ""
    missing = state.missing_tests.get("missing_tests", [])
    if missing:
        rows = "".join(
            f'<tr><td><code>{_e(item.get("file",""))}</code></td>'
            f'<td>{_e(item.get("scenario",""))}</td>'
            f'<td>{_e(item.get("reason",""))}</td></tr>'
            for item in missing
        )
        advisory_html = (
            '<div class="advisory" id="missing-tests">'
            '<h3>⚠️ Missing Test Coverage Advisory</h3>'
            '<p style="font-size:12px;margin-bottom:12px;color:#7a6000">'
            'These findings are advisory — a human reviewer should make the final decision.</p>'
            '<table><thead><tr><th>File</th><th>Scenario</th><th>Reason</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>'
            '</div>'
        )

    # Post review note
    post_html = ""
    if state.post_review_url:
        if state.post_review_url.startswith("ERROR:"):
            post_html = f'<p style="color:#c0392b">⚠️ Could not post GitHub review: {_e(state.post_review_url)}</p>'
        else:
            post_html = f'<p>✅ Review posted to GitHub: <a href="{_e(state.post_review_url)}">{_e(state.post_review_url)}</a></p>'

    meta_lines = []
    if state.pr_url:
        meta_lines.append(f'PR: <a href="{_e(state.pr_url)}">{_e(state.pr_url)}</a>')
    if state.repo_url:
        branch_note = f" (branch: <code>{_e(state.branch)}</code>)" if state.branch else ""
        meta_lines.append(f'Repo: <a href="{_e(state.repo_url)}">{_e(state.repo_url)}</a>{branch_note}')
    meta_lines.append(f'Generated: {generated}')

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>AI Code Review — {title}</title>
<style>{CSS}</style>
</head>
<body>

<nav id="sidebar">
  <div id="sidebar-header">
    <h1>🤖 AI Code Review</h1>
    <p>{title}</p>
  </div>
  <h2>Files</h2>
  {''.join(toc_items)}
  {'<a class="toc-link" href="#missing-tests">⚠️ Missing Tests</a>' if missing else ''}
</nav>

<main id="main">
  <h2 class="section-title">🤖 AI Code Review — {title}</h2>
  <p class="meta">{'  &nbsp;|&nbsp;  '.join(meta_lines)}</p>

  <div id="search-wrap">
    <input id="search" type="search" placeholder="🔍 Filter findings by keyword…"/>
  </div>

  <div class="summary-banner">
    <div class="stat-card">
      <div class="num">{len(state.reviews)}</div>
      <div class="lbl">Files Reviewed</div>
    </div>
    <div class="stat-card">
      <div class="num" style="color:#c0392b">{criticals}</div>
      <div class="lbl">🔴 Critical</div>
    </div>
    <div class="stat-card">
      <div class="num" style="color:#d68910">{warnings}</div>
      <div class="lbl">🟡 Warnings</div>
    </div>
    <div class="stat-card">
      <div class="num" style="color:#1a6fa8">{suggestions}</div>
      <div class="lbl">🔵 Suggestions</div>
    </div>
  </div>

  {''.join(file_sections)}
  {advisory_html}
  {post_html}
</main>

<script>{JS}</script>
</body>
</html>
"""

    path.write_text(html_doc, encoding="utf-8")
    print(f"  🌐 HTML report saved:     {path}")
