# cs-review-agent

An AI-powered code review agent for C# repositories and pull requests.  
It fetches source files, scores them across five quality dimensions, detects missing test coverage, and renders findings as a rich console report, Markdown, or a navigable HTML document.

---

## Features

| | |
|---|---|
| 🔍 **PR & branch review** | Review an open PR *or* any branch directly — no PR required |
| 📊 **Five-dimension scoring** | Formatting · Best Practices · SOLID · Clean Code/DRY · Unit Tests |
| 🧪 **Per-file test gap detection** | Flags each production file with no matching test file |
| 💬 **Optional GitHub comment** | Posts a structured Markdown review back to the PR (opt-in) |
| ⚡ **Parallel reviews** | Files reviewed concurrently via `ThreadPoolExecutor` |
| 🔁 **Automatic LLM retry** | Exponential backoff on transient API errors (tenacity) |
| 📄 **Multi-format output** | Console (rich), Markdown, and self-contained HTML with sidebar + live search |

---

## Prerequisites

- Python 3.11+
- A GitHub [Personal Access Token](https://github.com/settings/tokens) with `repo` scope
- An LLM provider — Portkey gateway **or** direct Anthropic (see below)

---

## Setup

```bash
# 1. Clone and enter the project
git clone https://github.com/flavioperezcarreto/cs-review-agent.git
cd cs-review-agent

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
# Edit .env with your keys
```

---

## LLM provider

The agent uses an **OpenAI-compatible endpoint**, so it works with any provider that speaks that API shape.

### Option A — Portkey gateway (company / self-hosted)

```env
PORTKEY_API_KEY=your_portkey_api_key
PORTKEY_BASE_URL=https://your-portkey-gateway.example.com/v1
MODEL_NAME=@aws-bedrock-use2/us.anthropic.claude-sonnet-4-6
```

The gateway URL and model slug depend on your Portkey deployment.  
The agent sends `Authorization: Bearer <key>` — the standard Bearer scheme.

### Option B — Direct Anthropic via OpenAI-compatible endpoint

```env
PORTKEY_API_KEY=your_anthropic_api_key
PORTKEY_BASE_URL=https://api.anthropic.com/v1
MODEL_NAME=claude-sonnet-4-5
```

> `PORTKEY_API_KEY` is used as the bearer token regardless of provider.  
> Rename it to `LLM_API_KEY` in `config.py` if you prefer cleaner naming for the direct-Anthropic case.

---

## Configuration (`.env`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `PORTKEY_API_KEY` | ✅ | — | API key / bearer token for the LLM endpoint |
| `PORTKEY_BASE_URL` | ✅ | — | Base URL of the LLM gateway (OpenAI-compatible) |
| `GITHUB_TOKEN` | ✅ | — | GitHub PAT with `repo` scope |
| `MODEL_NAME` | ❌ | `claude-sonnet-4-5` | Model slug passed to the LLM endpoint |
| `MAX_FILE_CHARS` | ❌ | `12000` | Max characters read per `.cs` file |
| `POST_GITHUB_REVIEW` | ❌ | `false` | Set to `true` to post a review comment to the PR |

---

## Usage

### Review a pull request

```bash
python main.py https://github.com/owner/repo/pull/42
```

### Review a repository branch (no PR needed)

```bash
python main.py --repo https://github.com/owner/repo
python main.py --repo https://github.com/owner/repo --branch develop
```

### Output formats

Formats can be combined with commas or by repeating the flag:

```bash
# Console only (default)
python main.py --repo https://github.com/owner/repo

# Markdown + HTML saved to ./reports/
python main.py --repo https://github.com/owner/repo --output md,html --out-dir ./reports

# All three
python main.py --repo https://github.com/owner/repo --output console,md,html --out-dir ./reports

# Shorthand flag
python main.py --repo https://github.com/owner/repo -o html --out-dir ./reports
```

| Flag | Values | Default | Description |
|---|---|---|---|
| `--output` / `-o` | `console` `md` `html` | `console` | Output format(s) — repeatable or comma-separated |
| `--out-dir` | path | `.` | Directory for `.md` / `.html` files |

The console is **always** printed. `--output` only controls what additional files to write.

### HTML report highlights

- Fixed sidebar with per-file navigation and severity badges
- Collapsible finding cards (click to expand description + suggestion)
- Live keyword search bar
- Score bars per category
- Self-contained — open the `.html` file in any browser with no server needed

---

## Review dimensions

| Category | What is checked |
|---|---|
| **Formatting** | Indentation, naming conventions, XML doc comments, `using` order |
| **Best Practices** | `async`/`await`, nullable types, `IDisposable`, no magic strings |
| **SOLID** | SRP, OCP, LSP, ISP, DIP |
| **Clean Code / DRY** | Method length, duplication, meaningful names, dead code |
| **Unit Tests** | AAA pattern, edge cases, mocking, naming convention, ≥85% coverage |

Scores are 0–10 per dimension. A human reviewer always makes the final merge decision.

---

## Architecture

```
main.py                        Entry point — argparse, output routing
├── agent/
│   ├── core.py                LangGraph graph: fetch → review_files → check_tests → post_review
│   └── state.py               ReviewState dataclass
├── tools/
│   └── github_tool.py         GitHub API: fetch PR files, fetch repo tree, post review comment
├── prompts/
│   └── review_prompts.py      System prompt, per-file schema, missing-tests prompt
└── output/
    ├── console.py             Rich terminal renderer
    ├── md_writer.py           Markdown report writer
    └── html_writer.py         Self-contained HTML report writer
```

---

## Windows note

PowerShell's default encoding can drop emoji. Run with:

```powershell
$env:PYTHONUTF8="1"
.venv\Scripts\python.exe main.py ...
```

Or set `PYTHONUTF8=1` permanently in your system environment variables.
