from rich.markup import escape
import io, os, shutil, time, rich, rich.layout
from typing import Dict, Optional, Tuple
from textarena.core import Env, Info, RenderWrapper

__all__ = ["SimpleRenderWrapper"]

class SimpleRenderWrapper(RenderWrapper):
    def __init__(
        self,
        env: Env,
        player_names: Optional[Dict[int, str]] = None,
        render_mode: str = "multi",
        record_dir: Optional[str] = None,
        record_only: bool = False,
        record_size: Tuple[int, int] = (168, 45),
    ):
        """
        Args:
            record_dir: If set, every rendered frame is also saved as ``frame_XXXX.svg`` in this directory.
            record_only: Render off-screen at ``record_size`` (columns, lines) instead of drawing to the
                terminal, so every recorded frame has identical dimensions. Requires ``record_dir``.
        """
        super().__init__(env)
        self.player_names = player_names
        self.render_mode = render_mode
        assert render_mode in ["standard", "board", "chat", "multi"], \
            f"The selected render_mode does not exist. The available options are:" +\
            f"\n\t'standard' - view both the game board and model chats"+\
            f"\n\t'board' - view just the game board"+\
            f"\n\t'chat' - view just the model chats side-by-side"+\
            f"\n\t'multi' - view the game board and a combined chat window"
        if record_only and not record_dir:
            raise ValueError("record_only=True requires a record_dir to save frames to")
        self.record_dir = record_dir
        self.record_only = record_only
        self.record_size = record_size
        self.frame_idx = 0
        if record_dir:
            os.makedirs(record_dir, exist_ok=True)
        if record_only:
            columns, lines = record_size
            self.console = rich.console.Console(record=True, file=io.StringIO(), width=columns, height=lines)
        else:
            self.console = rich.console.Console(record=bool(record_dir))

    def _terminal_size(self) -> os.terminal_size:
        # Off-screen frames must be laid out for the fixed console size, not the real terminal.
        if self.record_only:
            return os.terminal_size(self.record_size)
        return shutil.get_terminal_size()

    @staticmethod
    def _public_logs(state):
        """Return only events visible to every player; never expose whispers."""
        return [
            (from_id, message)
            for from_id, message, _observation_type, to_id in getattr(state, "events", [])
            if to_id == -1
        ]

    def _render(self, action):
        board = self.env.get_board_str() if hasattr(self.env, "get_board_str") and callable(getattr(self.env, "get_board_str")) else None
        logs = self._public_logs(self.env.state)
        board = f"No game board provided by {self.env.env_id}\n(not implemented / not available)" if board is None else board
        # Boards may already be rich renderables (e.g. coloured Text); only plain strings need markup escaping.
        board_panel = rich.panel.Panel.fit(escape(board) if isinstance(board, str) else board, title="Game Board", border_style="white", box=rich.box.SQUARE)

        # Separate logs by player
        logs_by_player = {}
        for pid, msg in logs:
            logs_by_player.setdefault(pid, []).append(msg)


        def get_message_text(pid, mode="standard", include_name=False):
            name = self.player_names.get(pid, f"Player {pid}")
            message_list = logs_by_player.get(pid, [])
            message = "(no message yet)" if not len(message_list) else message_list[-1].strip()

            terminal_size = self._terminal_size()
            if mode=="standard":
                max_chars = (terminal_size.columns/2-2)*(terminal_size.lines/3-3)
            elif mode=="chat":
                max_chars = (terminal_size.columns/2-2)*(terminal_size.lines-3)
            elif mode=="multi":
                max_chars = (terminal_size.columns-2)*(terminal_size.lines/3-3)
                if logs:
                    sender_id, message = logs[-1]
                    name = self.player_names.get(sender_id, f"Player {sender_id}")
                else:
                    name = "Public game log"
                    message = "(no public message yet)"
            
            message = message[-int(max_chars-len(name)-3):] # truncate message
            return rich.panel.Panel(rich.text.Text(f"[{name}] {message}" if include_name else message, no_wrap=False, overflow="fold"), title=name, border_style="white")

        # Setup layout
        layout = rich.layout.Layout()

        if self.render_mode == "standard":
            layout.split_column(rich.layout.Layout(name="spacer", size=1), rich.layout.Layout(name="top", ratio=2), rich.layout.Layout(name="bottom", ratio=1))
            layout["top"].update(rich.align.Align.center(board_panel, vertical="middle"))
            layout["bottom"].split_row(rich.layout.Layout(name="chat0"), rich.layout.Layout(name="chat1"))
            layout["chat0"].update(get_message_text(0, "standard"))
            layout["chat1"].update(get_message_text(1, "standard"))

        elif self.render_mode == "board":
            layout.update(rich.align.Align.center(board_panel, vertical="middle"))

        elif self.render_mode == "chat":
            layout.split_column(rich.layout.Layout(name="spacer", size=1), rich.layout.Layout(name="chats", ratio=1))
            layout["chats"].split_row(rich.layout.Layout(name="chat0"), rich.layout.Layout(name="chat1"))
            layout["chat0"].update(get_message_text(0, "chat"))
            layout["chat1"].update(get_message_text(1, "chat"))

        elif self.render_mode == "multi":
            layout.split_column(rich.layout.Layout(name="spacer", size=1), rich.layout.Layout(name="top", ratio=4), rich.layout.Layout(name="bottom", ratio=1))
            layout["top"].update(rich.align.Align.center(board_panel, vertical="middle"))
            layout["bottom"].update(get_message_text(None, "multi"))

        if not self.record_only:
            self.console.clear()
        self.console.print(layout)

        if self.record_dir:
            path = os.path.join(self.record_dir, f"frame_{self.frame_idx:04d}.svg")
            self.console.save_svg(path, clear=True, title="")
            self.frame_idx += 1
            if self.record_only:
                self.console.file.seek(0)
                self.console.file.truncate(0)

    def reset(self, num_players: Optional[int] = None, seed: Optional[int] = None) -> None:
        result = self.env.reset(num_players=num_players, seed=seed)
        self.state = self.env.state
        if self.player_names is None:
            self.player_names = {pid: f"Player {pid}" for pid in range(self.state.num_players)}
        self.player_names.update(self.state.role_mapping)
        self.game_over = False

        # assert render mode with num players
        if self.render_mode in ["standard", "chat"]:
            assert num_players==2, f"render_modes 'standard' and 'chat' can only be used with two players"
        return result

    def step(self, action: str) -> Tuple[bool, Optional[Info]]:
        step_results = self.env.step(action=action)
        if self.record_only:
            self._render(action)
            return step_results
        time.sleep(0.2)
        self._render(action)
        time.sleep(0.2)
        return step_results

    def close(self):
        return self.env.close()