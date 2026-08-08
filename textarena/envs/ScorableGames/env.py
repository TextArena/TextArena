import os
import re
from typing import Any, Dict, List, Optional, Tuple

import textarena as ta
from textarena.state import TeamMultiPlayerState
from textarena.envs.ScorableGames.renderer import (
    render_game_issues,
    render_deal_with_scores_and_votes
)


class ScorableGamesEnv(ta.Env):
    """
    Multi-player negotiation environment based on LLM-Deliberation research.
    Players negotiate over multiple issues with private scoring functions.
    """
    
    def __init__(self, game_config: str = "base", max_rounds: int = 120, 
                 required_votes: Optional[int] = None,
                 veto_roles: List[str] = ["p1", "p2"],
                 unanimity_bonus_role: str = "p1",
                 starting_role: str = "p1",
                 invalid_move_default: str = "[Accept]",
                 error_allowance: int = 3
                 ):
        """
        Initialize the ScorableGames environment.
        
        Args:
            game_config: Name of game configuration folder in games_descriptions/
            max_rounds: Maximum number of negotiation rounds
            required_votes: Number of accept votes needed (default: num_players - 1)
            veto_roles: List of roles with veto power (default: ["p1", "p2"])
            unanimity_bonus_role: Role that gets +10 bonus for unanimity (default: "p1")
            starting_role: Role that starts the negotiation (default: "p1")
            invalid_move_default: Default for a player who plays an invalid move.
            error_allowance: Number of invalid moves allowed before applying default action (default: 3)
        """
        self.game_config = game_config
        self.max_rounds = max_rounds
        self.required_votes = required_votes 
        self.veto_roles = veto_roles
        self.unanimity_bonus_role = unanimity_bonus_role
        self.starting_role = starting_role
        self.invalid_move_default = invalid_move_default
        self.error_allowance = error_allowance
        
        # Game configuration data
        self.game_dir = os.path.join(os.path.dirname(__file__), "games_descriptions", game_config)
        self.global_instructions = ""
        self.issues = {}  # Issue definitions and options
        self.player_configs = {}  # Player configurations from config.txt
        self.player_scores = {}  # Private scoring functions
        self.player_instructions = {}  # Individual instructions
        
        # Game state
        self.current_deal = {}  # Current deal proposal
        self.negotiation_history = []  # History of actions
        self.player_votes = {}  # Current round votes
        self.valid_actions_this_round = set()  # Players with valid actions
        
    def reset(self, num_players: int, seed: Optional[int] = None):
        """Reset the environment to initial state."""
        # Load game configuration
        self._load_game_configuration()
        
        # Validate number of players matches config
        if len(self.player_configs) != num_players:
            raise ValueError(f"Game config expects {len(self.player_configs)} players, got {num_players}")
        
        # Initialize TextArena state with TeamMultiPlayerState for better error handling
        self.state = TeamMultiPlayerState(
            num_players=num_players,
            max_turns=self.max_rounds,
            seed=seed,
            error_allowance=self.error_allowance
        )
        
        # Initialize game state
        game_state = {
            "current_deal": {},
            "negotiation_history": [],
            "player_votes": {},
            "valid_actions_this_round": set(),
        }
        
        # Call the state's reset method to properly initialize error_count and other attributes
        self.state.reset(
            game_state=game_state,
            player_prompt_function=self._generate_player_prompt
        )
        
        # Set starting player based on configured starting role
        starting_player_id = self._get_player_by_role(self.starting_role)
        if starting_player_id is not None:
            self.state.current_player_id = starting_player_id
        
        # Reset instance variables
        self.current_deal = {}
        self.negotiation_history = []
        self.player_votes = {}
        self.valid_actions_this_round = set()
    
    def _load_game_configuration(self):
        """Load game configuration from files."""
        if not os.path.exists(self.game_dir):
            raise FileNotFoundError(f"Game configuration directory not found: {self.game_dir}")
        
        # Load global instructions
        global_file = os.path.join(self.game_dir, "global_instructions.txt")
        with open(global_file, 'r') as f:
            self.global_instructions = f.read().strip()
        
        # Parse issues from global instructions
        self._parse_issues_from_global_instructions()
        
        # Load player configurations
        config_file = os.path.join(self.game_dir, "config.txt")
        self._load_player_configurations(config_file)
        
        # Load player scores and instructions
        self._load_player_data()
    
    def _parse_issues_from_global_instructions(self):
        """Parse issue definitions from global instructions."""
        self.issues = {}
        
        # Split by the separator lines to get individual issue sections
        sections = re.split(r'=+', self.global_instructions)
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
                
            # Look for Issue X: "Name" pattern
            issue_match = re.search(r'Issue ([A-Z]):\s*"([^"]+)"', section)
            if not issue_match:
                continue
                
            issue_key = issue_match.group(1)
            issue_name = issue_match.group(2)
            
            options = {}
            
            # Find all options in this section: A1 "name": description
            option_pattern = rf'{issue_key}(\d+)\s+"([^"]+)":\s*([^\n]+(?:\n(?!{issue_key}\d)[^\n]*)*)'
            option_matches = re.findall(option_pattern, section, re.MULTILINE)
            
            for option_num, option_name, option_desc in option_matches:
                option_key = f"{issue_key}{option_num}"
                # Clean up the description
                clean_desc = re.sub(r'\s+', ' ', option_desc.strip())
                options[option_key] = f"{option_name}: {clean_desc}"
            
            if options:  # Only add if we found valid options
                self.issues[issue_key] = {
                    "name": issue_name,
                    "options": options
                }
    
    def _load_player_configurations(self, config_file: str):
        """Load player configurations from config.txt."""
        self.player_configs = {}
        
        with open(config_file, 'r') as f:
            for line_num, line in enumerate(f):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = [part.strip() for part in line.split(',')]
                if len(parts) != 5:
                    raise ValueError(f"Invalid config line {line_num + 1}: {line}")
                
                agent_name, file_name, role, incentive, model = parts
                player_id = len(self.player_configs)
                
                self.player_configs[player_id] = {
                    "agent_name": agent_name,
                    "file_name": file_name,
                    "role": role,
                    "incentive": incentive,
                    "model": model
                }
    
    def _get_player_by_role(self, role: str) -> Optional[int]:
        """Get player ID by role (p1, p2, etc.)."""
        for player_id, config in self.player_configs.items():
            if config["role"] == role:
                return player_id
        return None
    
    def _load_player_data(self):
        """Load player scores and individual instructions."""
        self.player_scores = {}
        self.player_instructions = {}
        
        for player_id, config in self.player_configs.items():
            file_name = config["file_name"]
            incentive = config["incentive"]
            
            # Load scores
            scores_file = os.path.join(self.game_dir, "scores_files", f"{file_name}.txt")
            self.player_scores[player_id] = self._load_player_scores(scores_file)
            
            # Load individual instructions
            instructions_file = os.path.join(
                self.game_dir, "individual_instructions", incentive, f"{file_name}.txt"
            )
            with open(instructions_file, 'r') as f:
                self.player_instructions[player_id] = f.read().strip()
    
    def _load_player_scores(self, scores_file: str) -> Dict[str, Dict[str, int]]:
        """Load player scoring function from scores file."""
        scores = {}
        
        with open(scores_file, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]
        
        # Map lines to issues (A, B, C, etc.)
        issue_keys = sorted(self.issues.keys())
        
        for i, line in enumerate(lines[:-1]):  # Last line is threshold
            if i < len(issue_keys):
                issue_key = issue_keys[i]
                score_values = [int(x.strip()) for x in line.split(',')]
                
                # Map scores to options (A1, A2, etc.)
                issue_options = sorted(self.issues[issue_key]["options"].keys())
                issue_scores = {}
                
                for j, score in enumerate(score_values):
                    if j < len(issue_options):
                        option_key = issue_options[j]
                        issue_scores[option_key] = score
                
                scores[issue_key] = issue_scores
        
        # Store minimum threshold
        if lines:
            scores["threshold"] = int(lines[-1])
        
        return scores
    
    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        """Generate initial prompt for a player."""
        config = self.player_configs[player_id]
        agent_name = config["agent_name"]
        
        # Extract only the scenario part (before issues) from global instructions
        global_text = self._extract_scenario_from_global_instructions(agent_name)
        
        # Get individual instructions with scores filled in
        individual_text = self._fill_scores_in_instructions(player_id)
        
        # Generate dynamic voting rules based on configuration
        voting_rules = "\n" + self._generate_voting_rules_text(player_id)

        # Game rules and actions
        rules_text = f"""

GAME RULES:
- This is a {self.state.num_players}-player negotiation game with {self.max_rounds} rounds maximum.
- Currently, it is Round {self.state.turn + 1} of {self.max_rounds}.
- You must negotiate to reach a deal regarding all issues.
- Your goal is to maximize your total score from the final deal.
- The game ends when a deal is accepted or max rounds reached.
- You cannot under any circumstances disclose numbers in your scoring sheet or the values of the deal to the other parties. But you can share
high-level priorities (e.g., you can say I cannot accept option D5, etc.)

REQUIRED ACTION FORMAT:
- You must propose complete deals covering all issues (use space-separated format like A1 B2 C3 D1 E4).
- Always provide your reasoning BEFORE the bracketed action
- Any text after the bracketed action will be ignored

Examples:
- Make a proposal:
  ```
  I think this balances everyone's interests while protecting the environment.
  [Propose] A1 B2 C2 D2 E3
  ```

- Accept a proposal:
  ```
  This meets my minimum acceptable score and helps the community.
  [Accept]
  ```

- Reject a proposal:
  ```
  The environmental impact is too severe for my constituents.
  [Reject]
  ```

{voting_rules}

SCORING:
- You can see your own scores for different options below.
- Other players have different preferences (hidden from you).
- Your minimum acceptable score is {self.player_scores[player_id].get('threshold', 0)} points.
- If no deal is reached after max rounds, you will get {self.player_scores[player_id].get('threshold', 0)} points.
"""
        
        # Show available issues
        issues_text = "\n" + render_game_issues(self.issues)
        
        # Show player's private scores
        if self.current_deal:
            scores_text = "\n" + render_deal_with_scores_and_votes(
                self.current_deal, self.issues, 
                self.player_scores[player_id], agent_name,
                self.player_votes, self.player_configs
            )
        else:
            scores_text = f"\n{agent_name}'s Private Scoring Function:\n"
            scores_text += "=" * 30 + "\n"
            for issue_key, issue_scores in self.player_scores[player_id].items():
                scores_text += f"{issue_key}: {issue_scores}\n".replace('threshold','Minimum acceptable score')
        
        # Reorder: global_text + issues_text + individual_text + rules_text + scores_text
        return global_text + "\n" + issues_text + "\n\n" + individual_text + "\n" + rules_text + "\n" + scores_text
    
    def _fill_scores_in_instructions(self, player_id: int) -> str:
        """Fill score placeholders in individual instructions."""
        instructions = self.player_instructions[player_id]
        scores = self.player_scores[player_id]
        
        # Replace score placeholders like #A1_NUM, #A_MAX_NUM, etc.
        for issue_key, issue_scores in scores.items():
            if issue_key == "threshold":
                continue
                
            # Replace individual option scores
            for option_key, score in issue_scores.items():
                placeholder = f"#{option_key}_NUM"
                instructions = instructions.replace(placeholder, str(score))
            
            # Replace max score for issue
            max_score = max(issue_scores.values()) if issue_scores else 0
            max_placeholder = f"#{issue_key}_MAX_NUM"
            instructions = instructions.replace(max_placeholder, str(max_score))
        
        return instructions
    
    def _generate_voting_rules_text(self, player_id: int) -> str:
        """Generate dynamic voting rules text based on configuration parameters."""
        
        # Calculate required votes
        required_votes = self.required_votes if self.required_votes is not None else (self.state.num_players - 1)
        
        # Build threshold explanation
        threshold_text = f"- A proposal passes if at least {required_votes} out of {self.state.num_players} players accept"
        
        # Build veto power explanation
        veto_text = ""
        if self.veto_roles:
            veto_players = []
            current_player_has_veto = False
            
            for role in self.veto_roles:
                veto_player_id = self._get_player_by_role(role)
                if veto_player_id is not None:
                    veto_player_name = self.player_configs[veto_player_id]["agent_name"]
                    if veto_player_id == player_id:
                        current_player_has_veto = True
                    else:
                        veto_players.append(veto_player_name)
            
            if current_player_has_veto and veto_players:
                if len(veto_players) == 1:
                    veto_text = f"- Both you and {veto_players[0]} have veto power - you both must accept for any deal to pass"
                else:
                    veto_text = f"- You and {', '.join(veto_players)} have veto power - all veto players must accept for any deal to pass"
            elif current_player_has_veto and not veto_players:
                veto_text = f"- You have veto power - you must accept for any deal to pass"
            elif veto_players:
                if len(veto_players) == 1:
                    veto_text = f"- {veto_players[0]} has veto power - they must accept for any deal to pass"
                else:
                    veto_text = f"- {', '.join(veto_players)} have veto power - they all must accept for any deal to pass"
        
        # Build unanimity bonus explanation
        bonus_text = ""
        if self.unanimity_bonus_role:
            bonus_player_id = self._get_player_by_role(self.unanimity_bonus_role)
            if bonus_player_id is not None:
                bonus_player_name = self.player_configs[bonus_player_id]["agent_name"]
                if bonus_player_id == player_id:
                    bonus_text = f"- UNANIMITY BONUS: If all {self.state.num_players} players accept, you get +10 bonus points"
                else:
                    bonus_text = f"- {bonus_player_name} gets +10 bonus points if all players achieve unanimity"
        
        # Combine all parts
        voting_rules = "VOTING RULES:\n"
        voting_rules += threshold_text + "\n"
        if veto_text:
            voting_rules += veto_text + "\n"
        if bonus_text:
            voting_rules += bonus_text + "\n"
        
        return voting_rules

    def _extract_scenario_from_global_instructions(self, agent_name: str) -> str:
        """Extract only the scenario part (before issues) from global instructions."""
        # Replace agent name in global instructions
        global_text = self.global_instructions.replace(f'"{agent_name}"', f'"{agent_name}" (represented by you)')
        
        # Find where the issues start and cut off there
        # Look for the first "Issue A:" pattern to know where to stop
        issue_start = re.search(r'Issue [A-Z]:', global_text)
        if issue_start:
            # Return everything before the first issue
            return global_text[:issue_start.start()].strip()
        else:
            # If no issues found, return the whole text (fallback)
            return global_text
    
    def step(self, action: str) -> Tuple[bool, ta.Info]:
        """Process a player's action."""
        current_pid = self.state.current_player_id
        
        # Log the action
        self.state.add_observation(
            from_id=current_pid,
            to_id=current_pid,
            message=f"Your action: {action}",
            observation_type=ta.ObservationType.PLAYER_ACTION
        )
        
        # Process the action
        can_advance = False
        if self._is_valid_action(action):
            self.valid_actions_this_round.add(current_pid)
            self._process_valid_action(current_pid, action)
            can_advance = True
        else:
            # Handle invalid action - returns True if default was applied and we can advance
            can_advance = self._handle_invalid_action(current_pid, action)
            
            # If default was applied, treat it as a valid action
            if can_advance:
                self.valid_actions_this_round.add(current_pid)
        
        # Check for game end conditions
        if self._check_deal_accepted() or self.state.turn >= self.max_rounds - 1:
            self._end_game()
            return self.state.step()
        
        # Only advance to next player if we can advance (valid action or default applied)
        if can_advance:
            self.state.current_player_id = (self.state.current_player_id + 1) % self.state.num_players
        
        # Call TeamMultiPlayerState's step method
        return self.state.step()
    
    def _is_valid_action(self, action: str) -> bool:
        """Check if an action is valid."""
        action = action.strip()
        
        # Check for our specific bracketed actions only
        if "[Propose]" in action:
            return self._is_valid_proposal(action)
        elif "[Accept]" in action:
            return True
        elif "[Reject]" in action:
            return True
        return False
    
    def _is_valid_proposal(self, action: str) -> bool:
        """Check if a proposal is valid."""
        try:
            # Handle bracketed format [Propose] A1 B2 C3 D1 E4
            if "[Propose]" in action:
                proposal_part = action.split("[Propose]")[1].strip()
                # Only take the first line to avoid parsing extra text
                first_line = proposal_part.split('\n')[0].strip()
                deal_parts = first_line.split()
            else:
                return False
            
            # Check if all issues are covered
            expected_issues = set(self.issues.keys())
            proposed_issues = set()
            
            for part in deal_parts:
                part = part.strip().rstrip('.,!?;:')  # Remove common punctuation
                if len(part) >= 2:
                    issue_key = part[0]
                    if issue_key in expected_issues:
                        # Check if option exists
                        if issue_key in self.issues and part in self.issues[issue_key]["options"]:
                            proposed_issues.add(issue_key)
                        else:
                            return False
            
            return proposed_issues == expected_issues
            
        except Exception:
            return False
    
    def _process_valid_action(self, player_id: int, action: str):
        """Process a valid action."""
        action = action.strip()
        
        if "[Propose]" in action:
            self._process_proposal(player_id, action)
        elif "[Accept]" in action:
            self._process_vote(player_id, action, "[Accept]")
        elif "[Reject]" in action:
            self._process_vote(player_id, action, "[Reject]")
    
    def _process_proposal(self, player_id: int, action: str):
        """Process a deal proposal."""
        # Extract rationale (everything before [Propose])
        rationale = action.split("[Propose]")[0].strip()
        
        # Extract proposal part after [Propose]
        proposal_part = action.split("[Propose]")[1].strip()
        
        # Parse space-separated deal (A1 B2 C3 D1 E4)
        # Only take the first line and split by spaces to avoid parsing extra text
        first_line = proposal_part.split('\n')[0].strip()
        deal_parts = first_line.split()
        
        # Build the deal dictionary - only include valid issue options
        new_deal = {}
        expected_issues = set(self.issues.keys())
        
        for part in deal_parts:
            part = part.strip()
            if len(part) >= 2:
                issue_key = part[0]
                # Only add if it's a valid issue and option
                if (issue_key in expected_issues and 
                    issue_key in self.issues and 
                    part in self.issues[issue_key]["options"]):
                    new_deal[issue_key] = part
        
        # Only proceed if we have a complete deal
        if len(new_deal) == len(expected_issues):
            config = self.player_configs[player_id]
            
            # Check if this is identical to current deal
            if self.current_deal and new_deal == self.current_deal:
                # Same deal - treat as acceptance
                self.player_votes[player_id] = "[Accept]"
                self.state.game_state["player_votes"] = self.player_votes
                
                # Announce as acceptance with rationale
                if rationale:
                    message = f"{config['agent_name']} says: {rationale}\n{config['agent_name']} accepts the current proposal"
                else:
                    message = f"{config['agent_name']} accepts the current proposal"
                
                self.state.add_observation(
                    from_id=ta.GAME_ID,
                    to_id=-1,
                    message=message,
                    observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
                )
                
                # Record as acceptance in history
                self.negotiation_history.append({
                    "player_id": player_id,
                    "action_type": "[Accept]",
                    "rationale": rationale,
                    "proposal": self.current_deal.copy(),
                    "round": self.state.turn
                })
            else:
                # Different deal - normal proposal logic
                self.current_deal = new_deal
                self.state.game_state["current_deal"] = new_deal
                
                # Clear previous votes
                self.player_votes = {}
                self.state.game_state["player_votes"] = {}
                
                # Announce the proposal with rationale
                deal_str = ", ".join([f"{k}:{v}" for k, v in sorted(new_deal.items())])
                
                if rationale:
                    message = f"{config['agent_name']} says: {rationale}\n{config['agent_name']} proposes: {deal_str}"
                else:
                    message = f"{config['agent_name']} proposes: {deal_str}"
                
                self.state.add_observation(
                    from_id=ta.GAME_ID,
                    to_id=-1,
                    message=message,
                    observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
                )
                
                # Scores will be shown to current player via get_observation()
                
                # Record in history with enhanced structure
                self.negotiation_history.append({
                    "player_id": player_id,
                    "action_type": "[Propose]",
                    "rationale": rationale,
                    "proposal": new_deal.copy(),
                    "round": self.state.turn
                })
        else:
            # Invalid proposal - handle manually
            self._handle_invalid_action(player_id, action)
    
    def _process_vote(self, player_id: int, action: str, vote: str):
        """Process an accept/reject vote."""
        if not self.current_deal:
            # No current proposal - handle as invalid action
            self._handle_invalid_action(player_id, action)
            return
        
        # Extract rationale (everything before [Accept] or [Reject])
        if vote in action:
            rationale = action.split(vote)[0].strip()
        else:
            rationale = ""
        
        self.player_votes[player_id] = vote
        self.state.game_state["player_votes"] = self.player_votes
        
        config = self.player_configs[player_id]
        
        if rationale:
            message = f"{config['agent_name']} says: {rationale}\n{config['agent_name']} votes: {vote}"
        else:
            message = f"{config['agent_name']} votes: {vote}"
        
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=message,
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )
        
        # Record in history with enhanced structure
        self.negotiation_history.append({
            "player_id": player_id,
            "action_type": vote,
            "rationale": rationale,
            "proposal": self.current_deal.copy(),
            "round": self.state.turn
        })
    
    def _handle_invalid_action(self, player_id: int, action: str) -> bool:
        """Handle an invalid action using TeamMultiPlayerState's built-in escalation. Returns True if default action was applied."""
        # Determine the reason for invalid action
        if "[Propose]" in action:
            reason = "Invalid proposal format. Use: [Propose] A1 B2 C3 D1 E4 (cover all issues with valid options)"
        elif not any(keyword in action for keyword in ["[Propose]", "[Accept]", "[Reject]"]):
            reason = "Invalid action. Use: [Propose] A1 B2 C3 D1 E4, [Accept], or [Reject]"
        else:
            reason = "Invalid action format"
        
        # Use TeamMultiPlayerState's built-in escalation handling
        should_apply_default = self.state.set_invalid_move(reason)
        
        if should_apply_default:
            # Player exceeded error allowance - apply default action and advance turn
            self._apply_default_action(player_id)
            return True  # Signal that we applied default and can advance turn
        else:
            # Player gets another chance - don't advance turn
            return False  # Signal that turn should not advance
    
    def _apply_default_action(self, player_id: int):
        """Apply default action when player exceeds error allowance."""
        config = self.player_configs[player_id]
        
        if self.current_deal:
            # There's a current proposal - default their vote
            self.player_votes[player_id] = self.invalid_move_default
            self.state.game_state["player_votes"] = self.player_votes
            
            message = f"{config['agent_name']} exceeded number of invalid actions limit, defaulting vote to {self.invalid_move_default}"
            self.state.add_observation(
                from_id=ta.GAME_ID,
                to_id=-1,
                message=message,
                observation_type=ta.ObservationType.GAME_ADMIN
            )
            
            # Record in history with enhanced structure
            self.negotiation_history.append({
                "player_id": player_id,
                "action_type": self.invalid_move_default,
                "rationale": "Auto-defaulted after exceeding number of invalid actions limit",
                "proposal": self.current_deal.copy(),
                "round": self.state.turn
            })
        else:
            # No current proposal - generate optimal proposal
            optimal_proposal = self._generate_optimal_proposal(player_id)
            self.current_deal = optimal_proposal
            self.state.game_state["current_deal"] = optimal_proposal
            
            # Clear previous votes
            self.player_votes = {}
            self.state.game_state["player_votes"] = {}
            
            # Announce the auto-generated proposal
            deal_str = ", ".join([f"{k}:{v}" for k, v in sorted(optimal_proposal.items())])
            message = f"{config['agent_name']} exceeded error limit, auto-proposing: {deal_str}"
            
            self.state.add_observation(
                from_id=ta.GAME_ID,
                to_id=-1,
                message=message,
                observation_type=ta.ObservationType.GAME_ADMIN
            )
            
            
            # Record in history with enhanced structure
            self.negotiation_history.append({
                "player_id": player_id,
                "action_type": "[Propose]",
                "rationale": f"Auto-defaulted after exceeding number of invalid actions limit",
                "proposal": optimal_proposal.copy(),
                "round": self.state.turn
            })
        
        # Reset error count after applying default action so the game can continue normally
        self.state.error_count = 0
        self.state.made_invalid_move = False
    
    def _generate_optimal_proposal(self, player_id: int) -> Dict[str, str]:
        """Generate an optimal proposal that maximizes the player's score."""
        optimal_deal = {}
        player_scores = self.player_scores[player_id]
        
        for issue_key in self.issues.keys():
            if issue_key in player_scores and issue_key != "threshold":
                # Find the option with the highest score for this issue
                best_option = None
                best_score = float('-inf')
                
                for option_key, score in player_scores[issue_key].items():
                    if score > best_score:
                        best_score = score
                        best_option = option_key
                
                if best_option:
                    optimal_deal[issue_key] = best_option
        
        return optimal_deal
    
    def _check_deal_accepted(self) -> bool:
        """
        Check if the current deal has been accepted using configurable voting rules:
        - Need required_votes accept votes (default: num_players - 1)
        - Players with veto_roles must accept (default: ["p1", "p2"])
        - Deal cannot pass until all veto players have voted
        """
        if not self.current_deal or not self.player_votes:
            return False
        
        # Get veto player IDs
        veto_player_ids = []
        for role in self.veto_roles:
            player_id = self._get_player_by_role(role)
            if player_id is not None:
                veto_player_ids.append(player_id)
        
        # If no veto players found, fall back to simple majority
        if not veto_player_ids:
            return self._check_simple_majority()
        
        # Check if all veto players have voted
        veto_players_voted = all(pid in self.player_votes for pid in veto_player_ids)
        
        # Deal cannot pass until ALL veto players have voted
        if not veto_players_voted:
            return False
        
        # Check if all veto players accepted (veto power)
        veto_players_accepted = all(
            self.player_votes[pid] == "[Accept]" for pid in veto_player_ids
        )
        
        # If any veto player rejected, deal fails immediately
        if not veto_players_accepted:
            return False
        
        # Count total accept votes
        total_players = self.state.num_players
        accept_votes = sum(1 for vote in self.player_votes.values() if vote == "[Accept]")
        
        # Determine required votes (default: num_players - 1)
        required_votes = self.required_votes if self.required_votes is not None else (total_players - 1)
        
        return accept_votes >= required_votes
    
    def _check_simple_majority(self) -> bool:
        """Fallback to simple majority if P1/P2 not found."""
        total_players = self.state.num_players
        accept_votes = sum(1 for vote in self.player_votes.values() if vote == "[Accept]")
        majority_threshold = (total_players // 2) + 1
        return accept_votes >= majority_threshold
    
    def _check_unanimity(self) -> bool:
        """Check if all players voted [Accept] (for P1 bonus)."""
        if len(self.player_votes) != self.state.num_players:
            return False
        return all(vote == "[Accept]" for vote in self.player_votes.values())
    
    def _end_game(self):
        """End the game and determine winners."""
        if self._check_deal_accepted():
            # Deal was accepted
            self._finalize_accepted_deal()
        else:
            # No deal reached
            self._handle_no_deal()
        
        self.state.done = True
    
    def _finalize_accepted_deal(self):
        """Finalize an accepted deal, determine scores, and assign rewards based on thresholds."""
        deal_str = ", ".join([f"{k}:{v}" for k, v in self.current_deal.items()])
        
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=f"DEAL ACCEPTED: {deal_str}",
            observation_type=ta.ObservationType.GAME_ADMIN
        )
        
        # Step 1: Calculate final scores
        final_scores = {}
        unanimity_achieved = self._check_unanimity()
        bonus_player_id = self._get_player_by_role(self.unanimity_bonus_role)
        
        for pid in range(self.state.num_players):
            score = self._calculate_player_score(pid, self.current_deal)
            
            # Apply unanimity bonus if applicable
            if unanimity_achieved and pid == bonus_player_id:
                score += 10
                role_name = self.player_configs[pid]["agent_name"]
                self.state.add_observation(
                    from_id=ta.GAME_ID,
                    to_id=pid,
                    message=f"{role_name} unanimity bonus: +10 points",
                    observation_type=ta.ObservationType.GAME_ADMIN
                )
            
            final_scores[pid] = score
            
            # Save raw score in game_info
            self.state.game_info[pid]["score"] = score
            
            # Announce score vs threshold
            threshold = self.player_scores[pid].get("threshold", 0)
            config = self.player_configs[pid]
            self.state.add_observation(
                from_id=ta.GAME_ID,
                to_id=pid,
                message=f"{config['agent_name']} final score: {score} points (threshold: {threshold})",
                observation_type=ta.ObservationType.GAME_ADMIN
            )
        
        # Step 2: Threshold-based rewards
        rewards = {}
        winners = [pid for pid, score in final_scores.items()
                if score >= self.player_scores[pid].get("threshold", 0)]
        
        if winners:
            # Players who meet threshold → +1, others → -1
            for pid in range(self.state.num_players):
                rewards[pid] = 1.0 if pid in winners else -1.0
        else:
            # No players met threshold → everyone gets 0 (draw)
            rewards = {pid: 0.0 for pid in final_scores}
        
        self.state.rewards = rewards
        
        # Step 3: Winner/draw annotation
        if winners:
            best_score = max(final_scores[pid] for pid in winners)
            best_players = [pid for pid in winners if final_scores[pid] == best_score]
            
            if len(best_players) == 1:
                self.state.step_info["winner_reason"] = (
                    f"{self.player_configs[best_players[0]]['agent_name']} wins "
                    f"with highest score {best_score} (meeting threshold)"
                )
                for pid in range(self.state.num_players):
                    self.state.game_info[pid]["winner"] = pid in best_players
            else:
                self.state.step_info["draw_reason"] = f"Tie with score {best_score} among {len(best_players)} players"
                for pid in range(self.state.num_players):
                    self.state.game_info[pid]["winner"] = pid in best_players
        else:
            self.state.step_info["draw_reason"] = "No players met their minimum acceptable score"
            for pid in range(self.state.num_players):
                self.state.game_info[pid]["winner"] = False
        
        # Step 4: Log scores + rewards together
        lines = ["=== Final Scores and Rewards (Threshold-Based) ==="]
        for pid in range(self.state.num_players):
            config = self.player_configs[pid]
            score = final_scores[pid]
            reward = rewards[pid]
            threshold = self.player_scores[pid].get("threshold", 0)
            lines.append(f"{config['agent_name']}: {score} points (threshold {threshold}) → reward {reward:+.1f}")
        
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message="\n".join(lines),
            observation_type=ta.ObservationType.GAME_ADMIN
        )
    
    def _handle_no_deal(self):
        """Handle case where no deal was reached - give players their minimum acceptable scores."""
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message="NO DEAL REACHED - Each player receives their minimum acceptable score",
            observation_type=ta.ObservationType.GAME_ADMIN
        )
        
        # Give each player their threshold score directly
        threshold_rewards = {}
        for player_id in range(self.state.num_players):
            threshold = self.player_scores[player_id].get("threshold", 0)
            threshold_rewards[player_id] = threshold
            
            # Add individual notification with human-friendly language
            config = self.player_configs[player_id]
            message = f"{config['agent_name']} receives minimum acceptable score: {threshold} points"
            self.state.add_observation(
                from_id=ta.GAME_ID,
                to_id=player_id,
                message=message,
                observation_type=ta.ObservationType.GAME_ADMIN
            )
        
        self.state.rewards = threshold_rewards
        
        # Still set as draw since no negotiated agreement was reached
        for pid in range(self.state.num_players):
            self.state.game_info[pid]["winner"] = False
        self.state.step_info["draw_reason"] = "No agreement reached - players received minimum acceptable scores"
    
    def _calculate_player_score(self, player_id: int, deal: Dict[str, str]) -> int:
        """Calculate a player's score for a given deal."""
        total_score = 0
        player_scores = self.player_scores[player_id]
        
        for issue_key, option in deal.items():
            if issue_key in player_scores and option in player_scores[issue_key]:
                total_score += player_scores[issue_key][option]
        
        return total_score
    
    def get_observation(self):
        """Get observation for current player."""
        player_id = self.state.current_player_id
        observation = self.state.get_current_player_observation()
        
        # Add current game state information with combined deal and scores
        if self.current_deal:
            config = self.player_configs[player_id]
            combined_summary = render_deal_with_scores_and_votes(
                self.current_deal, self.issues, 
                self.player_scores[player_id], config["agent_name"],
                self.player_votes, self.player_configs
            )
            observation.append((ta.GAME_ID, combined_summary, ta.ObservationType.GAME_BOARD))
        
        return player_id, observation

    def get_board_str(self) -> str:
        """
        Return a formatted string representation of the negotiation state.
        - Ongoing: current deal with scores and voting status
        - Done: final results (deal accepted with scores OR no deal with thresholds)
        """
        # If the game is over
        if getattr(self.state, "done", False):
            lines = ["=== FINAL OUTCOME ===", ""]
            
            if self.current_deal:
                deal_str = ", ".join([f"{k}:{v}" for k, v in sorted(self.current_deal.items())])
                lines.append(f"Final Deal Accepted: {deal_str}")
            else:
                lines.append("No deal was reached.")
            
            lines.append("")
            lines.append("=== PLAYER RESULTS ===")
            
            # Show each player's score and threshold
            for pid, config in self.player_configs.items():
                agent_name = config["agent_name"]
                
                # Use raw score stored in game_info, not normalized reward
                score = self.state.game_info[pid].get("score", 0)
                threshold = self.player_scores[pid].get("threshold", 0)
                reward = self.state.rewards.get(pid, 0)
                
                status = "✅ Met threshold" if score >= threshold else "❌ Below threshold"
                lines.append(
                    f"{agent_name}: {score} points (threshold {threshold}) {status} → reward {reward:+.1f}"
                )
            
            return "\n".join(lines)
        
        # If the game is ongoing
        current_pid = self.state.current_player_id
        config = self.player_configs.get(current_pid, {"agent_name": f"Player {current_pid}"})
        agent_name = config["agent_name"]
        
        if self.current_deal:
            return render_deal_with_scores_and_votes(
                deal_state=self.current_deal,
                issues=self.issues,
                player_scores=self.player_scores[current_pid],
                player_name=agent_name,
                player_votes=self.player_votes,
                player_configs=self.player_configs
            )
        else:
            # No deal yet: show available issues
            return render_game_issues(self.issues)
