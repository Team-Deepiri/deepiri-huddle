from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, LoadingIndicator, Markdown, Static

from huddle.chat_agent import ChatAgent


class HuddleTui(App[None]):
    CSS = """
    Screen { background: #0b1020; color: #d9e5ff; }
    #titlebar {
        height: 3;
        background: #111a34;
        color: #c9d6ff;
        border-bottom: heavy #5b7cfa;
        padding: 1 2;
        text-style: bold;
    }
    #main_row { height: 1fr; }
    #left_panel {
        width: 32;
        border: round #5b7cfa;
        background: #101a36;
        padding: 1 1;
        margin-right: 1;
    }
    #right_panel { height: 1fr; }
    #quick_title { color: #a8b9ff; text-style: bold; margin-bottom: 1; }
    .quick_btn { margin-bottom: 1; }
    #chatlog {
        height: 1fr;
        border: round #6f8cff;
        background: #0f1730;
        color: #d9e5ff;
        padding: 1 2;
    }
    #status_row {
        height: 3;
        border: round #3abff8;
        background: #0f1730;
        color: #9ee8ff;
        padding: 0 1;
        align-vertical: middle;
    }
    #status { width: 1fr; }
    #spinner { width: 3; }
    #helpbar { height: 3; color: #9ba9d9; padding: 0 2; }
    Input {
        border: round #5b7cfa;
        background: #101a36;
        color: #ffffff;
    }
    """

    BINDINGS = [("ctrl+c", "quit", "Quit")]

    def __init__(self, agent: ChatAgent) -> None:
        super().__init__()
        self.agent = agent
        self._md: Markdown | None = None
        self._status: Static | None = None
        self._spinner: LoadingIndicator | None = None
        self._input: Input | None = None
        self._transcript = (
            "# deepiri-huddle agent\n\n"
            "- Try quick action buttons on the left\n"
            "- Try: `summarize latest #announcements context`\n\n"
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield Static("Deepiri Huddle Agentic Chat", id="titlebar")
            with Horizontal(id="main_row"):
                with Vertical(id="left_panel"):
                    yield Static("Quick Actions", id="quick_title")
                    yield Button("Next-week QA agenda", id="quick_qa", classes="quick_btn")
                    yield Button("Next-week AI/ML agenda", id="quick_ai", classes="quick_btn")
                    yield Button("Summarize #announcements", id="quick_discord", classes="quick_btn")
                    yield Button("Clear transcript", id="quick_clear", classes="quick_btn")
                with Vertical(id="right_panel"):
                    yield Markdown(self._transcript, id="chatlog")
            with Horizontal(id="status_row"):
                yield Static("Ready", id="status")
                yield LoadingIndicator(id="spinner")
            yield Static("Tips: Ctrl+C quit | Type clear to reset transcript", id="helpbar")
            yield Input(
                placeholder="Ask about meeting plans, blockers, or Discord announcements...",
                id="chat_input",
            )
        yield Footer()

    async def on_mount(self) -> None:
        self._md = self.query_one("#chatlog", Markdown)
        self._status = self.query_one("#status", Static)
        self._spinner = self.query_one("#spinner", LoadingIndicator)
        self._spinner.display = False
        self._input = self.query_one("#chat_input", Input)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if not self._input:
            return
        mapping = {
            "quick_qa": "Build a detailed next-week QA meeting agenda with owner-assigned action items.",
            "quick_ai": "Build a detailed next-week AI/ML meeting agenda with risks and blockers section.",
            "quick_discord": "Summarize the latest #announcements and add them to next week's agenda context.",
            "quick_clear": "clear",
        }
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
            self._transcript = "# deepiri-huddle agent\n\n"
            self._append("_Transcript cleared._")
            return
        self._append(f"**You:** {text}")
        self._set_status("Thinking...")
        if self._spinner:
            self._spinner.display = True
        reply = await asyncio.to_thread(self.agent.reply, text)
        self._append(f"**Agent:**\n{reply}")
        self._set_status("Ready")
        if self._spinner:
            self._spinner.display = False

    def _append(self, text: str) -> None:
        self._transcript += text + "\n\n"
        if self._md:
            self._md.update(self._transcript)

    def _set_status(self, text: str) -> None:
        if self._status:
            self._status.update(text)

