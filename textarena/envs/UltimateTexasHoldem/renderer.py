def create_board_str(game_state: dict) -> str:
    """Create a string representation of the game board."""
    gs = game_state
    
    # Game header
    board_str = "🎰 ULTIMATE TEXAS HOLD'EM 🎰\n"
    board_str += "=" * 50 + "\n\n"
    
    # Game info
    board_str += f"💰 Chips: ${gs['chips']}\n"
    board_str += f"🎯 Round: {gs['current_round']}\n"
    board_str += f"📋 Phase: {gs['current_phase'].upper().replace('_', ' ')}\n\n"
    
    # Player hand
    if gs['player_hand']:
        hand_str = ", ".join([f"{card['rank']}{card['suit']}" for card in gs['player_hand']])
        board_str += f"🎴 Your hand: {hand_str}\n"
    
    # Community cards
    if gs['visible_community_cards']:
        comm_str = ", ".join([f"{card['rank']}{card['suit']}" for card in gs['visible_community_cards']])
        board_str += f"🃏 Community cards: {comm_str}\n"
    else:
        board_str += "🃏 Community cards: [Hidden]\n"
    
    # Dealer hand (hidden during play)
    if gs['current_phase'] == 'showdown':
        dealer_str = ", ".join([f"{card['rank']}{card['suit']}" for card in gs['dealer_hand']])
        board_str += f"👤 Dealer's hand: {dealer_str}\n"
    else:
        board_str += "👤 Dealer's hand: [Hidden]\n"
    
    board_str += "\n"
    
    # Current bets
    board_str += "💸 Current Bets:\n"
    board_str += f"   Ante: ${gs['ante_bet']}\n"
    board_str += f"   Blind: ${gs['blind_bet']}\n"
    board_str += f"   Play: ${gs['play_bet']}\n"
    board_str += f"   Total: ${gs['total_bet']}\n\n"
    
    # Legal actions
    if gs['legal_actions'] and gs['current_phase'] != 'showdown':
        actions_str = ", ".join([f"[{action}]" for action in gs['legal_actions']])
        board_str += f"✅ Available actions: {actions_str}\n\n"
    
    # Game status
    if gs.get('game_complete', False) or gs.get('winner'):
        # Legacy support for old game state format
        if gs.get('winner') == 'player':
            board_str += "🏆 GAME OVER - YOU WIN! 🏆\n"
        else:
            board_str += "💀 GAME OVER - DEALER WINS 💀\n"
    elif gs.get('chips', 0) <= 0:
        board_str += "💀 GAME OVER - OUT OF CHIPS 💀\n"
    elif gs.get('current_round', 0) >= 1000:
        board_str += "🏆 GAME OVER - 1000 ROUNDS COMPLETED! 🏆\n"
    elif gs['round_complete']:
        board_str += "🔄 Round complete - starting next round...\n"
    
    return board_str 