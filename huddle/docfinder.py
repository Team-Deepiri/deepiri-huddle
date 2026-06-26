from __future__ import annotations

import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from huddle.models import DocContext, DocInfo


def _git(*args: str, repo_path: str) -> str:
    cmd = ["git", "-C", repo_path]
    cmd.extend(args)
    return subprocess.check_output(cmd, text=True, stderr=subprocess.PIPE)


def _is_git_repo(path: str) -> bool:
    try:
        _git("rev-parse", "--git-dir", repo_path=path)
        return True
    except Exception:
        return False


def _discover_git_repos(
    base_path: str | None = None, extra_paths: list[str] | None = None
) -> list[str]:
    found: set[str] = set()

    start = base_path or os.getcwd()

    # Check the starting path itself
    if _is_git_repo(start):
        found.add(os.path.abspath(start))

    # Check parent directories
    parent = os.path.dirname(start)
    while parent and parent != "/":
        if _is_git_repo(parent):
            found.add(os.path.abspath(parent))
            break
        parent = os.path.dirname(parent)

    # Check sibling directories for deepiri-* repos
    sibling_dir = os.path.dirname(start)
    if sibling_dir and sibling_dir != "/":
        try:
            for entry in os.listdir(sibling_dir):
                full = os.path.join(sibling_dir, entry)
                if os.path.isdir(full) and _is_git_repo(full):
                    found.add(os.path.abspath(full))
        except PermissionError:
            pass

    # Check extra paths
    if extra_paths:
        for p in extra_paths:
            expanded = os.path.expanduser(os.path.expandvars(p))
            if os.path.isdir(expanded) and _is_git_repo(expanded):
                found.add(os.path.abspath(expanded))

    # Check git worktrees and submodules
    try:
        root = os.path.abspath(start)
        if _is_git_repo(root):
            submodules = _git("submodule", "status", repo_path=root)
            for line in submodules.split("\n"):
                parts = line.strip().split()
                if len(parts) >= 2:
                    sub_path = os.path.join(root, parts[1])
                    if os.path.isdir(sub_path):
                        found.add(os.path.abspath(sub_path))
    except Exception:
        pass

    return sorted(found)


def _extract_title(filepath: str, content: str) -> str:
    """Extract the first H1 or the filename as title."""
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# ") and not line.startswith("##"):
            return line[2:].strip()
    return Path(filepath).stem.replace("-", " ").replace("_", " ").title()


def _extract_headings(content: str) -> list[str]:
    headings: list[str] = []
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("##") or line.startswith("###"):
            heading = re.sub(r"^#+\s*", "", line).strip()
            if heading:
                headings.append(heading)
    return headings[:20]


def _find_docs_in_repo(
    repo_path: str,
    patterns: list[str] | None = None,
    max_docs: int = 50,
) -> list[str]:
    if patterns is None:
        patterns = ["**/*.md", "**/*.rst"]

    found: list[str] = []
    repo_root = Path(repo_path)

    for pattern in patterns:
        for f in repo_root.glob(pattern):
            if not f.is_file():
                continue

            rel = str(f.relative_to(repo_root))

            # Skip vendor/common dirs
            skip_parts = {
                "node_modules",
                ".venv",
                "venv",
                "__pycache__",
                ".git",
                ".github",
                ".pytest_cache",
                ".egg-info",
                "dist",
                "build",
                ".obsidian",
                "site-packages",
            }
            parts = set(rel.replace("\\", "/").split("/"))
            if parts & skip_parts:
                continue

            # Skip binary-like files
            try:
                if f.stat().st_size > 1_000_000:
                    continue
            except OSError:
                continue

            found.append(rel)

    return sorted(found)[:max_docs]


def _repo_name(repo_path: str) -> str:
    return Path(repo_path).name


def scan_docs(
    base_path: str | None = None,
    extra_paths: list[str] | None = None,
    doc_patterns: list[str] | None = None,
) -> DocContext:
    repos = _discover_git_repos(base_path, extra_paths)

    if doc_patterns is None:
        doc_patterns = ["**/*.md", "**/*.rst"]

    all_docs: list[DocInfo] = []
    all_recent_changes: list[dict] = []

    for repo in repos:
        doc_paths = _find_docs_in_repo(repo, doc_patterns)
        rname = _repo_name(repo)

        for rel_path in doc_paths:
            full_path = Path(repo) / rel_path
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            title = _extract_title(rel_path, content)
            headings = _extract_headings(content)
            word_count = len(content.split())
            preview = content[:300].strip()

            # Get last modified date from git
            modified = ""
            try:
                log = _git("log", "-1", "--format=%ai", "--", rel_path, repo_path=repo)
                modified = log.strip()
            except Exception:
                try:
                    mtime = full_path.stat().st_mtime
                    modified = datetime.fromtimestamp(mtime, tz=UTC).isoformat()
                except Exception:
                    modified = "unknown"

            all_docs.append(
                DocInfo(
                    path=rel_path,
                    repo=rname,
                    title=title,
                    headings=headings,
                    word_count=word_count,
                    modified_date=modified,
                    content_preview=preview,
                )
            )

            # Track recent changes to docs
            try:
                changes = _git(
                    "log",
                    "--oneline",
                    "--diff-filter=M",
                    "-5",
                    "--",
                    rel_path,
                    repo_path=repo,
                )
                for line in changes.strip().split("\n"):
                    if line.strip():
                        all_recent_changes.append(
                            {
                                "repo": rname,
                                "file": rel_path,
                                "commit": line.strip(),
                            }
                        )
            except Exception:
                pass

    return DocContext(
        repos=[_repo_name(r) for r in repos],
        docs=all_docs,
        recent_changes=all_recent_changes[:30],
    )


def keyword_search(ctx: DocContext, query_terms: list[str]) -> list[tuple[DocInfo, float]]:
    """Simple keyword relevance scoring."""
    scored: list[tuple[DocInfo, int]] = []
    terms = [t.lower() for t in query_terms]

    for doc in ctx.docs:
        combined = f"{doc.title} {' '.join(doc.headings)} {doc.content_preview}".lower()
        score = sum(combined.count(term) for term in terms)
        if score > 0:
            scored.append((doc, score))

    scored.sort(key=lambda x: -x[1])
    return [(doc, s / max(1, max(s for _, s in scored))) for doc, s in scored]
