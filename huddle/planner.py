from __future__ import annotations

from datetime import UTC, datetime

from huddle.discord_feed import DiscordFeed
from huddle.llm import MultiProviderLlm
from huddle.memory import MemoryStore
from huddle.models import MeetingPlan, MeetingRequest, RenderMode
from huddle.schedule import DEFAULT_TEAM_SCHEDULE, IT_ATTENDANCE_RULE


class MeetingPlanner:
    def __init__(
        self,
        llm: MultiProviderLlm | None = None,
        memory: MemoryStore | None = None,
        discord_feed: DiscordFeed | None = None,
        no_llm_fallback: bool = True,
    ) -> None:
        self.llm = llm
        self.memory = memory
        self.discord_feed = discord_feed
        self.no_llm_fallback = no_llm_fallback
        self._env = None

    @property
    def _template_env(self):
        if self._env is None:
            try:
                from jinja2 import Environment, PackageLoader, select_autoescape

                self._env = Environment(
                    loader=PackageLoader("huddle", "templates"),
                    autoescape=select_autoescape(disabled_extensions=("j2",), default=False),
                    trim_blocks=True,
                    lstrip_blocks=True,
                )
            except Exception:
                self._env = False
        return self._env if self._env is not False else None

    def plan(self, request: MeetingRequest) -> MeetingPlan:
        context = self._build_context(request)

        if request.render_mode == RenderMode.HEURISTIC:
            return self._plan_heuristic(request, context)
        if request.render_mode == RenderMode.ENHANCED and self.llm and self.no_llm_fallback:
            return self._plan_llm(request, context)
        return self._plan_template(request, context)

    def _build_context(self, request: MeetingRequest) -> dict:
        schedule_lines = self._selected_schedule(request.team_focus)

        git_ctx = None
        doc_ctx = None
        try:
            from huddle.gitlog import gather_context

            git_ctx = gather_context(days=7)
        except Exception:
            git_ctx = None

        try:
            from huddle.docfinder import scan_docs

            doc_ctx = scan_docs()
        except Exception:
            doc_ctx = None

        risks = []
        if git_ctx:
            try:
                from huddle.risks import detect_risks, format_risks_markdown

                risks = detect_risks(git_ctx)
                risks_md = format_risks_markdown(risks)
            except Exception:
                risks_md = "*Risk detection unavailable.*"
        else:
            risks_md = "*No git context for risk detection.*"

        objectives_md = [o for o in request.objectives]
        memory_block = self._memory_block()
        discord_block = self._discord_block()

        return {
            "meeting_title": request.meeting_title,
            "meeting_type": request.meeting_type,
            "team_focus": request.team_focus,
            "attendees_count": request.attendees_count,
            "week_label": request.week_label,
            "target_date_iso": request.target_date_iso,
            "objectives": objectives_md,
            "notes": request.notes or "None provided.",
            "schedule": schedule_lines,
            "it_attendance_rule": IT_ATTENDANCE_RULE,
            "git_context": git_ctx,
            "doc_context": doc_ctx,
            "risks": risks,
            "risks_markdown": risks_md,
            "discord_context": discord_block,
            "memory": memory_block,
            "archetype": request.archetype.value if request.archetype else None,
            "generated_at": datetime.now(UTC).isoformat(),
            "git_days": 7,
        }

    def _plan_template(self, request: MeetingRequest, context: dict) -> MeetingPlan:
        env = self._template_env
        if env is not None:
            try:
                template = env.get_template("plan.md.j2")
                markdown = template.render(**context)
                return MeetingPlan(
                    markdown=markdown.strip(),
                    provider_used="jinja2-template",
                    model_used="n/a",
                    generated_at_iso=datetime.now(UTC).isoformat(),
                    render_mode=RenderMode.TEMPLATE,
                )
            except Exception:
                pass

        return self._plan_heuristic(request, context)

    def _plan_heuristic(self, request: MeetingRequest, context: dict) -> MeetingPlan:
        schedule_md = "\n".join(
            (
                f"- {slot.team_name}: {slot.day_of_week}, {slot.time_est} EST / "
                f"{slot.time_cst} CST / {slot.time_mst} MST / {slot.time_pst} PST"
            )
            for slot in context["schedule"]
        )
        objectives_md = "\n".join(f"- {o}" for o in context["objectives"])
        git_block = context.get("git_context")
        git_section = "*Git tracking not available.*"
        if git_block and git_block.commits:
            authors_md = "\n".join(
                f"- **{a.author}**: {a.commit_count} commit(s)" for a in git_block.authors[:8]
            )
            git_section = f"### Commits ({len(git_block.commits)} recent)\n{authors_md}"

        risk_section = context.get("risks_markdown", "*No risk data.*")

        return MeetingPlan(
            markdown=f"""# {request.meeting_title} ({request.week_label})

## Purpose
- Meeting type: {request.meeting_type}
- Team focus: {request.team_focus}
- Week anchor: {request.target_date_iso}

## Schedule
{schedule_md}
{IT_ATTENDANCE_RULE}

## Recent Activity
{git_section}

## Group Round Table
Each participant answers:
1. What they are working on / planning next
2. Wins
3. Blockers
- Timebox: 45-60 seconds each.

## Risks and Blockers
{risk_section}

## Decisions Needed
- Confirm week priorities and tradeoffs
- Confirm escalation path for blockers

## Action Items
- [ ] Owner: Facilitator - Publish meeting notes (due: 24h)
- [ ] Owner: Team Lead - Assign blocker owners (due: 48h)

## Meeting Objectives
{objectives_md}
""".strip(),
            provider_used="heuristic-fallback",
            model_used="n/a",
            generated_at_iso=datetime.now(UTC).isoformat(),
            render_mode=RenderMode.HEURISTIC,
        )

    def _plan_llm(self, request: MeetingRequest, _context: dict) -> MeetingPlan:
        prompt = self._build_prompt(request)
        try:
            result = self.llm.generate(prompt)
            markdown = result.text
            provider = result.provider
            model = result.model
            if not self._is_team_scope_valid(markdown, request.team_focus):
                return self._plan_template(request, self._build_context(request))
        except Exception:
            return self._plan_template(request, self._build_context(request))
        return MeetingPlan(
            markdown=markdown.strip(),
            provider_used=provider,
            model_used=model,
            generated_at_iso=datetime.now(UTC).isoformat(),
            render_mode=RenderMode.ENHANCED,
        )

    def _build_prompt(self, request: MeetingRequest) -> str:
        schedule_md = "\n".join(
            (
                f"- {slot.team_name}: {slot.day_of_week}, {slot.time_est} EST / "
                f"{slot.time_cst} CST / {slot.time_mst} MST / {slot.time_pst} PST"
            )
            for slot in self._selected_schedule(request.team_focus)
        )
        objectives_md = "\n".join(f"- {o}" for o in request.objectives)
        memory_block = self._memory_block()
        discord_block = self._discord_block()
        notes = request.notes or "None provided."
        return f"""
Create a facilitator-ready markdown meeting plan.

Meeting title: {request.meeting_title}
Meeting type: {request.meeting_type}
Team focus: {request.team_focus}
Attendees: {request.attendees_count}
Planning horizon: {request.week_label}
Target week date anchor: {request.target_date_iso}
Objectives:
{objectives_md}
Notes:
{notes}

Schedule:
{schedule_md}
{IT_ATTENDANCE_RULE}

Recent memory:
{memory_block}

Discord context:
{discord_block}

Required sections:
1) Purpose
2) Agenda Timeline
3) Group Round Table
4) Team Snapshot
5) Decisions Needed
6) Risks and Blockers
7) Action Items
8) Follow-up Checklist

Rules:
- Keep it detailed and practical.
- Timebox for 45-60 minutes.
- Group Round Table must ask: work/planning, wins, blockers.
- Include owner + due date style for action items.
"""

    def _memory_block(self) -> str:
        if not self.memory:
            return "No prior memory."
        entries = self.memory.latest(limit=8)
        if not entries:
            return "No prior memory."
        return "\n".join(f"- {e.role}: {e.content[:220]}" for e in entries)

    def _discord_block(self) -> str:
        if not self.discord_feed:
            return "Discord not configured."
        if not self.llm:
            try:
                messages = self.discord_feed.latest_messages()
                if not messages:
                    return "No Discord announcements available."
                bullets = "\n".join(f"- {m.author}: {m.content[:200]}" for m in messages[-8:])
                return "## Discord Announcements\n" + bullets
            except Exception:
                return "Discord unavailable."
        try:
            return self.discord_feed.summarized_context(self.llm)
        except Exception:
            return "Discord unavailable."

    @staticmethod
    def _selected_schedule(team_focus: str):
        normalized = (
            team_focus.strip()
            .lower()
            .replace("-", " ")
            .replace("_", " ")
            .replace("/", " ")
            .replace("+", " ")
        )
        if normalized in {"all teams", "all", "engineering", "it"}:
            return DEFAULT_TEAM_SCHEDULE
        return [
            slot
            for slot in DEFAULT_TEAM_SCHEDULE
            if normalized in slot.team_name.lower().replace("/", " ").replace("+", " ")
        ] or DEFAULT_TEAM_SCHEDULE

    @staticmethod
    def _is_team_scope_valid(markdown: str, team_focus: str) -> bool:
        normalized_team = team_focus.strip().lower()
        if normalized_team in {"all-teams", "all", "engineering", "it"}:
            return True
        text = markdown.lower()
        if "all teams" in text:
            return False
        forbidden = ["qa:", "frontend + backend + infrastructure:", "ai/ml:"]
        expected_label = {
            "ai-ml": "ai/ml:",
            "qa": "qa:",
            "frontend-backend-infra": "frontend + backend + infrastructure:",
        }.get(normalized_team)
        if expected_label and expected_label not in text:
            return False
        return all(not (item != expected_label and item in text) for item in forbidden)
