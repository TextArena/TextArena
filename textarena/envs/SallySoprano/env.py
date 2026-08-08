import re
from typing import Any, Dict, Optional, Tuple

import textarena as ta
from textarena.envs.SallySoprano.renderer import get_board_str


class SallySopranoEnv(ta.Env):
    """
    Sally Soprano is a 3-player negotiation game where:
    - Player 0: Sally's Agent
    - Player 1: Lyric Opera's Business Manager  
    - Player 2: LLM Judge (only acts after deal is reached or max rounds)
    
    Players negotiate salary with bracketed actions and free text.
    """

    def __init__(self, max_rounds: int = 60, error_allowance: int = 3):
        self.max_rounds = max_rounds
        self.error_allowance = error_allowance
        
        # Action patterns
        self.propose_pattern = re.compile(r'\[Propose\]\s*(\d+)', re.IGNORECASE)
        self.accept_pattern = re.compile(r'\[Accept\]', re.IGNORECASE)
        
        # Confidential instructions
        self.sally_instructions = """
Confidential Instructions for Sally's Agent

You have just become a partner in a firm that manages and acts as agent for celebrities. Sally Soprano is certainly not a major client, but you want to do a good job with this first assignment as a partner, especially since you have an interest in expanding your firm's opera practice. This is the first time you have handled Ms. Soprano's account.

You met Ms. Soprano yesterday. She is an older soprano who still has a good voice, particularly for her age. During your discussions with her, you gathered the following information:

She has not had a prime role in more than two years, although she has had a number of secondary roles. Her popularity has declined somewhat in the past few years. Lyric Opera, with whom Sally has sung many times over the years, has a production of Bellini's Norma scheduled to open in three weeks. The challenging title role is generally acknowledged to be a prize for a young soprano. When the Lyric announced this season's schedule over a year ago, Renata Risingstar was listed in the title role for Norma. Ms. Risingstar is generally regarded as a first-rate performer, although she has not yet attained the popularity Sally enjoyed at the peak of her career. Three weeks ago, Ms. Risingstar's name was suddenly dropped from the opera's advertising, and rumors began circulating that she had either become ill or gotten into a dispute with the artistic director. Sally got in touch with the artistic director to ask if the title role was open. Sally knows the part well and has sung it successfully many times. Yesterday Sally was informed by the Lyric that they might be interested in signing her for the Norma role. A meeting has been scheduled for today between you, as Sally's agent, and the Lyric's business manager to discuss the situation.

The Lyric Opera is an established institution in a major metropolitan area. As with most opera companies, it is a not-for-profit entity that is financed by a combination of ticket sales, foundation and corporate grants, and income from a modest endowment. It usually breaks even over the course of the year, with fairly good attendance in its 2,000-seat hall. Ticket prices range from $18 to $55. This production of Norma is scheduled to run for six weeks, with three performances per week.

Sally desperately wants this role. It could signal a real comeback and would give her a good chance at an important role in a forthcoming television special on opera. The TV special would pay $45,000 and would probably lead to many other singing engagements. Sally was overjoyed at Lyric's possible interest in her. Sally has told you that getting the part is what counts; the amount of compensation is secondary. She told you that, frankly, she would be willing to sing the part for nothing, except for reasons of professional pride, reputation, and the potential impact on future engagements, although the higher the price the better.

Sally's salary over the last two years for secondary roles in operas of this type has ranged from $10,000 to $18,000. Four years ago, when she was at the pinnacle of her career, she received $22,000 for performing the title role in Norma at the Lyric. Since then, due to inflation and the increased popularity of opera, the amount paid to top opera singers has nearly doubled. Sally recognizes, however, that she cannot count on producing sold-out performances the way she could then.

Last year, the inexperienced young soprano who sang the title role of Norma for the Lyric was said to have been paid over $24,000. The last time Sally sang for the Lyric was over a year ago, in the secondary soprano role of Adalgisa, also in Norma, for which she received $12,500 and received reasonably good reviews. Although it is difficult to generalize, performers in lead opera roles of this type are usually paid at least twice the amount received by singers in secondary roles.

Sally believes that her experience and maturity make her particularly appropriate for the title role. Norma is the high priestess of the Temple of Esus. She is secretly married to the Roman Consul and has had two children with him. There are two other sopranos in the opera: Adalgisa, the virgin of the temple, and Clotilde, the attendant to Norma. Sally feels that, given her age, she would no longer be the best person to play the role of Adalgisa or Clotilde. However, she believes that at this stage of her life she relates well to the role of Norma. In fact, Sally's view is that she actually may have been too young when she performed the role of Norma in the past and that she would perform this role better today.

One of the Lyric's major concerns is the attendance Sally's performances would generate. The Lyric is said to average around an 85 percent house over the course of the year, but many performances are sold out. On the other hand, a bad house can be financially devastating for the annual budget. While her voice remains strong, she has had a few mediocre days, which wasn't true four years ago. That is one reason why you think Sally has been offered fewer roles recently. If Sally's performances generated a 50 percent or 60 percent house, this would almost surely be her last leading role. In fact, anything under 80 percent would probably finish her career. Sally is confident, however, that a 50 percent or 60 percent house would be extremely unlikely to occur as a result of her contribution.

Prepare for your meeting with the Lyric Opera's Business Manager.
"""

        self.manager_instructions = """
Confidential Instructions for the Lyric Opera's Business Manager

You have been with Lyric Opera for three months. So far, things have been going well, but your negotiation with Sally Soprano's agent will be your most important assignment to date. You want to make sure that your boss, the artistic director, is pleased with the outcome.

You met with your boss yesterday, and gathered the following information:
The Lyric Opera is an established institution in a major metropolitan area. Like most opera companies, it is a not-for-profit entity and is financed by a combination of ticket sales, foundation and corporate grants, and income from a modest endowment. It usually breaks even over the course of the year, with fairly good attendance in its 2,000-seat hall. Ticket prices range from $18 to $55, with $28 a reasonable average for rule-of-thumb accounting.

A production of Bellini's Norma is scheduled to open in three weeks. The production is scheduled to run for six weeks, with three performances per week. There are three sopranos in Norma. Norma is the high priestess of the Temple of Esus and is secretly married to the Roman Consul, with whom she has two children. The other two soprano roles are those of Adalgisa, the virgin of the temple, and Clotilde, the attendant to Norma. The challenging title role is generally acknowledged to be a prize for a young soprano, although the age of the character is not specified. The age of the children is also unspecified, but Norma attempts to kill them in a rage over her husband's infidelity. When the Lyric announced this season's schedule more than a year ago, Renata Risingstar was listed in the title role for Norma. Ms. Risingstar is generally regarded as a first-rate performer, although she has not yet attained the popularity Sally enjoyed at the peak of her career. Three weeks ago, however, the Lyric suddenly dropped Ms. Risingstar from its advertising for Norma. Although it is not widely known (the opera wanted to hold off making a public announcement until the diagnosis was confirmed), the reason for the omission is that Ms. Risingstar has developed a benign throat tumor that will require surgery prior to the performance date. The Lyric has been unable to find any other good soprano who is available for the dates of the performance. The soprano engaged for the secondary role (at a salary of $14,000) knows the Norma role. She has a good voice but is a relative newcomer to professional opera and clearly lacks the experience necessary to perform the title role well. The Lyric is therefore in a tight spot. Cancellation of the opera would result in a loss of hundreds of thousands of dollars. Fortunately, Sally Soprano, a distinguished though somewhat aging soprano, heard rumors that the opera was in trouble and called the artistic director to inquire whether there was any possibility that she might sing the lead. Up to now, the artistic director has held her off, hoping to find a younger lead. Unfortunately, that now appears impossible, and the artistic director is suddenly quite desperate to sign Sally. You have scheduled an early appointment with her agent.

Sally Soprano has sung many times for the Lyric Opera over the years, but the last time she sang was more than a year ago in the secondary role of Adalgisa, also in Norma, for which she received $12,500. Four years ago, at the pinnacle of her singing career, the Lyric paid Ms. Soprano $22,000 for performing the title role in Norma. That was regarded as extremely high at the time, justified only by the fact that Sally was at the apex of her career and had a significant following, which has probably fallen off somewhat since then. On the other hand, over the last four years, inflation and the increased popularity of opera have in general brought about a near doubling of the average salaries of the top opera stars.

As a matter of policy, the Lyric does not generally disclose the compensation of its performers. However, for negotiating purposes, you have been given access to the salary figures paid by the Lyric in recent years for the title and secondary roles in Bellini's Norma:

| Title Role (Norma)      | Secondary Soprano (Adalgisa)|
| ----------------------- | ----------------------------|
| Five years ago: $14,000 | $7,000                      |
| Four years ago: $22,000 | $8,000                      |
| Three years ago: $17,500| $9,000                      |
| Two years ago: $21,000  | $12,500                     |
| Last year: $25,000      | $12,000                     |
| This year: ?            | $14,000                     |

Although cases vary widely, as a general rule the Lyric tends to follow the industry practice of paying performers in lead opera roles of this type about twice the amount received by singers in secondary roles. Also, following the industry practice, the Lyric has always paid its performers a flat rate salary.

In general, the nonprofit Lyric needs to keep the costs of performances as low as possible. The Lyric's average house over the year is generally 85 percent. This is also the break-even point. Of course, there have also been many sold-out performances, but the average is 85 percent, give or take five percent. Anything less than 80 percent attendance would cause the Lyric to lose $50,000 or more, and a house of 50 percent or 60 percent, while unlikely, would be a disaster. (These kinds of figures probably explain why Ms. Soprano has had so few offers for lead roles recently. While her voice remains fine, most operas are anxious to avoid even the smallest chance of an off day.) This year, Ms. Risingstar was to have been paid $30,000. In view of the emergency situation and the great desire of the artistic director to obtain Sally Soprano, the Lyric trustees have authorized you to offer her up to $45,000 should that be necessary. If she holds out for more than that, the Lyric will just have to use the neophyte secondary soprano in the title role and hope that she miraculously rises to the occasion. (You would probably pay her something less than double her secondary salary of $14,000 for that, certainly no more than $28,000.) You should also bear in mind the potential adverse impact on future negotiations with other performers should an unusually high salary for Sally become public knowledge.

The artistic director wants Sally, despite thinking that she is too old for the role. The director believes that with proper makeup and a little luck Sally could work out extremely well. In any event, there is little alternative. As it is, the late announcement of the title role may adversely affect box office sales. The artistic director is hoping, however, for a favorable public response to the announcement of Sally in the title role.

Prepare for your meeting with Sally Soprano's agent.
"""

    def reset(self, num_players: int, seed: Optional[int] = None):
        if num_players != 3:
            raise ValueError("SallySoprano requires exactly 3 players (Sally's Agent, Business Manager, and LLM Judge)")
            
        self.state = ta.FFAMultiPlayerState(num_players=num_players, max_turns=self.max_rounds, seed=seed)
        
        game_state = {
            "current_proposal": None,
            "proposal_history": [],
            "deal_reached": False,
            "final_deal": None,
            "negotiation_complete": False
        }
        
        role_mapping = {
            0: "Sally's Agent",
            1: "Business Manager",
            2: "Judge",
            ta.GAME_ID: "GAME"
        }
        
        self.state.reset(
            game_state=game_state,
            player_prompt_function=self._generate_player_prompt,
            role_mapping=role_mapping
        )

    def render(self, player_id: Optional[int] = None) -> str:
        """Render the current state for a player."""
        return get_board_str(
            self.state.game_state, 
            player_id
        )

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        current_player = self.state.current_player_id
        
        # Handle different player types
        if current_player == 2:  # Judge
            if self.state.game_state["negotiation_complete"]:
                self.state.add_observation(
                    from_id=current_player,
                    message=f"[Round {self.state.turn + 1}/{self.max_rounds}] {action}",
                    observation_type=ta.ObservationType.PLAYER_ACTION
                )
                self._process_judge_decision(action)
                # Game ends after judge decision
                return True, self.state.step_info
            else:
                # Judge observes silently during negotiation - skip to next negotiating player
                action = "*observing*"
                self.state.add_observation(
                    from_id=current_player,
                    message=f"[Round {self.state.turn + 1}/{self.max_rounds}] {action}",
                    observation_type=ta.ObservationType.PLAYER_ACTION
                )
                # Skip judge turn during negotiation - go to next negotiating player
                self.state.current_player_id = (self.state.current_player_id + 1) % 2
                return False, self.state.step_info
        else:  # Negotiating players (0, 1)
            self.state.add_observation(
                from_id=current_player,
                message=f"[Round {self.state.turn + 1}/{self.max_rounds}] {action}",
                observation_type=ta.ObservationType.PLAYER_ACTION
            )
            valid_move = self._process_negotiation_action(action)
            
            # Only advance turn if move was valid
            if not valid_move:
                return False, self.state.step_info  # Invalid move, don't advance turn
        
        # Check if we've reached max turns before stepping
        if self.state.turn >= self.max_rounds - 1 and not self.state.game_state["negotiation_complete"]:
            game_ended = self._start_judge_evaluation()
            return game_ended, self.state.step_info
        
        # Check if deal reached
        if self.state.game_state["deal_reached"] and not self.state.game_state["negotiation_complete"]:
            game_ended = self._start_judge_evaluation()
            return game_ended, self.state.step_info
        
        # During negotiation, only cycle between players 0 and 1
        if not self.state.game_state["negotiation_complete"]:
            self.state.current_player_id = 1 - current_player  # Toggle between 0 and 1
            self.state.turn += 1
            return False, self.state.step_info
        else:
            # Let TextArena handle turn management during judge phase
            return self.state.step()

    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        if player_id == 0:  # Sally's Agent
            prompt = self.sally_instructions + "\n\n"
            prompt += "GAME RULES:\n"
            prompt += "- Negotiate salary for Sally's Norma role\n"
            prompt += "- Use free text to argue and make promises about non-monetary items\n"
            prompt += "- Propose salary with: [Propose] amount (e.g., [Propose] 25000)\n"
            prompt += "- Accept proposal with: [Accept]\n"
            prompt += "- You cannot accept your own proposal\n"
            prompt += f"- Maximum {self.max_rounds} rounds (NOT including judge's)\n"
            prompt += "- After deal or max rounds, a judge will decide who got the better deal\n"
            prompt += "- CRITICAL: Do NOT include round counters like [Round X/Y] in your response\n"
            prompt += "- CRITICAL: Use [Propose] followed by just the number, no dollar sign (e.g., [Propose] 25000)\n\n"
            
        elif player_id == 1:  # Business Manager
            prompt = self.manager_instructions + "\n\n"
            prompt += "GAME RULES:\n"
            prompt += "- Negotiate salary for Sally's Norma role\n"
            prompt += "- Use free text to argue and make promises about non-monetary items\n"
            prompt += "- Propose salary with: [Propose] amount (e.g., [Propose] 25000)\n"
            prompt += "- Accept proposal with: [Accept]\n"
            prompt += "- You cannot accept your own proposal\n"
            prompt += f"- Maximum {self.max_rounds} rounds\n"
            prompt += "- After deal or max rounds, a judge will decide who got the better deal\n"
            prompt += "- CRITICAL: Do NOT include round counters like [Round X/Y] in your response\n"
            prompt += "- CRITICAL: Use [Propose] followed by just the number, no dollar sign (e.g., [Propose] 25000)\n\n"
            
        elif player_id == 2:  # Judge
            prompt = "You are observing the negotiation. Wait for it to complete before making your judgment.\n"
        
        return prompt

    def _process_negotiation_action(self, action: str):
        """Process negotiation action. Returns True if valid move, False if invalid."""
        current_player = self.state.current_player_id
        
        # Check for malformed proposal (has [Propose] but no valid number)
        if '[PROPOSE]' in action.upper():
            propose_match = self.propose_pattern.search(action)
            if propose_match:
                amount = int(propose_match.group(1))
                self._make_proposal(current_player, amount, action)
                return True  # Valid move
            else:
                self.state.set_invalid_move("Invalid proposal format. Use [Propose] followed by a number (e.g., [Propose] 25000)")
                return False  # Invalid move
            
        # Check for accept
        if self.accept_pattern.search(action):
            if self.state.game_state["current_proposal"]:
                proposer = self.state.game_state["current_proposal"]["proposer"]
                if current_player != proposer:
                    self._accept_proposal(current_player, action)
                    return True  # Valid move
                else:
                    self.state.set_invalid_move("You cannot accept your own proposal")
                    return False  # Invalid move
            else:
                self.state.set_invalid_move("No current proposal to accept")
                return False  # Invalid move
        
        # If no bracketed action, treat as free text discussion
        # Player action already displayed by TextArena framework
        return True  # Free text is always valid

    def _make_proposal(self, proposer: int, amount: int, full_action: str):
        # Extract rationale (text before [Propose])
        rationale = full_action.split('[Propose]')[0].strip()
        
        proposal = {
            "proposer": proposer,
            "amount": amount,
            "rationale": rationale,
            "round": self.state.turn
        }
        
        self.state.game_state["current_proposal"] = proposal
        self.state.game_state["proposal_history"].append(proposal)
        
        self.state.add_observation(
            message=f"{self.state.role_mapping[proposer]} proposes ${amount:,}",
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )

    def _accept_proposal(self, accepter: int, full_action: str):
        proposal = self.state.game_state["current_proposal"]
        rationale = full_action.split('[Accept]')[0].strip()
        
        self.state.game_state["deal_reached"] = True
        self.state.game_state["final_deal"] = {
            "amount": proposal["amount"],
            "proposer": proposal["proposer"],
            "accepter": accepter,
            "acceptance_rationale": rationale
        }
        
        self.state.add_observation(
            message=f"{self.state.role_mapping[accepter]} accepts the proposal of ${proposal['amount']:,}",
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )

    def _start_judge_evaluation(self):
        """Start the judge evaluation phase. Returns True if game should end, False if continuing to judge."""
        self.state.game_state["negotiation_complete"] = True
        
        # If no deal reached, automatically declare draw and end game
        if not self.state.game_state["deal_reached"]:
            self.state.add_observation(
                message="Negotiation complete. No deal reached - automatic draw.",
                observation_type=ta.ObservationType.GAME_ADMIN
            )
            self.state.set_draw("No deal reached after maximum rounds - both parties failed to negotiate successfully.")
            return True  # Game ends
        
        # Set current player to judge for deal evaluation
        self.state.current_player_id = 2
        
        # Add judge instructions as observation
        judge_instructions = "You are the Judge for the Sally Soprano negotiation.\n\n"
        judge_instructions += "CONFIDENTIAL INSTRUCTIONS FOR BOTH PLAYERS:\n\n"
        judge_instructions += "Sally's Agent Instructions:\n" + self.sally_instructions + "\n\n"
        judge_instructions += "Business Manager Instructions:\n" + self.manager_instructions + "\n\n"
        judge_instructions += "JUDGING TASK:\n"
        judge_instructions += "This is a negotiation about Sally Soprano's salary for performing the title role in the opera Norma.\n"
        judge_instructions += "Based on the confidential instructions above and the complete negotiation conversation, determine who got the better deal.\n"
        judge_instructions += "Consider the final salary amount, each party's constraints and goals, and negotiation tactics used.\n\n"
        judge_instructions += "REQUIRED FORMAT:\n"
        judge_instructions += "[winner] Sally's Agent | Business Manager | Draw\n"
        judge_instructions += "[reason] Your detailed analysis and reasoning\n\n"
        judge_instructions += "IMPORTANT: \n"
        judge_instructions += "- You have full context about this Sally Soprano opera negotiation\n"
        judge_instructions += "- You MUST analyze who got the better deal based on their secret constraints\n"
        judge_instructions += "- You MUST choose exactly one: Sally's Agent, Business Manager, or Draw\n"
        judge_instructions += "- Do not say you lack context - you have everything needed to judge\n"
        
        self.state.add_observation(
            message=judge_instructions,
            observation_type=ta.ObservationType.GAME_MESSAGE
        )
        
        # Add summary for judge
        deal = self.state.game_state["final_deal"]
        self.state.add_observation(
            message=f"Negotiation complete. Deal reached: ${deal['amount']:,}. Judge will now evaluate.",
            observation_type=ta.ObservationType.GAME_ADMIN
        )
        
        return False  # Game continues to judge evaluation
    
    def _process_judge_decision(self, decision: str):
        """Process the judge's final decision."""
        import re
        
        # Parse bracket format: [winner] Sally's Agent | Business Manager | Draw
        winner_match = re.search(r'\[winner\]\s*(.+?)(?:\n|\[|$)', decision, re.IGNORECASE)
        if winner_match:
            winner = winner_match.group(1).strip()
            
            if winner == "Sally's Agent":
                self.state.set_winners([0], decision)
                self.rewards = {0: 1, 1: -1}
                return
            elif winner == "Business Manager":
                self.state.set_winners([1], decision)
                self.rewards = {0: -1, 1: 1}
                return
            elif winner == "Draw":
                self.state.set_draw(decision)
                self.rewards = {0: 0, 1: 0}
                return
        
        # If parsing fails, default to draw
        self.state.set_draw(f"Judge decision parsing failed, defaulting to draw. Original decision: {decision}")