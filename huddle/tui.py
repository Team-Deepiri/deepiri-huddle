from __future__ import annotations

import asyncio
import shutil
import subprocess

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, LoadingIndicator, RichLog, Static

from huddle.chat_agent import ChatAgent


class HuddleTui(App[None]):
    CSS = """
    Screen { background: #0b1020; color: #d9e5ff; }
    #titlebar {
        height: 1;
        background: #111a34;
        color: #c9d6ff;
        border-bottom: solid #5b7cfa;
        padding: 0 1;
        text-style: bold;
    }
    #quick_row {
        height: 1;
        padding: 0 0;
    }
    .quick_btn {
        margin-right: 0;
        border: none;
        background: #101a36;
        color: #a8b9ff;
        min-width: 1;
    }
    #chatlog {
        height: 1fr;
        border: round #6f8cff;
        background: #0f1730;
        color: #d9e5ff;
        padding: 0 0;
    }
    #status_row {
        height: 1;
        border-top: solid #3abff8;
        background: #0f1730;
        color: #9ee8ff;
        padding: 0 0;
        align-vertical: middle;
    }
    #status { width: 1fr; }
    #spinner { width: 3; }
    #helpbar { display: none; }
    Input {
        height: 3;
        border: round #5b7cfa;
        background: #101a36;
        color: #ffffff;
        padding: 0 1;
    }
    """

    BINDINGS = [("ctrl+c", "quit", "Quit")]

    def __init__(self, agent: ChatAgent) -> None:
        super().__init__()
        self.agent = agent
        self._log: RichLog | None = None
        self._status: Static | None = None
        self._spinner: LoadingIndicator | None = None
        self._input: Input | None = None
        self._plain_log_lines: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Deepiri Huddle Chat", id="titlebar")
            with Horizontal(id="quick_row"):
                yield Button("QA", id="quick_qa", classes="quick_btn")
                yield Button("AI/ML", id="quick_ai", classes="quick_btn")
                yield Button("#announcements", id="quick_discord", classes="quick_btn")
                yield Button("/git", id="quick_git", classes="quick_btn")
                yield Button("/docs", id="quick_docs", classes="quick_btn")
                yield Button("/risks", id="quick_risks", classes="quick_btn")
                yield Button("copy", id="quick_copy", classes="quick_btn")
                yield Button("clear", id="quick_clear", classes="quick_btn")
            yield RichLog(id="chatlog", auto_scroll=True, markup=False, wrap=True)
            with Horizontal(id="status_row"):
                yield Static("Ready", id="status")
                yield LoadingIndicator(id="spinner")
            yield Input(
                placeholder="Type message and press Enter... (/git, /docs, /risks)",
                id="chat_input",
            )

    async def on_mount(self) -> None:
        self._log = self.query_one("#chatlog", RichLog)
        self._status = self.query_one("#status", Static)
        self._spinner = self.query_one("#spinner", LoadingIndicator)
        self._spinner.display = False
        self._input = self.query_one("#chat_input", Input)
        self._input.focus()
        self._append("deepiri-huddle agent")
        self._append("- Try quick action buttons or slash commands:")
        self._append("  /git    — recent commits and activity")
        self._append("  /docs   — documents found in repos")
        self._append("  /risks  — heuristic risk analysis")
        self._append("  /plan   — generate a quick meeting plan")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if not self._input:
            return
        mapping = {
            "quick_qa": "Build a next-week QA meeting agenda with owner-assigned action items.",
            "quick_ai": "Build a next-week AI/ML meeting agenda with risks and blockers section.",
            "quick_discord": "Summarize #announcements and add to next week's agenda.",
            "quick_git": "/git",
            "quick_docs": "/docs",
            "quick_risks": "/risks",
            "quick_clear": "clear",
        }
        if event.button.id == "quick_copy":
            copied = self._copy_transcript_to_clipboard()
            self._set_status("Transcript copied" if copied else "Clipboard unavailable")
            return
        text = mapping.get(event.button.id or "", "")
        if not text:
            return
        self._input.value = text
        self._input.focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        if text.lower() == "clear":
            if self._log:
                self._log.clear()
            self._plain_log_lines.clear()
            self._append("Transcript cleared.")
            return

        if text.lower() == "/git":
            await self._cmd_git()
            return
        if text.lower() == "/docs":
            await self._cmd_docs()
            return
        if text.lower() == "/risks":
            await self._cmd_risks()
            return
        if text.lower().startswith("/plan"):
            await self._cmd_plan(text)
            return

        self._append(f"You: {text}")
        self._set_status("Thinking...")
        if self._spinner:
            self._spinner.display = True
        try:
            reply = await asyncio.to_thread(self.agent.reply, text)
            self._append(f"Agent: {reply}")
        except Exception as exc:
            self._append(f"Agent error: {exc}")
        self._set_status("Ready")
        if self._spinner:
            self._spinner.display = False

    async def _cmd_git(self) -> None:
        self._append("Fetching recent git activity...")
        self._set_status("Running git log...")
        if self._spinner:
            self._spinner.display = True
        try:
            from huddle.gitlog import gather_context

            ctx = await asyncio.to_thread(gather_context, days=7)
            if ctx and ctx.commits:
                self._append(f"Repo: {ctx.repo_root}")
                self._append(f"Commits (last 7d): {len(ctx.commits)}")
                self._append("")
                for a in ctx.authors[:6]:
                    self._append(f"  {a.author}: {a.commit_count} commits")
                    for s in a.subjects[:3]:
                        self._append(f"    - {s[:80]}")
                if ctx.silent_authors:
                    self._append(f"  Silent: {', '.join(ctx.silent_authors[:3])}")
            else:
                self._append("No git history available.")
        except Exception as exc:
            self._append(f"Git error: {exc}")
        self._set_status("Ready")
        if self._spinner:
            self._spinner.display = False

    async def _cmd_docs(self) -> None:
        self._append("Scanning repos for documents...")
        self._set_status("Scanning docs...")
        if self._spinner:
            self._spinner.display = True
        try:
            from huddle.docfinder import scan_docs

            ctx = await asyncio.to_thread(scan_docs)
            if ctx.docs:
                self._append(f"Repos: {', '.join(ctx.repos)}")
                self._append(f"Documents found: {len(ctx.docs)}")
                self._append("")
                for d in ctx.docs[:6]:
                    self._append(f"  [{d.repo}] {d.title} ({d.word_count} words)")
                if ctx.recent_changes:
                    self._append("")
                    for c in ctx.recent_changes[:3]:
                        self._append(f"  Changed: {c['commit'][:60]}")
            else:
                self._append("No documents found. Set HUDDLE_REPOS or place repos as siblings.")
        except Exception as exc:
            self._append(f"Doc scan error: {exc}")
        self._set_status("Ready")
        if self._spinner:
            self._spinner.display = False

    async def _cmd_risks(self) -> None:
        self._append("Running heuristic risk detection...")
        self._set_status("Analyzing risks...")
        if self._spinner:
            self._spinner.display = True
        try:
            from huddle.gitlog import gather_context
            from huddle.risks import detect_risks, format_risks_markdown

            ctx = await asyncio.to_thread(gather_context, days=7)
            if ctx:
                risks = await asyncio.to_thread(detect_risks, ctx)
                if risks:
                    md = await asyncio.to_thread(format_risks_markdown, risks)
                    for line in md.split("\n"):
                        if line.strip():
                            self._append(line)
                else:
                    self._append("No significant risks detected from git activity.")
            else:
                self._append("No git context available for risk detection.")
        except Exception as exc:
            self._append(f"Risk detection error: {exc}")
        self._set_status("Ready")
        if self._spinner:
            self._spinner.display = False

    async def _cmd_plan(self, text: str) -> None:
        parts = text.split(None, 1)
        team = "all-teams"
        if len(parts) > 1:
            team = parts[1].strip().lower()
        self._append(f"Generating {team} plan with git/doc context...")
        self._set_status("Planning...")
        if self._spinner:
            self._spinner.display = True
        try:
            from huddle.models import MeetingRequest
            from huddle.planner import MeetingPlanner

            planner = MeetingPlanner(no_llm_fallback=False)
            req = MeetingRequest(
                meeting_title="Quick Huddle Plan",
                meeting_type="sync",
                team_focus=team,
                attendees_count=10,
                objectives=["Sync on recent work and blockers"],
                week_label="current-week",
                target_date_iso="today",
            )
            plan = await asyncio.to_thread(planner.plan, req)
            for line in plan.markdown.split("\n")[:30]:
                if line.strip():
                    self._append(line)
            self._append(f"\n[Rendered: {plan.render_mode.value}, provider: {plan.provider_used}]")
        except Exception as exc:
            self._append(f"Plan error: {exc}")
        self._set_status("Ready")
        if self._spinner:
            self._spinner.display = False

    def _append(self, text: str) -> None:
        if self._log:
            self._log.write(text)
        self._plain_log_lines.append(text)

    def _set_status(self, text: str) -> None:
        if self._status:
            self._status.update(text)

    def _copy_transcript_to_clipboard(self) -> bool:
        payload = "\n".join(self._plain_log_lines).strip()
        if not payload:
            return False
        commands = [
            ["wl-copy"],
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
            ["clip.exe"],
            ["pbcopy"],
        ]
        for cmd in commands:
            if not shutil.which(cmd[0]):
                continue
            try:
                subprocess.run(cmd, input=payload, text=True, check=True)
                return True
            except Exception:
                continue
        return False
