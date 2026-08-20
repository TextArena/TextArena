import pytest
import textarena as ta
from textarena.envs.UgliOrange.env import UgliOrangeEnv


def test_environment_creation():
    """Test basic environment creation and reset."""
    env = UgliOrangeEnv()
    env.reset(num_players=3)
    
    assert env.state.num_players == 3
    assert env.state.current_player_id == 0  # Roland starts
    assert not env.state.game_state["deal_reached"]


def test_proposal_creation():
    """Test proposal creation and numbering."""
    env = UgliOrangeEnv()
    env.reset(num_players=3)
    
    # Roland makes a proposal
    done, info = env.step("[Propose] I'll buy 2000 rinds for $100k, you buy 1000 juice for $50k")
    
    assert not done
    assert len(env.state.game_state["proposals"]) == 1
    assert env.state.game_state["proposals"][0]["number"] == 1
    assert env.state.game_state["proposals"][0]["proposer"] == 0


def test_proposal_acceptance():
    """Test accepting the latest proposal."""
    env = UgliOrangeEnv()
    env.reset(num_players=3)
    
    # Roland proposes
    env.step("[Propose] I'll handle rinds, you handle juice, split costs 50/50")
    
    # Jones accepts latest proposal
    done, info = env.step("[Accept]")
    
    assert not done  # Should go to judge evaluation
    assert env.state.game_state["deal_reached"]
    assert env.state.game_state["final_deal"]["proposal_number"] == 1


def test_accept_no_proposals():
    """Test accepting when no proposals exist."""
    env = UgliOrangeEnv()
    env.reset(num_players=3)
    
    # Roland tries to accept when no proposals exist
    done, info = env.step("[Accept]")
    
    assert not done
    assert not env.state.game_state["deal_reached"]


def test_self_acceptance_blocked():
    """Test that players cannot accept their own proposals."""
    env = UgliOrangeEnv()
    env.reset(num_players=3)
    
    # Roland proposes
    env.step("[Propose] My proposal")
    
    # Now it's Jones's turn, let Jones pass
    env.step("I'll think about it")
    
    # Now it's Roland's turn again - Roland tries to accept own proposal (should fail)
    done, info = env.step("[Accept]")
    
    assert not done
    assert not env.state.game_state["deal_reached"]


def test_accept_variations():
    """Test that various accept formats work."""
    env = UgliOrangeEnv()
    env.reset(num_players=3)
    
    # Roland proposes
    env.step("[Propose] My proposal")
    
    # Jones accepts with various formats (all should work)
    done, info = env.step("[Accept] Proposal #1")
    
    assert not done  # Should go to judge evaluation
    assert env.state.game_state["deal_reached"]


def test_judge_evaluation():
    """Test judge evaluation phase with comprehensive format."""
    env = UgliOrangeEnv()
    env.reset(num_players=3)
    
    # Make a deal
    env.step("[Propose] Roland gets 3000 rinds for $200k, Jones gets 3000 juice for $200k")
    env.step("[Accept]")  # Deal reached, should trigger judge evaluation
    
    # Judge should be current player now
    assert env.state.current_player_id == 2
    assert env.state.game_state["negotiation_complete"]
    
    # Judge makes comprehensive decision
    judge_response = """Roland gets: rind
Roland pays: 200000
Roland oranges: 3000
Jones gets: juice
Jones pays: 200000
Jones oranges: 3000"""
    
    done, info = env.step(judge_response)
    
    assert done
    assert env.state.rewards[0] == 1  # Roland wins
    assert env.state.rewards[1] == 1  # Jones wins


def test_judge_evaluation_with_defaults():
    """Test judge evaluation with missing information defaults to 3000 oranges."""
    env = UgliOrangeEnv()
    env.reset(num_players=3)
    
    # Make a deal
    env.step("[Propose] We split everything 50/50")
    env.step("[Accept]")
    
    # Judge makes minimal decision (should default to 3000 oranges each)
    judge_response = """Roland gets: rind
Roland pays: 125000
Jones gets: juice
Jones pays: 125000"""
    
    done, info = env.step(judge_response)
    
    assert done
    assert env.state.rewards[0] == 1  # Roland wins (gets rind, 3000 oranges default, ≤$250k)
    assert env.state.rewards[1] == 1  # Jones wins (gets juice, 3000 oranges default, ≤$250k)


def test_judge_evaluation_failure():
    """Test judge evaluation where players don't meet objectives."""
    env = UgliOrangeEnv()
    env.reset(num_players=3)
    
    # Make a bad deal
    env.step("[Propose] Roland gets 1000 rinds for $300k")
    env.step("[Accept]")
    
    # Judge evaluates - Roland fails (too expensive and not enough oranges)
    judge_response = """Roland gets: rind
Roland pays: 300000
Roland oranges: 1000
Jones gets: nothing
Jones pays: 0
Jones oranges: 0"""
    
    done, info = env.step(judge_response)
    
    assert done
    assert env.state.rewards[0] == -1  # Roland loses (over budget and insufficient oranges)
    assert env.state.rewards[1] == -1  # Jones loses (gets nothing)


def test_no_deal_timeout():
    """Test game ending without deal after max rounds."""
    env = UgliOrangeEnv(max_rounds=2)  # Very short game
    env.reset(num_players=3)
    
    # Just discussion, no deal
    env.step("Let's negotiate")
    done, info = env.step("I'm thinking about it")
    
    assert done
    # Should be a draw when no deal is reached


def test_free_text_discussion():
    """Test that free text without actions is valid."""
    env = UgliOrangeEnv()
    env.reset(num_players=3)
    
    # Free text should be valid
    done, info = env.step("Hello Dr. Jones, let's discuss this matter")
    
    assert not done
    assert not env.state.game_state["deal_reached"]


if __name__ == "__main__":
    pytest.main([__file__])