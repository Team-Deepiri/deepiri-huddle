from huddle.gitlog import analyze_contributions, file_churn, module_churn, recent_commits
from huddle.models import CommitInfo


def _make_commit(
    hash: str, author: str, files: list[str], ins: int = 10, dels: int = 2
) -> CommitInfo:
    return CommitInfo(
        hash=hash,
        author=author,
        date="2026-06-01",
        subject=f"commit {hash}",
        body="",
        files_changed=files,
        insertions=ins,
        deletions=dels,
    )


def test_recent_commits_returns_list() -> None:
    commits = recent_commits(days=7)
    assert isinstance(commits, list)


def test_analyze_contributions_groups_by_author() -> None:
    commits = [
        _make_commit("a1", "Alice", ["src/foo.py"]),
        _make_commit("a2", "Bob", ["src/bar.py"]),
        _make_commit("a3", "Alice", ["src/baz.py"]),
    ]
    authors = analyze_contributions(commits)
    names = [a.author for a in authors]
    assert "Alice" in names
    assert "Bob" in names
    for a in authors:
        if a.author == "Alice":
            assert a.commit_count == 2
        if a.author == "Bob":
            assert a.commit_count == 1


def test_module_churn_counts_modules() -> None:
    commits = [
        _make_commit("a1", "Alice", ["src/foo.py"]),
        _make_commit("a2", "Alice", ["src/bar.py", "docs/guide.md"]),
        _make_commit("a3", "Bob", ["src/baz.py"]),
    ]
    churn = module_churn(commits)
    assert churn.get("src", 0) >= 3
    assert churn.get("docs", 0) == 1


def test_file_churn_counts_files() -> None:
    commits = [
        _make_commit("a1", "Alice", ["src/foo.py"]),
        _make_commit("a2", "Alice", ["src/foo.py"]),
        _make_commit("a3", "Bob", ["src/bar.py"]),
    ]
    churn = file_churn(commits)
    assert churn.get("src/foo.py", 0) == 2
    assert churn.get("src/bar.py", 0) == 1
