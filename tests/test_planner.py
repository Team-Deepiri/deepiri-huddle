from huddle.models import MeetingRequest, RenderMode
from huddle.planner import MeetingPlanner


def test_planner_template_contains_round_table() -> None:
    planner = MeetingPlanner()
    request = MeetingRequest(
        meeting_title="Deepiri Weekly Sync",
        meeting_type="weekly-status-sync",
        team_focus="qa",
        attendees_count=15,
        objectives=["Align", "Unblock"],
        week_label="next-week",
        target_date_iso="2026-05-04",
    )
    plan = planner.plan(request)
    assert "## Group Round Table" in plan.markdown or "Group Round Table" in plan.markdown
    assert "What they are working on" in plan.markdown
    assert plan.provider_used == "jinja2-template"


def test_team_filter_supports_hyphenated_team_slug() -> None:
    planner = MeetingPlanner()
    request = MeetingRequest(
        meeting_title="Deepiri AI ML Sync",
        meeting_type="weekly-status-sync",
        team_focus="ai-ml",
        attendees_count=15,
        objectives=["Align", "Unblock"],
        week_label="next-week",
        target_date_iso="2026-05-04",
    )
    plan = planner.plan(request)
    assert "AI/ML" in plan.markdown
    assert "9:30 PM EST" in plan.markdown


def test_heuristic_fallback_works() -> None:
    planner = MeetingPlanner()
    request = MeetingRequest(
        meeting_title="Deepiri Sync",
        meeting_type="sync",
        team_focus="qa",
        attendees_count=5,
        objectives=["Test"],
        week_label="next-week",
        target_date_iso="2026-05-04",
        render_mode=RenderMode.HEURISTIC,
    )
    plan = planner.plan(request)
    assert plan.render_mode == RenderMode.HEURISTIC
    assert "## Purpose" in plan.markdown
    assert "## Group Round Table" in plan.markdown


def test_schedule_filters_qa() -> None:
    slots = MeetingPlanner._selected_schedule("qa")
    names = [s.team_name for s in slots]
    assert "QA" in names
    assert "AI/ML" not in names
    assert "Frontend" not in names


def test_schedule_returns_all_for_all_teams() -> None:
    slots = MeetingPlanner._selected_schedule("all-teams")
    assert len(slots) == 3
