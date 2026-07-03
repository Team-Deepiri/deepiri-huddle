from __future__ import annotations

import contextlib
import subprocess
from collections import defaultdict
from datetime import UTC, datetime

from huddle.models import AuthorSummary, CommitInfo, GitContext


def _git(*args: str, repo_path: str | None = None) -> str:
    cmd = ["git"]
    if repo_path:
        cmd.extend(["-C", repo_path])
    cmd.extend(args)
    return subprocess.check_output(cmd, text=True, stderr=subprocess.PIPE)


def _is_git_repo(path: str) -> bool:
    try:
        _git("rev-parse", "--git-dir", repo_path=path)
        return True
    except Exception:
        return False


def get_repo_root(path: str | None = None) -> str | None:
    try:
        return _git("rev-parse", "--show-toplevel", repo_path=path).strip()
    except Exception:
        return None


def recent_commits(
    days: int = 7, max_count: int = 50, repo_path: str | None = None
) -> list[CommitInfo]:
    since = f"{(datetime.now(UTC)).strftime('%Y-%m-%d')}"
    try:
        output = _git(
            "log",
            f"--since={since}",
            f"--max-count={max_count}",
            "--numstat",
            "--format===COMMIT==%n%H%n%an%n%ai%n%s%n==BODY==%n%b%n==FILES==",
            repo_path=repo_path,
        )
    except Exception:
        return []

    commits: list[CommitInfo] = []
    blocks = (
        output.split("==COMMIT==\n") if "==COMMIT==\n" in output else output.split("==COMMIT==")
    )

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n")
        if len(lines) < 5:
            continue

        commit_hash = lines[0].strip()
        author = lines[1].strip()
        date = lines[2].strip()
        subject = lines[3].strip()

        body_parts: list[str] = []
        files_changed: list[str] = []
        insertions = 0
        deletions = 0
        in_body = False
        in_files = False

        for line in lines[4:]:
            stripped = line.strip()
            if stripped == "==BODY==":
                in_body = True
                continue
            if stripped == "==FILES==":
                in_body = False
                in_files = True
                continue
            if in_body:
                body_parts.append(line)
            elif in_files:
                parts = stripped.split("\t")
                if len(parts) == 3:
                    ins_str, del_str, filepath = parts
                    if ins_str != "-":
                        with contextlib.suppress(ValueError):
                            insertions += int(ins_str)
                    if del_str != "-":
                        with contextlib.suppress(ValueError):
                            deletions += int(del_str)
                    if filepath:
                        files_changed.append(filepath)

        commits.append(
            CommitInfo(
                hash=commit_hash,
                author=author,
                date=date,
                subject=subject,
                body="\n".join(body_parts).strip(),
                files_changed=files_changed,
                insertions=insertions,
                deletions=deletions,
            )
        )

    return commits


def analyze_contributions(commits: list[CommitInfo]) -> list[AuthorSummary]:
    author_map: dict[str, dict] = {}
    for c in commits:
        if c.author not in author_map:
            author_map[c.author] = {"files": set(), "subjects": []}
        author_map[c.author]["files"].update(c.files_changed)
        if c.subject not in author_map[c.author]["subjects"]:
            author_map[c.author]["subjects"].append(c.subject)

    return [
        AuthorSummary(
            author=author,
            commit_count=sum(1 for c in commits if c.author == author),
            files_affected=sorted(data["files"]),
            subjects=data["subjects"][:10],
        )
        for author, data in sorted(
            author_map.items(), key=lambda x: -sum(1 for c in commits if c.author == x[0])
        )
    ]


def module_churn(commits: list[CommitInfo]) -> dict[str, int]:
    churn: dict[str, int] = defaultdict(int)
    for c in commits:
        modules_seen: set[str] = set()
        for f in c.files_changed:
            parts = f.split("/")
            module = parts[0] if len(parts) > 1 else "root"
            if module not in modules_seen:
                churn[module] += 1
                modules_seen.add(module)
    return dict(sorted(churn.items(), key=lambda x: -x[1]))


def file_churn(commits: list[CommitInfo]) -> dict[str, int]:
    churn: dict[str, int] = defaultdict(int)
    for c in commits:
        for f in c.files_changed:
            churn[f] += 1
    return dict(sorted(churn.items(), key=lambda x: -x[1]))


def silent_authors(
    all_commits: list[CommitInfo], recent_commits_list: list[CommitInfo], threshold_days: int = 14
) -> list[str]:
    all_authors = set(c.author for c in all_commits)
    recent_names = {c.author for c in recent_commits_list}
    return sorted(all_authors - recent_names)


def branch_summary(repo_path: str | None = None) -> str:
    try:
        branches = _git("branch", "-a", repo_path=repo_path).strip()
        if not branches:
            return "No branches found."
        lines = branches.split("\n")
        current = ""
        others: list[str] = []
        for line in lines:
            stripped = line.strip()
            if line.startswith("*"):
                current = stripped
            elif stripped:
                others.append(stripped)
        parts = [f"current: {current}"] if current else []
        if others:
            parts.append(f"all ({len(others)}): {', '.join(others[:10])}")
            if len(others) > 10:
                parts[-1] += f" (+{len(others) - 10} more)"
        return " | ".join(parts) if parts else "No branch info."
    except Exception:
        return "Branch info unavailable."


def gather_context(days: int = 7, repo_path: str | None = None) -> GitContext | None:
    root = get_repo_root(repo_path)
    if not root:
        return None

    commits = recent_commits(days=days, repo_path=root)
    authors = analyze_contributions(commits) if commits else []
    m_churn = module_churn(commits) if commits else {}
    f_churn = file_churn(commits) if commits else {}

    # Get all-time authors for silent detection
    all_commits = recent_commits(days=365, max_count=500, repo_path=root)

    silent = silent_authors(all_commits, commits, threshold_days=days) if all_commits else []
    branches = branch_summary(root)

    return GitContext(
        repo_root=root,
        commits=commits,
        authors=authors,
        module_churn=m_churn,
        file_churn=f_churn,
        silent_authors=silent,
        branch_summary=branches,
    )
