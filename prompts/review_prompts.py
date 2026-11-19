SYSTEM_PROMPT = """You are a senior C# software engineer performing a thorough code review.
You are precise, objective, and constructive.
Always respond with valid JSON only — no prose outside the JSON structure.
"""

FILE_REVIEW_PROMPT = """Review the following C# file from a pull request.

## File: {filename}
## Change type: {status}

### Diff (changed lines):
```diff
{patch}
```

### Full file content:
```csharp
{content}
```

Return a JSON object with this exact structure:

{{
  "filename": "{filename}",
  "summary": "One sentence overall impression",
  "findings": [
    {{
      "category": "FORMATTING | BEST_PRACTICES | SOLID | CLEAN_CODE_DRY | UNIT_TESTS",
      "severity": "CRITICAL | WARNING | SUGGESTION",
      "line": null,
      "title": "Short title",
      "description": "What the problem is and why it matters",
      "suggestion": "Concrete fix or improvement"
    }}
  ],
  "test_coverage_assessment": {{
    "has_tests": true,
    "estimated_coverage": "e.g. ~90% or unknown",
    "coverage_ok": true,
    "notes": "..."
  }},
  "score": {{
    "formatting": 0,
    "best_practices": 0,
    "solid": 0,
    "clean_code_dry": 0,
    "unit_tests": 0
  }}
}}

## Review criteria:

### FORMATTING
- Consistent indentation, braces, blank lines
- PascalCase for types/methods, camelCase for locals, _camelCase for private fields
- XML doc comments on public APIs
- Using directives ordered (System namespaces first)

### BEST_PRACTICES
- No .Result or .Wait() on tasks — use async/await
- Nullable reference types respected
- IDisposable / using statements used correctly
- No magic strings or numbers
- Pattern matching used where appropriate

### SOLID
- SRP: one class, one responsibility
- OCP: extend via abstraction, not modification
- LSP: subtypes honor base type contracts
- ISP: small, focused interfaces
- DIP: depend on abstractions, inject via constructor

### CLEAN_CODE_DRY
- Methods under ~25 lines
- No duplicated logic
- Meaningful names for everything
- No commented-out code

### UNIT_TESTS
- Arrange-Act-Assert pattern
- Tests edge cases and failure paths
- Mocks dependencies (not internals)
- No test interdependencies
- Min 85% coverage for changed code
- Test names follow MethodName_Scenario_ExpectedResult
"""

NO_TESTS_PROMPT = """The pull request modifies production C# code but includes no test files.

List the top missing test scenarios for these files:
{filenames}

Return JSON:
{{
  "missing_tests": [
    {{
      "file": "filename",
      "scenario": "What should be tested",
      "reason": "Why it matters"
    }}
  ]
}}
"""
