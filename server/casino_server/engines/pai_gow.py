"""
Pai Gow Poker engine: Fortune Pai Gow and Face Up Pai Gow, ported from Casino
v2's games/pai_gow_poker/logic.py and games/pai_gow_poker_face_up/logic.py.

Same rules, Joker handling, House Way chart and paytables as v2, with these
changes:
  - Money is integer pence (v2 used float pounds).
  - The pieces are pure functions (house_way_set, settle_ante, bonus,
    is_ace_high_pai_gow...), so the table machine can deal seven hands from
    one deck and settle any number of seats against the dealer.
  - BUG FIX: v2's House Way grouped only real cards of the same rank, so a
    Joker next to a real Ace (the Joker's one pairing role) was never seen
    as the pair of Aces it is. Joker + Ace + five unpaired cards went down
    the "no pair" branch, which split the Joker and the Ace between the two
    hands -- and in Face Up that read as a dealer Ace-high Pai Gow and pushed
    every Ante. The Joker now joins the Aces when there's a real Ace for it
    to pair (_groups), and the Ace-high check looks at all seven cards
    (is_ace_high_pai_gow), not the two set halves.
  - BUG FIX: v2's foul check compared a 2-card pair with a 5-card pair of the
    same rank tuple-by-tuple ((9, 9) against (9, K, 7, 4)), so it called a
    legal split a foul -- the 5-card pair has kickers, so it's the higher
    hand. That broke the chart's four-of-a-kind splits (e.g. four 9s with no
    King: a pair of 9s each way) and four Aces with the Joker; the safety net
    then set them some other way. is_foul now compares like for like.
  - The Envy Bonus (both tables), which v2 left out as single-player:
    with a Fortune bet of £5 or more you're paid a fixed bonus whenever
    another player at the table hits Four of a Kind or better.

The game: 53 cards (52 + a semi-wild Joker, which can only complete a
Straight or Flush or otherwise plays as an Ace). Seven hands of seven cards.
Each player sets a 2-card front ("low") and a 5-card back ("high"); the back
must outrank the front. Front plays front, back plays back: win both and the
Ante pays 1:1, lose both and it's lost, one each pushes; a tied hand (a
"copy") goes to the dealer. The dealer always sets by House Way.

  Fortune Pai Gow: 5% commission on a winning Ante. The dealer's hand stays
    face down until every player has set.
  Face Up Pai Gow: no commission. The dealer's hand is set and shown first.
    A dealer Ace-high Pai Gow (nothing but an Ace-high hand across all seven
    cards) pushes every Ante at once; players may fold, losing the Ante.
Both: the Fortune (any amount) and £1 Jackpot side bets pay off the player's
own seven cards, whatever happens to the Ante.
"""
from dataclasses import dataclass
from itertools import combinations

from casino_server.engines.cards import RANK_ORDER, Card, Suit
from casino_server.engines.hand_evaluator import (
    FIVE_CARD_FLUSH,
    FIVE_CARD_HAND_NAMES,
    FIVE_CARD_HIGH_CARD,
    FIVE_CARD_STRAIGHT,
    FIVE_CARD_STRAIGHT_FLUSH,
    FIVE_CARD_THREE_OF_A_KIND,
    FOUR_OF_A_KIND,
    FULL_HOUSE,
    HandEval,
    compare_hands,
    evaluate_five_card_hand,
)

FORTUNE = "pai_gow_fortune"
FACE_UP = "pai_gow_face_up"
LABELS = {FORTUNE: "Fortune Pai Gow", FACE_UP: "Face Up Pai Gow"}

COMMISSION_PERCENT = 5   # Fortune Pai Gow, on a winning Ante only
JACKPOT_BET = 100        # pence, flat
ENVY_MIN_FORTUNE = 500   # a Fortune bet of at least £5 qualifies for the Envy Bonus

TWO_CARD_HIGH_CARD = 0
TWO_CARD_PAIR = 1

_RANK_FOR_VALUE = {i + 2: rank for i, rank in enumerate(RANK_ORDER)}
_NAMES = {14: "Ace", 13: "King", 12: "Queen", 11: "Jack"}


def _rank_value(card) -> int:
    return 14 if card.is_joker else card.value


# ---------------------------------------------------------------------- evaluation
def evaluate_two_card_hand(two_cards) -> HandEval:
    """The front hand: a pair beats any non-pair, else the higher card wins.
    A Joker here always plays as an Ace."""
    if len(two_cards) != 2:
        raise ValueError("A Pai Gow front hand is exactly 2 cards.")
    values = sorted((_rank_value(c) for c in two_cards), reverse=True)
    if values[0] == values[1]:
        return (TWO_CARD_PAIR, "Pair", tuple(values))
    return (TWO_CARD_HIGH_CARD, "High Card", tuple(values))


def _missing_straight_ranks(values) -> list[int]:
    unique = sorted(set(values))
    if len(unique) != 4:
        return []
    found = []
    for candidate in range(2, 15):
        if candidate in unique:
            continue
        combined = sorted(unique + [candidate])
        if combined[-1] - combined[0] == 4:
            found.append(candidate)
            continue
        alt = sorted(1 if v == 14 else v for v in combined)  # Ace-low wheel
        if len(set(alt)) == 5 and alt[-1] - alt[0] == 4:
            found.append(candidate)
    return found


def _joker_candidates(other_cards) -> list[Card]:
    """The Joker's only legal stand-ins: a card completing a Straight, the best
    card completing a Flush, or a bare Ace."""
    candidates = []
    for rank_value in _missing_straight_ranks([c.value for c in other_cards]):
        for suit in Suit:
            candidates.append(Card(_RANK_FOR_VALUE[rank_value], suit))
    suits = {c.suit for c in other_cards}
    if len(suits) == 1:
        flush_suit = next(iter(suits))
        used = {c.rank for c in other_cards}
        for rank in reversed(RANK_ORDER):
            if rank not in used:
                candidates.append(Card(rank, flush_suit))
                break
    ace_suit = next((s for s in Suit if s not in suits), Suit.SPADES)
    candidates.append(Card("A", ace_suit))
    return candidates


def evaluate_five(cards) -> HandEval:
    """The back hand, with the Joker as whichever legal stand-in is best."""
    if len(cards) != 5:
        raise ValueError("A Pai Gow back hand is exactly 5 cards.")
    joker_idx = next((i for i, c in enumerate(cards) if c.is_joker), None)
    if joker_idx is None:
        return evaluate_five_card_hand(cards)
    others = [c for i, c in enumerate(cards) if i != joker_idx]
    best = None
    for sub in _joker_candidates(others):
        trial = list(cards)
        trial[joker_idx] = sub
        ev = evaluate_five_card_hand(trial)
        if best is None or compare_hands(ev, best) > 0:
            best = ev
    return best


def best_five_of_seven(seven_cards) -> tuple[HandEval, list]:
    best_eval, best_cards = None, None
    for combo in combinations(seven_cards, 5):
        ev = evaluate_five(list(combo))
        if best_eval is None or compare_hands(ev, best_eval) > 0:
            best_eval, best_cards = ev, list(combo)
    return best_eval, best_cards


def is_foul(front, back) -> bool:
    """A set hand fouls if the back doesn't outrank the front. The 2-card and
    5-card hands share rank numbers for High Card (0) and a Pair (1); at the
    same rank the back must be at least as high card for card, and a tie on
    the cards the front has goes to the back (its extra kickers)."""
    f, b = evaluate_two_card_hand(front), evaluate_five(back)
    if b[0] != f[0]:
        return b[0] < f[0]
    if f[0] == TWO_CARD_PAIR:
        return b[2][0] < f[2][0]
    return tuple(b[2][:2]) < tuple(f[2])


def two_card_label(ev: HandEval) -> str:
    """'Pair of Kings', 'Ace-Queen'."""
    hi, lo = ev[2]
    if ev[0] == TWO_CARD_PAIR:
        return f"Pair of {_NAMES.get(hi, hi)}s"
    return f"{_NAMES.get(hi, hi)}-{_NAMES.get(lo, lo)}"


def five_card_label(ev: HandEval) -> str:
    """'Two Pair', 'Pair of 9s', 'King high', 'Straight'."""
    if ev[0] == FIVE_CARD_HIGH_CARD:
        return f"{_NAMES.get(ev[2][0], ev[2][0])} high"
    if ev[0] == FIVE_CARD_STRAIGHT_FLUSH and ev[2][0] == 14:
        return "Royal Flush"
    if ev[0] == 1:  # One Pair
        v = ev[2][0]
        return f"Pair of {_NAMES.get(v, v)}s"
    return FIVE_CARD_HAND_NAMES[ev[0]]


# ---------------------------------------------------------------------- bonuses
SEVEN_CARD_STRAIGHT_FLUSH = "seven_card_straight_flush"
ROYAL_FLUSH_ROYAL_MATCH = "royal_flush_royal_match"
SEVEN_CARD_STRAIGHT_FLUSH_JOKER = "seven_card_straight_flush_joker"
FIVE_ACES = "five_aces"
ROYAL_FLUSH = "royal_flush"
STRAIGHT_FLUSH_TIER = "straight_flush"
FOUR_OF_A_KIND_TIER = "four_of_a_kind"
FULL_HOUSE_TIER = "full_house"
FLUSH_TIER = "flush"
THREE_OF_A_KIND_TIER = "three_of_a_kind"
STRAIGHT_TIER = "straight"

TIER_NAMES = {
    SEVEN_CARD_STRAIGHT_FLUSH: "7-Card Straight Flush", ROYAL_FLUSH_ROYAL_MATCH: "Royal Flush + Royal Match",
    SEVEN_CARD_STRAIGHT_FLUSH_JOKER: "7-Card Straight Flush (Joker)", FIVE_ACES: "Five Aces",
    ROYAL_FLUSH: "Royal Flush", STRAIGHT_FLUSH_TIER: "Straight Flush", FOUR_OF_A_KIND_TIER: "Four of a Kind",
    FULL_HOUSE_TIER: "Full House", FLUSH_TIER: "Flush", THREE_OF_A_KIND_TIER: "Three of a Kind",
    STRAIGHT_TIER: "Straight",
}

FORTUNE_MULTIPLIERS = {  # "X to 1"
    SEVEN_CARD_STRAIGHT_FLUSH: 5000, ROYAL_FLUSH_ROYAL_MATCH: 2000, SEVEN_CARD_STRAIGHT_FLUSH_JOKER: 1000,
    FIVE_ACES: 400, ROYAL_FLUSH: 150, STRAIGHT_FLUSH_TIER: 50, FOUR_OF_A_KIND_TIER: 25,
    FULL_HOUSE_TIER: 5, FLUSH_TIER: 4, THREE_OF_A_KIND_TIER: 3, STRAIGHT_TIER: 2,
}

# (fixed pence, share of the progressive pool) -- exactly one is set.
JACKPOT_TIERS = {
    SEVEN_CARD_STRAIGHT_FLUSH: (None, 1.0), ROYAL_FLUSH_ROYAL_MATCH: (None, 0.5),
    SEVEN_CARD_STRAIGHT_FLUSH_JOKER: (None, 0.25), FIVE_ACES: (250_000, None), ROYAL_FLUSH: (20_000, None),
    STRAIGHT_FLUSH_TIER: (10_000, None), FOUR_OF_A_KIND_TIER: (7_500, None), FULL_HOUSE_TIER: (600, None),
}

ENVY_BONUS = {  # pence, paid per other player's qualifying hand
    SEVEN_CARD_STRAIGHT_FLUSH: 500_000, ROYAL_FLUSH_ROYAL_MATCH: 100_000, SEVEN_CARD_STRAIGHT_FLUSH_JOKER: 50_000,
    FIVE_ACES: 25_000, ROYAL_FLUSH: 5_000, STRAIGHT_FLUSH_TIER: 2_500, FOUR_OF_A_KIND_TIER: 500,
}


def _seven_card_straight_flush_no_joker(cards) -> bool:
    if any(c.is_joker for c in cards) or len({c.suit for c in cards}) != 1:
        return False
    values = sorted(c.value for c in cards)
    if len(set(values)) != 7:
        return False
    if values[-1] - values[0] == 6:
        return True
    alt = sorted(1 if v == 14 else v for v in values)
    return alt[-1] - alt[0] == 6


def _seven_card_straight_flush_with_joker(cards) -> bool:
    if not any(c.is_joker for c in cards):
        return False
    others = [c for c in cards if not c.is_joker]
    if len({c.suit for c in others}) != 1:
        return False

    def fits(values):
        values = sorted(set(values))
        return len(values) == 6 and values[-1] - values[0] in (5, 6)

    values = [c.value for c in others]
    return fits(values) or fits([1 if v == 14 else v for v in values])


def _royal_flush_royal_match(cards) -> bool:
    if any(c.is_joker for c in cards):
        return False
    for combo in combinations(cards, 5):
        if {c.value for c in combo} == {14, 13, 12, 11, 10} and len({c.suit for c in combo}) == 1:
            other = [c for c in cards if c not in combo]
            if {c.value for c in other} == {13, 12} and other[0].suit == other[1].suit:
                return True
    return False


def _five_aces(cards) -> bool:
    return any(c.is_joker for c in cards) and sum(1 for c in cards if not c.is_joker and c.rank == "A") == 4


def classify_seven_card_bonus(cards) -> str | None:
    """The best bonus tier the raw seven cards make (Fortune, Jackpot and Envy)."""
    if _seven_card_straight_flush_no_joker(cards):
        return SEVEN_CARD_STRAIGHT_FLUSH
    if _royal_flush_royal_match(cards):
        return ROYAL_FLUSH_ROYAL_MATCH
    if _seven_card_straight_flush_with_joker(cards):
        return SEVEN_CARD_STRAIGHT_FLUSH_JOKER
    if _five_aces(cards):
        return FIVE_ACES
    best, _ = best_five_of_seven(cards)
    rank = best[0]
    if rank == FIVE_CARD_STRAIGHT_FLUSH:
        return ROYAL_FLUSH if best[2][0] == 14 else STRAIGHT_FLUSH_TIER
    return {FOUR_OF_A_KIND: FOUR_OF_A_KIND_TIER, FULL_HOUSE: FULL_HOUSE_TIER, FIVE_CARD_FLUSH: FLUSH_TIER,
            FIVE_CARD_STRAIGHT: STRAIGHT_TIER, FIVE_CARD_THREE_OF_A_KIND: THREE_OF_A_KIND_TIER}.get(rank)


@dataclass
class Bonus:
    tier: str | None = None
    fortune_return: int = 0      # stake + winnings, 0 if lost
    jackpot_fixed: int = 0       # a fixed Jackpot payout...
    jackpot_share: float = 0.0   # ...or this share of the progressive pool


def bonus(cards, fortune_bet: int, jackpot_bet: int) -> Bonus:
    """What the Fortune and Jackpot bets win off these seven cards."""
    b = Bonus(classify_seven_card_bonus(cards))
    if b.tier is None:
        return b
    if fortune_bet > 0:
        b.fortune_return = fortune_bet * (FORTUNE_MULTIPLIERS[b.tier] + 1)
    if jackpot_bet > 0 and b.tier in JACKPOT_TIERS:
        fixed, share = JACKPOT_TIERS[b.tier]
        b.jackpot_fixed, b.jackpot_share = (fixed or 0), (share or 0.0)
    return b


# ---------------------------------------------------------------------- House Way
def _sorted_desc(cards) -> list:
    return sorted(cards, key=_rank_value, reverse=True)


def _remove(cards, to_remove) -> list:
    remaining = list(cards)
    for c in to_remove:
        remaining.remove(c)
    return remaining


def _groups(seven_cards) -> list[list]:
    """Same-rank groups of two or more (pairs, trips, quads), biggest first.
    The Joker joins the Aces when there's a real Ace for it to pair with --
    its only pairing role (the v2 bug: it was always left out). Real cards
    lead each group, so g[0] always has a real rank."""
    by_rank: dict[int, list] = {}
    joker = None
    for c in seven_cards:
        if c.is_joker:
            joker = c
        else:
            by_rank.setdefault(c.value, []).append(c)
    if joker is not None and 14 in by_rank:
        by_rank[14].append(joker)
    groups = [g for g in by_rank.values() if len(g) >= 2]
    groups.sort(key=lambda g: (len(g), g[0].value), reverse=True)
    return groups


def _best_pair_from(cards) -> list | None:
    by_rank: dict[int, list] = {}
    joker = None
    for c in cards:
        if c.is_joker:
            joker = c
        else:
            by_rank.setdefault(c.value, []).append(c)
    candidates = [(rank, g[:2]) for rank, g in by_rank.items() if len(g) >= 2]
    if joker is not None and by_rank.get(14):
        candidates.append((14, [joker, by_rank[14][0]]))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _search_two_front_leaving_made_hand(seven_cards, min_back_rank):
    best, best_front = None, None
    for idx in combinations(range(7), 2):
        front = [seven_cards[i] for i in idx]
        back = [seven_cards[i] for i in range(7) if i not in idx]
        if evaluate_five(back)[0] < min_back_rank:
            continue
        ev = evaluate_two_card_hand(front)
        if best_front is None or compare_hands(ev, best_front) > 0:
            best, best_front = (front, back), ev
    return best


def _set_four_of_a_kind(seven_cards, quad):
    quad_rank = quad[0].value
    rest = _sorted_desc(_remove(seven_cards, quad))

    def split():
        return quad[:2], quad[2:] + rest

    if quad_rank >= 12:  # A, K, Q: back if at least a pair up front, else split
        pair = _best_pair_from(rest)
        if pair:
            return pair, quad + _remove(rest, pair)
        return split()
    if quad_rank >= 9:
        threshold = 13
    elif quad_rank >= 6:
        threshold = 12
    else:  # 5s and below: never split
        return rest[:2], quad + rest[2:]
    if rest and _rank_value(rest[0]) >= threshold:
        return rest[:2], quad + rest[2:]
    return split()


def _set_two_trips(seven_cards, trips):
    high, low = sorted(trips, key=lambda g: g[0].value, reverse=True)
    kicker = _remove(seven_cards, high + low)
    return high[:2], [high[2]] + low + kicker


def _set_three_pairs(seven_cards, pairs):
    pairs = sorted(pairs, key=lambda g: g[0].value, reverse=True)
    others = pairs[1] + pairs[2]
    return pairs[0], others + _remove(seven_cards, pairs[0] + others)


def _set_full_house(seven_cards, trip, pair):
    return pair, trip + _remove(seven_cards, trip + pair)


def _set_three_of_a_kind(seven_cards, trip):
    rest = _remove(seven_cards, trip)
    for tc in trip:
        back = [tc] + rest
        if evaluate_five(back)[0] >= FIVE_CARD_STRAIGHT:
            return [c for c in trip if c is not tc], back
    rest_sorted = _sorted_desc(rest)
    if trip[0].value == 14:  # Aces: an Ace and the next highest card in front
        ace = trip[0]
        return [ace, rest_sorted[0]], [c for c in trip if c is not ace] + rest_sorted[1:]
    return rest_sorted[:2], trip + rest_sorted[2:]


def _set_two_pairs(seven_cards, pairs):
    big, small = sorted(pairs, key=lambda g: g[0].value, reverse=True)
    big_rank = big[0].value
    rest = _sorted_desc(_remove(seven_cards, big + small))

    def split():
        return small, big + rest

    def both_back_if(qualifies):
        if rest and qualifies(rest[0]):
            return rest[:2], big + small + rest[2:]
        return split()

    if big_rank >= 12:
        return split()
    if big_rank >= 9:
        return both_back_if(lambda c: c.is_joker or c.value == 14)
    if big_rank >= 6:
        return both_back_if(lambda c: _rank_value(c) >= 13)
    return both_back_if(lambda c: _rank_value(c) >= 12)


def _set_one_pair(seven_cards, pair):
    found = _search_two_front_leaving_made_hand(seven_cards, FIVE_CARD_STRAIGHT)
    if found:
        return found
    rest_sorted = _sorted_desc(_remove(seven_cards, pair))
    return rest_sorted[:2], pair + rest_sorted[2:]


def _set_no_pair(seven_cards):
    found = _search_two_front_leaving_made_hand(seven_cards, FIVE_CARD_STRAIGHT)
    if found:
        return found
    desc = _sorted_desc(seven_cards)
    return desc[1:3], [desc[0]] + desc[3:]


def _house_way_set_by_chart(seven_cards):
    joker = next((c for c in seven_cards if c.is_joker), None)
    if joker is not None:
        aces = [c for c in seven_cards if not c.is_joker and c.rank == "A"]
        if len(aces) == 4:  # Five Aces: a pair of Aces in front
            return aces[:2], aces[2:] + [joker] + _remove(seven_cards, aces + [joker])
    groups = _groups(seven_cards)
    if groups and len(groups[0]) == 4:
        return _set_four_of_a_kind(seven_cards, groups[0])
    trips = [g for g in groups if len(g) == 3]
    if len(trips) == 2:
        return _set_two_trips(seven_cards, trips)
    pairs = [g for g in groups if len(g) == 2]
    if len(pairs) == 3 and not trips:
        return _set_three_pairs(seven_cards, pairs)
    if len(trips) == 1 and len(pairs) == 1:
        return _set_full_house(seven_cards, trips[0], pairs[0])
    if len(trips) == 1:
        return _set_three_of_a_kind(seven_cards, trips[0])
    if len(pairs) == 2:
        return _set_two_pairs(seven_cards, pairs)
    if len(pairs) == 1:
        return _set_one_pair(seven_cards, pairs[0])
    return _set_no_pair(seven_cards)


def _strongest_valid_split(seven_cards):
    best, best_front = None, None
    for idx in combinations(range(7), 2):
        front = [seven_cards[i] for i in idx]
        back = [seven_cards[i] for i in range(7) if i not in idx]
        if is_foul(front, back):
            continue
        ev = evaluate_two_card_hand(front)
        if best_front is None or compare_hands(ev, best_front) > 0:
            best, best_front = (front, back), ev
    return best


def house_way_set(seven_cards) -> tuple[list, list]:
    """(front 2, back 5) by the House Way chart, with a safety net: if the
    chart's pick would foul, the strongest split that doesn't."""
    if len(seven_cards) != 7:
        raise ValueError("Pai Gow deals exactly 7 cards to a hand.")
    front, back = _house_way_set_by_chart(seven_cards)
    if not is_foul(front, back):
        return front, back
    return _strongest_valid_split(seven_cards)


def is_ace_high_pai_gow(seven_cards) -> bool:
    """The lowest hand in the game: nothing anywhere in the seven cards -- no
    pair (a Joker with an Ace IS a pair of Aces), straight or flush -- with an
    Ace (or the Joker, playing as one) the highest card. Judged on all seven
    cards, not on how they were set."""
    best, _ = best_five_of_seven(seven_cards)
    return best[0] == FIVE_CARD_HIGH_CARD and best[2][0] == 14


# ---------------------------------------------------------------------- settling
@dataclass
class AnteResult:
    outcome: str          # win | push | lose
    returned: int         # pence back on the Ante
    commission: int = 0
    front_win: bool = False
    back_win: bool = False


def settle_ante(front, back, dealer_front, dealer_back, ante: int, commission: bool) -> AnteResult:
    """Front plays front, back plays back; a copy goes to the dealer. Win both
    pays 1:1 (less 5% at Fortune Pai Gow), one each pushes, lose both loses."""
    front_win = compare_hands(evaluate_two_card_hand(front), evaluate_two_card_hand(dealer_front)) > 0
    back_win = compare_hands(evaluate_five(back), evaluate_five(dealer_back)) > 0
    if front_win and back_win:
        fee = ante * COMMISSION_PERCENT // 100 if commission else 0
        return AnteResult("win", ante * 2 - fee, fee, True, True)
    if not front_win and not back_win:
        return AnteResult("lose", 0, 0, False, False)
    return AnteResult("push", ante, 0, front_win, back_win)



def best_set_against(seven_cards, dealer_front, dealer_back) -> tuple[str, list, list]:
    """Face Up Pai Gow, where the dealer's set hand is on show: the best way
    to set these seven against it -- (outcome, front, back). A winning split if
    there is one, else a push, else "lose" (with the House Way set). The House
    Way set is kept whenever it does as well as the best."""
    house = house_way_set(seven_cards)
    found = {settle_ante(*house, dealer_front, dealer_back, 1, False).outcome: house}
    for idx in combinations(range(7), 2):
        if "win" in found:
            break
        front = [seven_cards[i] for i in idx]
        back = [seven_cards[i] for i in range(7) if i not in idx]
        if not is_foul(front, back):
            found.setdefault(settle_ante(front, back, dealer_front, dealer_back, 1, False).outcome, (front, back))
    outcome = next(o for o in ("win", "push", "lose") if o in found)
    return (outcome, *found[outcome])

# ---------------------------------------------------------------------- paytable
def rules(game: str) -> dict:
    notes = [
        "53 cards: the Joker completes a Straight or Flush, or plays as an Ace.",
        "Set a 2-card Low hand and a 5-card High hand; the High hand must beat the Low hand.",
        "Win both hands: Ante pays 1 to 1. Win one: push. Ties go to the dealer.",
        "The dealer sets by House Way.",
    ]
    if game == FORTUNE:
        notes.insert(3, "A winning Ante pays less 5% commission.")
    else:
        notes.insert(3, "No commission. The dealer's hand is set face up first; you may fold (every bet is lost).")
        notes.append("A dealer Ace-high Pai Gow pushes every Ante.")
    notes.append("Envy Bonus: with £5+ on Fortune, you're paid when another player hits Four of a Kind or better.")
    sections = [
        {"title": "Fortune", "rows": [[TIER_NAMES[t], f"{m:,} to 1"] for t, m in FORTUNE_MULTIPLIERS.items()]},
        {"title": "Jackpot (£1)", "rows": [[TIER_NAMES[t], f"{int(share * 100)}% of the Jackpot" if share
                                            else f"£{fixed // 100:,}"] for t, (fixed, share) in JACKPOT_TIERS.items()]},
    ]
    sections.append({"title": "Envy Bonus", "rows": [[TIER_NAMES[t], f"£{v // 100:,}"] for t, v in ENVY_BONUS.items()]})
    return {"game": game, "title": LABELS[game], "sections": sections, "notes": notes}
