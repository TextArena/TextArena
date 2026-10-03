from rich.markup import escape
import os, re, shutil, time, io, rich, rich.layout
from typing import Dict, Optional, Tuple
from textarena.core import Env, Message, Info, RenderWrapper, State

__all__ = ["SimpleRenderWrapper"]

class SimpleRenderWrapper(RenderWrapper):
    def __init__(
        self,
        env: Env,
        player_names: Optional[Dict[int, str]] = None,
        render_mode: str = "multi",
        record_dir: Optional[str] = None,
        record_only: bool = False,
        record_size: Tuple[int, int] = (168, 45)
    ):
        super().__init__(env)
        self.player_names = player_names
        self.render_mode = render_mode
        assert render_mode in ["standard", "board", "chat", "multi"], \
            f"The selected render_mode does not exist. The available options are:" +\
            f"\n\t'standard' - view both the game board and model chats"+\
            f"\n\t'board' - view just the game board"+\
            f"\n\t'chat' - view just the model chats side-by-side"+\
            f"\n\t'multi' - view the game board and a combined chat window"

        self.record_dir = record_dir
        self.record_only = record_only
        self.record_size = record_size
        self.frame_idx = 0
        if self.record_dir:
            os.makedirs(self.record_dir, exist_ok=True)

        if self.record_only:
            # Render off-screen at a fixed size so every frame has identical
            # dimensions regardless of the actual terminal.
            self.console = rich.console.Console(
                record=True,
                file=io.StringIO(),
                width=record_size[0],
                height=record_size[1],
            )
        else:
            self.console = rich.console.Console(record=bool(record_dir))

    def _terminal_size(self):
        # When recording off-screen, shutil reports the real terminal,
        # which may not match the fixed console size — use the console's.
        if self.record_only:
            return os.terminal_size(self.record_size)
        return shutil.get_terminal_size()

    def _render(self, action, acting_player_id):
        board = self.env.get_board_str() if hasattr(self.env, "get_board_str") and callable(getattr(self.env, "get_board_str")) else None
        logs = getattr(self.env.state, "logs", [])
        board = f"No game board provided by {self.env.env_id}\n(not implemented / not available)" if board is None else board
        board_panel = rich.panel.Panel.fit(escape(board), title="Game Board", border_style="white", box=rich.box.SQUARE)
 
        # Separate logs by player
        logs_by_player = {}
        for pid, msg in logs:
            logs_by_player.setdefault(pid, []).append(msg)
 
        def get_message_text(pid, mode="standard", include_name=False):
            name = self.player_names.get(pid, f"Player {pid}")
            message_list = logs_by_player.get(pid, [])
            message = "(no message yet)" if not len(message_list) else message_list[-1].strip()
 
            terminal_size = self._terminal_size()
            if mode == "standard":
                max_chars = (terminal_size.columns/2-2)*(terminal_size.lines/3-3)
            elif mode == "chat":
                max_chars = (terminal_size.columns/2-2)*(terminal_size.lines-3)
            elif mode == "multi":
                # pid is the acting player (captured before the env rotated),
                # so the name from the top of this function is already correct.
                max_chars = (terminal_size.columns-2)*(terminal_size.lines/3-3)
                message = action
 
            message = message[-int(max_chars-len(name)-3):]  # truncate message
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
            layout["bottom"].update(get_message_text(acting_player_id, "multi"))
 
        if not self.record_only:
            self.console.clear()
        self.console.print(layout)
 
        # save this frame
        if self.record_dir:
            self.console.save_svg(
                os.path.join(self.record_dir, f"frame_{self.frame_idx:04d}.svg"),
                clear=True,   # reset the record buffer -> one frame per file
                title="",
            )
            self.frame_idx += 1
            if self.record_only:
                # Also reset the StringIO so it doesn't grow forever
                self.console.file.seek(0)
                self.console.file.truncate(0)

    def reset(self, num_players: int, seed: Optional[int] = None, lang_mapping: Optional[Dict[int, str]] = None) -> None:
        result = self.env.reset(num_players=num_players, seed=seed, lang_mapping=lang_mapping)
        self.state = self.env.state
        if self.player_names is None:
            self.player_names = {pid: f"Player {pid}" for pid in range(self.state.num_players)}
        self.player_names.update(self.state.role_mapping)
        self.game_over = False

        # assert render mode with num players
        if self.render_mode in ["standard", "chat"]:
            assert num_players == 2, f"render_modes 'standard' and 'chat' can only be used with two players"
        return result

    def step(self, action: str) -> Tuple[bool, Optional[Info]]:
        active_player_id = self.env.state.current_player_id
        step_results = self.env.step(action=action)
        time.sleep(0.2)
        self._render(action, active_player_id)
        time.sleep(0.2)
        return step_results

    def close(self):
        return self.env.close()