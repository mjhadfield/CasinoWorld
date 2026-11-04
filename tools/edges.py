#!/usr/bin/env python3
"""
Work out casino_server/edges.json: the house edge and spread of every bet spot (casino_server/edges.py says what's in
it and how the Tracker uses it). Run it from server/ after changing a paytable, a strategy or a slot's maths, or
building a slot, then commit the file:

    .venv/bin/python ../tools/edges.py                 every game and slot (about 45 minutes)
    .venv/bin/python ../tools/edges.py craps roulette  just those (the rest of the file is kept)
    .venv/bin/python ../tools/edges.py --rounds 50000  shorter simulations (the main lines' figures wobble more)

How each figure is found:
  exact       Roulette (1/37, La Partage), Craps (each bet's edge per decision: engines/craps.py EDGES and the line
              bets), the Blackjack Insurance bet
  enumerated  every hand counted off the engines' own paytables: Baccarat (every coup from a full 8-deck shoe), the
              3-card bets (Pair Plus, Prime, the Three Card Poker Jackpot, Let It Ride's 3 Card Bonus, Mississippi
              Stud's Bonus), Blackjack's side bets (from the 8-deck shoe), every 5-card bet (Let It Ride's Bonus and
              Jackpot, the Hold'em Jackpot), High Card Flush's Flush, Straight Flush and Jackpot (every 7-card
              suit pattern), and the pool tiers of Mississippi Stud's and Pai Gow's Jackpots
  simulated   each decision game's main line on its real table machine with the NPCs' optimal strategy (no slips, no
              Gambler's flourishes), with the side bets no simple count covers (Trips, Fortune, the fixed tiers of
              the Mississippi and Pai Gow Jackpots). Mississippi Stud's and Hold'em's main lines swing too much for that, so
              they're played straight off the engine for millions of rounds (fast_main). `n` is the rounds, `se` the
              edge's standard error.
  slots       1 - RTP for each machine, from slots/sim.expected_rtp (and its Buy Bonus from simulate_buy)
"""
import argparse
import itertools
import json
import math
import sys
import time
from collections import Counter, defaultdict
from fractions import Fraction
from math import comb
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1] / "server"
sys.path.insert(0, str(SERVER))

from casino_server import edges as edges_mod   # noqa: E402
from casino_server.engines import baccarat as bac   # noqa: E402
from casino_server.engines import blackjack as bj   # noqa: E402
from casino_server.engines import craps as cr   # noqa: E402
from casino_server.engines import high_card_flush as hcf   # noqa: E402
from casino_server.engines import let_it_ride as lir   # noqa: E402
from casino_server.engines import mississippi_stud as ms   # noqa: E402
from casino_server.engines import pai_gow as pg   # noqa: E402
from casino_server.engines import roulette as rou   # noqa: E402
from casino_server.engines import three_card_poker as tcp   # noqa: E402
from casino_server.engines import ultimate_texas_holdem as uth   # noqa: E402
from casino_server.engines.cards import RANK_ORDER, Card, Suit   # noqa: E402
from casino_server.engines.hand_evaluator import evaluate_five_card_hand, evaluate_three_card_hand   # noqa: E402

DECK = [Card(r, s) for s in Suit for r in RANK_ORDER]
ROUNDS = 300_000


# ---------------------------------------------------------------------- helpers
def spot(edge, sd, line, source, **extra) -> dict:
    out = {"edge": round(float(edge), 7), "sd": round(float(sd), 5), "line": line, "source": source}
    out.update({k: (round(v, 7) if isinstance(v, float) else v) for k, v in extra.items()})
    return out


def from_returns(dist) -> tuple[float, float]:
    """(edge, sd) of a bet from {return per unit staked (stake included): probability}."""
    mean = sum(p * r for r, p in dist.items())
    second = sum(p * (r - 1) ** 2 for r, p in dist.items())
    return 1 - mean, math.sqrt(max(0.0, second - (mean - 1) ** 2))


def pool(dist_fixed: dict, dist_share: dict, bet: int, source: str, line: str = "jackpot", **extra) -> dict:
    """A progressive Jackpot spot: {fixed pence: probability} and {share of the pool: probability} (misses left out).
    `edge`/`sd` are with an empty pool, for reference; the Tracker works the EV out from the pool at the time."""
    fixed = sum(p * v for v, p in dist_fixed.items())
    fixed2 = sum(p * v * v for v, p in dist_fixed.items())
    share = sum(p * s for s, p in dist_share.items())
    share2 = sum(p * s * s for s, p in dist_share.items())
    edge = 1 - fixed / bet
    sd = math.sqrt(max(0.0, fixed2 - fixed * fixed)) / bet
    return {**spot(edge, sd, line, source, **extra),
            "pool": {"bet": bet, "fixed": round(fixed, 6), "fixed2": round(fixed2, 4), "share": share, "share2": share2}}


def combos(n_cards: int):
    return itertools.combinations(DECK, n_cards)


# ---------------------------------------------------------------------- Roulette (exact)
ROULETTE_LINES = {1: "straight", 2: "split", 3: "street", 4: "corner", 6: "line", 12: "dozen_column", 18: "even"}


def roulette() -> dict:
    out = {}
    for sid, bet in rou.BETS.items():
        n = len(bet.numbers)
        dist = {bet.pays + 1: Fraction(n, 37)}
        if bet.even_money:
            dist[Fraction(1, 2)] = Fraction(1, 37)    # La Partage: half back on zero
            dist[0] = 1 - Fraction(n + 1, 37)
        else:
            dist[0] = 1 - Fraction(n, 37)
        e, sd = from_returns(dist)
        line = "first_four" if sid == "ff" else "trio" if sid.startswith("tr_") else ROULETTE_LINES[n]
        out[sid] = spot(e, sd, line, "exact")
    return {"spots": out, "lines": {"straight": "Straight up", "split": "Splits", "street": "Streets", "trio": "Trios",
                                    "corner": "Corners", "first_four": "First four", "line": "Six lines",
                                    "dozen_column": "Dozens and columns", "even": "Even chances"}}


# ---------------------------------------------------------------------- Craps (exact, per decision)
ROLLS = list(itertools.product(range(1, 7), repeat=2))


def _decision(spot_id: str, point, stake: int) -> tuple[Fraction, Fraction]:
    """(mean, second moment) of the bettor's net per unit staked, per decision (rolling until something happens).
    A Lay bet's vig, paid up front, is lost with it."""
    total = second = decided = Fraction(0)
    carried = cr.vig_up_front({spot_id: stake})
    for d1, d2 in ROLLS:
        o = cr.resolve({spot_id: stake}, d1, d2, point, True).get(spot_id)
        if o is None:
            continue
        decided += Fraction(1, 36)
        net = Fraction(o.win if o.kind == "win" else -stake - carried if o.kind == "lose" else 0, stake)
        total += Fraction(1, 36) * net
        second += Fraction(1, 36) * net * net
    return total / decided, second / decided


def _line(spot_id: str) -> tuple[Fraction, Fraction]:
    """A Pass or Don't Pass (Come, Don't Come) bet from the come-out to its decision, a bar-12 push counting as one."""
    mean = second = Fraction(0)
    for d1, d2 in ROLLS:
        t = d1 + d2
        o = cr.resolve({spot_id: 6000}, d1, d2, None).get(spot_id)
        if o is None and t in cr.NUMBERS:
            m, s2 = _decision(spot_id, t, 6000)
            mean += Fraction(1, 36) * m
            second += Fraction(1, 36) * s2
        elif o is not None:
            net = Fraction(o.win if o.kind == "win" else -6000, 6000)
            mean += Fraction(1, 36) * net
            second += Fraction(1, 36) * net * net
    return mean, second


CRAPS_LINES = {"pass": "Pass line", "dont_pass": "Don't pass", "come": "Come", "dont_come": "Don't come",
               "odds": "Odds", "place": "Place bets", "buy": "Buy bets", "lay": "Lay bets", "field": "Field",
               "big": "Big 6 and 8", "hardways": "Hardways", "props": "One-roll bets", "other": "Other"}


def craps() -> dict:
    out = {}
    for s in ("pass", "dont_pass"):
        m, s2 = _line(s)
        sd = math.sqrt(s2 - m * m)
        out[s] = spot(-m, sd, s, "exact")
        twin = "come" if s == "pass" else "dont_come"
        out[twin] = spot(-m, sd, twin, "exact")
    for s in cr.SPOTS:
        if s in out:
            continue
        n = cr.number_of(s)
        if "odds" in s:
            stake = 6000 if s.startswith(("pass", "come")) else 6000 * 6
            m, s2 = _decision(s, n or 4, stake) if not s.startswith(("pass_odds", "dont_odds")) else _decision(s, 4, stake)
            out[s] = spot(0.0, math.sqrt(s2 - m * m), "odds", "exact")
            continue
        if cr.is_travelled(s):   # come_6, dcome_8: a Come bet that's travelled (charged when it went down)
            out[s] = spot(0.0, 1.0, "come" if s.startswith("come") else "dont_come", "exact")
            continue
        stake = {4: 12_000, 10: 12_000, 5: 9000, 9: 9000, 6: 7200, 8: 7200}[n] if s.startswith("lay_") else 6000
        m, s2 = _decision(s, 4 if n != 4 else 5, stake)
        assert -m == cr.EDGES[s], (s, -m, cr.EDGES[s])
        line = ("place" if s.startswith("place_") else "buy" if s.startswith("buy_") else "lay" if s.startswith("lay_")
                else "field" if s == "field" else "big" if s.startswith("big") else "hardways" if s in cr.HARDWAYS
                else "props")
        out[s] = spot(-m, math.sqrt(s2 - m * m), line, "exact")
    return {"spots": out, "lines": CRAPS_LINES}


# ---------------------------------------------------------------------- Baccarat (every coup from a full shoe)
def baccarat() -> dict:
    decks = 8
    counts = [16 * decks] + [4 * decks] * 9     # point value 0 (tens, pictures) and 1-9
    total = sum(counts)
    rank_of = {0: "10", 1: "A", **{v: str(v) for v in range(2, 10)}}
    cards = {v: Card(rank_of[v], Suit.SPADES) for v in range(10)}
    unit = 100
    bets = {s: unit for s in bac.MAIN_SPOTS + bac.DRAGON_SPOTS}
    sums = defaultdict(Counter)   # spot -> {return: weight}

    def draw(left, n_left, v):
        return left[v] / n_left

    def finish(seq, prob):
        player = [cards[seq[0]], cards[seq[2]]]
        banker = [cards[seq[1]], cards[seq[3]]]
        coup = bac.Coup(player, banker, bac.total(player) in (8, 9), bac.total(banker) in (8, 9))
        rest = list(seq[4:])
        if not (coup.player_natural or coup.banker_natural):
            p0, b0 = bac.total(player), bac.total(banker)
            third = None
            if p0 <= 5:
                third = cards[rest.pop(0)]
                player.append(third)
            if (b0 <= 5) if third is None else bac.points(third) in bac.BANKER_DRAWS[b0]:
                banker.append(cards[rest.pop(0)])
        r = bac.settle(coup, bets)
        for s in bets:
            sums[s][r[s]] += prob

    def needs(seq) -> int:
        """How many more cards the coup takes after `seq` (0: it's complete)."""
        if len(seq) < 4:
            return 4 - len(seq)
        p0, b0 = (seq[0] + seq[2]) % 10, (seq[1] + seq[3]) % 10
        if p0 >= 8 or b0 >= 8:
            return 0
        if p0 <= 5:
            if len(seq) == 4:
                return 1
            third = seq[4]
            if third in bac.BANKER_DRAWS[b0]:
                return 1 if len(seq) == 5 else 0
            return 0
        return (1 if b0 <= 5 else 0) if len(seq) == 4 else 0

    def walk(seq, left, n_left, prob):
        if needs(seq) == 0:
            finish(seq, prob)
            return
        for v in range(10):
            if left[v]:
                p = prob * left[v] / n_left
                left[v] -= 1
                walk(seq + (v,), left, n_left - 1, p)
                left[v] += 1

    walk((), counts[:], total, 1.0)
    out = {}
    for s in bets:
        e, sd = from_returns({r / unit: p for r, p in sums[s].items()})
        out[s] = spot(e, sd, s, "enumerated")
    return {"spots": out, "lines": {"player": "Player", "banker": "Banker", "tie": "Tie",
                                    "player_dragon": "Player Dragon", "banker_dragon": "Banker Dragon"}}


# ---------------------------------------------------------------------- the card bets counted hand by hand
def three_card_bets() -> dict:
    """Three Card Poker's Pair Plus, Prime and Jackpot; Let It Ride's 3 Card Bonus; Mississippi Stud's Bonus."""
    n = comb(52, 3)
    pair_plus, prime, three, bonus = Counter(), Counter(), Counter(), Counter()
    fixed, share = Counter(), Counter()
    # Prime: the player's three one colour pays 3:1, all six with the dealer's 4:1
    six = comb(23, 3) / comb(49, 3)
    for hand in combos(3):
        ev = evaluate_three_card_hand(list(hand))
        m = tcp.PAIR_PLUS_MULTIPLIERS.get(ev[1], 0)
        pair_plus[m + 1 if m else 0] += 1
        if len({c.color for c in hand}) == 1:
            prime[tcp.PRIME_SAME_COLOUR_6_MULTIPLIER + 1] += six
            prime[tcp.PRIME_SAME_COLOUR_3_MULTIPLIER + 1] += 1 - six
        else:
            prime[0] += 1
        pay, hits = tcp.jackpot_payout(ev, list(hand), 0)
        if hits:
            share[1.0] += 1
        elif pay:
            fixed[pay] += 1
        t = lir.THREE_CARD_PAYS.get(lir.three_card_tier(ev), 0)
        three[t + 1 if t else 0] += 1
        b = ms.bonus_multiplier(ev)
        bonus[b + 1 if b else 0] += 1
    norm = lambda c: {k: v / n for k, v in c.items()}
    out = {}
    for name, c in (("pair_plus", pair_plus), ("prime", prime), ("three_card", three), ("bonus", bonus)):
        out[name] = from_returns(norm(c))
    out["tcp_jackpot"] = pool(norm(fixed), norm(share), tcp.JACKPOT_BET, "enumerated")
    return out


def five_card_bets() -> dict:
    """Every 5-card hand: Let It Ride's Bonus and Jackpot, Hold'em's Jackpot (on the hole cards and flop), and the
    hands that pay the Mississippi Stud Jackpot from the pool (played out to see how often the strategy gets there)."""
    n = comb(52, 5)
    lir_bonus, lir_fixed, lir_share = Counter(), Counter(), Counter()
    uth_fixed, uth_share = Counter(), Counter()
    ms_pool = []
    for hand in combos(5):
        ev = evaluate_five_card_hand(hand)
        tier = lir.five_card_tier(ev)
        b = lir.BONUS_PAYS.get(tier, 0)
        lir_bonus[b + 1 if b else 0] += 1
        f, s = lir.jackpot_payout(tier)
        if s:
            lir_share[s] += 1
        elif f:
            lir_fixed[f] += 1
        f, s = uth.jackpot_payout(ev)
        if s:
            uth_share[s] += 1
        elif f:
            uth_fixed[f] += 1
        f, s = ms.jackpot_payout(ev)
        if s:
            ms_pool.append((hand, s))
    norm = lambda c: {k: v / n for k, v in c.items()}
    # Mississippi Stud: each order the five could come out in (which two are the hole cards, then the streets), with the
    # strategy's choice on each street; a fold loses the Jackpot.
    ms_share = Counter()
    for hand, s in ms_pool:
        played = orders = 0
        for hole in itertools.combinations(hand, 2):
            rest = [c for c in hand if c not in hole]
            for community in itertools.permutations(rest):
                orders += 1
                raised = False
                ok = True
                for street in range(3):
                    r = ms.strategy(list(hole) + list(community[:street]), raised)
                    if r == 0:
                        ok = False
                        break
                    raised = raised or r == 3
                played += ok
        ms_share[s] += played / orders
    return {"lir_bonus": from_returns(norm(lir_bonus)),
            "lir_jackpot": pool(norm(lir_fixed), norm(lir_share), lir.JACKPOT_BET, "enumerated"),
            "uth_jackpot": pool(norm(uth_fixed), norm(uth_share), uth.JACKPOT_BET, "enumerated"),
            "ms_pool": {k: v / n for k, v in ms_share.items()}}


def blackjack_sides() -> dict:
    """Blackjack's side bets on the first two cards and the dealer's up-card, from a full 8-deck shoe."""
    d = bj.DECK_COUNT
    n = 52 * d
    types = DECK
    unit = 100
    sums = defaultdict(Counter)
    fixed, share = Counter(), Counter()
    bets = {"super_pairs": unit, "twenty_one_plus_three": unit, "top_three": unit, "jackpot": bj.JACKPOT_BET}
    for i, a in enumerate(types):
        for j, b in enumerate(types):
            for k, u in enumerate(types):
                w = d * (d - (i == j)) * (d - (k == i) - (k == j))
                if w <= 0:
                    continue
                p = w / (n * (n - 1) * (n - 2))
                r = bj.side_bet_returns([a, b], u, bets)
                for s in ("super_pairs", "twenty_one_plus_three", "top_three"):
                    sums[s][r.returns.get(s, 0) / unit] += p
                jp = r.returns.get("jackpot", 0)
                if r.hits_pool:
                    share[1.0] += p
                elif jp:
                    fixed[jp] += p
    out = {s: from_returns(sums[s]) for s in ("super_pairs", "twenty_one_plus_three", "top_three")}
    out["jackpot"] = pool(fixed, share, bj.JACKPOT_BET, "enumerated")
    ten = 16 * d
    q = ten / (n - 1)   # the hole card's a ten (dealer's Ace up; nothing else seen)
    out["insurance"] = from_returns({1 + bj.INSURANCE_MULTIPLIER: q, 0: 1 - q})
    return out


def high_card_flush_bets() -> dict:
    """The Flush, Straight Flush and Jackpot bets on seven cards: every way they fall into suits, and in each suit
    every set of ranks, for the longest flush and the longest straight flush (an Ace high or low)."""
    def longest(ranks) -> int:
        vals = set(ranks)
        if 14 in vals:
            vals.add(1)
        best = run = 0
        for v in range(1, 15):
            run = run + 1 if v in vals else 0
            best = max(best, run)
        return best
    runs = {k: Counter(longest(rs) for rs in itertools.combinations(range(2, 15), k)) for k in range(8)}
    total = comb(52, 7)
    flush, sfd, jfix, jshare = Counter(), Counter(), Counter(), Counter()
    for split in itertools.product(range(8), repeat=4):
        if sum(split) != 7:
            continue
        ways = math.prod(comb(13, k) for k in split)
        length = max(split)
        # P(longest run across the suits <= L) is the product over suits
        cdf = []
        for L in range(8):
            p = 1.0
            for k in split:
                p *= sum(c for r, c in runs[k].items() if r <= L) / comb(13, k)
            cdf.append(p)
        for L in range(8):
            pL = cdf[L] - (cdf[L - 1] if L else 0.0)
            if pL <= 0:
                continue
            w = ways * pL / total
            m = hcf.STRAIGHT_FLUSH_PAYS.get(L, 0)
            sfd[m + 1 if m else 0] += w
            s = hcf.JACKPOT_SHARES.get(L, 0.0) if L >= 6 else 0.0
            if s:
                jshare[s] += w
            elif hcf.JACKPOT_FIXED.get(L):
                jfix[hcf.JACKPOT_FIXED[L]] += w
        m = hcf.FLUSH_PAYS.get(length, 0)
        flush[m + 1 if m else 0] += ways / total
    return {"flush": from_returns(flush), "straight_flush": from_returns(sfd),
            "jackpot": pool(jfix, jshare, hcf.JACKPOT_BET, "enumerated")}


def pai_gow_pool_tiers() -> dict:
    """The Pai Gow Jackpot's pool tiers, counted from the 53-card deck: a 7-card straight flush (no Joker), a Royal
    Flush with a Royal Match (K-Q suited), and a 7-card straight flush with the Joker."""
    total = comb(53, 7)
    windows = [set(range(lo, lo + 7)) for lo in range(1, 9)]   # 1 = an Ace low ... 8-14
    sf7 = 4 * len(windows)
    joker_sf = 0
    for ranks in itertools.combinations(range(2, 15), 6):
        r = set(ranks)
        low = {1 if v == 14 else v for v in r}
        if any(r <= w or low <= w for w in windows):
            joker_sf += 4
    royal_match = 4 * 3   # the royal's suit, then the K-Q's
    return {1.0: sf7 / total, 0.5: royal_match / total, 0.25: joker_sf / total}


# ---------------------------------------------------------------------- the main lines, played on the machines
class Sim:
    """A seat at a table with bottomless pockets, noting what goes on and comes off each spot in each round."""
    is_human = False
    entity_id = "sim"
    name = "Sim"
    here = True
    game = ""
    tracker = None

    def __init__(self):
        self.round = defaultdict(lambda: [0, 0])   # spot -> [staked, returned], this round

    @property
    def balance(self):
        return 10 ** 12

    def debit(self, amount, note, detail=None):
        for s, v in (detail or {}).get("spots", {}).items():
            self.round[s][0] += v
        return True

    def credit(self, amount, note, detail=None):
        for s, d in (detail or {}).get("spots", {}).items():
            self.round[s][1] += d["returned"]

    def refund(self, amount, note):
        pass

    def place(self, *a):
        pass


class NoPool:
    """The progressive's pool, empty: a Jackpot bet's fixed prizes only (its pool tiers are counted separately)."""
    amount = 0

    def take(self, share):
        return 0

    def win(self):
        return 0

    def snapshot(self):
        return {"type": "jackpot", "amount": 0, "rate": 0.0, "ceiling": 0}


def _timings(cls):
    t = cls.instant()
    for name in t.__dataclass_fields__:
        if name in ("decide", "turn", "insurance", "setting", "claiming", "claim", "deciding"):
            setattr(t, name, 1e9)
    return t


def _decide_tcp(m, now):
    r = m.round.get(0)
    if m.phase == "deciding" and r is not None and not r.decided:
        m.decide(0, tcp.should_play(tcp.evaluate_three_card_hand(r.cards)), now)


def _decide_bj(m, now):
    box = m.round.get(0)
    if box is None:
        return
    if m.phase == "insurance" and not box.insurance_decided:
        m.insure(0, False, now)
    elif m.phase == "playing" and m.turn is not None and m.turn[0] == 0:
        hand = box.hands[m.turn[1]]
        m.play_action(0, bj.recommend(hand.cards, m.up_card, hand.can_double, hand.can_split(len(box.hands) - 1)), now)


def _decide_pai_gow(m, now):
    hand = m.round.get(0)
    if hand is None or hand.folded:
        return
    if m.phase == "claiming" and not hand.claimed:
        m.claim(0, now) if hand.bonus_name else m.fold(0, now)
    elif m.phase == "setting" and not hand.set:
        front, back = pg.house_way_set(hand.cards)
        if m.game == pg.FACE_UP:
            outcome, front, back = pg.best_set_against(hand.cards, m.dealer_front, m.dealer_back)
            b = pg.bonus(hand.cards, hand.bets["fortune"], hand.bets["jackpot"])
            if outcome == "lose" and not (b.fortune_return or b.jackpot_fixed or b.jackpot_share):
                return m.fold(0, now)
        m.set_hand(0, [c.code for c in front], [c.code for c in back], now)


def _decide_ms(m, now):
    hand = m.round.get(0)
    if m.phase == "deciding" and hand is not None and not hand.folded and not hand.decided:
        r = ms.strategy(hand.cards + m.community[:m.revealed], hand.raised_3x)
        m.play_action(0, {0: "fold", 1: "bet1", 3: "bet3"}[r], now)


def _decide_uth(m, now):
    hand = m.round.get(0)
    if m.phase == "deciding" and hand is not None and hand.waiting and not hand.decided:
        board = m.board[:m.revealed]
        stage = min(m.stage, 2)
        bet, wait = [("bet4", "check"), ("bet2", "check"), ("bet1", "fold")][stage]
        right = [uth.preflop_bet(hand.cards), uth.flop_bet(hand.cards, board) if stage == 1 else 0,
                 uth.river_bet(hand.cards, board) if stage == 2 else 0][stage]
        m.play_action(0, bet if right else wait, now)


def _decide_lir(m, now):
    hand = m.round.get(0)
    if m.phase == "deciding" and hand is not None and not hand.decided:
        seen = hand.cards + m.community[:m.revealed]
        ride = lir.ride_first(seen) if m.stage == 0 else lir.ride_second(seen)
        m.play_action(0, "ride" if ride else "pull", now)


def _decide_hcf(m, now):
    hand = m.round.get(0)
    if m.phase == "deciding" and hand is not None and not hand.decided:
        times = hcf.raise_by(hand.cards)
        m.play_action(0, f"raise{times}" if times else "fold", now)


U = 1000   # the simulated bets' unit: £10, side bets £5
MAIN = {   # game -> (bets, the main line's spots, its first wager, how a decision's made, the side bets simulated)
    tcp.GAME_KEY: ({"ante": U}, ("ante", "play", "ante_bonus"), "ante", _decide_tcp, ()),
    bj.GAME_KEY: ({"bet": U}, ("bet", "double", "split"), "bet", _decide_bj, ()),
    hcf.GAME_KEY: ({"ante": U}, ("ante", "raise"), "ante", _decide_hcf, ()),
    lir.GAME_KEY: ({"bet1": U, "bet2": U, "ante": U}, ("bet1", "bet2", "ante"), "ante", _decide_lir, ()),
    ms.GAME_KEY: ({"ante": U, "jackpot": ms.JACKPOT_BET}, ("ante", "third", "fourth", "fifth"), "ante", _decide_ms,
                  ("jackpot",)),
    uth.GAME_KEY: ({"ante": U, "trips": U // 2}, ("ante", "blind", "play"), "ante", _decide_uth, ("trips",)),
    pg.FORTUNE: ({"ante": U, "fortune": U // 2, "jackpot": pg.JACKPOT_BET}, ("ante",), "ante", _decide_pai_gow,
                 ("fortune", "jackpot")),
    pg.FACE_UP: ({"ante": U, "fortune": U // 2, "jackpot": pg.JACKPOT_BET}, ("ante",), "ante", _decide_pai_gow,
                 ("fortune", "jackpot")),
}


def simulate(game: str, rounds: int) -> dict:
    """Play `rounds` hands at a table of the game, one seat, the NPCs' strategy. Returns, per line, the mean and
    sd of its net per unit of its first wager, and per simulated side bet the same per unit staked on it; and for
    a side bet with a Jackpot, how often each fixed prize came up."""
    from casino_server.casino import MACHINES
    import importlib
    bets, line, charge, decide, sides = MAIN[game]
    cls = MACHINES[game]
    module = importlib.import_module(cls.__module__)
    m = cls(f"{game}_sim", 6, _timings(module.Timings), NoPool())
    p = Sim()
    now = 0.0
    m.sit(0, p, now)
    nets = []
    side_nets = {s: [] for s in sides}
    jackpot_hits = Counter()
    started = time.time()
    for i in range(rounds):
        p.round.clear()
        m.set_bets(0, bets, now)
        m.ready(0, now)
        for _ in range(500):
            now = max(now + 0.001, m.deadline or 0.0)
            decide(m, now)
            events = m.tick(now)
            if any(e["kind"] == "round_end" for e in events):
                break
        else:
            raise RuntimeError(f"{game}: a round didn't finish")
        stake = p.round[charge][0]
        nets.append(sum(p.round[s][1] - p.round[s][0] for s in line if s in p.round) / stake)
        for s in sides:
            st, ret = p.round[s]
            if st:
                side_nets[s].append((ret - st) / st)
                if s == "jackpot" and ret:
                    jackpot_hits[ret] += 1
        if i and i % 50_000 == 0:
            print(f"  {game}: {i:,} rounds ({time.time() - started:.0f}s)", flush=True)
    out = {"main": _mean_sd(nets), "n": rounds}
    for s, xs in side_nets.items():
        out[s] = _mean_sd(xs)
        out[s + "_n"] = len(xs)
    out["jackpot_hits"] = {k: v / max(1, len(side_nets.get("jackpot", []))) for k, v in jackpot_hits.items()}
    return out


def fast_main(game: str, rounds: int) -> tuple[float, float, float]:
    """Mississippi Stud's and Hold'em's main lines, which swing too much for the machine runs: played straight off the
    engine (deal, the NPCs' strategy as the machine runs it, settle), so millions of rounds are quick. (edge, sd, se)."""
    import random as _r
    rng = _r.Random(17)
    deck = list(DECK)
    n = total = total2 = 0.0
    for _ in range(rounds):
        rng.shuffle(deck)
        if game == ms.GAME_KEY:
            hole, community = deck[:2], deck[2:5]
            streets, raised, folded = [0, 0, 0], False, False
            for street in range(3):
                r = ms.strategy(hole + community[:street], raised)
                if r == 0:
                    folded = True
                    break
                streets[street] = r
                raised = raised or r == 3
            res = ms.settle(hole, community, ms.Bets(ante=1, streets=streets), folded)
            net = res.main_return - 1 - sum(streets)
        else:
            hole, dealer, board = deck[:2], deck[2:4], deck[4:9]
            play, folded = 0, False
            if uth.preflop_bet(hole):
                play = 4
            elif uth.flop_bet(hole, board[:3]):
                play = 2
            elif uth.river_bet(hole, board):
                play = 1
            else:
                folded = True
            res = uth.settle(hole, dealer, board, uth.Bets(ante=100, play=100 * play), folded)
            net = (res.ante_return + res.blind_return + res.play_return - 200 - 100 * play) / 100
        n += 1
        total += net
        total2 += net * net
    mean = total / n
    var = total2 / n - mean * mean
    return -mean, math.sqrt(var), math.sqrt(var / n)


FAST = {ms.GAME_KEY: 10_000_000, uth.GAME_KEY: 2_000_000}   # rounds for fast_main


def _mean_sd(xs) -> tuple[float, float, float]:
    """(edge, sd, se) from a list of nets per unit."""
    n = len(xs)
    if not n:
        return 0.0, 0.0, 0.0
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / max(1, n - 1)
    return -mean, math.sqrt(var), math.sqrt(var / n)


# ---------------------------------------------------------------------- per game
def card_games(only, rounds) -> dict:
    out = {}
    need = lambda *gs: any(g in only for g in gs)
    three = three_card_bets() if need(tcp.GAME_KEY, lir.GAME_KEY, ms.GAME_KEY) else None
    five = five_card_bets() if need(lir.GAME_KEY, uth.GAME_KEY, ms.GAME_KEY) else None

    def main_line(game, label="Main bet", extra=()):
        print(f"simulating {game} ({rounds:,} rounds)...", flush=True)
        r = simulate(game, rounds)
        e, sd, se = r["main"]
        n = rounds
        if game in FAST:   # (the machine run still gives the side bets; the main line wants far more rounds)
            n = max(rounds, FAST[game] * rounds // ROUNDS)
            print(f"  {game}: main line straight off the engine, {n:,} rounds...", flush=True)
            e, sd, se = fast_main(game, n)
        bets, line, charge, _, _ = MAIN[game]
        spots = {s: spot(e if s == charge else 0.0, sd if s == charge else 0.0, "main", "simulated",
                         **({"n": n, "se": se} if s == charge else {})) for s in line}
        for s in extra:
            spots[s] = spot(0.0, 0.0, "main", "simulated")
        return spots, r, {"main": label}

    if tcp.GAME_KEY in only:
        spots, _, lines = main_line(tcp.GAME_KEY, "Ante and Play")
        spots["pair_plus"] = spot(*three["pair_plus"], "pair_plus", "enumerated")
        spots["prime"] = spot(*three["prime"], "prime", "enumerated")
        spots["jackpot"] = three["tcp_jackpot"]
        out[tcp.GAME_KEY] = {"spots": spots, "lines": {**lines, "pair_plus": "Pair Plus", "prime": "Prime", "jackpot": "Jackpot"}}
    if bj.GAME_KEY in only:
        sides = blackjack_sides()
        spots, _, lines = main_line(bj.GAME_KEY, "Bet, doubles and splits")
        for s in ("super_pairs", "twenty_one_plus_three", "top_three"):
            spots[s] = spot(*sides[s], s, "enumerated")
        spots["jackpot"] = sides["jackpot"]
        spots["insurance"] = spot(*sides["insurance"], "insurance", "exact")
        out[bj.GAME_KEY] = {"spots": spots, "lines": {**lines, "super_pairs": "Super Pairs", "twenty_one_plus_three": "21+3",
                                                      "top_three": "Top 3", "jackpot": "Jackpot", "insurance": "Insurance"}}
    if hcf.GAME_KEY in only:
        sides = high_card_flush_bets()
        spots, _, lines = main_line(hcf.GAME_KEY, "Ante and Raise")
        spots["flush"] = spot(*sides["flush"], "flush", "enumerated")
        spots["straight_flush"] = spot(*sides["straight_flush"], "straight_flush", "enumerated")
        spots["jackpot"] = sides["jackpot"]
        out[hcf.GAME_KEY] = {"spots": spots, "lines": {**lines, "flush": "Flush", "straight_flush": "Straight Flush",
                                                       "jackpot": "Jackpot"}}
    if lir.GAME_KEY in only:
        spots, _, lines = main_line(lir.GAME_KEY, "Bets 1, 2 and $")
        spots["bonus"] = spot(*five["lir_bonus"], "bonus", "enumerated")
        spots["three_card"] = spot(*three["three_card"], "three_card", "enumerated")
        spots["jackpot"] = five["lir_jackpot"]
        out[lir.GAME_KEY] = {"spots": spots, "lines": {**lines, "bonus": "Bonus", "three_card": "3 Card Bonus",
                                                       "jackpot": "Jackpot"}}
    if ms.GAME_KEY in only:
        spots, r, lines = main_line(ms.GAME_KEY, "Ante and streets")
        spots["bonus"] = spot(*three["bonus"], "bonus", "enumerated")
        n_j = r["jackpot_n"]
        spots["jackpot"] = pool({k: v for k, v in r["jackpot_hits"].items()}, five["ms_pool"], ms.JACKPOT_BET,
                                "simulated", n=n_j)
        out[ms.GAME_KEY] = {"spots": spots, "lines": {**lines, "bonus": "3 Card Bonus", "jackpot": "Jackpot"}}
    if uth.GAME_KEY in only:
        spots, r, lines = main_line(uth.GAME_KEY, "Ante, Blind and Play")
        e, sd, se = r["trips"]
        spots["trips"] = spot(e, sd, "trips", "simulated", n=r["trips_n"], se=se)
        spots["jackpot"] = five["uth_jackpot"]
        out[uth.GAME_KEY] = {"spots": spots, "lines": {**lines, "trips": "Trips", "jackpot": "Jackpot"}}
    tiers = pai_gow_pool_tiers() if need(pg.FORTUNE, pg.FACE_UP) else None
    for game in (pg.FORTUNE, pg.FACE_UP):
        if game not in only:
            continue
        spots, r, lines = main_line(game, "Ante" + (" (less commission)" if game == pg.FORTUNE else ""))
        e, sd, se = r["fortune"]
        spots["fortune"] = spot(e, sd, "fortune", "simulated", n=r["fortune_n"], se=se)
        spots["envy"] = spot(0.0, 0.0, "fortune", "simulated")   # (paid off other players' hands: on the Fortune line)
        spots["jackpot"] = pool(r["jackpot_hits"], tiers, pg.JACKPOT_BET, "simulated", n=r["jackpot_n"])
        out[game] = {"spots": spots, "lines": {**lines, "fortune": "Fortune", "jackpot": "Jackpot"}}
    return out


def slots() -> dict:
    from casino_server import slot_builds
    from casino_server.slots import sim
    from casino_server.slots.variants import VARIANTS
    slot_builds.install()
    out = {}
    for vid, v in VARIANTS.items():
        print(f"slots: {vid}...", flush=True)
        r = sim.expected_rtp(v)
        entry = {"name": v.name, "edge": round(1 - r["total"] / 100, 6), "rtp": round(r["total"], 3),
                 "sd": round(_spin_sd(v), 3), "source": "slots"}
        if v.buy_cost and v.routes.get("buy"):
            b = sim.simulate_buy(v, 50_000)
            entry["buy_edge"] = round(1 - b["rtp"] / 100, 6)
            entry["buy_sd"] = round(entry["sd"] / math.sqrt(v.buy_cost), 3)
        out[vid] = entry
    return out


def _spin_sd(v, spins: int = 100_000) -> float:
    """The spread of one spin's return, per unit bet (bonuses played out), from a run of spins."""
    from casino_server.slots import sim
    from casino_server.slots.outcome import spin_outcome
    rng = sim.mulberry32(5)
    total = total2 = 0.0
    for _ in range(spins):
        o = spin_outcome(v, 100, rng)
        won = o["total"]
        if o["trigger"] == "trail":
            st = sim.trail_start(v, 100, rng)
            sim.trail_play_out(v, st, rng)
            won += st["total"]
        elif o["trigger"] == "free":
            won += sum(g["total"] for g in sim.free_games(v, 100, rng, v.free_games))
        elif o["trigger"] == "battle":
            won += sim.battle_value(v, 100, rng)
        elif o["trigger"] == "voyage":
            won += sim.voyage_value(v, 100, rng)
        elif o["trigger"] == "expedition":
            won += sim.expedition_value(v, 100, rng)
        x = won / 100
        total += x
        total2 += x * x
    mean = total / spins
    return math.sqrt(max(0.0, total2 / spins - mean * mean))


EXACT = {"roulette": roulette, "craps": craps, "baccarat": baccarat}
CARD_GAMES = (tcp.GAME_KEY, bj.GAME_KEY, hcf.GAME_KEY, lir.GAME_KEY, ms.GAME_KEY, uth.GAME_KEY, pg.FORTUNE, pg.FACE_UP)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("games", nargs="*", help="only these (game keys, or 'slots'); default every one")
    ap.add_argument("--rounds", type=int, default=ROUNDS, help=f"simulated rounds per game (default {ROUNDS:,})")
    args = ap.parse_args()
    only = set(args.games) or set(EXACT) | set(CARD_GAMES) | {"slots"}
    path = edges_mod.PATH
    data = json.loads(path.read_text()) if path.exists() else {}
    games = data.setdefault("games", {})
    for g, fn in EXACT.items():
        if g in only:
            print(f"{g}...", flush=True)
            games[g] = fn()
    games.update(card_games(only & set(CARD_GAMES), args.rounds))
    if "slots" in only:
        data["slots"] = slots()
    data["made"] = time.strftime("%Y-%m-%d")
    data["about"] = "Made by tools/edges.py (see casino_server/edges.py). Don't edit by hand."
    path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
