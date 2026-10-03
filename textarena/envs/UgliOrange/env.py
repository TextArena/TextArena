import re
from typing import Any, Dict, Optional, Tuple

import textarena as ta


class UgliOrangeEnv(ta.Env):
    """
    Ugli Orange is a 3-player negotiation game where:
    - Player 0: Roland (needs 3000 orange rinds, budget $250k)
    - Player 1: Jones (needs 3000 orange juice, budget $250k)  
    - Player 2: LLM Judge (evaluates if players met objectives)
    
    Players negotiate with R.H. Cardoza through bracketed actions and free text.
    """

    def __init__(self, max_rounds: int = 60, error_allowance: int = 3):
        self.max_rounds = max_rounds
        self.error_allowance = error_allowance
        
        # Action patterns
        self.propose_pattern = re.compile(r'\[Propose(?:\s+\d+)?\]\s*(.*)', re.IGNORECASE | re.DOTALL)
        self.accept_pattern = re.compile(r'\[Accept\]', re.IGNORECASE)
        
        # Player instructions
        self.roland_instructions = """
A. Role for Roland - Ugli Orange Case
You are Dr. P.W. Roland. You work as a research biologist for a pharmaceutical firm.
The firm is under contract with the government to do research on methods to combat
enemy uses of biological warfare.

Recently several World War II experimental nerve gas bombs were moved from the U.S.
to a small island just off the U.S. coast in the Pacific. In the process of transporting them
two of the bombs developed a leak. The leak is presently controlled but government
scientists believe that the gas will permeate the bomb chambers within two weeks. They
know of no method of preventing the gas from getting into the atmosphere and
spreading to other islands, and very likely that several thousands of people will incur
serious brain damage or die.

You've developed a synthetic vapor which will neutralize the nerve gas if it is injected
into the bomb chamber before the gas leaks out. The vapor is made with a chemical
taken from the rind of the Ugli orange, a very rare fruit. Unfortunately, only 4000 of these
oranges were produced this season.

You've been informed, on good evidence, that an R.H. Cardoza, a fruit exporter in South
America is in possession of 3000 Ugli oranges. The chemicals from the rinds of this
number of oranges would be enough to neutralize the gas if the serum is developed
and injected efficiently. You have also been informed that the rinds of these oranges are
in good condition.

You have also been informed the Dr. J.W. Jones is also urgently seeking purchase of
Ugli oranges and s/he is aware of R.H. Cardoza's possession of the 3000 available. Dr.
Jones works for a firm with which your firm is highly competitive. There is a great deal of
industrial espionage in the pharmaceutical industry. Over the years, your firm and Dr.
Jones' firm have sued each other for violations of industrial espionage laws and
infringement of patent rights several times. Litigation on two suits is still in process.

The Federal government has asked your firm for assistance. You've been authorized by
your firm to approach R.H. Cardoza to purchase the 3000 Ugli oranges. You have been
told s/he will sell them to the highest bidder. Your firm has authorized you to bid as high
as $250,000 to obtain the rind of the oranges.

Before approaching R.H. Cardoza, you have decided to talk to Dr. Jones to influence
her/him so that s/he will not prevent you from purchasing the oranges.

CRITICAL GAME RULES:
- STAY IN CHARACTER as Dr. P.W. Roland at all times
- FORMAT: Free text discussion, then [Propose] your terms OR [Accept] to accept latest proposal
- Bracketed action, if any, ALWAYS come last
- Use [Propose] followed by your proposal details to make formal proposals
- Use [Accept] to accept the latest proposal
- You cannot accept your own proposals
- Maximum 60 rounds of negotiation
- After deal or max rounds, judge determines who met their objectives
- YOUR OBJECTIVE: Get the rinds from 3000 Ugli oranges within your $250,000 budget
- IMPORTANT: Always respond as Dr. Roland would, never break character or mention being an AI
"""

        self.jones_instructions = """
You are Dr. J. W. Jones, a biological research scientist employed by a pharmaceutical
firm. You have recently developed a synthetic chemical useful for curing and preventing
Rudosen. Rudosen is a disease contracted by pregnant women. If not caught in the first
four weeks of pregnancy, the disease causes serious brain, eye, and ear damage to the
unborn child. Recently, there has been an outbreak of Rudosen in your state and several
thousand women have contracted the disease. You have found, with volunteer victims,
that your recently developed synthetic serum cures Rudosen in its early stages.

Unfortunately, the serum is made from the juice of the Ugli orange which is a very rare
fruit. Only a small quantity (approximately 4000) of these oranges were produced last
season. No additional Ugli oranges will be available until next season, which will be too
late to cure the present Rudosen victims.

You've demonstrated that your synthetic serum is in no way harmful to pregnant women.
Consequently, there are not side effects. The Food and Drug Administration has
approved the production and distribution of the serum as a cure for Rudosen.
Unfortunately, the present outbreak was unexpected, and your firm had not planned on
having the compound serum available for six months. Your firm holds the patent on the
synthetic serum and is expected to be a highly profitable product when it is generally
available to the public.

You have recently been informed, on good evidence, that R.H. Cardoza, a south
American fruit exporter, is in possession of the juice of 3000 Ugli oranges in good
condition. If you could obtain the juice of all 3000 you would be able to cure the
present victims and provide enough inoculation for the remaining pregnant women in
the state. No other state currently has a Rudosen threat.

You have recently been informed that Dr. P.W. Roland is also urgently seeking Ugli
oranges and is also aware of R.H. Cardoza's possession of the 3000 available. Dr.
Roland is employed by a competitor pharmaceutical firm. S/he has been working on
biological warfare research for the past several years. There is a great deal of industrial
espionage in the pharmaceutical industry. Over the past several years, Dr. Roland's firm
and your firm have sued each other for infringement of patent rights and espionage law
violations several times.

You've been authorized by your firm to approach R.H. Cardoza to purchase the 3000
Ugli oranges. You have been told s/he will sell them to the highest bidder. Your firm has
authorized you to bid as high as $250,000 to obtain the juice of the 3000 available
oranges.

Before approaching R.H. Cardoza, you have decided to talk with Dr. Roland to influence
her/him so that s/he will not prevent you from purchasing the oranges.

CRITICAL GAME RULES:
- STAY IN CHARACTER as Dr. J.W. Jones at all times
- FORMAT: Free text discussion, then [Propose] your terms OR [Accept] to accept latest proposal
- Bracketed action, if any, ALWAYS come last
- Use [Propose] followed by your proposal details to make formal proposals
- Use [Accept] to accept the latest proposal
- You cannot accept your own proposals
- Maximum 60 rounds of negotiation
- After deal or max rounds, judge determines who met their objectives
- YOUR OBJECTIVE: Get the juice from 3000 Ugli oranges within your $250,000 budget
- IMPORTANT: Always respond as Dr. Jones would, never break character or mention being an AI
"""

    def reset(self, num_players: int, seed: Optional[int] = None):
        if num_players != 3:
            raise ValueError("UgliOrange requires exactly 3 players (Roland, Jones, and Judge)")
            
        self.state = ta.FFAMultiPlayerState(num_players=num_players, max_turns=self.max_rounds, seed=seed)
        
        game_state = {
            "proposals": [],  # List of all proposals with numbers
            "current_proposal_number": 0,
            "deal_reached": False,
            "final_deal": None,
            "negotiation_complete": False
        }
        
        role_mapping = {
            0: "Roland",
            1: "Jones", 
            2: "Judge",
            ta.GAME_ID: "GAME"
        }
        
        self.state.reset(
            game_state=game_state,
            player_prompt_function=self._generate_player_prompt,
            role_mapping=role_mapping
        )

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        current_player = self.state.current_player_id
        
        # Handle judge
        if current_player == 2:  # Judge
            if self.state.game_state["negotiation_complete"]:
                self.state.add_observation(
                    from_id=current_player,
                    message=f"[Round {self.state.turn + 1}/{self.max_rounds}] {action}",
                    observation_type=ta.ObservationType.PLAYER_ACTION
                )
                self._process_judge_decision(action)
                return True, self.state.step_info
            else:
                # Judge observes silently during negotiation
                self.state.add_observation(
                    from_id=current_player,
                    message=f"[Round {self.state.turn + 1}/{self.max_rounds}] *observing*",
                    observation_type=ta.ObservationType.PLAYER_ACTION
                )
                # Skip to next negotiating player
                self.state.current_player_id = (self.state.current_player_id + 1) % 2
                return False, self.state.step_info
        else:  # Negotiating players (Roland, Jones)
            self.state.add_observation(
                from_id=current_player,
                message=f"[Round {self.state.turn + 1}/{self.max_rounds}] {action}",
                observation_type=ta.ObservationType.PLAYER_ACTION
            )
            
            valid_move = self._process_negotiation_action(action)
            if not valid_move:
                return False, self.state.step_info
        
        # Check end conditions
        if self.state.turn >= self.max_rounds - 1 and not self.state.game_state["negotiation_complete"]:
            game_ended = self._start_judge_evaluation()
            return game_ended, self.state.step_info
        
        if self.state.game_state["deal_reached"] and not self.state.game_state["negotiation_complete"]:
            game_ended = self._start_judge_evaluation()
            return game_ended, self.state.step_info
        
        # Continue negotiation - alternate between Roland and Jones
        if not self.state.game_state["negotiation_complete"]:
            self.state.current_player_id = 1 - current_player
            self.state.turn += 1
            return False, self.state.step_info
        else:
            return self.state.step()

    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        if player_id == 0:  # Roland
            return self.roland_instructions
        elif player_id == 1:  # Jones
            return self.jones_instructions
        elif player_id == 2:  # Judge
            return "You are observing the negotiation. Wait for it to complete before evaluating."
        
    def _process_negotiation_action(self, action: str) -> bool:
        """Process negotiation action. Returns True if valid, False if invalid."""
        current_player = self.state.current_player_id
        
        # Check for accept first
        if self.accept_pattern.search(action):
            if not self.state.game_state["proposals"]:
                self.state.set_invalid_move("No proposals to accept")
                return False
                
            latest_proposal = self.state.game_state["proposals"][-1]
            
            if latest_proposal["proposer"] == current_player:
                self.state.set_invalid_move("You cannot accept your own proposal")
                return False
            
            return self._accept_proposal(current_player, latest_proposal["number"])
            
        # Check for proposal
        propose_match = self.propose_pattern.search(action)
        if propose_match:
            proposal_text = propose_match.group(1).strip()
            self._make_proposal(current_player, proposal_text)
            return True
        
        # Free text discussion is always valid
        return True

    def _make_proposal(self, proposer: int, proposal_text: str):
        """Create a new proposal with auto-incremented number."""
        self.state.game_state["current_proposal_number"] += 1
        proposal_number = self.state.game_state["current_proposal_number"]
        
        proposal = {
            "number": proposal_number,
            "proposer": proposer,
            "text": proposal_text,
            "round": self.state.turn
        }
        
        self.state.game_state["proposals"].append(proposal)
        
        self.state.add_observation(
            message=f"{self.state.role_mapping[proposer]} makes Proposal #{proposal_number}: {proposal_text}",
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )

    def _accept_proposal(self, accepter: int, proposal_number: int) -> bool:
        """Accept a proposal by number. Assumes validation already done."""
        # Find the proposal (we know it exists from validation)
        proposal = None
        for p in self.state.game_state["proposals"]:
            if p["number"] == proposal_number:
                proposal = p
                break
        
        # Deal reached
        self.state.game_state["deal_reached"] = True
        self.state.game_state["final_deal"] = {
            "proposal_number": proposal_number,
            "proposal_text": proposal["text"],
            "proposer": proposal["proposer"],
            "accepter": accepter
        }
        
        self.state.add_observation(
            message=f"{self.state.role_mapping[accepter]} accepts Proposal #{proposal_number}",
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )
        
        return True

    def _start_judge_evaluation(self) -> bool:
        """Start judge evaluation phase."""
        self.state.game_state["negotiation_complete"] = True
        
        # If no deal, automatic draw
        if not self.state.game_state["deal_reached"]:
            self.state.add_observation(
                message="No deal reached after maximum rounds - Draw",
                observation_type=ta.ObservationType.GAME_ADMIN
            )
            self.state.set_draw("No deal reached - both players failed to negotiate successfully")
            return True
        
        # Set judge as current player and ask for comprehensive evaluation
        self.state.current_player_id = 2
        
        prompt = f"""Analyze this deal and determine the winners:

DEAL: {self.state.game_state["final_deal"]["proposal_text"]}
Proposed by: {"Roland" if self.state.game_state["final_deal"]["proposer"] == 0 else "Jones"}

Answer in this exact format:
Roland gets: rind or juice or all or nothing or unclear
Roland pays: dollar amount as number or 0 if none
Roland oranges: number of oranges or 3000 if not specified
Jones gets: rind or juice or all or nothing or unclear
Jones pays: dollar amount as number or 0 if none
Jones oranges: number of oranges or 3000 if not specified

Remember: Roland needs 3000 or more oranges for rind at 250000 dollars or less, Jones needs 3000 or more oranges for juice at 250000 dollars or less. Both can win."""
        
        self.state.add_observation(
            message=prompt,
            observation_type=ta.ObservationType.GAME_MESSAGE
        )
        
        return False  # Continue to judge evaluation

    def _process_judge_decision(self, decision: str):
        """Process judge's comprehensive evaluation."""
        # Parse the structured response
        roland_gets = "unclear"
        roland_cost = 0
        roland_oranges = 3000  # Default to 3000 if not specified
        jones_gets = "unclear"
        jones_cost = 0
        jones_oranges = 3000  # Default to 3000 if not specified
        
        lines = decision.lower().split('\n')
        for line in lines:
            if 'roland gets:' in line:
                roland_gets = line.split(':')[1].strip()
            elif 'roland pays:' in line:
                try:
                    roland_cost = int(re.sub(r'[^0-9]', '', line.split(':')[1]))
                except:
                    roland_cost = 0
            elif 'roland oranges:' in line:
                try:
                    roland_oranges = int(re.sub(r'[^0-9]', '', line.split(':')[1]))
                except:
                    roland_oranges = 3000
            elif 'jones gets:' in line:
                jones_gets = line.split(':')[1].strip()
            elif 'jones pays:' in line:
                try:
                    jones_cost = int(re.sub(r'[^0-9]', '', line.split(':')[1]))
                except:
                    jones_cost = 0
            elif 'jones oranges:' in line:
                try:
                    jones_oranges = int(re.sub(r'[^0-9]', '', line.split(':')[1]))
                except:
                    jones_oranges = 3000
        
        # Determine winners
        roland_wins = ((roland_gets == "rind" or roland_gets == "all") and roland_cost <= 250000 and roland_oranges >= 3000)
        jones_wins = ((jones_gets == "juice" or jones_gets == "all") and jones_cost <= 250000 and jones_oranges >= 3000)
        
        if roland_wins and jones_wins:
            winner = "Both"
        elif roland_wins:
            winner = "Roland"
        elif jones_wins:
            winner = "Jones"
        else:
            winner = "Neither"
            
        final_decision = f"winner {winner} reason Roland gets {roland_gets} from {roland_oranges} oranges at {roland_cost} dollars, Jones gets {jones_gets} from {jones_oranges} oranges at {jones_cost} dollars. Roland needs 3000 or more oranges for rind at 250000 dollars or less, Jones needs 3000 or more oranges for juice at 250000 dollars or less. Judge response: {decision}"
        
        if winner == "Roland":
            self.state.set_winners([0], final_decision)
            self.rewards = {0:1, 1:-1}
        elif winner == "Jones":
            self.state.set_winners([1], final_decision)
            self.rewards = {0:-1, 1:1}
        elif winner == "Both":
            self.state.set_winners([0, 1], final_decision)
            self.rewards = {0:1, 1:1}
        else:
            self.state.set_winners([], final_decision)
            self.rewards = {0:0, 1:0}