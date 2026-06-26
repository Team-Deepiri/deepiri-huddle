from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class RenderMode(Enum):
    HEURISTIC = "heuristic"
    TEMPLATE = "template"
    ENHANCED = "enhanced"


class MeetingArchetype(Enum):
    STANDUP = "standup"
    SPRINT_REVIEW = "sprint-review"
    RETRO = "retro"
    PLANNING = "planning"
    DEEP_DIVE = "deep-dive"
    CUSTOM = "custom"


class RiskSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(slots=True)
class TeamMeeting:
    team_name: str
    day_of_week: str
    time_est: str
    time_cst: str
    time_mst: str
    time_pst: str


@dataclass(slots=True)
class CommitInfo:
    hash: str
    author: str
    date: str
    subject: str
    body: str
    files_changed: list[str]
    insertions: int
    deletions: int


@dataclass(slots=True)
class AuthorSummary:
    author: str
    commit_count: int
    files_affected: list[str]
    subjects: list[str]


@dataclass(slots=True)
class GitContext:
    repo_root: str
    commits: list[CommitInfo]
    authors: list[AuthorSummary]
    module_churn: dict[str, int]
    file_churn: dict[str, int]
    silent_authors: list[str]
    branch_summary: str


@dataclass(slots=True)
class DocInfo:
    path: str
    repo: str
    title: str
    headings: list[str]
    word_count: int
    modified_date: str
    content_preview: str


@dataclass(slots=True)
class DocContext:
    repos: list[str]
    docs: list[DocInfo]
    recent_changes: list[dict]


@dataclass(slots=True)
class Risk:
    risk_type: str
    severity: RiskSeverity
    title: str
    description: str
    evidence: str


@dataclass(slots=True)
class MeetingRequest:
    meeting_title: str
    meeting_type: str
    team_focus: str
    attendees_count: int
    objectives: list[str]
    week_label: str
    target_date_iso: str
    notes: str | None = None
    archetype: MeetingArchetype = MeetingArchetype.CUSTOM
    render_mode: RenderMode = RenderMode.TEMPLATE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class MeetingPlan:
    markdown: str
    provider_used: str
    model_used: str
    generated_at_iso: str
    render_mode: RenderMode = RenderMode.TEMPLATE
