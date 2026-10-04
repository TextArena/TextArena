# Used Car Negotiation Environment

This is an implementation of a two-player negotiation game based on the paper "Let's Make a Deal: A Dynamic Exercise for Practicing Negotiation Skill" by Gerard Beenen and John E. Barbuto, Jr.. 

## Game Description

The players engage in a negotiation between a buyer and seller of a used car. A unique feature is that the game can be configured to have either symmetrical or asymmetrical distributions of power by providing the parties with different information on their backgrounds.  

## Action Space

- **Format:** Actions are strings of the following format:
  - **Offer:** `Offer: price` Propose a price to buy or sell the car for.
  - **Discuss:** `Discuss: message` Make an argument or statement.
  - **Accept/Reject Offer:** `Accept` or `Reject`.

## Observation Space

**Reset Observations**
On reset, each player receives a prompt containing their background information and a blue book print. For example:

```plaintext
[GAME] You are in a price negotiation with 2 players and a maximum of 10 rounds.
Your old car just died, so you need to buy a car. You’re focused on finding a used Toyota Prius. After scouring Craig’s List and AutoTrader.com, you found two “Prii” (yes, that’s the new plural for “Prius”) that seem promising. 
Both are 2006 base models with standard features (air conditioning, power steering, AM/FM stereo with CD player, air bags, and 4-wheel ABS braking system). That’s really all you want. 

The first Prius you saw was in good condition with 89,000 miles and doesn’t need any maintenance work. You negotiated the sellers down to a price of $10,000 but they refused to lower the price any more. 
You told them you’d keep looking, and they told you that if you changed your mind and were ready to pay $10,000, you should come back. 

The second Prius was advertised for $10,000 but you think you can get it for less. During a test-drive you took it to an honest and trusted mechanic. Your mechanic said the car is generally well maintained and in good shape. 
There are some small dings and scrapes on the paint, and marks on the seats, but that’s to be expected in a 6 year old car with 95,000 miles. 
The Blue Book (see chart) suggests the car may sell for between $8,000 and $9,000 for a private party. But you know this is only an estimate. Similar cars may sell for more or less than that.
You’re returning from your test drive and preparing to meet the seller of this second Prius. 

You’ve already secured financing. You need a car because taking the bus is inconvenient and time consuming, and you live too far from school and work to ride a bike. 
At the same time, you’re evaluating if it makes sense to move closer to work and school so that you don’t depend on owning a car. 
In fact, an opportunity has just come up for you to move to a new place that’s close enough to bike to work and school, without raising your rent.
This new place also is closer to more convenient bus routes that would allow you to use the bus for work, school and shopping when the weather is bad. 
Plus ZIPCarR , the new car sharing service, recently added vehicles near campus that you can use for day trips when you want a car, for less than the cost of owning.
On the one hand, you like the freedom that goes with owning your own car. So you’re still willing to buy the Prius if you can get a really good deal. 
On the other hand, rising gas prices, the opportunity to move to a more convenient place, and the potential for ZIPCarR as a lower cost option, cause you to question if you really need to buy this Prius.

                            Blue Book Pricing
######################################################################
Estimated Market Value for 2006 Toyota Prius:

                        Trade-in        Private Party   Dealer Retail
----------------------------------------------------------------------
National Base Price     $7,737          $9,207          $10.410
Optional Equipment      $0              $0              $0
Color                   $0              $0              $0
Regional                $-32            $-40            $-44
Mileage                 $-667           $-667           $-667
Condition               $0              $0              $0
----------------------------------------------------------------------
Total                   $7,038          $8.500          $9,699


Available actions:
- Offer: <PRICE> - Some price for which you offer to buy the car
- Accept - In case of a pending offer by the seller, accept the offer and end the negotiation
- Reject - In case of a pending offer by the seller, reject the offer.
- Discuss: <MESSAGE> - Make a statement or argument

Guidelines:
- Do not use coercion, lie, or misrepresent any facts presented to you in order to accomplish your goals in the negotiation
- The game ends when a player accepts an offer or the maximum number of negotiation turns is reached.
```

**Step Observations**
During gameplay, players receive various observations based on actions taken. For example:

```plaintext
[Player 0] Your action: Offer: $8000
[GAME] The buyer proposed a price of $8000.
[GAME] The seller rejected the offer.
[GAME] The seller says: I want more than $9,000!
```

## Variants

| Env-id                             | Stronger Position |
|------------------------------------|:-----------------:|
| `UsedCar-v0`                       | `Random`          |
| `UsedCar-v0-strong-buyer`          | `Buyer`           |
| `UsedCar-v0-strong-seller`         | `Seller`          |
| `UsedCar-v0-balanced`              | `Balanced`        |

## References

- Beenen, G., & Barbuto, J. E., Jr. (2014). Let's make a deal: A dynamic exercise for practicing negotiation skills. *Journal of Education for Business*, 89(3), 149–155. [PDF](https://doi.org/10.1080/08832323.2013.794121)
