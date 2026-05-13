# AI Decision Rules

## Bidding – Round 1

Rules are evaluated in priority order; the first match wins.

| # | Condition | Action |
|---|-----------|--------|
| 1 | Revealed card **is a Jack** | Always take — the Jack is worth 20 points as trump and must not be handed to opponents. |
| 2 | AI holds the **Jack** of the offered suit | Take — the AI already controls the strongest trump. With the revealed card it holds ≥ 2 trumps. |
| 3 | AI holds the **9** of the offered suit **and** already has ≥ 2 cards of that suit in hand | Take — receiving the revealed card gives the AI ≥ 3 trumps including the second-strongest. |
| 4 | Weighted hand score ≥ 58 | Take — fallback heuristic that values trump card points + trump count + plain card points. |

If none of the above apply, pass.

## Bidding – Round 2

No revealed card is received; the taker chooses any suit except the one already refused.
For each candidate suit the AI computes a score and picks the best:

- Base score: same weighted heuristic as round 1.
- **+20** bonus if AI holds the Jack of that suit.
- **+10** bonus if AI holds the 9 of that suit **and** has ≥ 2 cards of that suit.

The AI takes with the best-scoring suit if the adjusted score exceeds the threshold (40).

## Playing – Card Selection

### Tracking played cards
The AI maintains a running list of every card played across all tricks so far.
A card is *master* when every higher-ranked card of the same suit has already been played.

### Leading a trick (empty table)

| Priority | Condition | Play |
|----------|-----------|------|
| 1 | AI has a **master card** | Lead it — guaranteed win regardless of what opponents hold. Prefer the one with the highest point value. |
| 2 | **Partner took the contract** | Lead trump — helps drain opponent trump cards so the contract holder can win later tricks. |
| 3 | **AI itself took the contract** | Lead trump aggressively to pull out opposing trumps. |
| 4 | Default | Lead the highest point-value card available — **except**: do not lead the trump 9 while the trump Jack has not yet been played (it would be captured). Fall back to leading the 9 only if it is the only legal play. |

### Following a trick (cards already on table)

| Priority | Condition | Play |
|----------|-----------|------|
| 1 | **Partner is currently winning** the trick | Play the highest point-value legal card to maximise points for the team. |
| 2 | AI **can beat** the current winner | Play the lowest card that wins (conserve strong cards). |
| 3 | AI **cannot beat** the current winner | Play the lowest point-value card (minimise the gift to opponents). |

Legal-play obligations (follow suit, over-trump) are always enforced by `legal_plays()` before these rules apply.
