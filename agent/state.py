from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from tools.github_tool import PRFile


@dataclass
class ReviewState:
    # PR mode
    pr_url: str = ""
    # Repo/branch mode
    repo_url: str = ""
    branch: str = ""
    # Shared
    pr_title: str = ""
    pr_description: str = ""
    files: List[PRFile] = field(default_factory=list)
    reviews: List[Dict[str, Any]] = field(default_factory=list)
    missing_tests: Dict[str, Any] = field(default_factory=dict)
    post_review_url: Optional[str] = None
    error: Optional[str] = None
