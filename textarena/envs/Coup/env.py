import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta
from textarena.envs.Coup import base_coup_prompts
from textarena.envs.Coup.coup_types import ActionMetadata, CoupActionType, GamePhase

from rich.text import Text


class CoupEnv(ta.GameEnv):
    """
    A minimal text-based implementation of the Coup card game using textarena.

    Example actions a player might enter:
      - <action> <target_player_id>
      - PASS                 -> The player makes an action.
      - BULLSHIT             -> The player challenges the last play.
      - block foreign aid    -> The player counteracts the last play.
    """

    min_players = 2
    max_players = 6
    error_allowance = 3

    def setup(self) -> Dict[str, Any]:
        # Create deck with three of each card
        deck = ["Duke", "Assassin", "Ambassador", "Captain", "Contessa"] * 3
        self.rng.shuffle(deck)

        num_players = self.state.num_players
        game_state = {
            "phase": GamePhase.Play,

            "hidden_hand": {},  # The cards each player has in their hand
            "revealed_hand": {},  # The cards each player has revealed/lost
            "pile": [],  # The cards in the pile in the middle

            "coins": {pid: 2 for pid in range(num_players)},  # Each player starts with 2 coins
            "treasury_coins": 50 - 2 * num_players,  # Max 50 coins in the pot, minus the coins each player starts with

            "action_metadata": None,  # The metadata about the current action that is being taken (can span multiple "turns")
            "pending_influence_loss": None,
        }

        # Deal two cards to each player
        for player_id in range(num_players):
            game_state["hidden_hand"].setdefault(player_id, [])
            game_state["revealed_hand"].setdefault(player_id, [])
            game_state["hidden_hand"][player_id].append(deck.pop())
            game_state["hidden_hand"][player_id].append(deck.pop())

        # Pile has whatever is left in the deck
        game_state["pile"] = deck
        return game_state

    def prompt(self, player_id: int) -> str:
        prompt = base_coup_prompts.base_prompt.replace("<NUM_PLAYERS>", str(self.state.num_players))
        prompt = prompt.replace("<PLAYER_ID>", str(player_id))
        prompt = prompt.replace("<PLAYER_OBSERVATIONS>", self._make_player_observations_prompt(player_id))
        return prompt

    def render(self, player_id: int) -> str:
        """Call-to-action shown to the player about to act (state summary + what they may do)."""
        msg = base_coup_prompts.base_reprompt
        msg = msg.replace("<PLAYER_OBSERVATIONS>", self._make_player_observations_prompt(player_id))
        msg = msg.replace("<CALL_TO_ACTION_OR_CHALLENGE>", self._make_call_to_action_str(player_id))
        return msg

    def get_board_str(self):
        return self._render_board(viewer_id=self.state.current_player_id)

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        # A keep response exposes the exchange player's private card options.
        if self.game_state["phase"] == GamePhase.QueryWhichToKeep:
            return player_id
        return -1

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        try:
            action_type, arg = self._parse_action(action)
        except ValueError as e:
            return self.invalid(str(e))

        phase = self.game_state["phase"]
        if phase == GamePhase.Play:
            result = self._apply_play_phase(player_id, action_type, arg)  # arg here is the target player id
        elif phase == GamePhase.QueryForBlockOrChallenge:
            result = self._apply_query_for_block_or_challenge_phase(player_id, action_type)
        elif phase == GamePhase.QueryToChallengeTheBlocker:
            result = self._apply_query_to_challenge_the_blocker_phase(player_id, action_type)
        elif phase == GamePhase.QueryWhichToKeep:
            result = self._apply_query_which_to_keep_phase(player_id, action_type, arg)
        elif phase == GamePhase.QueryWhichToReveal:
            result = self._apply_query_which_to_reveal_phase(player_id, action_type, arg)
        else:
            raise Exception(f"Unexpected game phase: {phase}")

        if isinstance(result, ta.Invalid):
            return result
        return self._advance_game_turn()

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        """The player exceeded the error allowance: they lose all their influence cards and are eliminated."""
        gs = self.game_state
        self.eliminate(player_id)

        # During an exchange, return the two temporary Court-deck cards before
        # removing the player's actual influences.
        if gs["phase"] == GamePhase.QueryWhichToKeep:
            influence_count = 2 - len(gs["revealed_hand"][player_id])
            while len(gs["hidden_hand"][player_id]) > influence_count:
                gs["pile"].append(gs["hidden_hand"][player_id].pop())
            self.rng.shuffle(gs["pile"])
            gs["phase"] = GamePhase.Play
            gs["action_metadata"] = None
        elif gs["phase"] == GamePhase.QueryWhichToReveal:
            gs["pending_influence_loss"] = None
            gs["phase"] = GamePhase.Play
            gs["action_metadata"] = None

        while gs["hidden_hand"][player_id]:
            self._make_player_lose_a_card(player_id)
        self.message(player_id, "You made too many invalid moves in a row and are eliminated from play.", ta.ObservationType.GAME_ADMIN)
        self._broadcast_observations(f"Player #{player_id} made too many invalid moves in a row and is eliminated from play.", exclude_player_ids=[player_id])

        # If they were queued to be queried about a block/challenge, drop them from the queue
        metadata = gs["action_metadata"]
        if metadata is not None and metadata.players_to_query:
            metadata.players_to_query = [pid for pid in metadata.players_to_query if pid != player_id]

        if metadata is not None:
            if metadata.source_player_id == player_id or metadata.target_player_id == player_id:
                metadata.action_type = CoupActionType.PASS
                metadata.players_to_query = []
            elif (
                gs["phase"] == GamePhase.QueryToChallengeTheBlocker
                and metadata.blocker_player_id == player_id
            ):
                # An administratively eliminated blocker cannot sustain a block.
                metadata.blocker_challenger_player_id = metadata.source_player_id
                metadata.players_to_query = []

        winner = self._get_winner()
        if winner is not None:
            self.step_info["winner"] = winner
            return self.winner(winner, reason=f"Player {winner} has won the game!")
        return self._advance_game_turn()

    # ---------------------------------------------------------------------
    # PER-PHASE ACTION HANDLERS
    # ---------------------------------------------------------------------
    def _apply_play_phase(self, player_id: int, action_type: CoupActionType, action_target_player_id: Optional[int] = None) -> Optional[ta.Invalid]:
        """
        This validates state and updates state as needed. NOTE THAT ONLY ALLOWABLE ACTIONS HERE ARE THE ONES FROM THE OFFICIAL CHEATSHEET "ACTION" COLUMN (see README.md)
        """
        gs = self.game_state
        if gs["coins"][player_id] >= 10 and action_type is not CoupActionType.Coup:
            return self.invalid("Invalid move. You cannot do anything other than coup when you have 10 or more coins. Please pick a player id to Coup and respond with: 'coup x'.")

        if action_type is CoupActionType.Income:
            gs["action_metadata"] = ActionMetadata(action_type=action_type, source_player_id=player_id, target_player_id=action_target_player_id)
            self._execute_current_action()

        elif action_type is CoupActionType.Coup:
            if gs["coins"][player_id] < 7:
                return self.invalid("Invalid move. You don't have enough coins to coup.")
            if not self._is_valid_target(action_target_player_id):
                return self.invalid("Invalid move. The second value in the 'coup x' response must be a valid player id.")
            if action_target_player_id == player_id:
                return self.invalid("Invalid move. You cannot coup yourself.")
            if gs["hidden_hand"][action_target_player_id] == []:
                return self.invalid(f"Invalid move. Can't coup player {action_target_player_id} because they are already eliminated from play.")
            gs["action_metadata"] = ActionMetadata(action_type=action_type, source_player_id=player_id, target_player_id=action_target_player_id)
            self._execute_current_action()

        elif action_type is CoupActionType.Exchange or action_type is CoupActionType.Tax:  # Exchange and Tax are not blockable, so we just skip to QueryForBlockOrChallenge phase
            gs["phase"] = GamePhase.QueryForBlockOrChallenge
            active_players = [pid for pid in range(self.state.num_players) if len(gs["hidden_hand"][pid]) > 0 and pid != player_id]
            gs["action_metadata"] = ActionMetadata(action_type=action_type, source_player_id=player_id, players_to_query=active_players)

        elif action_type is CoupActionType.ForeignAid or action_type is CoupActionType.Assassinate or action_type is CoupActionType.Steal:
            if action_type is CoupActionType.Assassinate and gs["coins"][player_id] < 3:
                return self.invalid("Invalid move. You don't have enough coins to assassinate.")
            if action_type in (CoupActionType.Assassinate, CoupActionType.Steal) and not self._is_valid_target(action_target_player_id):
                return self.invalid(f"Invalid move. The second value in the '{action_type.value} x' response must be a valid player id.")
            if action_type in (CoupActionType.Assassinate, CoupActionType.Steal):
                if action_target_player_id == player_id:
                    return self.invalid(f"Invalid move. You cannot {action_type.value} yourself.")
                if gs["hidden_hand"][action_target_player_id] == []:
                    return self.invalid(f"Invalid move. Player {action_target_player_id} is already eliminated from play.")

            # For assassination, deduct the cost immediately (per rules, you pay even if blocked)
            if action_type is CoupActionType.Assassinate:
                gs["coins"][player_id] -= 3
                gs["treasury_coins"] += 3

            gs["phase"] = GamePhase.QueryForBlockOrChallenge
            # Only query active players (those with cards remaining)
            active_players = [pid for pid in range(self.state.num_players) if len(gs["hidden_hand"][pid]) > 0 and pid != player_id]
            # For targeted actions, ensure target is first in query list if they're active
            if action_target_player_id is not None and action_target_player_id in active_players:
                active_players.remove(action_target_player_id)
                active_players = [action_target_player_id] + active_players
            gs["action_metadata"] = ActionMetadata(action_type=action_type, source_player_id=player_id, target_player_id=action_target_player_id, players_to_query=active_players)

        else:  # PASS / BULLSHIT / blocks / keep are not actions you can take on your own turn
            return self.invalid(f"Invalid action: {action_type}. It is your turn, you must take one of the cheatsheet actions: 'income', 'foreign aid', 'coup x', 'tax', 'assassinate x', 'steal x' or 'exchange'.")
        return None

    def _apply_query_for_block_or_challenge_phase(self, player_id: int, action: CoupActionType) -> Optional[ta.Invalid]:
        gs = self.game_state
        metadata = gs["action_metadata"]
        # If the player passes (they don't want to challenge), then we don't need to do anything, just advance
        if action is CoupActionType.PASS:
            return None
        elif action is CoupActionType.BULLSHIT:
            if metadata.action_type is CoupActionType.ForeignAid:  # you can't bullshit on foreign aid (it requires no card claim)
                return self.invalid(self._invalid_block_or_challenge_msg(action, player_id))
            if metadata.challenger_player_id is not None:
                return self.invalid(
                    "The action claim has already survived a challenge; "
                    "you may only block it (when eligible) or PASS."
                )
            metadata.challenger_player_id = player_id
            self._execute_showdown_on_bullshit()
            return None
        elif action in (CoupActionType.BlockForeignAid, CoupActionType.BlockStealAmbassador, CoupActionType.BlockStealCaptain, CoupActionType.BlockAssassinate):
            if action in (CoupActionType.BlockStealAmbassador, CoupActionType.BlockStealCaptain) and metadata.action_type is not CoupActionType.Steal:
                return self.invalid(f"Invalid move. You cannot call 'block steal x' when the last played action is a {metadata.action_type.name}.")
            if action is CoupActionType.BlockAssassinate and metadata.action_type is not CoupActionType.Assassinate:
                return self.invalid(f"Invalid move. You cannot call 'block assassinate' when the last played action is a {metadata.action_type.name}.")
            if action is CoupActionType.BlockForeignAid and metadata.action_type is not CoupActionType.ForeignAid:
                return self.invalid(f"Invalid move. You cannot call 'block foreign aid' when the last played action is a {metadata.action_type.name}.")
            if (
                action in {
                    CoupActionType.BlockStealAmbassador,
                    CoupActionType.BlockStealCaptain,
                    CoupActionType.BlockAssassinate,
                }
                and metadata.target_player_id != player_id
            ):
                return self.invalid("Only the target player may block a targeted action.")
            gs["phase"] = GamePhase.QueryToChallengeTheBlocker
            metadata.blocker_player_id = player_id
            metadata.block_type = action  # Track which specific block was used

            # This is a bit of a hack to ensure that the source player is always first in the query list.
            active_players = [metadata.source_player_id] + [pid for pid in range(self.state.num_players) if len(gs["hidden_hand"][pid]) > 0 and pid != player_id and pid != metadata.source_player_id]
            metadata.players_to_query = active_players
            return None
        else:  # Anything other than PASS or BULLSHIT or BlockXXXX is invalid in this phase
            return self.invalid(self._invalid_block_or_challenge_msg(action, player_id))

    def _invalid_block_or_challenge_msg(self, action: CoupActionType, player_id: int) -> str:
        metadata = self.game_state["action_metadata"]
        if metadata.action_type is CoupActionType.Steal and metadata.target_player_id == player_id:
            block_options_str = "'block steal captain', 'block steal ambassador', "
        elif metadata.action_type is CoupActionType.Assassinate and metadata.target_player_id == player_id:
            block_options_str = "'block assassinate', "
        elif metadata.action_type is CoupActionType.ForeignAid:
            block_options_str = "'block foreign aid', "
        else:
            block_options_str = ""
        bullshit_str = (
            "call 'BULLSHIT', "
            if metadata.action_type is not CoupActionType.ForeignAid
            and metadata.challenger_player_id is None
            else ""
        )
        return f"Invalid action: {action}, Player #{metadata.source_player_id} is attempting to {metadata.action_type}, you must either {block_options_str}{bullshit_str}or 'PASS'"

    def _apply_query_to_challenge_the_blocker_phase(self, player_id: int, action: CoupActionType) -> Optional[ta.Invalid]:
        if action is CoupActionType.PASS:
            return None
        elif action is CoupActionType.BULLSHIT:
            self.game_state["action_metadata"].blocker_challenger_player_id = player_id
            self._execute_showdown_on_blocker_bullshit()
            return None
        else:
            return self.invalid(f"Invalid action: {action}, you must either 'PASS' or call 'BULLSHIT'")

    def _apply_query_which_to_keep_phase(self, player_id: int, action_type: CoupActionType, cards_to_keep: Optional[List[str]] = None) -> Optional[ta.Invalid]:
        """Handle the phase where player is choosing which cards to keep after an exchange"""
        gs = self.game_state
        if action_type is not CoupActionType.Keep:
            cards_str = "<card1> <card2>" if len(gs["revealed_hand"][player_id]) == 0 else "<card>"
            return self.invalid(f"Invalid action: {action_type}, you must respond with 'keep {cards_str}' to specify the card(s) to keep")

        if cards_to_keep is None:
            return self.invalid("You must specify which cards to keep")

        # Check how many cards the player should keep based on their remaining influences
        expected_cards_to_keep = 2 - len(gs["revealed_hand"][player_id])
        if len(cards_to_keep) != expected_cards_to_keep:
            if expected_cards_to_keep == 2:
                return self.invalid("You must specify exactly two cards to keep")
            else:
                return self.invalid("You must specify exactly one card to keep (since you have lost an influence)")

        cards_to_keep = [c.title() for c in cards_to_keep]

        # Validate that the cards to keep are actually available (before mutating any state)
        cards_available = gs["hidden_hand"][player_id][:]
        for card in cards_to_keep:
            if card in cards_available:
                cards_available.remove(card)
            else:
                return self.invalid(f"Cannot keep {card} - it's not one of your available cards")

        # Store the cards to keep in metadata and complete the exchange action
        gs["action_metadata"].cards_to_keep = cards_to_keep
        self._execute_exchange_action(cards_available)
        return None

    def _apply_query_which_to_reveal_phase(
        self,
        player_id: int,
        action_type: CoupActionType,
        cards_to_reveal: Optional[List[str]] = None,
    ) -> Optional[ta.Invalid]:
        """Let the affected player choose which hidden influence to lose."""
        gs = self.game_state
        pending = gs["pending_influence_loss"]
        if pending is None or pending["player_id"] != player_id:
            return self.invalid("No influence loss is awaiting your choice.")
        if action_type is not CoupActionType.Reveal:
            return self.invalid(
                "You must choose a hidden influence with 'reveal <card>'."
            )
        if cards_to_reveal is None or len(cards_to_reveal) != 1:
            return self.invalid("Reveal exactly one hidden influence card.")

        card = cards_to_reveal[0].title()
        if card not in gs["hidden_hand"][player_id]:
            return self.invalid(f"Cannot reveal {card}; it is not in your hidden hand.")

        gs["hidden_hand"][player_id].remove(card)
        gs["revealed_hand"][player_id].append(card)
        pending["lost_card"] = card
        pending["resolved"] = True
        self.broadcast(
            f"Player #{player_id} revealed and lost a {card} influence.",
            ta.ObservationType.GAME_ACTION_DESCRIPTION,
        )
        if not gs["hidden_hand"][player_id]:
            self.eliminate(player_id)
            gs["treasury_coins"] += gs["coins"][player_id]
            gs["coins"][player_id] = 0
        return None

    ######################################################################################################################################################################
    # These are all the "sink" states for a single turn. Either we execute the action, or we resolve a block or challenge and then potentially execute the action still. #
    ######################################################################################################################################################################
    def _queue_influence_loss(self, player_id: int, continuation: str):
        """Pause resolution until ``player_id`` chooses an influence to reveal."""
        gs = self.game_state
        if not gs["hidden_hand"][player_id]:
            return
        gs["pending_influence_loss"] = {
            "player_id": player_id,
            "continuation": continuation,
            "resolved": False,
            "lost_card": None,
        }
        gs["phase"] = GamePhase.QueryWhichToReveal
        self.message(
            player_id,
            "You must lose an influence. Choose it with 'reveal <card>'.",
            ta.ObservationType.GAME_ACTION_DESCRIPTION,
        )

    def _execute_current_action(self):
        gs = self.game_state
        curr_action = gs["action_metadata"]

        # This means no-op, a challenge/block was successful and we're not executing the action
        if curr_action.action_type is CoupActionType.PASS:
            return

        source_player_observation, target_player_observation, other_player_observations = None, None, None

        if curr_action.action_type is CoupActionType.Income:
            gs["coins"][curr_action.source_player_id] += 1
            gs["treasury_coins"] -= 1
            source_player_observation = f"You just successfully played income. You now have {gs['coins'][curr_action.source_player_id]} coins"
            other_player_observations = f"Player #{curr_action.source_player_id} just played income. They now have {gs['coins'][curr_action.source_player_id]} coins"

        elif curr_action.action_type is CoupActionType.Coup:
            gs["coins"][curr_action.source_player_id] -= 7
            gs["treasury_coins"] += 7

            self._queue_influence_loss(
                curr_action.target_player_id, "finish_direct_action"
            )
            source_player_observation = (
                f"Your coup against Player #{curr_action.target_player_id} succeeded. "
                "They must choose an influence to reveal."
            )
            target_player_observation = (
                f"Player #{curr_action.source_player_id} couped you. "
                "Choose an influence to reveal."
            )
            other_player_observations = (
                f"Player #{curr_action.source_player_id} couped Player "
                f"#{curr_action.target_player_id}, who must reveal an influence."
            )

        elif curr_action.action_type is CoupActionType.ForeignAid:
            gs["coins"][curr_action.source_player_id] += 2
            gs["treasury_coins"] -= 2

            source_player_observation = f"You just successfully played foreign aid. You now have {gs['coins'][curr_action.source_player_id]} coins"
            other_player_observations = f"Player #{curr_action.source_player_id} just played foreign aid. They now have {gs['coins'][curr_action.source_player_id]} coins"

        elif curr_action.action_type is CoupActionType.Tax:
            gs["coins"][curr_action.source_player_id] += 3
            gs["treasury_coins"] -= 3

            source_player_observation = f"You just successfully played tax. You now have {gs['coins'][curr_action.source_player_id]} coins"
            other_player_observations = f"Player #{curr_action.source_player_id} just played tax. They now have {gs['coins'][curr_action.source_player_id]} coins"

        elif curr_action.action_type is CoupActionType.Assassinate:
            # Check for if player is already out, do nothing if so.
            if len(gs["hidden_hand"][curr_action.target_player_id]) == 0:
                return

            self._queue_influence_loss(
                curr_action.target_player_id, "finish_direct_action"
            )
            source_player_observation = (
                f"Your assassination of Player #{curr_action.target_player_id} "
                "succeeded. They must choose an influence to reveal."
            )
            target_player_observation = (
                f"Player #{curr_action.source_player_id} successfully assassinated "
                "you. Choose an influence to reveal."
            )
            other_player_observations = (
                f"Player #{curr_action.source_player_id} successfully assassinated "
                f"Player #{curr_action.target_player_id}, who must reveal an influence."
            )

        elif curr_action.action_type is CoupActionType.Steal:
            if len(gs["hidden_hand"][curr_action.target_player_id]) == 0:
                return
            amount_stolen = min(2, gs["coins"][curr_action.target_player_id])
            gs["coins"][curr_action.source_player_id] += amount_stolen
            gs["coins"][curr_action.target_player_id] -= amount_stolen

            source_player_observation = f"You just successfully stole {amount_stolen} coin(s) from Player #{curr_action.target_player_id}. You now have {gs['coins'][curr_action.source_player_id]} coins. Player #{curr_action.target_player_id} has {gs['coins'][curr_action.target_player_id]} coins"
            target_player_observation = f"Player #{curr_action.source_player_id} just stole {amount_stolen} coin(s) from you. You now have {gs['coins'][curr_action.target_player_id]} coins. Player #{curr_action.source_player_id} has {gs['coins'][curr_action.source_player_id]} coins"
            other_player_observations = f"Player #{curr_action.source_player_id} just stole {amount_stolen} coin(s) from Player #{curr_action.target_player_id}. Player #{curr_action.source_player_id} has {gs['coins'][curr_action.source_player_id]} coins. Player #{curr_action.target_player_id} has {gs['coins'][curr_action.target_player_id]} coins"

        elif curr_action.action_type is CoupActionType.Exchange:
            # Draw two cards from the pile
            if len(gs["pile"]) < 2:
                raise Exception("Not enough cards in pile for exchange")

            # Draw two cards and add them directly to the player's hand
            card1 = gs["pile"].pop()
            card2 = gs["pile"].pop()
            gs["hidden_hand"][curr_action.source_player_id].append(card1)
            gs["hidden_hand"][curr_action.source_player_id].append(card2)

            # Change phase to QueryWhichToKeep
            gs["phase"] = GamePhase.QueryWhichToKeep

            # Send observation to player about their options
            all_cards = gs["hidden_hand"][curr_action.source_player_id]
            cards_str = ", ".join(all_cards)

            # Determine how many cards they need to keep based on revealed cards (influences lost)
            cards_to_keep_count = 2 - len(gs["revealed_hand"][curr_action.source_player_id])

            if cards_to_keep_count == 2:
                source_player_observation = f"You drew two cards from the pile for exchange. You now have: {cards_str}. You must choose which two cards to keep using 'keep <card1>" + \
                    f"{' <card2>' if len(gs['revealed_hand'][curr_action.source_player_id]) == 0 else ''}'"
            else:  # cards_to_keep_count == 1
                source_player_observation = f"You drew two cards from the pile for exchange. You now have: {cards_str}. Since you have lost an influence, you must choose which one card to keep using 'keep <card>'"

            other_player_observations = f"Player #{curr_action.source_player_id} is exchanging cards with the Court deck."

        # Broadcast the observations to the players
        if source_player_observation:
            self.message(curr_action.source_player_id, source_player_observation, ta.ObservationType.GAME_ACTION_DESCRIPTION)
        if target_player_observation is not None:
            self.message(curr_action.target_player_id, target_player_observation, ta.ObservationType.GAME_ACTION_DESCRIPTION)
        if other_player_observations is not None:
            exclude_ids = [curr_action.source_player_id]
            if curr_action.target_player_id is not None:
                exclude_ids.append(curr_action.target_player_id)
            self._broadcast_observations(other_player_observations, exclude_player_ids=exclude_ids)

    def _execute_showdown_on_bullshit(self):
        gs = self.game_state
        metadata = gs["action_metadata"]
        # the "challenged" player is the player who initially played the challenged card
        challenger_player_id = metadata.challenger_player_id
        challenged_card = self._action_to_card(metadata.action_type)
        challenged_player_id = metadata.source_player_id  # The person who made the original claim
        is_honest = gs["hidden_hand"][challenged_player_id].count(challenged_card) > 0

        if is_honest:
            # If player was honest, then he gets a new card from the pile, and we reshuffle. Then challenger loses a card
            gs["hidden_hand"][challenged_player_id].remove(challenged_card)
            gs["pile"].append(challenged_card)
            self.rng.shuffle(gs["pile"])

            new_pulled_card = gs["pile"].pop()
            gs["hidden_hand"][challenged_player_id].append(new_pulled_card)

            # Player who called bullshit loses a card
            card_lost_by_challenger = self._make_player_lose_a_card(challenger_player_id)

            ###### UPDATE OBSERVATIONS
            challenger_remaining_cards = gs["hidden_hand"][challenger_player_id]

            # A targeted action cannot continue against a challenger who just
            # lost their final influence.
            if (metadata.action_type in {CoupActionType.Assassinate, CoupActionType.Steal} and
                    metadata.target_player_id == challenger_player_id and
                    len(challenger_remaining_cards) == 0):
                metadata.action_type = CoupActionType.PASS

            # Tell the challenger that their bullshit call failed
            challenger_message = f"Your bullshit call on Player #{challenged_player_id} failed. They did indeed have a {challenged_card} card." + \
                (f"You lost a {card_lost_by_challenger} card." if (len(challenger_remaining_cards) == 0 or challenger_remaining_cards[0] != card_lost_by_challenger) else f"You lost one of your {card_lost_by_challenger} cards.") + \
                (f"You now have only one card remaining, the {challenger_remaining_cards[0]} card." if len(challenger_remaining_cards) > 0 else
                 "You have no cards remaining, you're eliminated!")
            # Tell the challenged player that they just survived a bullshit challenge
            challenged_message = f"You were unsuccessfully challenged on your {challenged_card} claim by Player #{challenger_player_id}. " + \
                f"Because you had to reveal your {challenged_card} card to prove them wrong, you were given a new one from the pile. It is a {new_pulled_card} card. Player #{challenger_player_id} revealed and lost a {card_lost_by_challenger} card, " + \
                ("they now have only one card remaining." if len(challenger_remaining_cards) > 0 else f"they have no cards remaining, Player #{challenger_player_id} is eliminated!")
            # Tell everyone else what happened
            other_player_observations = f"Player #{challenger_player_id} just unsuccessfully called bullshit on Player #{challenged_player_id}'s {challenged_card} claim! " + \
                f"Player #{challenged_player_id} did indeed have a {challenged_card} card, put it back in the pile and got a new one. Player #{challenger_player_id} lost an influence and revealed a {card_lost_by_challenger} card." + \
                (f"Player #{challenger_player_id} now has 1 card remaining." if len(challenger_remaining_cards) > 0 else f"Player #{challenger_player_id} has no cards remaining, they're eliminated!")

        else:
            # Player who got challenged loses a card, nothing else changes
            card_lost_by_challenged = self._make_player_lose_a_card(challenged_player_id)

            challenged_remaining_cards = gs["hidden_hand"][challenged_player_id]
            challenged_message = f"You were challenged on your {challenged_card} claim by Player #{challenger_player_id}, Since you did not have a {challenged_card} card, you lost your {card_lost_by_challenged} card." + \
                (f" You now have only one card remaining, the {challenged_remaining_cards[0]} card." if len(challenged_remaining_cards) > 0 else
                 " You have no cards remaining, you're eliminated!")
            # Tell the challenger that they just successfully challenged the challenged player
            challenger_message = f"You just successfully challenged Player #{challenged_player_id} on their {challenged_card} claim! " + \
                (f"They are blocked from doing it and have {len(challenged_remaining_cards)} card remaining." if len(challenged_remaining_cards) > 0 else
                 "They have no cards remaining, they're eliminated!")
            # Other players see the challenger successfully challenge the challenged player
            other_player_observations = f"Player #{challenger_player_id} just successfully challenged Player #{challenged_player_id} on their {challenged_card} claim! " + \
                (f"Player #{challenged_player_id} was blocked from doing it and has {len(challenged_remaining_cards)} card remaining." if len(challenged_remaining_cards) > 0 else
                 f"Player #{challenged_player_id} has no cards remaining, they're eliminated!")

            # Mark no-op for _advance_turn()
            metadata.action_type = CoupActionType.PASS

        # A surviving target that unsuccessfully challenged a targeted action
        # still gets its separate counteraction opportunity. The claim itself
        # is now proven, so it cannot be challenged a second time.
        if (
            is_honest
            and metadata.action_type in {
                CoupActionType.Assassinate,
                CoupActionType.Steal,
            }
            and metadata.target_player_id == challenger_player_id
            and challenger_remaining_cards
        ):
            metadata.players_to_query = [challenger_player_id]
        else:
            metadata.players_to_query = None
        self.message(challenged_player_id, challenged_message, ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self.message(challenger_player_id, challenger_message, ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self._broadcast_observations(other_player_observations, exclude_player_ids=[challenged_player_id, challenger_player_id])

    def _execute_showdown_on_blocker_bullshit(self):
        gs = self.game_state
        metadata = gs["action_metadata"]
        blocker_player_id = metadata.blocker_player_id
        challenger_player_id = metadata.blocker_challenger_player_id

        # Determine which card the blocker claimed to have based on the block type
        block_type = metadata.block_type

        # Map the block type to the card claimed
        if block_type is CoupActionType.BlockForeignAid:
            block_card = "Duke"
        elif block_type is CoupActionType.BlockStealCaptain:
            block_card = "Captain"
        elif block_type is CoupActionType.BlockStealAmbassador:
            block_card = "Ambassador"
        elif block_type is CoupActionType.BlockAssassinate:
            block_card = "Contessa"
        else:
            raise Exception(f"Unexpected block type: {block_type}")

        # Check if blocker actually has the card they claimed
        is_honest = gs["hidden_hand"][blocker_player_id].count(block_card) > 0

        if is_honest:
            # Blocker was honest - they shuffle their card back and draw new, challenger loses a card
            gs["hidden_hand"][blocker_player_id].remove(block_card)
            gs["pile"].append(block_card)
            self.rng.shuffle(gs["pile"])

            new_card = gs["pile"].pop()
            gs["hidden_hand"][blocker_player_id].append(new_card)

            # Challenger loses a card
            card_lost = self._make_player_lose_a_card(challenger_player_id)
            challenger_remaining = len(gs["hidden_hand"][challenger_player_id])

            # Send observations
            blocker_msg = f"You were challenged on your {block_card} block by Player #{challenger_player_id}. Since you had the {block_card}, you shuffled it back and drew a {new_card}. Player #{challenger_player_id} lost a {card_lost} and has {challenger_remaining} card(s) remaining."
            challenger_msg = f"Your challenge on Player #{blocker_player_id}'s {block_card} block failed. They did have a {block_card}. You lost a {card_lost} and have {challenger_remaining} card(s) remaining."
            others_msg = f"Player #{challenger_player_id} challenged Player #{blocker_player_id}'s {block_card} block and failed. Player #{blocker_player_id} had the {block_card}, shuffled it back and drew a new card. Player #{challenger_player_id} lost a {card_lost} and has {challenger_remaining} card(s) remaining."

            # The block was successful, so the original action is cancelled
            metadata.action_type = CoupActionType.PASS

        else:
            # Blocker was lying - they lose a card, original action proceeds
            card_lost = self._make_player_lose_a_card(blocker_player_id)
            blocker_remaining = len(gs["hidden_hand"][blocker_player_id])

            # Send observations
            blocker_msg = f"You were challenged on your {block_card} block by Player #{challenger_player_id}. Since you didn't have a {block_card}, you lost a {card_lost} and have {blocker_remaining} card(s) remaining."
            challenger_msg = f"Your challenge on Player #{blocker_player_id}'s {block_card} block succeeded! They didn't have a {block_card}. They lost a {card_lost} and have {blocker_remaining} card(s) remaining."
            others_msg = f"Player #{challenger_player_id} successfully challenged Player #{blocker_player_id}'s {block_card} block. Player #{blocker_player_id} didn't have the {block_card}, lost a {card_lost} and has {blocker_remaining} card(s) remaining."

            # The block failed, so the original action will proceed
            # No need to change action_type

        # Send all observations
        self.message(blocker_player_id, blocker_msg, ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self.message(challenger_player_id, challenger_msg, ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self._broadcast_observations(others_msg, exclude_player_ids=[blocker_player_id, challenger_player_id])

        # Mark that we're done querying
        metadata.players_to_query = None

    def _execute_exchange_action(self, cards_returned: List[str]):
        """Execute the exchange action after player has chosen which cards to keep"""
        gs = self.game_state
        metadata = gs["action_metadata"]
        player_id = metadata.source_player_id
        cards_to_keep = metadata.cards_to_keep

        # Update player's hand with only the kept cards
        gs["hidden_hand"][player_id] = list(cards_to_keep)

        # Put the non-kept cards back in the pile and shuffle
        for card in cards_returned:
            gs["pile"].append(card)
        self.rng.shuffle(gs["pile"])

        # Send observations
        if len(cards_to_keep) == 1:
            source_observation = f"You have completed your exchange and kept: {cards_to_keep[0]}"
        else:
            source_observation = f"You have completed your exchange and kept: {', '.join(cards_to_keep)}"
        other_observation = f"Player #{player_id} has completed their exchange."

        self.message(player_id, source_observation, ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self._broadcast_observations(other_observation, exclude_player_ids=[player_id])

    def _broadcast_observations(self, other_player_observations: str, exclude_player_ids: Optional[List[int]] = None):
        """ Broadcast the observations to the players except for the players in `exclude_player_ids` """
        excluded = set(exclude_player_ids or [])
        for pid in range(self.state.num_players):
            if pid in excluded:
                continue
            self.message(pid, other_player_observations, ta.ObservationType.GAME_ACTION_DESCRIPTION)

    # ---------------------------------------------------------------------
    # PROMPT GENERATION METHODS -- CONVERTS GAME STATE TO PROMPT
    # ---------------------------------------------------------------------
    def _make_player_observations_prompt(self, player_id: Optional[int] = None) -> str:
        """
        Make a prompt for the specified player. Tells them their latest hand and the state of the game (what cards are in the pile, what cards are in the revealed hand, etc).
        """
        if player_id is None:
            player_id = self.state.current_player_id
        game_state = self.game_state
        msg = f"There are {self.state.num_players} players in the game.\n"

        for pid in range(self.state.num_players):
            if pid == player_id:
                continue
            if len(game_state['hidden_hand'][pid]) == 0:
                msg += f"Player #{pid} is out.\n"
            elif len(game_state['revealed_hand'][pid]) > 0:
                msg += f"Player #{pid} has {game_state['coins'][pid]} coins, has revealed and lost a {game_state['revealed_hand'][pid][0]} card, and has {len(game_state['hidden_hand'][pid])} hidden influence cards remaining.\n"
            else:
                msg += f"Player #{pid} has {game_state['coins'][pid]} coins, and has {len(game_state['hidden_hand'][pid])} hidden influence cards remaining.\n"

        msg += f"\n ------ You are Player #{player_id}. You have {game_state['coins'][player_id]} coins"

        if len(game_state['hidden_hand'][player_id]) == 2:
            msg += f" and {len(game_state['hidden_hand'][player_id])} hidden influence cards remaining: You have a {game_state['hidden_hand'][player_id][0]} and a {game_state['hidden_hand'][player_id][1]}."
        elif len(game_state['hidden_hand'][player_id]) == 1:
            msg += f", a hidden {game_state['hidden_hand'][player_id][0]} card, and you have a revealed {game_state['revealed_hand'][player_id][0]} card that is out of play."

        msg += " --------\n"
        return msg

    def _make_call_to_action_str(self, player_id: int) -> str:
        """
        Make the call-to-action for the player about to act (asks them to make an action or challenge).
        """
        gs = self.game_state
        # Determine the call to action based on the current phase
        if gs["phase"] == GamePhase.QueryWhichToKeep:
            # Player needs to choose which cards to keep after exchange
            call_to_action_str = f"You need to choose which {'two cards' if len(gs['revealed_hand'][player_id]) == 0 else 'card'} to keep. Use 'keep <card1>" + \
                f"{' <card2>' if len(gs['revealed_hand'][player_id]) == 0 else ''}'"

        elif gs["phase"] == GamePhase.QueryForBlockOrChallenge:
            # Player is being asked if they want to block or challenge
            metadata = gs["action_metadata"]
            action = metadata.action_type
            source_player_id = metadata.source_player_id
            target_player_id = metadata.target_player_id

            # Build the action description
            action_desc = f"Player #{source_player_id} is attempting to {action.value}"
            if action is CoupActionType.Assassinate:
                action_desc += " (they have paid 3 coins)"
            if target_player_id is not None and target_player_id != player_id:
                action_desc += f" on Player #{target_player_id}"
            elif target_player_id == player_id:
                action_desc += " on you"

            # Determine valid block options for current player
            block_options = []
            if action is CoupActionType.ForeignAid:
                block_options.append("'block foreign aid'")
            elif action is CoupActionType.Steal and target_player_id == player_id:
                block_options.extend(["'block steal captain'", "'block steal ambassador'"])
            elif action is CoupActionType.Assassinate and target_player_id == player_id:
                block_options.append("'block assassinate'")

            # Build the call to action
            if block_options:
                block_str = ", ".join(block_options) + ", "
            else:
                block_str = ""

            # Add claim info for challengeable actions
            claim_str = ""
            if action in {CoupActionType.Tax, CoupActionType.Assassinate, CoupActionType.Steal, CoupActionType.Exchange}:
                claim_str = f" (claiming {self._action_to_card(action)})"

            # Build the call to action with proper handling for foreign aid
            bullshit_str = (
                "call 'BULLSHIT', "
                if action is not CoupActionType.ForeignAid
                and metadata.challenger_player_id is None
                else ""
            )
            call_to_action_str = f"{action_desc}{claim_str}. Do you want to {block_str}{bullshit_str}or 'PASS'?"

        elif gs["phase"] == GamePhase.QueryToChallengeTheBlocker:
            # Someone blocked, asking if anyone wants to challenge the block
            metadata = gs["action_metadata"]
            blocker_id = metadata.blocker_player_id
            block_type = metadata.block_type

            # Determine which card the blocker is claiming based on block type
            if block_type is CoupActionType.BlockForeignAid:
                block_claim = "Duke"
            elif block_type is CoupActionType.BlockStealCaptain:
                block_claim = "Captain"
            elif block_type is CoupActionType.BlockStealAmbassador:
                block_claim = "Ambassador"
            elif block_type is CoupActionType.BlockAssassinate:
                block_claim = "Contessa"
            else:
                block_claim = "unknown card"

            call_to_action_str = f"Player #{blocker_id} is blocking with {block_claim}. Do you want to call 'BULLSHIT' or 'PASS'?"

        elif gs["coins"][player_id] >= 10:
            # Forced coup
            call_to_action_str = "You have 10 or more coins and must coup. Use 'coup x' where x is the player id number."

        else:
            # Normal play phase
            call_to_action_str = "What action do you want to take?"

        return call_to_action_str

    def _action_to_card(self, action: CoupActionType) -> str:
        """ Convert a CoupActionType to a card """
        if action is CoupActionType.Tax:
            return "Duke"
        elif action is CoupActionType.Assassinate:
            return "Assassin"
        elif action is CoupActionType.Steal:
            return "Captain"
        elif action is CoupActionType.Exchange:
            return "Ambassador"

        elif action is CoupActionType.BlockAssassinate:
            return "Contessa"
        elif action is CoupActionType.BlockStealCaptain:
            return "Captain"
        elif action is CoupActionType.BlockStealAmbassador:
            return "Ambassador"
        elif action is CoupActionType.BlockForeignAid:
            return "Duke"

        else:
            return "."

    # ---------------------------------------------------------------------
    # GAME STATE ADJUSTMENT METHODS -- SYNTACTIC SUGAR FOR THE GAME LOGIC
    # ---------------------------------------------------------------------
    def _is_valid_target(self, target_player_id: Optional[int]) -> bool:
        return target_player_id is not None and 0 <= target_player_id < self.state.num_players

    def _make_player_lose_a_card(self, player_id: int):
        """
        In a perfect world, the player would pick which card they want to lose.
        But for now, we'll just pop the last card in their hand.
        """
        card = self.game_state["hidden_hand"][player_id].pop()
        self.game_state["revealed_hand"][player_id].append(card)
        if not self.game_state["hidden_hand"][player_id]:
            self.eliminate(player_id)
        return card

    def _advance_game_turn(self) -> Optional[ta.Outcome]:
        """
        Advance the state to the next player based on current phase.
        """
        gs = self.game_state
        if gs["phase"] == GamePhase.Play:
            # Normal play phase - go to next player in turn order
            next_pid = self._next_active_player_after(self.state.current_player_id)

            # Income and Coup immediately advance the turn, so action_metadata is no longer needed
            if gs["action_metadata"] is not None and gs["action_metadata"].action_type in {CoupActionType.Income, CoupActionType.Coup}:
                gs["action_metadata"] = None

        elif gs["phase"] == GamePhase.QueryWhichToKeep:
            # Check if the exchange has been completed (cards_to_keep is set)
            metadata = gs["action_metadata"]
            if metadata.cards_to_keep is not None:
                # Exchange is complete, move to next player
                gs["phase"] = GamePhase.Play
                next_pid = self._next_active_player_after(metadata.source_player_id)
                gs["action_metadata"] = None
            else:
                # Stay with the same player - they still need to choose cards
                next_pid = self.state.current_player_id

        elif gs["phase"] in {GamePhase.QueryForBlockOrChallenge, GamePhase.QueryToChallengeTheBlocker}:
            metadata = gs["action_metadata"]
            if metadata.players_to_query and len(metadata.players_to_query) > 0:
                # Query next player in the list
                next_pid = metadata.players_to_query.pop(0)
            else:
                # No more players to query
                if gs["phase"] == GamePhase.QueryToChallengeTheBlocker:
                    # Only cancel the original action if no one challenged the block
                    # (If someone did challenge and the blocker was honest, the action was already set to PASS in _execute_showdown_on_blocker_bullshit)
                    if metadata.blocker_challenger_player_id is None:
                        # Block was not challenged, so cancel the original action
                        metadata.action_type = CoupActionType.PASS

                # Execute the action (may be PASS if blocked/challenged successfully)
                self._execute_current_action()

                # If we just executed an Exchange, we'll be in QueryWhichToKeep phase
                if gs["phase"] == GamePhase.QueryWhichToKeep:
                    next_pid = metadata.source_player_id
                    metadata.players_to_query = []  # No more players to query
                else:
                    # Return to normal play - next player after action source
                    gs["phase"] = GamePhase.Play
                    next_pid = self._next_active_player_after(metadata.source_player_id)
                    gs["action_metadata"] = None
        else:
            raise Exception(f"Unexpected game phase: {gs['phase']}")

        self.set_next_player(next_pid)

        # Check for winner
        winner = self._get_winner()
        if winner is not None:
            self.step_info["winner"] = winner
            return self.winner(winner, reason=f"Player {winner} has won the game!")
        return None

    def _next_active_player_after(self, player_id: int) -> int:
        """Next player clockwise who still has hidden influence cards (falls back to `player_id`)."""
        next_pid = (player_id + 1) % self.state.num_players
        while len(self.game_state["hidden_hand"][next_pid]) == 0:
            next_pid = (next_pid + 1) % self.state.num_players
            if next_pid == player_id:  # All other players eliminated
                break
        return next_pid

    def _get_winner(self) -> Optional[int]:
        """
        Check if the game is over. Return winning player id if so, otherwise return None.
        """
        remaining_players = [pid for pid in range(self.state.num_players) if len(self.game_state["hidden_hand"][pid]) > 0]
        if len(remaining_players) == 1:
            return remaining_players[0]
        else:
            return None

    # -----------------------------------------------------------------------
    #  PARSE ACTIONS -- JUST BOILERPLATE CODE NOTHING INTERESTING BELOW HERE
    # -----------------------------------------------------------------------
    def _parse_action(self, response_str: str) -> Tuple[CoupActionType, Optional[Union[int, List[str]]]]:
        """
        Convert the submitted action to (CoupActionType, arg). The action is the bare command
        (e.g. 'income', 'coup 3'); stray square brackets are tolerated for robustness (the last
        bracketed chunk is used if any are present).

        The purpose of this method is TO PARSE ONLY. It makes sure the response is translated into a valid action, but does not validate against the state of the game.
        """
        cleaned = response_str.replace("[GAME]", " ").strip()
        bracketed = re.fullmatch(r"\[\s*([^\[\]]+?)\s*\]", cleaned)
        if bracketed:
            cmd = bracketed.group(1).strip().lower()
        else:
            if "[" in cleaned or "]" in cleaned:
                raise ValueError("Submit exactly one complete Coup command.")
            cmd = cleaned.lower()
        tokens = cmd.split()

        if not tokens:
            raise ValueError("Empty command. What is your desired action?")

        # ---------- Simple one-word actions ----------
        simple = {"income": CoupActionType.Income, "tax": CoupActionType.Tax, "exchange": CoupActionType.Exchange, "pass": CoupActionType.PASS, "bullshit": CoupActionType.BULLSHIT}
        if tokens[0] in simple:
            if len(tokens) > 1:
                raise ValueError(f"Invalid action: {tokens[0]}, cannot have more than one word when doing a {tokens[0]}")
            return simple[tokens[0]], None

        if tokens[:2] == ["foreign", "aid"]:
            if len(tokens) > 2:
                raise ValueError(f"Invalid action: {response_str}, cannot have more than two words when doing a foreign aid")
            return CoupActionType.ForeignAid, None

        # ---------- Directed actions ----------
        directed_map = {"coup": CoupActionType.Coup, "assassinate": CoupActionType.Assassinate, "steal": CoupActionType.Steal}
        if tokens[0] in directed_map:
            if len(tokens) != 2 or not tokens[1].isdigit():
                raise ValueError(f"Missing / invalid target for '{tokens[0]}'.")
            return directed_map[tokens[0]], int(tokens[1])

        # ---------- Ambassador "keep" special ----------
        if tokens[0] == "keep":
            if len(tokens) < 2 or len(tokens) > 3:
                raise ValueError("'keep' must specify one or two cards to keep.")

            cards = []
            for i in range(1, len(tokens)):
                if tokens[i].lower() not in {"duke", "assassin", "ambassador", "captain", "contessa"}:
                    raise ValueError(f"Invalid card name: {tokens[i]}")
                cards.append(tokens[i].lower())

            return CoupActionType.Keep, cards

        # ---------- Blocks ----------
        if tokens[0] == "block":
            if tokens == ["block", "foreign", "aid"]:
                return CoupActionType.BlockForeignAid, None
            if len(tokens) == 3 and tokens[1] == "steal":
                if tokens[2] == "ambassador":
                    return CoupActionType.BlockStealAmbassador, None
                if tokens[2] == "captain":
                    return CoupActionType.BlockStealCaptain, None
                raise ValueError("Block steal must specify 'ambassador' or 'captain'.")
            if tokens == ["block", "assassinate"]:
                return CoupActionType.BlockAssassinate, None

        raise ValueError(f"Unrecognized command: {cmd}")

    #########################################################################
    #  RENDERING METHOD
    #########################################################################
    def _game_state_to_headline_str(self, game_state: Dict[str, Any]):
        """
        Convert the game state to a headline string.
        """
        if self._get_winner() == self.state.current_player_id:
            return f"Player #{self._get_winner()} has won!"
        if game_state["phase"] == GamePhase.Play:
            return f"It's Player #{self.state.current_player_id}'s turn"
        elif game_state["phase"] == GamePhase.QueryForBlockOrChallenge:
            tgt_player_str = ""
            if game_state['action_metadata'].action_type in {CoupActionType.Assassinate, CoupActionType.Steal}:
                tgt_player_str = f" on Player #{game_state['action_metadata'].target_player_id}" if game_state['action_metadata'].action_type is CoupActionType.Assassinate else f" from Player #{game_state['action_metadata'].target_player_id}"
            return f"Player #{game_state['action_metadata'].source_player_id} is attempting a {game_state['action_metadata'].action_type.name}{tgt_player_str}, asking if Player #{self.state.current_player_id} wants to block/challenge."
        elif game_state["phase"] == GamePhase.QueryToChallengeTheBlocker:
            return f"Player #{game_state['action_metadata'].blocker_player_id} is doing a {game_state['action_metadata'].block_type.name} on Player #{game_state['action_metadata'].source_player_id}, asking if Player #{self.state.current_player_id} wants to challenge the block."
        elif game_state["phase"] == GamePhase.QueryWhichToKeep:
            return f"Player #{game_state['action_metadata'].source_player_id} is attempting an Exchange, asking which they wish to keep."
        else:
            raise Exception(f"Unexpected game phase: {game_state['phase']}")

    def _get_player_marker(self, player_id: int, game_state: Dict[str, Any]):
        """
        Helper function to display a useful marker to show the player's status in the game.
        """
        if self._get_winner() == player_id:
            return "👑"  # Player is the winner
        if game_state["hidden_hand"][player_id] == []:
            return "💀"  # Player is eliminated
        if (game_state["phase"] == GamePhase.QueryForBlockOrChallenge or game_state["phase"] == GamePhase.QueryToChallengeTheBlocker) and \
                player_id == game_state["action_metadata"].blocker_player_id:
            return "B"  # Player is blocking the action

        if game_state["phase"] == GamePhase.QueryWhichToKeep and player_id == game_state["action_metadata"].source_player_id:
            return "🔀"  # Player being asked which cards they wish to keep

        if self.state.current_player_id == player_id:
            return "*"  # Player is the current player

        if game_state["action_metadata"] is not None and game_state["action_metadata"].source_player_id == player_id:
            return "."  # Player is awaiting potential challenges

        return " "  # Player is not involved in the action

    def _render_board(self, viewer_id: Optional[int] = None):
        """
        Pretty console renderer for a Coup game_state.

        The offset and adjustment are used to ensure that the board is always LINE_WIDTH characters wide, because ansii codes add to char count but not to spacing.
        """
        # --- helpers -----------------------------------------------------------
        game_state = self.game_state

        # Card colors - specific ANSI codes for each card type
        CARD_COLOURS = {
            "Contessa": 91,      # Red
            "Ambassador": 92,    # Green
            "Duke": 95,          # Purple/Magenta
            "Captain": 94,       # Blue
            "Assassin": 90       # Dark Grey
        }

        # Player header colors - using different colors from cards
        # Using: Yellow(93), Cyan(96), White(97), and variations
        PLAYER_COLOURS = [93, 96, 97, 33, 35, 36]

        def colour(text: str, code: int) -> str:
            return f"\033[{code}m{text}\033[0m"

        def bold_underline_colour(text: str, code: int) -> str:
            # Combines bold (1), underline (4) and color in one ANSI code
            return f"\033[1;4;{code}m{text}\033[0m"

        def strike(text: str) -> str:
            # ANSI strike-through (not supported in a few older terminals)
            return f"\033[9m{text}\033[0m"

        # -----------------------------------------------------------------------

        out_lines = ["", self._game_state_to_headline_str(game_state), ""]
        # Sort players numerically for reproducibility
        for pid in range(self.state.num_players):
            player_colour_code = PLAYER_COLOURS[pid % len(PLAYER_COLOURS)]

            # "*" means this is the current player who just did an action
            # "." means this is the player who initially triggered a QueryForX phase
            # " " means this is a player who is not involved in the action

            # ----- header: "Player #x" (unique colour) -----
            curr_player_marker = self._get_player_marker(pid, game_state)
            header = bold_underline_colour(f"[{curr_player_marker}] - Player #{pid}", player_colour_code)
            out_lines.append(f"{header}  ––  {game_state['coins'][pid]} coin{'s' if game_state['coins'][pid] != 1 else ''}")

            # ----- cards -----------------------------------
            hand_cards = game_state["hidden_hand"][pid]   # Hidden cards
            revealed = game_state["revealed_hand"][pid]   # Revealed/lost cards

            if pid == viewer_id:
                for card in hand_cards:
                    card_colour_code = CARD_COLOURS.get(card, 97)  # Default to white if card not found
                    out_lines.append(f"   - {colour(card, card_colour_code)}")
            else:
                for _ in hand_cards:
                    out_lines.append("   - Hidden influence")

            # Sometimes revealed cards may no longer be in hand (fully lost)
            for card in revealed:
                card_colour_code = CARD_COLOURS.get(card, 97)  # Default to white if card not found
                out_lines.append(f"   - {colour(strike(card), card_colour_code)}")

            out_lines.append("")

        out_lines.append("")
        out_lines.append("")
        # from_ansi is used to ensure that the ANSI codes are properly padded while rendering
        return Text.from_ansi("\n".join(out_lines))
