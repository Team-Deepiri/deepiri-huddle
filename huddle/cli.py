from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.status import Status

from huddle.chat_agent import ChatAgent
from huddle.config import Settings
from huddle.discord_feed import DiscordFeed
from huddle.llm import MultiProviderLlm
from huddle.memory import MemoryStore
from huddle.models import MeetingArchetype, MeetingRequest, RenderMode
from huddle.planner import MeetingPlanner
from huddle.tui import HuddleTui

app = typer.Typer(help="deepiri-huddle: artifact-driven meeting planning agent")
plan_app = typer.Typer(help="Generate meeting plans")
app.add_typer(plan_app, name="plan")
console = Console()
TEAM_CHOICES = ["ai-ml", "qa", "frontend-backend-infra", "it", "all-teams"]
WEEK_CHOICES = ["current", "next"]
RENDER_CHOICES = ["template", "heuristic", "enhanced"]
ARCHETYPE_CHOICES = ["custom", "standup", "sprint-review", "retro", "planning", "deep-dive"]


def _build_llm(settings: Settings) -> MultiProviderLlm | None:
    if not settings.no_llm_fallback:
        return None
    try:
        return MultiProviderLlm(settings=settings)
    except Exception:
        return None


def _build_planner(settings: Settings | None = None) -> MeetingPlanner:
    s = settings or Settings()
    return MeetingPlanner(
        llm=_build_llm(s),
        memory=MemoryStore(s.memory_file),
        discord_feed=DiscordFeed(s),
        no_llm_fallback=s.no_llm_fallback,
    )


def _build_chat_agent() -> ChatAgent:
    settings = Settings()
    return ChatAgent(
        llm=MultiProviderLlm(settings=settings),
        memory=MemoryStore(settings.memory_file),
        discord_feed=DiscordFeed(settings),
    )


def _next_monday(anchor: date) -> date:
    days = (7 - anchor.weekday()) % 7
    if days == 0:
        days = 7
    return anchor + timedelta(days=days)


def _week_anchor(week: str) -> date:
    base = _next_monday(date.today())
    return base if week == "current" else base + timedelta(days=7)


def _default_output(team: str, meeting_type: str, week: str) -> Path:
    anchor = _week_anchor(week).isoformat()
    safe_team = team.replace("-", "_")
    safe_type = meeting_type.replace("-", "_")
    return Path(f"plans/{safe_team}_{safe_type}_{anchor}.md")


@plan_app.command()
def weekly(
    team: str = typer.Option(
        "all-teams",
        "--team",
        "-t",
        prompt="Which team is this meeting for? (ai-ml, qa, frontend-backend-infra, it, all-teams)",
    ),
    week: str = typer.Option("next", "--week", help="current or next"),
    render: str = typer.Option(
        "template", "--render", "-r", help="template, heuristic, or enhanced"
    ),
    archetype: str = typer.Option("custom", "--archetype", "-a", help="Meeting archetype"),
    output: Path | None = typer.Option(None, "--output", "-o"),  # noqa: B008
) -> None:
    if team not in TEAM_CHOICES:
        raise typer.BadParameter(f"team must be one of: {', '.join(TEAM_CHOICES)}")
    if week not in WEEK_CHOICES:
        raise typer.BadParameter(f"week must be one of: {', '.join(WEEK_CHOICES)}")
    if render not in RENDER_CHOICES:
        raise typer.BadParameter(f"render must be one of: {', '.join(RENDER_CHOICES)}")
    if archetype not in ARCHETYPE_CHOICES:
        raise typer.BadParameter(f"archetype must be one of: {', '.join(ARCHETYPE_CHOICES)}")

    target = _week_anchor(week)
    req = MeetingRequest(
        meeting_title="Deepiri Weekly Engineering Round Table",
        meeting_type="weekly-status-sync",
        team_focus=team,
        attendees_count=15,
        objectives=[
            "Align weekly priorities across participating teams",
            "Surface wins and blockers quickly",
            "Assign ownership and due dates for every action",
            "Use Discord announcements as context when available",
        ],
        week_label=f"{week}-week",
        target_date_iso=target.isoformat(),
        notes="Use recurring schedule and include mandatory round table.",
        render_mode=RenderMode(render),
        archetype=MeetingArchetype(archetype),
    )
    _generate_and_write(req, output or _default_output(team, req.meeting_type, week))


@plan_app.command()
def custom(
    meeting_title: str = typer.Option(..., help="Meeting title"),
    meeting_type: str = typer.Option(..., help="Meeting type"),
    team: str = typer.Option(
        "all-teams",
        "--team",
        "-t",
        prompt="Which team is this meeting for? (ai-ml, qa, frontend-backend-infra, it, all-teams)",
    ),
    week: str = typer.Option("next", "--week", help="current or next"),
    attendees: int = typer.Option(15, min=2, max=100),
    render: str = typer.Option(
        "template", "--render", "-r", help="template, heuristic, or enhanced"
    ),
    archetype: str = typer.Option("custom", "--archetype", "-a", help="Meeting archetype"),
    notes: str = typer.Option("", help="Additional planning context"),
    output: Path | None = typer.Option(None, "--output", "-o"),  # noqa: B008
) -> None:
    if team not in TEAM_CHOICES:
        raise typer.BadParameter(f"team must be one of: {', '.join(TEAM_CHOICES)}")
    if week not in WEEK_CHOICES:
        raise typer.BadParameter(f"week must be one of: {', '.join(WEEK_CHOICES)}")
    if render not in RENDER_CHOICES:
        raise typer.BadParameter(f"render must be one of: {', '.join(RENDER_CHOICES)}")
    if archetype not in ARCHETYPE_CHOICES:
        raise typer.BadParameter(f"archetype must be one of: {', '.join(ARCHETYPE_CHOICES)}")

    target = _week_anchor(week)
    req = MeetingRequest(
        meeting_title=meeting_title,
        meeting_type=meeting_type,
        team_focus=team,
        attendees_count=attendees,
        objectives=[
            "Drive clarity on immediate goals",
            "Collect concise status from each participant",
            "Turn blockers into owner-assigned action items",
        ],
        week_label=f"{week}-week",
        target_date_iso=target.isoformat(),
        notes=notes or None,
        render_mode=RenderMode(render),
        archetype=MeetingArchetype(archetype),
    )
    _generate_and_write(req, output or _default_output(team, meeting_type, week))


@plan_app.command()
def status() -> None:
    """Show what data sources are available for planning."""
    from huddle.docfinder import scan_docs
    from huddle.gitlog import gather_context

    settings = Settings()
    console.print("[bold]deepiri-huddle status[/bold]\n")

    console.print("[bold]Git:[/bold]")
    ctx = gather_context(days=7)
    if ctx:
        console.print(f"  Repo: {ctx.repo_root}")
        console.print(f"  Recent commits: {len(ctx.commits)}")
        console.print(f"  Active authors: {len(ctx.authors)}")
    else:
        console.print("  [yellow]Not a git repository or no recent activity[/yellow]")

    console.print("\n[bold]Documents:[/bold]")
    docs = scan_docs(extra_paths=settings.extra_repos() if settings.huddle_repos else None)
    if docs.repos:
        console.print(f"  Repos discovered: {', '.join(docs.repos)}")
        console.print(f"  Docs found: {len(docs.docs)}")
    else:
        console.print(
            "  [yellow]No repos discovered. Set HUDDLE_REPOS or place repos as siblings.[/yellow]"
        )

    console.print("\n[bold]LLM:[/bold]")
    llm = _build_llm(settings)
    if llm:
        console.print("  [green]Available[/green]")
        console.print(f"  Provider order: {settings.provider_order()}")
    else:
        console.print("  [yellow]Not configured (NO_LLM_FALLBACK set or no providers)[/yellow]")

    console.print("\n[bold]Discord:[/bold]")
    feed = DiscordFeed(settings)
    if feed.enabled():
        console.print("  [green]Configured[/green]")
    else:
        console.print("  [yellow]Not configured (no DISCORD_BOT_TOKEN)[/yellow]")

    console.print("\n[bold]Memory:[/bold]")
    mem = MemoryStore(settings.memory_file)
    entries = mem.latest(5)
    if entries:
        console.print(f"  Stored entries: {len(entries)}+")
    else:
        console.print("  [yellow]Empty[/yellow]")


def _generate_and_write(request: MeetingRequest, output: Path) -> None:
    planner = _build_planner()
    with Status(
        "Gathering context and generating meeting plan...", spinner="dots", console=console
    ):
        plan = planner.plan(request)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(plan.markdown + "\n", encoding="utf-8")
    console.print(
        Panel.fit(
            f"Wrote plan to [bold]{output}[/bold]\n"
            f"Render mode: [bold]{plan.render_mode.value}[/bold]\n"
            f"Provider: [bold]{plan.provider_used}[/bold]\n"
            f"Model: [bold]{plan.model_used}[/bold]\n"
            f"Generated: {plan.generated_at_iso}",
            title="deepiri-huddle",
        )
    )


@app.command()
def chat() -> None:
    """Launch full-screen chat TUI."""
    HuddleTui(agent=_build_chat_agent()).run()


if __name__ == "__main__":
    app()
