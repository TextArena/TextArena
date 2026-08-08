import pytest
import random
from textarena.envs.Santorini.env import SantoriniBaseFixedWorkerEnv
from textarena.envs.Santorini.renderer import create_board_str

def test_init():
    """Test environment initialization."""
    env = SantoriniBaseFixedWorkerEnv()
    assert env.rows == 5
    assert env.cols == 5
    assert env.is_open == True
    assert env.show_valid == True

    env = SantoriniBaseFixedWorkerEnv(is_open=False, show_valid=False)
    assert env.is_open == False
    assert env.show_valid == False

def test_reset():
    """Test environment reset with different player counts."""
    env = SantoriniBaseFixedWorkerEnv()
    
    # Test invalid player count
    with pytest.raises(ValueError):
        env.reset(num_players=1)
    with pytest.raises(ValueError):
        env.reset(num_players=4)

    # Test 2-player setup
    env.reset(num_players=2)
    assert env.state.num_players == 2
    # Verify initial worker positions for 2 players
    assert env.board[2][1][1] == (0, 1)  # Player 0, Worker 1 at C2
    assert env.board[1][2][1] == (0, 2)  # Player 0, Worker 2 at B3
    assert env.board[3][2][1] == (1, 1)  # Player 1, Worker 1 at D3
    assert env.board[2][3][1] == (1, 2)  # Player 1, Worker 2 at C4

    # Test 3-player setup
    env.reset(num_players=3)
    assert env.state.num_players == 3
    # Verify initial worker positions for 3 players
    assert env.board[2][2][1] == (0, 1)  # Player 0, Worker 1 at C3
    assert env.board[1][2][1] == (0, 2)  # Player 0, Worker 2 at B3
    assert env.board[3][2][1] == (1, 1)  # Player 1, Worker 1 at D3
    assert env.board[1][3][1] == (1, 2)  # Player 1, Worker 2 at B4
    assert env.board[3][1][1] == (2, 1)  # Player 2, Worker 1 at D2
    assert env.board[3][3][1] == (2, 2)  # Player 2, Worker 2 at D4

def test_valid_moves():
    """Test valid move generation."""
    env = SantoriniBaseFixedWorkerEnv()
    env.reset(num_players=2)
    
    # Get valid moves for player 0
    valid_moves = env._get_valid_moves(0)
    assert isinstance(valid_moves, str)
    assert len(valid_moves) > 0
    
    # Verify move format
    for move in valid_moves.split(", "):
        assert env.move_pattern.search(move) is not None

def test_move_validation():
    """Test move validation logic."""
    env = SantoriniBaseFixedWorkerEnv()
    env.reset(num_players=2)
    
    # Clear the board first
    env.board = [[(0, None) for _ in range(env.cols)] for _ in range(env.rows)]
    
    # Place a test worker at center position (2,2)
    env.board[2][2] = (0, (0, 1))  # Height 0, Player 0's Worker 1
    
    # Test adjacent vs non-adjacent moves
    # Center position (2,2) testing all surrounding positions
    assert env._is_valid_move(2, 2, 1, 1)  # Adjacent diagonal
    assert env._is_valid_move(2, 2, 1, 2)  # Adjacent up
    assert env._is_valid_move(2, 2, 1, 3)  # Adjacent diagonal
    assert env._is_valid_move(2, 2, 2, 1)  # Adjacent left
    assert env._is_valid_move(2, 2, 2, 3)  # Adjacent right
    assert env._is_valid_move(2, 2, 3, 1)  # Adjacent diagonal
    assert env._is_valid_move(2, 2, 3, 2)  # Adjacent down
    assert env._is_valid_move(2, 2, 3, 3)  # Adjacent diagonal
    
    # Test non-adjacent moves
    assert not env._is_valid_move(2, 2, 0, 0)  # Two spaces away
    assert not env._is_valid_move(2, 2, 0, 2)  # Two spaces away
    assert not env._is_valid_move(2, 2, 2, 4)  # Two spaces away
    assert not env._is_valid_move(2, 2, 4, 2)  # Two spaces away
    assert not env._is_valid_move(2, 2, 4, 4)  # Two spaces away diagonal
    
    # Test same position
    assert not env._is_valid_move(2, 2, 2, 2)  # Same position
    
    # Test all height difference combinations
    # Starting from height 0
    env.board[2][2] = (0, None)  # Source position
    
    # Test 0 -> X moves
    env.board[2][3] = (0, None)
    assert env._is_valid_move(2, 2, 2, 3)  # 0 -> 0
    env.board[2][3] = (1, None)
    assert env._is_valid_move(2, 2, 2, 3)  # 0 -> 1
    env.board[2][3] = (2, None)
    assert not env._is_valid_move(2, 2, 2, 3)  # 0 -> 2
    env.board[2][3] = (3, None)
    assert not env._is_valid_move(2, 2, 2, 3)  # 0 -> 3
    env.board[2][3] = (4, None)
    assert not env._is_valid_move(2, 2, 2, 3)  # 0 -> 4 (dome)
    
    # Starting from height 1
    env.board[2][2] = (1, None)  # Source position
    
    # Test 1 -> X moves
    env.board[2][3] = (0, None)
    assert env._is_valid_move(2, 2, 2, 3)  # 1 -> 0
    env.board[2][3] = (1, None)
    assert env._is_valid_move(2, 2, 2, 3)  # 1 -> 1
    env.board[2][3] = (2, None)
    assert env._is_valid_move(2, 2, 2, 3)  # 1 -> 2
    env.board[2][3] = (3, None)
    assert not env._is_valid_move(2, 2, 2, 3)  # 1 -> 3
    env.board[2][3] = (4, None)
    assert not env._is_valid_move(2, 2, 2, 3)  # 1 -> 4 (dome)
    
    # Starting from height 2
    env.board[2][2] = (2, None)  # Source position
    
    # Test 2 -> X moves
    env.board[2][3] = (0, None)
    assert env._is_valid_move(2, 2, 2, 3)  # 2 -> 0
    env.board[2][3] = (1, None)
    assert env._is_valid_move(2, 2, 2, 3)  # 2 -> 1
    env.board[2][3] = (2, None)
    assert env._is_valid_move(2, 2, 2, 3)  # 2 -> 2
    env.board[2][3] = (3, None)
    assert env._is_valid_move(2, 2, 2, 3)  # 2 -> 3
    env.board[2][3] = (4, None)
    assert not env._is_valid_move(2, 2, 2, 3)  # 2 -> 4 (dome)
    
    # Starting from height 3
    env.board[2][2] = (3, None)  # Source position
    
    # Test 3 -> X moves
    env.board[2][3] = (0, None)
    assert env._is_valid_move(2, 2, 2, 3)  # 3 -> 0
    env.board[2][3] = (1, None)
    assert env._is_valid_move(2, 2, 2, 3)  # 3 -> 1
    env.board[2][3] = (2, None)
    assert env._is_valid_move(2, 2, 2, 3)  # 3 -> 2
    env.board[2][3] = (3, None)
    assert env._is_valid_move(2, 2, 2, 3)  # 3 -> 3
    env.board[2][3] = (4, None)
    assert not env._is_valid_move(2, 2, 2, 3)  # 3 -> 4 (dome)
    
    # Test occupied destination
    env.board[2][2] = (0, None)  # Reset source
    env.board[2][3] = (0, (1, 1))  # Place worker at destination
    assert not env._is_valid_move(2, 2, 2, 3)  # Can't move to occupied space

def test_build_validation():
    """Test build validation logic."""
    env = SantoriniBaseFixedWorkerEnv()
    env.reset(num_players=2)
    
    # Clear the board first
    env.board = [[(0, None) for _ in range(env.cols)] for _ in range(env.rows)]
    
    # Place a test worker at center position (2,2)
    env.board[2][2] = (0, (0, 1))  # Height 0, Player 0's Worker 1
    
    # Test adjacent vs non-adjacent builds
    # Test all 8 adjacent positions from center (2,2)
    assert env._is_valid_build(env.board, 2, 2, 1, 1)  # Adjacent diagonal
    assert env._is_valid_build(env.board, 2, 2, 1, 2)  # Adjacent up
    assert env._is_valid_build(env.board, 2, 2, 1, 3)  # Adjacent diagonal
    assert env._is_valid_build(env.board, 2, 2, 2, 1)  # Adjacent left
    assert env._is_valid_build(env.board, 2, 2, 2, 3)  # Adjacent right
    assert env._is_valid_build(env.board, 2, 2, 3, 1)  # Adjacent diagonal
    assert env._is_valid_build(env.board, 2, 2, 3, 2)  # Adjacent down
    assert env._is_valid_build(env.board, 2, 2, 3, 3)  # Adjacent diagonal
    
    # Test non-adjacent builds
    assert not env._is_valid_build(env.board, 2, 2, 0, 0)  # Two spaces away
    assert not env._is_valid_build(env.board, 2, 2, 0, 2)  # Two spaces away
    assert not env._is_valid_build(env.board, 2, 2, 2, 4)  # Two spaces away
    assert not env._is_valid_build(env.board, 2, 2, 4, 2)  # Two spaces away
    assert not env._is_valid_build(env.board, 2, 2, 4, 4)  # Two spaces away diagonal
    
    # Test building on same position as worker
    assert not env._is_valid_build(env.board, 2, 2, 2, 2)  # Can't build where worker is
    
    # Test building on occupied spaces
    env.board[2][3] = (0, (1, 1))  # Place another worker
    assert not env._is_valid_build(env.board, 2, 2, 2, 3)  # Can't build where worker is
    
    # Test building at different heights
    env.board[2][3] = (0, None)  # Clear the space
    
    # Test building on level 0
    assert env._is_valid_build(env.board, 2, 2, 2, 3)  # Can build on level 0
    
    # Test building on level 1
    env.board[2][3] = (1, None)
    assert env._is_valid_build(env.board, 2, 2, 2, 3)  # Can build on level 1
    
    # Test building on level 2
    env.board[2][3] = (2, None)
    assert env._is_valid_build(env.board, 2, 2, 2, 3)  # Can build on level 2
    
    # Test building on level 3
    env.board[2][3] = (3, None)
    assert env._is_valid_build(env.board, 2, 2, 2, 3)  # Can build on level 3 (creates dome)
    
    # Test building on dome (level 4)
    env.board[2][3] = (4, None)
    assert not env._is_valid_build(env.board, 2, 2, 2, 3)  # Can't build on dome
    
    # Test building at board edges
    # Reset board to clear any previous test states
    env.board = [[(0, None) for _ in range(env.cols)] for _ in range(env.rows)]
    
    # Top edge
    env.board[0][2] = (0, (0, 1))  # Move worker to top edge
    assert env._is_valid_build(env.board, 0, 2, 0, 1)  # Left
    assert env._is_valid_build(env.board, 0, 2, 0, 3)  # Right
    assert env._is_valid_build(env.board, 0, 2, 1, 1)  # Bottom-left
    assert env._is_valid_build(env.board, 0, 2, 1, 2)  # Bottom
    assert env._is_valid_build(env.board, 0, 2, 1, 3)  # Bottom-right
    
    # Bottom edge
    env.board[0][2] = (0, None)  # Clear previous
    env.board[4][2] = (0, (0, 1))  # Move worker to bottom edge
    assert env._is_valid_build(env.board, 4, 2, 4, 1)  # Left
    assert env._is_valid_build(env.board, 4, 2, 4, 3)  # Right
    assert env._is_valid_build(env.board, 4, 2, 3, 1)  # Top-left
    assert env._is_valid_build(env.board, 4, 2, 3, 2)  # Top
    assert env._is_valid_build(env.board, 4, 2, 3, 3)  # Top-right
    
    # Left edge
    env.board[4][2] = (0, None)  # Clear previous
    env.board[2][0] = (0, (0, 1))  # Move worker to left edge
    assert env._is_valid_build(env.board, 2, 0, 1, 0)  # Top
    assert env._is_valid_build(env.board, 2, 0, 3, 0)  # Bottom
    assert env._is_valid_build(env.board, 2, 0, 1, 1)  # Top-right
    assert env._is_valid_build(env.board, 2, 0, 2, 1)  # Right
    assert env._is_valid_build(env.board, 2, 0, 3, 1)  # Bottom-right
    
    # Right edge
    env.board[2][0] = (0, None)  # Clear previous
    env.board[2][4] = (0, (0, 1))  # Move worker to right edge
    assert env._is_valid_build(env.board, 2, 4, 1, 4)  # Top
    assert env._is_valid_build(env.board, 2, 4, 3, 4)  # Bottom
    assert env._is_valid_build(env.board, 2, 4, 1, 3)  # Top-left
    assert env._is_valid_build(env.board, 2, 4, 2, 3)  # Left
    assert env._is_valid_build(env.board, 2, 4, 3, 3)  # Bottom-left

def test_move_execution():
    """Test move execution."""
    env = SantoriniBaseFixedWorkerEnv()
    env.reset(num_players=2)
    
    # Execute a valid move with no additional text
    action = "[N1C2C3B2]"  # Move Navy worker 1 from C2 to C3 and build at B2
    success = env._execute_player_move(action)
    assert success
    
    # Verify worker moved
    assert env.board[2][1][1] is None  # Old position empty
    assert env.board[2][2][1] == (0, 1)  # New position has worker
    
    # Verify build executed
    assert env.board[1][1][0] == 1  # Build location height increased

    # Reset for next test
    env.reset(num_players=2)
    
    # Execute a valid move with additional text before
    action = "I move my worker [N1C2C3B2] to block opponent"
    success = env._execute_player_move(action)
    assert success
    
    # Verify worker moved
    assert env.board[2][1][1] is None  # Old position empty
    assert env.board[2][2][1] == (0, 1)  # New position has worker
    
    # Verify build executed
    assert env.board[1][1][0] == 1  # Build location height increased

    # Reset for next test
    env.reset(num_players=2)
    
    # Execute a valid move with additional text after
    action = "[N1C2C3B2] to get closer to winning"
    success = env._execute_player_move(action)
    assert success
    
    # Verify worker moved
    assert env.board[2][1][1] is None  # Old position empty
    assert env.board[2][2][1] == (0, 1)  # New position has worker
    
    # Verify build executed
    assert env.board[1][1][0] == 1  # Build location height increased

def test_invalid_moves():
    """Test invalid move handling."""
    env = SantoriniBaseFixedWorkerEnv()
    env.reset(num_players=2)
    
    # Test invalid move format
    assert not env._execute_player_move("invalid")
    
    # Test wrong worker
    assert not env._execute_player_move("[N1A1A2A3]")  # No worker at A1
    
    # Test invalid destination
    assert not env._execute_player_move("[N1C2E5B3]")  # E5 not adjacent
    
    # Test invalid build
    assert not env._execute_player_move("[N1C2C3E5]")  # E5 not adjacent to C3

def test_win_conditions():
    """Test win condition detection."""
    env = SantoriniBaseFixedWorkerEnv()
    env.reset(num_players=2)
    
    # Test win by reaching level 3
    env.board[2][2] = (3, (0, 1))  # Place worker on level 3
    env._check_gameover()
    assert env.state.rewards[0] == 1  # Winner should get reward 1
    assert env.state.rewards[1] == -1  # Loser should get reward -1
    
    # Reset and test win by blocking opponent
    env.reset(num_players=2)
    # Place domes to block all possible moves for Player 1's workers
    # Player 1's workers are at D3 (3,2) and C4 (2,3)
    # Block all adjacent spaces around D3
    for r, c in [(2,1), (2,2), (2,3), (3,1), (3,3), (4,1), (4,2), (4,3)]:
        if env.board[r][c][1] is None:  # Don't overwrite workers
            env.board[r][c] = (4, None)
    # Block all adjacent spaces around C4
    for r, c in [(1,2), (1,3), (1,4), (2,2), (2,4), (3,2), (3,3), (3,4)]:
        if env.board[r][c][1] is None:  # Don't overwrite workers
            env.board[r][c] = (4, None)
    env._check_gameover()
    assert env.state.rewards[0] == 1  # Winner should get reward 1
    assert env.state.rewards[1] == -1  # Loser should get reward -1

def test_game_flow():
    """Test complete game flow."""
    env = SantoriniBaseFixedWorkerEnv()
    env.reset(num_players=2)
    
    # Make a series of valid moves
    moves = [
        "[N1C2C3B2]",  # Player 0: Move Navy worker 1 from C2 to C3, build at B2
        "[W1D3D2E2]",  # Player 1: Move White worker 1 from D3 to D2, build at E2
        "[N2B3B4A4]",  # Player 0: Move Navy worker 2 from B3 to B4, build at A4
        "[W2C4D4E4]"   # Player 1: Move White worker 2 from C4 to D4, build at E4
    ]
    
    for move in moves:
        done, info = env.step(move)
        assert not done  # Game shouldn't be over
        
    # Verify game state maintained correctly
    assert env.state.current_player_id == 0  # Back to player 0
    assert isinstance(env._get_valid_moves(0), str)  # Should have valid moves

def test_random_play():
    """Test playing random valid moves until game completion."""
    
    # Set seed for reproducibility
    random.seed(112)
    
    env = SantoriniBaseFixedWorkerEnv()
    env.reset(num_players=2)
    
    done = False
    turn_count = 0
    max_turns = 1000  # Safety limit to prevent infinite loops
    
    # Track highest level reached by each player's workers
    player_heights = {0: 0, 1: 0}
    
    while not done and turn_count < max_turns:
        current_player = env.state.current_player_id
        valid_moves = env._get_valid_moves(current_player).split(", ")
        assert len(valid_moves) > 0, f"Player {current_player} has no valid moves but game not ended"
        
        # Select random move
        move = random.choice(valid_moves)
        done, info = env.step(move)
        
        # Track highest level for each player
        for row in range(env.rows):
            for col in range(env.cols):
                if env.board[row][col][1] is not None:
                    player = env.board[row][col][1][0]
                    height = env.board[row][col][0]
                    player_heights[player] = max(player_heights[player], height)
        
        turn_count += 1
    
    print(f"\nGame ended after {turn_count} turns")
    print(create_board_str(env.board))
    print(f"Final player heights: {player_heights}")
    
    assert done, f"Game should have ended (last move: {move})"
    assert turn_count < max_turns, f"Game exceeded maximum turns. Final heights: {player_heights}"
    assert 1 in env.state.rewards.values(), "Game ended without a winner (no reward of 1)"
    assert -1 in env.state.rewards.values(), "Game ended without a loser (no reward of -1)"
    winner = next(player_id for player_id, reward in env.state.rewards.items() if reward == 1)
    assert winner in [0, 1], "Winner should be player 0 or 1"
