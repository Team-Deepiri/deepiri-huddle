from huddle.gitlog import analyze_contributions, file_churn, module_churn
from huddle.models import CommitInfo, GitContext
from huddle.risks import detect_risks, format_risks_markdown


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


def _make_git_context(commits: list[CommitInfo], silent: list[str] | None = None) -> GitContext:
    return GitContext(
        repo_root="/test/repo",
        commits=commits,
        authors=analyze_contributions(commits),
        module_churn=module_churn(commits),
        file_churn=file_churn(commits),
        silent_authors=silent or [],
        branch_summary="main",
    )


def test_detect_no_risks_with_empty_git() -> None:
    risks = detect_risks(None)
    assert risks == []


def test_detect_silent_author_risk() -> None:
    commits = [_make_commit("a1", "Alice", ["src/foo.py"])]
    ctx = _make_git_context(commits, silent=["Bob"])
    risks = detect_risks(ctx)
    types = [r.risk_type for r in risks]
    assert "SILENT_AUTHOR" in types


def test_detect_large_commit_risk() -> None:
    commits = [_make_commit("a1", "Alice", ["src/foo.py"], ins=600, dels=100)]
    ctx = _make_git_context(commits)
    risks = detect_risks(ctx)
    types = [r.risk_type for r in risks]
    assert "LARGE_COMMIT" in types


def test_format_risks_markdown_handles_empty() -> None:
    md = format_risks_markdown([])
    assert "No significant risks" in md


def test_format_risks_markdown_includes_titles() -> None:
    from huddle.models import Risk, RiskSeverity

    risks = [
        Risk(
            risk_type="TEST",
            severity=RiskSeverity.HIGH,
            title="Test risk",
            description="A test risk description",
            evidence="Evidence here",
        )
    ]
    md = format_risks_markdown(risks)
    assert "Test risk" in md
    assert "A test risk description" in md
    assert "Evidence here" in md
