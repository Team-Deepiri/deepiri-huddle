from __future__ import annotations

from collections import defaultdict

from huddle.models import GitContext, Risk, RiskSeverity


def detect_risks(
    git: GitContext | None,
    high_churn_threshold: int = 10,
    stale_days: int = 30,
) -> list[Risk]:
    risks: list[Risk] = []

    if not git:
        return risks

    # 1. HIGH_CHURN: files with unusually many changes
    if git.file_churn:
        for filepath, count in list(git.file_churn.items())[:5]:
            if count >= high_churn_threshold:
                risks.append(
                    Risk(
                        risk_type="HIGH_CHURN",
                        severity=RiskSeverity.HIGH
                        if count >= high_churn_threshold * 2
                        else RiskSeverity.MEDIUM,
                        title=f"High churn in `{filepath}`",
                        description=(
                            f"Modified {count} times in recent commits."
                            " This file is seeing disproportionate activity"
                            " and may indicate instability or refactoring."
                        ),
                        evidence=f"{count} changes across {len(git.commits)} recent commits",
                    )
                )

    # 2. MODULE_HOTSPOT: modules with concentrated change activity
    if git.module_churn:
        total_commits = len(git.commits)
        for module, count in list(git.module_churn.items())[:3]:
            pct = round(count / max(1, total_commits) * 100)
            if pct > 40:
                risks.append(
                    Risk(
                        risk_type="MODULE_HOTSPOT",
                        severity=RiskSeverity.MEDIUM,
                        title=f"Activity concentrated in `{module}/`",
                        description=(
                            f"{pct}% of all recent commits touch this module. This"
                            " concentration may create review bottlenecks or"
                            " missed cross-module impacts."
                        ),
                        evidence=f"{count}/{total_commits} commits ({pct}%) in {module}/",
                    )
                )

    # 3. SILENT_AUTHOR: team members with no recent commits
    if git.silent_authors:
        risks.append(
            Risk(
                risk_type="SILENT_AUTHOR",
                severity=RiskSeverity.LOW,
                title=f"Silent authors: {', '.join(git.silent_authors[:3])}",
                description=(
                    "These contributors have git history but no recent commits."
                    " May indicate blockers, PTO, or context switching."
                ),
                evidence=f"No commits from: {', '.join(git.silent_authors[:5])}",
            )
        )

    # 4. SOLO_OWNER: files with a single author
    author_file_map: dict[str, set[str]] = defaultdict(set)
    for c in git.commits:
        for f in c.files_changed:
            author_file_map[c.author].add(f)
    all_files = set()
    for files in author_file_map.values():
        all_files.update(files)
    solo_files: list[str] = []
    for f in all_files:
        authors_for_file = {author for author, files in author_file_map.items() if f in files}
        if len(authors_for_file) == 1:
            solo_files.append(f)
    if solo_files:
        risks.append(
            Risk(
                risk_type="SOLO_OWNER",
                severity=RiskSeverity.MEDIUM,
                title=f"{len(solo_files)} file(s) with single contributor",
                description=(
                    "Files touched by only one author represent bus-factor risk."
                    " If that person is unavailable, these areas may be hard to maintain."
                ),
                evidence=f"Solo-owned files: {', '.join(solo_files[:5])}",
            )
        )

    # 5. LARGE_COMMITS: unusually large changes
    for c in git.commits[:20]:
        total_changes = c.insertions + c.deletions
        if total_changes > 500:
            risks.append(
                Risk(
                    risk_type="LARGE_COMMIT",
                    severity=RiskSeverity.HIGH if total_changes > 1000 else RiskSeverity.MEDIUM,
                    title=f"Large commit: {c.hash[:8]}",
                    description=(
                        f"{total_changes} line changes ({c.insertions}+, {c.deletions}-)."
                        " Large commits are harder to review and may hide regressions."
                    ),
                    evidence=f"{c.hash[:8]} by {c.author}: {c.subject[:80]}",
                )
            )

    return risks


def format_risks_markdown(risks: list[Risk]) -> str:
    if not risks:
        return "No significant risks detected based on recent git activity."

    by_severity = {"critical": [], "high": [], "medium": [], "low": []}
    for r in risks:
        by_severity.setdefault(r.severity.value, []).append(r)

    lines: list[str] = []
    for sev_name in ["critical", "high", "medium", "low"]:
        items = by_severity.get(sev_name, [])
        if not items:
            continue
        emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(sev_name, "⚪")
        label = sev_name.upper()
        for r in items:
            lines.append(f"- {emoji} **[{label}]** {r.title}")
            lines.append(f"  - {r.description}")
            lines.append(f"  - *Evidence: {r.evidence}*")

    return "\n".join(lines)
