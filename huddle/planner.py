from __future__ import annotations

import logging
from datetime import UTC, datetime

from huddle.discord_feed import DiscordFeed
from huddle.llm import MultiProviderLlm
from huddle.memory import MemoryStore
from huddle.models import MeetingPlan, MeetingRequest
from huddle.plan_output import (
    is_too_close_to_fallback,
    similarity_to_fallback,
    validate_meeting_plan_markdown,
)
from huddle.schedule import DEFAULT_TEAM_SCHEDULE, IT_ATTENDANCE_RULE

log = logging.getLogger(__name__)


class MeetingPlanner:
    def __init__(
        self,
        llm: MultiProviderLlm,
        memory: MemoryStore | None = None,
        discord_feed: DiscordFeed | None = None,
    ) -> None:
        self.llm = llm
        self.memory = memory
        self.discord_feed = discord_feed

    def plan(self, request: MeetingRequest) -> MeetingPlan:
        prompt = self._build_prompt(request)
        fallback_markdown = self._fallback_markdown(request).strip()
        provider = "deterministic-fallback"
        model = "n/a"
        try:
            result = self.llm.generate(prompt)
            markdown = result.text.strip()
            provider = result.provider
            model = result.model
            log.info(
                "planner_llm_response_ok meeting_title=%r provider=%s model=%s",
                request.meeting_title,
                provider,
                model,
            )
            if not self._is_team_scope_valid(markdown, request.team_focus):
                log.warning(
                    "planner_using_deterministic_fallback reason=invalid_team_scope "
                    "meeting_title=%r team_focus=%r",
                    request.meeting_title,
                    request.team_focus,
                )
                markdown = fallback_markdown
                provider = "deterministic-fallback"
                model = "n/a"
            else:
                schema = validate_meeting_plan_markdown(markdown)
                too_close = is_too_close_to_fallback(markdown, fallback_markdown)
                if not schema.ok:
                    err_preview = "; ".join(schema.errors)[:1200]
                    log.warning(
                        "planner_using_deterministic_fallback reason=schema_invalid "
                        "meeting_title=%r errors=%s",
                        request.meeting_title,
                        err_preview,
                    )
                elif too_close:
                    sim = similarity_to_fallback(markdown, fallback_markdown)
                    log.warning(
                        "planner_using_deterministic_fallback reason=too_similar_to_fallback "
                        "meeting_title=%r similarity=%.3f",
                        request.meeting_title,
                        sim,
                    )
                if not schema.ok or too_close:
                    markdown = fallback_markdown
                    provider = "deterministic-fallback"
                    model = "n/a"
        except Exception as exc:
            log.warning(
                "planner_using_deterministic_fallback reason=llm_error meeting_title=%r "
                "error_type=%s error=%s",
                request.meeting_title,
                type(exc).__name__,
                str(exc)[:800],
                exc_info=log.isEnabledFor(logging.DEBUG),
            )
            markdown = fallback_markdown
            provider = "deterministic-fallback"
            model = "n/a"
        plan = MeetingPlan(
            markdown=markdown.strip(),
            provider_used=provider,
            model_used=model,
            generated_at_iso=datetime.now(UTC).isoformat(),
        )
        log.info(
            "planner_plan_ready meeting_title=%r provider_used=%s model_used=%s",
            request.meeting_title,
            plan.provider_used,
            plan.model_used,
        )
        if self.memory:
            self.memory.append("planner_request", f"{request.meeting_title} ({request.week_label})")
            self.memory.append("planner_response", plan.markdown[:1500])
        return plan

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

    def _fallback_markdown(self, request: MeetingRequest) -> str:
        schedule_md = "\n".join(
            (
                f"- {slot.team_name}: {slot.day_of_week}, {slot.time_est} EST / "
                f"{slot.time_cst} CST / {slot.time_mst} MST / {slot.time_pst} PST"
            )
            for slot in self._selected_schedule(request.team_focus)
        )
        objectives_md = "\n".join(f"- {o}" for o in request.objectives)
        return f"""# {request.meeting_title} ({request.week_label})

## Purpose
- Meeting type: {request.meeting_type}
- Team focus: {request.team_focus}
- Week anchor: {request.target_date_iso}

## Agenda Timeline
- 0:00-0:05 Opening, outcomes, and constraints
- 0:05-0:12 Team Snapshot
- 0:12-0:35 Group Round Table
- 0:35-0:45 Decisions and blocker triage
- 0:45-0:55 Action assignment
- 0:55-1:00 Confidence check and close

## Group Round Table
- Each participant answers:
  1. What they are working on / planning next
  2. Wins
  3. Blockers
- Enforce 45-60 seconds each.

## Team Snapshot
- Current schedule:
{schedule_md}
- Top streams:
  1. Delivery commitments
  2. Cross-team dependencies
  3. Quality and reliability concerns

## Decisions Needed
- Confirm week priorities and tradeoffs.
- Confirm escalation path for blockers.

## Risks and Blockers
- Ownership ambiguity across teams.
- Delivery risk from hidden dependencies.
- Capacity constraints on critical paths.

## Action Items
- [ ] Owner: Team lead - Publish weekly priorities (due: next business day)
- [ ] Owner: EM - Assign blocker owners (due: 48h)
- [ ] Owner: Facilitator - Share notes + action tracker (due: 24h)

## Follow-up Checklist
- [ ] Notes posted
- [ ] Owners acknowledged actions
- [ ] Unresolved blockers moved to next prep list

## Meeting Objectives
{objectives_md}
"""

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

