"""
Rendering functions for the Vendor Negotiation environment.

Provides LLM-optimized display functions for game state, product data,
and final results. All displays are minimal and structured for easy parsing.
"""

from typing import Dict, List, Any, Optional


def render_product_data_for_brand(products: Dict, 
                                  selected_products: List[str],
                                  allowed_discounts: List[int]) -> str:
    """
    Render product data for Brand Specialist (Player 0).
    Shows only sales data, not costs or profits.
    """
    lines = ["PRODUCTS & SALES FORECASTS (MEAN and 95% CI):"]
    
    for product_name in selected_products:
        p = products[product_name]
        lines.append(f"\n{product_name} (${p['price']}/unit):")
        
        for discount in allowed_discounts:
            data = p['data'][discount]
            # Calculate 95% CI for units and sales
            units_lower = max(0, data['mean_units'] - 1.96 * data['std_units'])
            units_upper = data['mean_units'] + 1.96 * data['std_units']
            sales_lower = max(0, data['mean_sales'] - 1.96 * data['std_sales'])
            sales_upper = data['mean_sales'] + 1.96 * data['std_sales']
            
            lines.append(
                f"  {discount}%: {data['mean_units']:.0f} units (95% CI: {units_lower:.0f}-{units_upper:.0f}) "
                f"→ ${data['mean_sales']:.0f} sales (95% CI: ${sales_lower:.0f}-${sales_upper:.0f})"
            )
    
    return "\n".join(lines)


def render_product_data_for_vendor(products: Dict, 
                                   selected_products: List[str],
                                   allowed_discounts: List[int]) -> str:
    """
    Render product data for Vendor (Player 1).
    Shows sales data AND profit data.
    """
    lines = ["PRODUCTS & PROFIT DATA (MEAN and 95% CI):"]
    
    for product_name in selected_products:
        p = products[product_name]
        lines.append(f"\n{product_name} (Price: ${p['price']}, Cost: ${p['cost']}):")
        
        for discount in allowed_discounts:
            data = p['data'][discount]
            # Calculate 95% CI for units and profit
            units_lower = max(0, data['mean_units'] - 1.96 * data['std_units'])
            units_upper = data['mean_units'] + 1.96 * data['std_units']
            profit_lower = data['mean_profit'] - 1.96 * data['std_profit']
            profit_upper = data['mean_profit'] + 1.96 * data['std_profit']
            
            lines.append(
                f"  {discount}%: {data['mean_units']:.0f} units (95% CI: {units_lower:.0f}-{units_upper:.0f}) "
                f"→ ${data['mean_profit']:.0f} profit (95% CI: ${profit_lower:.0f}-${profit_upper:.0f})"
            )
    
    return "\n".join(lines)


def render_current_state(current_proposal: Optional[Dict],
                        negotiation_history: List[Dict],
                        current_round: int,
                        max_rounds: int,
                        conversation_history: Optional[List[Dict]] = None,
                        products: Optional[Dict] = None,
                        brand_target: Optional[float] = None,
                        vendor_baseline: Optional[float] = None,
                        current_player_id: Optional[int] = None) -> str:
    """
    Render minimal current game state.
    Shows current proposal, recent conversation, and last 3 actions.
    """
    lines = [f"ROUND {current_round}/{max_rounds}\n"]
    
    if current_proposal and current_proposal.get('discounts'):
        lines.append("CURRENT PROPOSAL:")
        proposal_str = ", ".join(
            f"{p}:{d}%" for p, d in current_proposal['discounts'].items()
        )
        lines.append(proposal_str)
        lines.append(f"Proposed by: Player {current_proposal['proposer']}")
        
        # Show proposal analysis if we have the data
        if products and brand_target is not None and vendor_baseline is not None:
            lines.append("")
            lines.append("PROPOSAL ANALYSIS WITH 95% CONFIDENCE INTERVALS:")
            
            total_sales_mean = 0
            total_sales_std = 0
            total_profit_mean = 0
            total_profit_std = 0
            
            for product, discount in current_proposal['discounts'].items():
                if product in products:
                    data = products[product]['data'][discount]
                    total_sales_mean += data['mean_sales']
                    total_sales_std += data['std_sales'] ** 2  # Sum variances
                    total_profit_mean += data['mean_profit']
                    total_profit_std += data['std_profit'] ** 2  # Sum variances
            
            # Convert back to standard deviations
            total_sales_std = total_sales_std ** 0.5
            total_profit_std = total_profit_std ** 0.5
            
            # Calculate 95% confidence intervals (mean ± 1.96 * std)
            sales_lower = max(0, total_sales_mean - 1.96 * total_sales_std)
            sales_upper = total_sales_mean + 1.96 * total_sales_std
            profit_lower = total_profit_mean - 1.96 * total_profit_std
            profit_upper = total_profit_mean + 1.96 * total_profit_std
            
            # Show analysis for current player
            if current_player_id == 0:  # Brand Specialist
                status = "LIKELY MEETS TARGET" if sales_lower >= brand_target else "RISKY - MAY MISS TARGET"
                lines.append(f"Expected Sales: ${total_sales_mean:.0f} (95% CI: ${sales_lower:.0f}-${sales_upper:.0f}) - {status}")
                lines.append(f"Your Target: ${brand_target:.0f}")
            elif current_player_id == 1:  # Vendor
                status = "LIKELY BEATS BASELINE" if profit_lower > vendor_baseline else "RISKY - MAY MISS BASELINE"
                lines.append(f"Expected Profit: ${total_profit_mean:.0f} (95% CI: ${profit_lower:.0f}-${profit_upper:.0f}) - {status}")
                lines.append(f"Your Baseline: ${vendor_baseline:.0f}")
        
        lines.append("")
    else:
        lines.append("NO CURRENT PROPOSAL\n")
    
    # Show recent conversation (last 3 messages)
    if conversation_history:
        lines.append("RECENT CONVERSATION:")
        for conv in conversation_history[-3:]:
            lines.append(f"Player {conv['player']}: {conv['message']}")
        lines.append("")
    
    # Show last 3 actions only (excluding conversation)
    if negotiation_history:
        lines.append("RECENT HISTORY:")
        # Filter to only show propose/accept/reject actions
        important_actions = [a for a in negotiation_history if a['type'] in ['propose', 'accept', 'reject']]
        for action in important_actions[-3:]:
            if action['type'] == 'propose':
                proposal_str = ", ".join(
                    f"{p}:{d}%" for p, d in action['discounts'].items()
                )
                lines.append(f"R{action['round']}: Player {action['player']} proposed {proposal_str}")
            elif action['type'] == 'accept':
                lines.append(f"R{action['round']}: Player {action['player']} accepted")
            elif action['type'] == 'reject':
                lines.append(f"R{action['round']}: Player {action['player']} rejected")
    
    return "\n".join(lines)


def render_final_results(simulation_results: Dict,
                        agreed_discounts: Dict,
                        brand_won: bool,
                        vendor_won: bool,
                        brand_target: float,
                        vendor_baseline: float,
                        num_simulations: int) -> str:
    """
    Render minimal final results with Monte Carlo statistics.
    One line per product, clear outcome summary.
    """
    lines = ["DEAL ACCEPTED\n"]
    
    # Agreed discounts
    lines.append("AGREED DISCOUNTS:")
    discount_str = ", ".join(f"{p}:{d}%" for p, d in agreed_discounts.items())
    lines.append(discount_str + "\n")
    
    # Simulation results (one line per product)
    lines.append(f"SIMULATION RESULTS ({num_simulations} runs):")
    for product, results in simulation_results.items():
        lines.append(
            f"{product}: {results['avg_units']:.0f} units, "
            f"${results['avg_sales']:.0f} sales, "
            f"${results['avg_profit']:.0f} profit"
        )
    
    # Totals
    total_sales = sum(r['avg_sales'] for r in simulation_results.values())
    total_profit = sum(r['avg_profit'] for r in simulation_results.values())
    lines.append(f"\nTOTALS:")
    lines.append(f"Sales: ${total_sales:.0f}")
    lines.append(f"Profit: ${total_profit:.0f}")
    
    # Outcomes
    lines.append(f"\nOUTCOMES:")
    brand_status = "WON" if brand_won else "LOST"
    vendor_status = "WON" if vendor_won else "LOST"
    lines.append(
        f"Brand Specialist: {brand_status} "
        f"(Target: ${brand_target:.0f}, Achieved: ${total_sales:.0f})"
    )
    lines.append(
        f"Vendor: {vendor_status} "
        f"(Baseline: ${vendor_baseline:.0f}, Achieved: ${total_profit:.0f})"
    )
    
    return "\n".join(lines)


def render_no_deal(brand_target: float, vendor_baseline: float) -> str:
    """Render result when no deal was reached."""
    lines = ["NO DEAL REACHED\n"]
    lines.append("OUTCOMES:")
    lines.append(f"Brand Specialist: LOST (Target: ${brand_target:.0f}, Achieved: $0)")
    lines.append(f"Vendor: LOST (Baseline: ${vendor_baseline:.0f}, Achieved: $0)")
    return "\n".join(lines)
