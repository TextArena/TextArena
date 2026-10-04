import re
from typing import Any, Dict, List, Optional, Union

import textarena as ta


class TwoRoomsAndABoomEnv(ta.GameEnv):
    """
    Two Rooms and a Boom game environment for the textarena framework.

    A social deduction game where players are split between two teams (Red and Blue) and
    placed in two different rooms. The Red Team aims to get the Bomber and President in
    the same room by the end, while the Blue Team wants to keep them in different rooms.
    """

    min_players = 6  # Absolute minimum for gameplay
    max_players = 20  # Reasonable maximum for communication

    # Support bare 'Player X' / 'X' selections, tolerating optional stray brackets
    target_pattern = re.compile(r'^\s*\[?\s*(?:player\s*)?(\d+)\s*\]?\s*$', re.IGNORECASE)
    # Only a discussion reply consisting of exactly this command starts a role reveal;
    # every other reply, even one mentioning reveals or roles, is ordinary discussion.
    reveal_command_pattern = re.compile(r"\s*reveal\s*", re.IGNORECASE)

    # Maximum number of role reveals per player per game
    MAX_REVEALS_PER_PLAYER = 5

    # Maximum message history per room
    MAX_MESSAGE_HISTORY = 200

    # Maximum number of automatic phase transitions in a single turn hand-off
    MAX_RECURSION_DEPTH = 10

    # Role definitions with team affiliations and descriptions
    ROLES = {
        "Red": {
            "team": "Red Team",
            "description": "Member of the Red Team. Your goal is to make sure the Bomber and President are in the same room at the end of the game."
        },
        "Blue": {
            "team": "Blue Team",
            "description": "Member of the Blue Team. Your goal is to make sure the Bomber and President are in different rooms at the end of the game."
        },
        "Bomber": {
            "team": "Red Team",
            "description": "You are the Bomber on the Red Team. Your goal is to be in the same room as the President at the end of the game."
        },
        "President": {
            "team": "Blue Team",
            "description": "You are the President on the Blue Team. Your goal is to be in a different room from the Bomber at the end of the game."
        }
    }

    def __init__(self, num_rounds: int = 3, cards_per_room: int = 3, discussion_rounds: int = 2):
        """
        Initialize the Two Rooms and a Boom environment.

        Args:
            num_rounds (int): Number of rounds to play (default: 3)
            cards_per_room (int): Number of cards to initially place in each room (default: 3)
            discussion_rounds (int): Number of discussion turns per player per round (default: 2)
        """
        if isinstance(num_rounds, bool) or not isinstance(num_rounds, int) or num_rounds < 1:
            raise ValueError("num_rounds must be a positive integer")
        if (
            isinstance(cards_per_room, bool)
            or not isinstance(cards_per_room, int)
            or not self.min_players // 2 <= cards_per_room <= self.max_players // 2
        ):
            raise ValueError("cards_per_room must be an integer between 3 and 10")
        if (
            isinstance(discussion_rounds, bool)
            or not isinstance(discussion_rounds, int)
            or discussion_rounds < 0
        ):
            raise ValueError("discussion_rounds must be a non-negative integer")

        # Game configuration parameters
        self.num_rounds = num_rounds
        self.cards_per_room = cards_per_room
        self.discussion_rounds = discussion_rounds

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        # Actions are never echoed globally: discussion messages are routed only to
        # the speaker's room by the game logic itself (see _handle_discussion).
        return None

    def setup(self) -> Dict[str, Any]:
        num_players = self.state.num_players
        expected_players = self.cards_per_room * 2
        if num_players != expected_players:
            raise ValueError(
                f"cards_per_room={self.cards_per_room} requires exactly "
                f"{expected_players} players, received {num_players}"
            )

        # Assign roles and distribute players into the two rooms
        player_roles, rooms, leaders = self._assign_roles_and_rooms(num_players)
        for pid, role in player_roles.items():
            self.set_role(pid, role)

        # Store initial room assignments for reference
        original_room_assignments = {}
        for room_idx, room_players in enumerate(rooms):
            for pid in room_players:
                original_room_assignments[pid] = room_idx

        return {
            "round": 1,
            "current_phase": "Discussion",
            "rooms": rooms,
            "player_roles": player_roles,
            "leaders": leaders,
            "hostages_to_trade": {},
            "message_history": {},  # Track message history per room
            "revealed_roles": {i: [] for i in range(num_players)},  # Which roles each player has seen
            "reveal_counts": {i: 0 for i in range(num_players)},  # Count reveals per player
            "original_room_assignments": original_room_assignments,
            "team_discussions": {},  # Private team discussions
            "revealing_player": None,  # To track who initiated a role reveal
            "paused_discussion_player_ids": None,
            "next_player_ids": [],  # Turn-order queue for the current phase
        }

    def on_start(self):
        # Start with Discussion phase
        self._phase_transition_player_prompts(new_phase="Discussion")
        self._transition_current_pid(immediate=True)

        # Final validation after initialization
        self._validate_game_state()

    def _validate_game_state(self):
        """Validate game state without mutating it."""
        gs = self.game_state
        required_keys = {
            "rooms", "player_roles", "leaders", "hostages_to_trade",
            "revealed_roles", "reveal_counts", "current_phase",
            "next_player_ids", "message_history", "round",
            "revealing_player", "paused_discussion_player_ids",
        }
        missing_keys = required_keys - set(gs)
        if missing_keys:
            raise ValueError(f"missing game-state keys: {sorted(missing_keys)}")

        rooms = gs["rooms"]
        if not isinstance(rooms, list) or len(rooms) != 2 or not all(isinstance(room, list) for room in rooms):
            raise ValueError("rooms must contain exactly two player lists")

        expected_players = set(range(self.state.num_players))
        assigned_players = rooms[0] + rooms[1]
        if (
            len(assigned_players) != self.state.num_players
            or any(type(pid) is not int for pid in assigned_players)
            or set(assigned_players) != expected_players
        ):
            raise ValueError("every player must be assigned to exactly one room")

        roles = gs["player_roles"]
        if not isinstance(roles, dict) or set(roles) != expected_players:
            raise ValueError("player_roles must contain every player exactly once")
        if any(not isinstance(role, str) or role not in self.ROLES for role in roles.values()):
            raise ValueError("player_roles contains an unknown role")
        if list(roles.values()).count("President") != 1 or list(roles.values()).count("Bomber") != 1:
            raise ValueError("player_roles must contain exactly one President and one Bomber")

        leaders = gs["leaders"]
        if not isinstance(leaders, list) or len(leaders) != 2:
            raise ValueError("leaders must contain exactly two entries")
        for room_idx, leader in enumerate(leaders):
            if leader not in rooms[room_idx]:
                raise ValueError(f"Room {room_idx} leader must be in that room")

        next_player_ids = gs["next_player_ids"]
        if (
            not isinstance(next_player_ids, list)
            or any(type(pid) is not int or pid not in expected_players for pid in next_player_ids)
        ):
            raise ValueError("turn queue contains an unknown player")

        current_phase = gs["current_phase"]
        if (
            not isinstance(current_phase, str)
            or current_phase not in {"Discussion", "Role_Reveal", "Leader_Selection", "Trade_Execution"}
        ):
            raise ValueError("current_phase is not recognized")

        hostages = gs["hostages_to_trade"]
        if (
            not isinstance(hostages, dict)
            or any(room_idx not in (0, 1) for room_idx in hostages)
            or any(type(pid) is not int or pid not in expected_players for pid in hostages.values())
        ):
            raise ValueError("hostages_to_trade contains an invalid selection")

        revealed_roles = gs["revealed_roles"]
        if (
            not isinstance(revealed_roles, dict)
            or set(revealed_roles) != expected_players
            or any(not isinstance(seen, list) for seen in revealed_roles.values())
            or any(
                type(pid) is not int or pid not in expected_players
                for seen in revealed_roles.values()
                if isinstance(seen, list)
                for pid in seen
            )
        ):
            raise ValueError("revealed_roles is invalid")

        reveal_counts = gs["reveal_counts"]
        if (
            not isinstance(reveal_counts, dict)
            or set(reveal_counts) != expected_players
            or any(type(count) is not int or count < 0 for count in reveal_counts.values())
        ):
            raise ValueError("reveal_counts is invalid")

        if not isinstance(gs["message_history"], dict):
            raise ValueError("message_history must be a dictionary")
        if type(gs["round"]) is not int or gs["round"] < 1:
            raise ValueError("round must be a positive integer")

        revealing_player = gs["revealing_player"]
        if revealing_player is not None and (
            type(revealing_player) is not int or revealing_player not in expected_players
        ):
            raise ValueError("revealing_player is invalid")

        paused_queue = gs["paused_discussion_player_ids"]
        if paused_queue is not None and (
            not isinstance(paused_queue, list)
            or any(type(pid) is not int or pid not in expected_players for pid in paused_queue)
        ):
            raise ValueError("paused discussion queue is invalid")

    def _assign_roles_and_rooms(self, num_players: int):
        """
        Assign roles to players and distribute them into two rooms,
        ensuring initial role separation for fairness.

        Args:
            num_players (int): Number of players in the game
        """
        player_roles = {}
        rooms = [[], []]  # Two rooms
        leaders = [None, None]  # Leaders for each room

        # Calculate team sizes (roughly equal)
        half_players = num_players // 2
        red_team_size = half_players
        blue_team_size = num_players - red_team_size

        # Create player roles with appropriate team balance
        role_pool = ["Red"] * red_team_size + ["Blue"] * blue_team_size

        # Assign special roles (President and Bomber)
        blue_indices = [i for i, role in enumerate(role_pool) if role == "Blue"]
        red_indices = [i for i, role in enumerate(role_pool) if role == "Red"]

        # Randomly select one Blue team member to be President
        president_idx = self.rng.choice(blue_indices)
        role_pool[president_idx] = "President"

        # Randomly select one Red team member to be Bomber
        bomber_idx = self.rng.choice(red_indices)
        role_pool[bomber_idx] = "Bomber"

        # Randomize the complete role pool so player IDs do not reveal team membership.
        self.rng.shuffle(role_pool)

        # Assign the randomized roles to player IDs.
        for i in range(num_players):
            player_roles[i] = role_pool[i]

        # Find the President and Bomber IDs after direct assignment
        president_id = None
        bomber_id = None
        for pid, role in player_roles.items():
            if role == "President":
                president_id = pid
            elif role == "Bomber":
                bomber_id = pid

        # Ensure both special roles were assigned
        if president_id is None or bomber_id is None:
            raise ValueError("Failed to assign special roles properly")

        # Initially distribute players to rooms - ensuring President and Bomber in different rooms
        all_players = list(range(num_players))
        self.rng.shuffle(all_players)

        # Remove President and Bomber from initial list to place them separately
        all_players.remove(president_id)
        all_players.remove(bomber_id)

        # Calculate balanced room sizes (adjusting for President and Bomber)
        room0_size = (num_players - 2) // 2

        # Distribute regular players
        rooms[0] = all_players[:room0_size]
        rooms[1] = all_players[room0_size:]

        # Add President to Room 0 and Bomber to Room 1 (initial separation)
        rooms[0].append(president_id)
        rooms[1].append(bomber_id)

        # Additional shuffle to mix positions in room
        self.rng.shuffle(rooms[0])
        self.rng.shuffle(rooms[1])

        # Assign leaders for each room, avoiding special roles if possible
        for room_idx in range(2):
            # Prefer regular players as leaders
            regular_players = [pid for pid in rooms[room_idx]
                               if player_roles[pid] not in ["President", "Bomber"]]

            if regular_players:
                leaders[room_idx] = self.rng.choice(regular_players)
            else:
                # If no regular players, assign any player from the room
                leaders[room_idx] = self.rng.choice(rooms[room_idx])

        return player_roles, rooms, leaders

    def prompt(self, player_id: int) -> str:
        """
        Generate the initial prompt for each player, including their role and objectives

        Args:
            player_id (int): The player's ID

        Returns:
            str: Personalized prompt for the player
        """
        game_state = self.game_state
        # Get player's role and team info
        role = game_state["player_roles"][player_id]
        role_info = self.ROLES[role]

        # Determine which room the player is in
        player_room = None
        if player_id in game_state["rooms"][0]:
            player_room = 0
        elif player_id in game_state["rooms"][1]:
            player_room = 1
        else:
            # Failsafe for missing room assignment
            player_room = "unknown"

        # Leadership is public knowledge within a room
        is_leader = player_id in game_state["leaders"]
        if is_leader:
            leader_status = "You are the Leader of your room."
        elif player_room in (0, 1):
            leader_status = f"The Leader of your room is Player {game_state['leaders'][player_room]}."
        else:
            leader_status = ""

        # Basic prompt for all players
        prompt = (
            f"Welcome to Two Rooms and a Boom! You are Player {player_id}.\n"
            f"Your role: {role}\n"
            f"Team: {role_info['team']}\n"
            f"Description: {role_info['description']}\n\n"
            f"You are currently in Room {player_room}.\n"
            f"{leader_status}\n\n"
            f"The game progresses through {self.num_rounds} rounds:\n"
            f"• In each round, players in the same room can talk to each other\n"
            f"• Each room has a Leader, known to everyone in that room, who chooses one player to trade to the other room\n"
            f"• During discussions, you can choose to privately reveal your card to another player\n"
            f"• At the end of all rounds, the game checks which room contains the President and Bomber\n\n"
            f"The Red Team wins if the President and Bomber are in the same room at the end.\n"
            f"The Blue Team wins if the President and Bomber are in different rooms at the end.\n\n"
        )

        # Add role-specific information
        if role == "Bomber":
            prompt += (
                "As the Bomber, you are a crucial member of the Red Team.\n"
                "Your goal is to end up in the same room as the President.\n"
                "You may choose whether to reveal your identity to others or keep it secret.\n\n"
            )
        elif role == "President":
            prompt += (
                "As the President, you are a crucial member of the Blue Team.\n"
                "Your goal is to end up in a different room from the Bomber.\n"
                "You may choose whether to reveal your identity to others or keep it secret.\n\n"
            )

        # Add leader-specific information
        if is_leader:
            prompt += (
                "As a Room Leader, you have special responsibilities:\n"
                "• You'll choose one player from your room to trade with the other room\n"
                "• You'll receive information from other players in your room\n"
                "• Use this information to make strategic decisions for your team\n"
                "• Leaders cannot trade themselves to the other room\n\n"
            )

        # Add information about revealing roles
        prompt += (
            "Role Revealing:\n"
            "• To reveal your role, reply with exactly 'reveal' (and nothing else) on your discussion turn\n"
            "• The game will then ask which player in your room to reveal it to; reply with their number\n"
            "• Any other reply, even one that mentions revealing or roles, is sent to your room as discussion\n"
            f"• You can reveal your role up to {self.MAX_REVEALS_PER_PLAYER} times per game\n"
            "• This is a way to build trust, but be careful who you reveal to!\n\n"
        )

        # Add information about team coordination
        prompt += (
            f"Team Coordination:\n"
            f"• When you're with teammates, strategize on how to achieve your team's goal\n"
            f"• Blue team wants President and Bomber in different rooms\n"
            f"• Red team wants President and Bomber in the same room\n"
        )

        return prompt

    def _phase_transition_player_prompts(self, new_phase) -> Optional[ta.Outcome]:
        """
        During a phase transition, provide relevant prompts to all players
        and update game state.

        Returns an Outcome if the transition ends the game (final trade executed).

        Args:
            new_phase (str): The new game phase to transition to
        """
        gs = self.game_state
        # Validate game state before any phase transition to catch issues early
        self._validate_game_state()

        if new_phase == "Discussion":
            # Reset any role reveal state
            gs["revealing_player"] = None
            gs["paused_discussion_player_ids"] = None

            # All players in each room can discuss with each other
            for room_idx, room_players in enumerate(gs["rooms"]):
                # Skip empty rooms
                if not room_players:
                    continue

                # Initialize message history for this room if not present
                if str(room_idx) not in gs["message_history"]:
                    gs["message_history"][str(room_idx)] = []

                # Create a player list string
                player_list = ", ".join([f"Player {pid}" for pid in room_players])
                room_leader = gs["leaders"][room_idx]

                # List roles that have been revealed to each player
                for pid in room_players:
                    revealed_roles = []
                    for revealed_pid in gs["revealed_roles"].get(pid, []):
                        role = gs["player_roles"][revealed_pid]
                        revealed_roles.append(f"Player {revealed_pid}: {role}")

                    # Build previous messages summary if any exist
                    previous_messages = ""
                    if gs["message_history"].get(str(room_idx)):
                        previous_messages = "\nPrevious discussions in this room:\n"
                        # Only replay messages this player actually witnessed.
                        visible_messages = [
                            msg for msg in gs["message_history"][str(room_idx)]
                            if pid in msg.get("visible_to", ())
                        ]
                        recent_messages = visible_messages[-10:]
                        for msg in recent_messages:
                            previous_messages += f"Player {msg['from']}: {msg['message']}\n"
                        if not recent_messages:
                            previous_messages = ""

                    # Create the discussion observation
                    if pid == room_leader:
                        leader_line = "You are the Leader of this room.\n"
                    elif room_leader is not None:
                        leader_line = f"The Leader of this room is Player {room_leader}.\n"
                    else:
                        leader_line = ""
                    discussion_observation = (
                        f"Round {gs['round']}: Discussion phase has started.\n"
                        f"You are in Room {room_idx} with: {player_list}.\n"
                        f"{leader_line}"
                        f"You can talk freely with the other players in your room.\n"
                        f"To reveal your role to someone, reply with exactly 'reveal' on your turn; "
                        f"any other reply is sent to your room.\n"
                    )

                    # Add revealed roles if any
                    if revealed_roles:
                        discussion_observation += "\nPlayers who have revealed their roles to you:\n"
                        discussion_observation += "\n".join(revealed_roles) + "\n"

                    # Add previous messages if any
                    discussion_observation += previous_messages

                    # Add advice for leader
                    if pid in gs["leaders"]:
                        discussion_observation += (
                            "\nAs the room leader, pay close attention to discussions. "
                            "You'll be selecting a player to trade after this phase.\n"
                        )

                        # Add team-specific advice
                        player_role = gs["player_roles"][pid]
                        team = self.ROLES[player_role]["team"]
                        if "Red" in team:
                            discussion_observation += (
                                "Remember: Your Red Team's goal is to get the Bomber and President in the same room.\n"
                            )
                        else:
                            discussion_observation += (
                                "Remember: Your Blue Team's goal is to keep the Bomber and President in different rooms.\n"
                            )

                    # Send the tailored observation to each player
                    self.message(pid, discussion_observation, ta.ObservationType.GAME_MESSAGE)

            # Set up player order for discussion (each player speaks a few times)
            gs["next_player_ids"] = []

            for _ in range(self.discussion_rounds):  # Each player gets multiple turns to speak
                for room_players in gs["rooms"]:
                    # Skip empty rooms
                    if not room_players:
                        continue

                    # Shuffle players within each room for variety
                    shuffled_players = room_players.copy()
                    self.rng.shuffle(shuffled_players)
                    gs["next_player_ids"].extend(shuffled_players)

        elif new_phase == "Role_Reveal":
            if gs.get("paused_discussion_player_ids") is None:
                gs["paused_discussion_player_ids"] = list(gs["next_player_ids"])

            # Only proceed if we have a valid player who wants to reveal
            revealing_player = gs.get("revealing_player")
            if revealing_player is None:
                self._resume_discussion_after_reveal()
                return None

            # Determine which room the revealing player is in
            player_room = None
            if revealing_player in gs["rooms"][0]:
                player_room = 0
            elif revealing_player in gs["rooms"][1]:
                player_room = 1
            else:
                # Error - player not in any room
                self._resume_discussion_after_reveal()
                return None

            # apply() already rejects unavailable reveals as invalid moves
            unavailable = self._reveal_unavailable_reason(revealing_player)
            if unavailable is not None:
                self.message(revealing_player, unavailable, ta.ObservationType.GAME_ADMIN)
                # Return to Discussion, continuing with the existing turn queue
                self._resume_discussion_after_reveal()
                return None

            current_reveals = gs["reveal_counts"].get(revealing_player, 0)
            room_players = [
                pid for pid in gs["rooms"][player_room]
                if pid != revealing_player
            ]
            player_list = ", ".join([f"Player {pid}" for pid in room_players])
            selection_options = ", ".join(str(pid) for pid in room_players)

            reveal_prompt = (
                f"You've chosen to reveal your role.\n"
                f"Players in your room: {player_list}\n\n"
                f"To whom would you like to reveal your role?\n"
                f"Simply reply with the player number, e.g. 'Player X' or just 'X'\n"
                f"Valid options: {selection_options}\n\n"
                f"Note: This will be your reveal #{current_reveals + 1} out of {self.MAX_REVEALS_PER_PLAYER} allowed reveals."
            )

            self.message(revealing_player, reveal_prompt, ta.ObservationType.GAME_MESSAGE)

            # Only the revealing player should act in this phase
            gs["next_player_ids"] = [revealing_player]

        elif new_phase == "Leader_Selection":
            # Reset any role reveal state
            gs["revealing_player"] = None

            # Check each room for leader status
            for room_idx in range(2):
                # Skip empty rooms
                if not gs["rooms"][room_idx]:
                    gs["leaders"][room_idx] = None
                    continue

                # If the leader is no longer in this room (traded), assign a new one
                current_leader = gs["leaders"][room_idx]
                if current_leader not in gs["rooms"][room_idx]:
                    # Select a new leader from the room, preferring regular players
                    regular_players = [
                        pid for pid in gs["rooms"][room_idx]
                        if gs["player_roles"][pid] not in ["President", "Bomber"]
                    ]

                    if regular_players:
                        new_leader = self.rng.choice(regular_players)
                    else:
                        new_leader = self.rng.choice(gs["rooms"][room_idx])

                    gs["leaders"][room_idx] = new_leader

                    # Notify all players in the room about the new leader
                    leader_change_msg = f"Room {room_idx} has a new leader: Player {new_leader}"
                    for pid in gs["rooms"][room_idx]:
                        self.message(pid, leader_change_msg, ta.ObservationType.GAME_MESSAGE)

            # Leaders select players to trade
            for room_idx, leader_id in enumerate(gs["leaders"]):
                # Skip empty rooms or None leaders
                if leader_id is None or not gs["rooms"][room_idx]:
                    continue

                # Get all players in the room except the leader
                room_players = [pid for pid in gs["rooms"][room_idx] if pid != leader_id]

                # Only proceed if there are players to select
                if room_players:
                    player_options = ", ".join(str(pid) for pid in room_players)

                    # Get team information to provide strategic context
                    leader_role = gs["player_roles"][leader_id]
                    leader_team = "Red" if "Red" in self.ROLES[leader_role]["team"] else "Blue"

                    # Get known information about players in the room
                    player_intel = []
                    for pid in room_players:
                        if pid in gs["revealed_roles"].get(leader_id, []):
                            role = gs["player_roles"][pid]
                            player_intel.append(f"Player {pid}: {role}")

                    intel_info = "\n".join(player_intel) if player_intel else "No players have revealed their roles to you."

                    # Create leader observation with strategic information
                    leader_observation = (
                        f"Round {gs['round']}: As the Leader of Room {room_idx}, "
                        f"you must select one player to trade with the other room.\n"
                        f"Your team: {leader_team} Team\n\n"
                        f"Known player roles:\n{intel_info}\n\n"
                        f"Simply reply with the player number, e.g. 'Player X' or just 'X'\n"
                        f"Valid options: {player_options}\n\n"
                    )

                    # Add team-specific strategic guidance
                    if leader_team == "Red":
                        leader_observation += (
                            "Strategic reminder: Red Team wants the President and Bomber in the same room at the end.\n"
                            "If you know who the President is, consider your strategy carefully.\n"
                        )
                    else:
                        leader_observation += (
                            "Strategic reminder: Blue Team wants the President and Bomber in different rooms at the end.\n"
                            "If you know who the Bomber is, consider your strategy carefully.\n"
                        )

                    self.message(leader_id, leader_observation, ta.ObservationType.GAME_MESSAGE)

            # Leaders act in sequence, filtering out None values
            gs["next_player_ids"] = [leader for leader in gs["leaders"] if leader is not None]

            # If no leaders are left or no valid leaders, force trade with random selection
            if not gs["next_player_ids"] and gs["round"] < self.num_rounds:
                # Force random selection for rooms without leaders
                for room_idx in range(2):
                    if gs["leaders"][room_idx] is None and gs["rooms"][room_idx]:
                        eligible_players = [
                            pid for pid in gs["rooms"][room_idx]
                            if pid != gs["leaders"][room_idx]
                        ]

                        if eligible_players:
                            hostage = self.rng.choice(eligible_players)
                            gs["hostages_to_trade"][room_idx] = hostage

                            # Inform the room
                            message = f"With no leader, Player {hostage} was randomly selected to be traded."
                            for pid in gs["rooms"][room_idx]:
                                self.message(pid, message, ta.ObservationType.GAME_MESSAGE)

                # Move to trade execution
                gs["current_phase"] = "Trade_Execution"
                return self._phase_transition_player_prompts(new_phase="Trade_Execution")

        elif new_phase == "Trade_Execution":
            # Reset any role reveal state
            gs["revealing_player"] = None

            # Ensure both rooms have selected hostages (crucial game mechanic)
            for room_idx in range(2):
                # Skip empty rooms
                if not gs["rooms"][room_idx]:
                    continue

                if room_idx not in gs["hostages_to_trade"]:
                    # Room has players but no hostage selected - make random selection
                    eligible_players = [
                        p for p in gs["rooms"][room_idx]
                        if p != gs["leaders"][room_idx]
                    ]

                    # Only proceed if there are eligible players
                    if eligible_players:
                        random_hostage = self.rng.choice(eligible_players)
                        gs["hostages_to_trade"][room_idx] = random_hostage

                        # Inform all players in the room
                        random_selection_msg = (
                            f"Since no hostage was selected for Room {room_idx}, "
                            f"Player {random_hostage} was randomly chosen to be traded."
                        )
                        for pid in gs["rooms"][room_idx]:
                            self.message(pid, random_selection_msg, ta.ObservationType.GAME_MESSAGE)

            # Execute the trade and inform players
            room0_hostage = gs["hostages_to_trade"].get(0)
            room1_hostage = gs["hostages_to_trade"].get(1)

            # Track if trade was executed
            trade_executed = False

            # Both rooms have hostages - standard trade
            if room0_hostage is not None and room1_hostage is not None:
                # Verify both hostages are actually in their respective rooms
                if (room0_hostage in gs["rooms"][0] and
                        room1_hostage in gs["rooms"][1]):

                    # Remove players from their current rooms
                    gs["rooms"][0].remove(room0_hostage)
                    gs["rooms"][1].remove(room1_hostage)

                    # Add players to their new rooms
                    gs["rooms"][0].append(room1_hostage)
                    gs["rooms"][1].append(room0_hostage)

                    trade_executed = True

                    # Inform all players about the trade
                    trade_observation = (
                        f"Round {gs['round']}: The Leaders have exchanged hostages.\n"
                        f"Player {room0_hostage} moved from Room 0 to Room 1.\n"
                        f"Player {room1_hostage} moved from Room 1 to Room 0."
                    )

                    self.broadcast(trade_observation, ta.ObservationType.GAME_MESSAGE)
                else:
                    # Invalid hostage selection - hostages not in their rooms
                    self.broadcast("Trade error: Selected hostages are not in their expected rooms.", ta.ObservationType.GAME_ADMIN)

                    # Try to find replacement hostages
                    if (room0_hostage not in gs["rooms"][0] and
                            len(gs["rooms"][0]) > 1):
                        # Find a new hostage from room 0
                        eligible_players = [
                            p for p in gs["rooms"][0]
                            if p != gs["leaders"][0]
                        ]
                        if eligible_players:
                            new_room0_hostage = self.rng.choice(eligible_players)
                            gs["hostages_to_trade"][0] = new_room0_hostage

                    if (room1_hostage not in gs["rooms"][1] and
                            len(gs["rooms"][1]) > 1):
                        # Find a new hostage from room 1
                        eligible_players = [
                            p for p in gs["rooms"][1]
                            if p != gs["leaders"][1]
                        ]
                        if eligible_players:
                            new_room1_hostage = self.rng.choice(eligible_players)
                            gs["hostages_to_trade"][1] = new_room1_hostage

                    # Try trade again with new hostages
                    room0_hostage = gs["hostages_to_trade"].get(0)
                    room1_hostage = gs["hostages_to_trade"].get(1)

                    if (room0_hostage is not None and room1_hostage is not None and
                            room0_hostage in gs["rooms"][0] and
                            room1_hostage in gs["rooms"][1]):

                        # Execute trade with new hostages
                        gs["rooms"][0].remove(room0_hostage)
                        gs["rooms"][1].remove(room1_hostage)
                        gs["rooms"][0].append(room1_hostage)
                        gs["rooms"][1].append(room0_hostage)

                        trade_executed = True

                        recovery_msg = (
                            f"Trade recovery: New hostages were selected.\n"
                            f"Player {room0_hostage} moved from Room 0 to Room 1.\n"
                            f"Player {room1_hostage} moved from Room 1 to Room 0."
                        )
                        self.broadcast(recovery_msg, ta.ObservationType.GAME_ADMIN)

            # One-sided trades (if one room is empty)
            elif room0_hostage is not None and not gs["rooms"][1]:
                # Only room 0 has players, just announce no trade
                self.broadcast(f"Round {gs['round']}: No trade occurred as Room 1 is empty.", ta.ObservationType.GAME_MESSAGE)

            elif room1_hostage is not None and not gs["rooms"][0]:
                # Only room 1 has players, just announce no trade
                self.broadcast(f"Round {gs['round']}: No trade occurred as Room 0 is empty.", ta.ObservationType.GAME_MESSAGE)

            # If no trade happened and both rooms have players, force a trade
            elif (not trade_executed and
                  gs["rooms"][0] and
                  gs["rooms"][1]):

                # Try to identify eligible players for forced trade
                eligible_room0 = [
                    p for p in gs["rooms"][0]
                    if p != gs["leaders"][0]
                ]
                eligible_room1 = [
                    p for p in gs["rooms"][1]
                    if p != gs["leaders"][1]
                ]

                # Only proceed if both rooms have eligible players
                if eligible_room0 and eligible_room1:
                    force_room0_hostage = self.rng.choice(eligible_room0)
                    force_room1_hostage = self.rng.choice(eligible_room1)

                    # Remove players from their current rooms
                    gs["rooms"][0].remove(force_room0_hostage)
                    gs["rooms"][1].remove(force_room1_hostage)

                    # Add players to their new rooms
                    gs["rooms"][0].append(force_room1_hostage)
                    gs["rooms"][1].append(force_room0_hostage)

                    # Inform all players about the forced trade
                    forced_trade_msg = (
                        f"Round {gs['round']}: A trade had to be forced to continue the game.\n"
                        f"Player {force_room0_hostage} moved from Room 0 to Room 1.\n"
                        f"Player {force_room1_hostage} moved from Room 1 to Room 0."
                    )
                    self.broadcast(forced_trade_msg, ta.ObservationType.GAME_MESSAGE)
                else:
                    # Cannot force a trade - leaders are the only players
                    self.broadcast(f"Round {gs['round']}: No trade occurred as there are not enough eligible players.", ta.ObservationType.GAME_MESSAGE)

            # Reset hostages for next round
            gs["hostages_to_trade"] = {}

            # No player needs to take action in this phase
            gs["next_player_ids"] = []

            # Check if we need to advance to the next round
            if gs["round"] >= self.num_rounds:
                # This was the last round, determine winner
                return self._determine_winner()
            else:
                # Advance to the next round
                gs["round"] += 1

                # Move to Discussion phase for the next round
                gs["current_phase"] = "Discussion"
                return self._phase_transition_player_prompts(new_phase="Discussion")
        else:
            raise Exception(f"{new_phase} phase not recognized.")
        return None

    def _resume_discussion_after_reveal(self):
        """Resume the exact discussion queue paused by a role reveal."""
        gs = self.game_state
        paused_queue = gs.get("paused_discussion_player_ids")
        gs["current_phase"] = "Discussion"
        gs["revealing_player"] = None
        gs["next_player_ids"] = list(paused_queue) if paused_queue is not None else []
        gs["paused_discussion_player_ids"] = None

    def _transition_current_pid(self, immediate: bool = False) -> Optional[ta.Outcome]:
        """
        Hand the turn to the next queued player, transitioning phases whenever the
        current phase's queue is exhausted. Returns an Outcome if the game ends
        during an automatic Trade_Execution phase.

        Args:
            immediate: select the actor immediately during reset; otherwise
                schedule the actor after turn bookkeeping.
        """
        gs = self.game_state
        for _ in range(self.MAX_RECURSION_DEPTH):
            if gs["next_player_ids"]:
                next_pid = gs["next_player_ids"].pop(0)

                # Validate the player still exists in the game before updating
                all_players = set(gs["rooms"][0] + gs["rooms"][1])
                if next_pid not in all_players:
                    continue  # Skip this player - they're somehow not in a room

                if immediate:
                    self.set_current_player(next_pid)
                else:
                    self.set_next_player(next_pid)
                return None

            # Queue exhausted - transition to the next phase
            current_phase = gs["current_phase"]
            if current_phase == "Discussion":
                gs["current_phase"] = "Leader_Selection"
                outcome = self._phase_transition_player_prompts(new_phase="Leader_Selection")
            elif current_phase == "Leader_Selection":
                gs["current_phase"] = "Trade_Execution"
                outcome = self._phase_transition_player_prompts(new_phase="Trade_Execution")
            elif current_phase == "Role_Reveal":
                # If role reveal completes or fails, resume the paused discussion.
                self._resume_discussion_after_reveal()
                continue
            else:
                outcome = None

            if outcome is not None:
                return outcome

            # If we still don't have player IDs and we're in the final round, end the game
            if not gs["next_player_ids"] and gs["round"] >= self.num_rounds:
                return self._determine_winner()

        # Safety valve: the phase machinery failed to produce a player to act
        self.broadcast("Recursion depth exceeded in player transitions. Ending the game.", ta.ObservationType.GAME_ADMIN)
        return self._determine_winner()

    def _determine_winner(self) -> ta.Outcome:
        """
        Determine which team wins based on the final positions of President and Bomber
        """
        gs = self.game_state
        # Find which rooms the President and Bomber are in
        president_room = None
        bomber_room = None
        president_id = None
        bomber_id = None

        for room_idx, room_players in enumerate(gs["rooms"]):
            for pid in room_players:
                role = gs["player_roles"][pid]
                if role == "President":
                    president_room = room_idx
                    president_id = pid
                elif role == "Bomber":
                    bomber_room = room_idx
                    bomber_id = pid

        # Create final game state observation
        final_state = (
            f"===== GAME OVER =====\n\n"
            f"Final room positions:\n"
        )

        for room_idx, players in enumerate(gs["rooms"]):
            player_list = ", ".join([f"Player {p}" for p in players])
            final_state += f"Room {room_idx}: {player_list}\n"

        if president_id is not None:
            final_state += f"\nThe President (Player {president_id}) is in Room {president_room}.\n"

        if bomber_id is not None:
            final_state += f"The Bomber (Player {bomber_id}) is in Room {bomber_room}.\n"

        # Determine winner
        if president_room is not None and bomber_room is not None:
            if president_room == bomber_room:
                # Red team wins
                red_team_pids = [pid for pid, role in gs["player_roles"].items()
                                 if self.ROLES[role]["team"] == "Red Team"]

                reason = "The Red Team wins! The Bomber and President are in the same room."
                self.broadcast(final_state, ta.ObservationType.GAME_ADMIN)
                return self.winner(red_team_pids, reason=reason)
            else:
                # Blue team wins
                blue_team_pids = [pid for pid, role in gs["player_roles"].items()
                                  if self.ROLES[role]["team"] == "Blue Team"]

                reason = "The Blue Team wins! The Bomber and President are in different rooms."
                self.broadcast(final_state, ta.ObservationType.GAME_ADMIN)
                return self.winner(blue_team_pids, reason=reason)
        else:
            # This should never happen with proper validation, but as a failsafe:
            missing_roles = []
            if president_room is None:
                missing_roles.append("President")
            if bomber_room is None:
                missing_roles.append("Bomber")

            error_msg = f"Game could not determine a winner. Missing roles: {', '.join(missing_roles)}"
            self.broadcast(error_msg, ta.ObservationType.GAME_ADMIN)

            # Default to Blue team win as in original logic, but with explanation
            blue_team_pids = [pid for pid, role in gs["player_roles"].items()
                              if self.ROLES[role]["team"] == "Blue Team"]
            reason = "The Blue Team wins by default due to missing special roles."
            return self.winner(blue_team_pids, reason=reason)

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        """
        Process a single action from the current player.
        """
        gs = self.game_state
        try:
            self._validate_game_state()
        except ValueError as e:
            return self.draw(reason=f"Game ended safely due to invalid state: {e}")

        current_phase = gs["current_phase"]

        # Verify player is in a valid room
        player_in_room0 = player_id in gs["rooms"][0]
        player_in_room1 = player_id in gs["rooms"][1]

        if not (player_in_room0 or player_in_room1):
            error_msg = f"Player {player_id} is not assigned to any room. This is a game state error."
            return self.invalid(error_msg)

        # Handle different phases
        if current_phase == "Discussion":
            if self.reveal_command_pattern.fullmatch(action):
                unavailable = self._reveal_unavailable_reason(player_id)
                if unavailable is not None:
                    return self.invalid(unavailable)
                # Player wants to reveal their role - start the role reveal phase
                gs["revealing_player"] = player_id
                gs["current_phase"] = "Role_Reveal"
                self._phase_transition_player_prompts(new_phase="Role_Reveal")
                result = None
            else:
                # Normal discussion
                result = self._handle_discussion(current_pid=player_id, action=action)

        elif current_phase == "Role_Reveal":
            # Handle role reveal target selection
            result = self._handle_role_reveal_selection(current_pid=player_id, action=action)

        elif current_phase == "Leader_Selection":
            # Handle leader selection of hostages
            result = self._handle_leader_selection(current_pid=player_id, action=action)

        else:
            # Trade_Execution phase doesn't require player actions
            result = None

        if isinstance(result, ta.Invalid):
            return result

        # Hand the turn to the next queued player (may auto-run phases and end the game)
        return self._transition_current_pid()

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        """
        Legacy behavior: a player who exhausts the error allowance forfeits their
        action (they stay in the game) and play continues with the next queued player.
        """
        return self._transition_current_pid()

    def _reveal_unavailable_reason(self, player_id: int) -> Optional[str]:
        """Why `player_id` cannot start a role reveal right now, or None if they can."""
        gs = self.game_state
        if gs["reveal_counts"].get(player_id, 0) >= self.MAX_REVEALS_PER_PLAYER:
            return f"You have already used all {self.MAX_REVEALS_PER_PLAYER} of your allowed role reveals."
        room_idx = 0 if player_id in gs["rooms"][0] else 1
        if not any(pid != player_id for pid in gs["rooms"][room_idx]):
            return "There are no other players in your room to reveal your role to."
        return None

    def _handle_role_reveal_selection(self, current_pid, action) -> Optional[ta.Invalid]:
        """
        Handle the selection of a player to reveal role to during the Role_Reveal phase

        Args:
            current_pid (int): ID of the player making the selection
            action (str): The selection action
        """
        gs = self.game_state
        # Verify this is the player who initiated the reveal
        if current_pid != gs["revealing_player"]:
            error_msg = "Only the player who initiated the role reveal can select a target."
            self.message(current_pid, error_msg, ta.ObservationType.GAME_ADMIN)
            return self.invalid(error_msg)

        # Determine which room the player is in
        player_room = None
        if current_pid in gs["rooms"][0]:
            player_room = 0
        elif current_pid in gs["rooms"][1]:
            player_room = 1
        else:
            # This shouldn't happen due to earlier validation
            error_msg = "You are not in any room. Cannot process role reveal."
            self.message(current_pid, error_msg, ta.ObservationType.GAME_ADMIN)
            return self.invalid(error_msg)

        # Extract target player ID - check both formats
        target_pid = None

        # Check for 'Player X' / 'X' format
        match = self.target_pattern.search(action)
        if match:
            try:
                target_pid = int(match.group(1))
            except ValueError:
                pass

        # If we couldn't extract a player ID
        if target_pid is None:
            error_msg = "Could not determine which player you want to reveal your role to. Please reply with the player number, e.g. 'Player X' or just 'X'."
            self.message(current_pid, error_msg, ta.ObservationType.GAME_ADMIN)
            return self.invalid(error_msg)

        # Check if player has reveals left (double-check)
        current_reveals = gs["reveal_counts"].get(current_pid, 0)
        if current_reveals >= self.MAX_REVEALS_PER_PLAYER:
            error_msg = f"You have already used all {self.MAX_REVEALS_PER_PLAYER} of your allowed role reveals."
            self.message(current_pid, error_msg, ta.ObservationType.GAME_ADMIN)
            return self.invalid(error_msg)

        # Check if target is in the same room
        if target_pid not in gs["rooms"][player_room]:
            error_msg = f"Player {target_pid} is not in your room. You can only reveal your role to players in the same room."
            self.message(current_pid, error_msg, ta.ObservationType.GAME_ADMIN)
            return self.invalid(error_msg)

        if target_pid == current_pid:
            return self.invalid("You cannot reveal your role to yourself.")

        # Process the role reveal
        true_role = gs["player_roles"][current_pid]

        # Add this player to the target's revealed_roles list
        if target_pid not in gs["revealed_roles"]:
            gs["revealed_roles"][target_pid] = []

        # Update reveal count
        gs["reveal_counts"][current_pid] = current_reveals + 1

        # Add to revealed roles if not already revealed
        if current_pid not in gs["revealed_roles"][target_pid]:
            gs["revealed_roles"][target_pid].append(current_pid)

        # Send private message to the target
        reveal_msg = (
            f"[PRIVATE] Player {current_pid} has revealed their card to you. "
            f"Their true role is: {true_role}"
        )
        self.message(target_pid, reveal_msg, ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=current_pid)

        # Send confirmation to the revealing player
        reveals_left = self.MAX_REVEALS_PER_PLAYER - (current_reveals + 1)
        confirm_msg = (
            f"You revealed your role ({true_role}) to Player {target_pid}. "
            f"You have {reveals_left} reveals remaining."
        )
        self.message(current_pid, confirm_msg, ta.ObservationType.GAME_MESSAGE)

        # Create public version of the message without revealing the role
        public_msg = f"I am revealing my card to Player {target_pid}."

        # Process as normal discussion after handling the reveal
        self._handle_discussion(current_pid=current_pid, action=public_msg)

        # Return to discussion phase
        self._resume_discussion_after_reveal()
        return None

    def _handle_discussion(self, current_pid, action) -> Optional[ta.Invalid]:
        """
        Handle discussion phase - broadcast message to all players in the same room
        and store message history with improved validation

        Args:
            current_pid (int): ID of the speaking player
            action (str): The message being sent
        """
        gs = self.game_state
        # Determine which room the player is in
        player_room = None
        if current_pid in gs["rooms"][0]:
            player_room = 0
        elif current_pid in gs["rooms"][1]:
            player_room = 1
        else:
            # This shouldn't happen due to earlier validation, but just in case
            error_msg = f"Player {current_pid} is not in any room. Cannot process discussion."
            self.message(current_pid, error_msg, ta.ObservationType.GAME_ADMIN)
            return self.invalid(error_msg)

        # Sanitize the message for safety
        sanitized_action = self.strip_role_tags(action).strip()

        # Store message in history with room-specific tracking
        if str(player_room) not in gs["message_history"]:
            gs["message_history"][str(player_room)] = []

        # Add message to history
        gs["message_history"][str(player_room)].append({
            "from": current_pid,
            "message": sanitized_action,
            "round": gs["round"],
            "visible_to": list(gs["rooms"][player_room]),
        })

        # Limit message history size per room
        if len(gs["message_history"][str(player_room)]) > self.MAX_MESSAGE_HISTORY:
            # Remove oldest messages
            gs["message_history"][str(player_room)] = (
                gs["message_history"][str(player_room)][-self.MAX_MESSAGE_HISTORY:]
            )

        # Broadcast message to all players in the same room
        for pid in gs["rooms"][player_room]:
            if pid != current_pid:  # Don't send to self
                self.message(pid, sanitized_action, ta.ObservationType.PLAYER_ACTION, from_id=current_pid)

        # Send confirmation to the speaking player
        self.message(current_pid, "Your message was sent to all players in your room.", ta.ObservationType.GAME_MESSAGE)

        return None

    def _handle_leader_selection(self, current_pid, action) -> Optional[ta.Invalid]:
        """
        Handle leader selection of hostages to trade with improved validation

        Args:
            current_pid (int): ID of the leader making a selection
            action (str): The selection action
        """
        gs = self.game_state
        # Verify this is actually a leader
        if current_pid not in gs["leaders"]:
            return self.invalid("Only room leaders can select hostages.")

        # Determine which room the leader is in
        room_idx = None
        if current_pid == gs["leaders"][0]:
            room_idx = 0
        elif current_pid == gs["leaders"][1]:
            room_idx = 1
        else:
            # Should never happen due to earlier check, but just in case
            return self.invalid("Leader room assignment error.")

        # Try to extract player ID using different formats
        selected_pid = None

        # Try 'Player X' / 'X' format
        match = self.target_pattern.search(action)
        if match:
            try:
                selected_pid = int(match.group(1))
            except ValueError:
                pass

        # If we couldn't extract a player ID
        if selected_pid is None:
            return self.invalid("Could not determine which player you selected. Please reply with the player number, e.g. 'Player X' or just 'X'.")

        # Verify the selected player is in the leader's room
        if selected_pid not in gs["rooms"][room_idx]:
            return self.invalid(f"Player {selected_pid} is not in your room. You can only select players from your own room.")

        # Verify the selected player is not the leader themselves
        if selected_pid == current_pid:
            return self.invalid("You cannot select yourself as a hostage.")

        # Verify not trading the President and Bomber directly (if leader knows their identities)
        if selected_pid in gs["revealed_roles"].get(current_pid, []):
            selected_role = gs["player_roles"][selected_pid]

            # Check other room's selected hostage if already chosen
            other_room = 1 - room_idx
            other_hostage = gs["hostages_to_trade"].get(other_room)

            if other_hostage is not None and other_hostage in gs["revealed_roles"].get(current_pid, []):
                other_role = gs["player_roles"][other_hostage]

                # Prevent direct President-Bomber trade if leader knows both roles
                if ((selected_role == "President" and other_role == "Bomber") or
                        (selected_role == "Bomber" and other_role == "President")):
                    warning_msg = (
                        "Warning: You are about to trade the President and Bomber directly. "
                        "This may help the other team. Proceeding anyway..."
                    )
                    self.message(current_pid, warning_msg, ta.ObservationType.GAME_MESSAGE)

        # Record the selection
        gs["hostages_to_trade"][room_idx] = selected_pid

        # Get selected player's role for leader's information
        selected_role = gs["player_roles"][selected_pid]

        # Inform all players in the room about the selection
        selection_message = f"[LEADER] I have selected Player {selected_pid} to be traded with the other room."

        # Separately inform the leader about the player's role (if known)
        if selected_pid in gs["revealed_roles"].get(current_pid, []):
            leader_info = f"[PRIVATE] You've selected Player {selected_pid} who revealed to you as: {selected_role}"
            self.message(current_pid, leader_info, ta.ObservationType.GAME_MESSAGE)

        # Broadcast decision to all players in the room
        for pid in gs["rooms"][room_idx]:
            self.message(pid, selection_message, ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=current_pid)
        return None
