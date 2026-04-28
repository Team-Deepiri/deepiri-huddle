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
                yield Button("copy", id="quick_copy", classes="quick_btn")
                yield Button("clear", id="quick_clear", classes="quick_btn")
            yield RichLog(id="chatlog", auto_scroll=True, markup=False, wrap=True)
            with Horizontal(id="status_row"):
                yield Static("Ready", id="status")
                yield LoadingIndicator(id="spinner")
            yield Input(
                placeholder="Type message and press Enter...",
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
        self._append("- Try quick action buttons on the left")
        self._append("- Try: summarize latest #announcements context")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if not self._input:
            return
        mapping = {
            "quick_qa": "Build a detailed next-week QA meeting agenda with owner-assigned action items.",
            "quick_ai": "Build a detailed next-week AI/ML meeting agenda with risks and blockers section.",
            "quick_discord": "Summarize the latest #announcements and add them to next week's agenda context.",
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
        self._append(f"You: {text}")
        self._set_status("Thinking...")
        if self._spinner:
            self._spinner.display = True
        try:
            reply = await asyncio.to_thread(self.agent.reply, text)
            self._append(f"Agent: {reply}")
        except Exception as exc:  # noqa: BLE001
            self._append(f"Agent error: {exc}")
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
            except Exception:  # noqa: BLE001
                continue
        return False

