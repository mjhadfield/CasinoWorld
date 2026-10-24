@tool
class_name BlackjackTable
extends CasinoTable
## A Blackjack table: everything shared with the other games comes from
## CasinoTable; this adds the layout and the round. Cards come one at a time
## out of the 8-deck shoe -- a card to every box, the dealer's up-card, a
## second card each, the hole card face down -- then the side bets settle
## (winnings stay beside their spots until the hand's over), insurance and the
## dealer's peek if there's an Ace or a 10 showing, Blackjacks paid at once,
## each box plays in turn (Hit, Stand, Double, Split; a bust is swept at once),
## the dealer draws to 17, and each box is settled from third base.
## The discards pile up in the rack until the cut card comes out; then they
## and the rest of the shoe go through the shuffler and a new shoe goes in.
##
## Each seat, top to bottom: the Jackpot disc and Top 3, Super Pairs and 21+3,
## the Blackjack betting circle (insurance goes beside it), then the cards.

const TOP_Y := -78.5      # the Jackpot disc and Top 3
const SIDE_Y := -61.5     # Super Pairs and 21+3: 2 below the top row, so no spot touches another
const BET_Y := -44.0      # the betting circle
const SPLIT_BET_Y := -47.0   # each hand's bet once a box has split, leaving room for its total below
const CARD_Y := -19.0     # first card of a hand
const SPLIT_CARD_Y := -25.0  # first card of each hand once a box has split
const LAST_CARD_Y := -17.0   # no card sits lower: its bottom stays 2 inside the front border
const BET_R := 10.5
const SPOTS := ["bet", "super_pairs", "twenty_one_plus_three", "top_three", "jackpot"]
const SIDE_SPOTS := ["super_pairs", "twenty_one_plus_three", "top_three", "jackpot"]
const ACTION_KEYS := {"hit": "Space", "stand": "Backspace", "double": "D", "split": "P"}   # Space plays on, Backspace stops, at every table
const FLANK := {"split": "left", "double": "right"}

var _hands := {}          # seat -> [{cards: [Card2D], key, dkey, label, done, gone}]
var _uid := 0
var turn_seat := -1
var turn_hand := -1
var turn_options: Array = []
var dealer_label := ""
var insurance_seats := {} # seat -> true while they're deciding on insurance
var insurance_costs := {} # seat -> pence

@onready var shoe: CardShoe = $Felt/Fixtures/Shoe


# ------------------------------------------------------------------ layout
func bet_spots() -> Array:
	return SPOTS


func spot_radius(spot: String) -> float:
	return BET_R if spot == "bet" else SPOT_R + 1.0


## The betting circle is big, and Top 3 is a diamond.
func spot_shape(seat: int, spot: String) -> Dictionary:
	match spot:
		"bet":
			return {"shape": "circle", "at": spot_pos(seat, spot), "r": BET_R}
		"top_three":
			return {"shape": "diamond", "at": spot_pos(seat, spot), "hw": 8.5, "hh": 7.5}
	return super(seat, spot)


func main_spot() -> String:
	return "bet"


## Room to double: a bet can cost up to twice itself, plus the side bets.
func max_cost(b: Dictionary) -> int:
	var total := int(b.get("bet", 0))
	for spot in b:
		total += int(b[spot])
	return total


func spot_pos(seat: int, spot: String) -> Vector2:
	var x := seat_x(seat)
	match spot:
		"jackpot":
			return Vector2(x - 9.5, TOP_Y)
		"top_three":
			return Vector2(x + 9.5, TOP_Y)
		"super_pairs":
			return Vector2(x - 9.5, SIDE_Y)
		"twenty_one_plus_three":
			return Vector2(x + 9.5, SIDE_Y)
		"insurance":
			return Vector2(x - 17, BET_Y)
	return Vector2(x, BET_Y)


## Where winnings go, all staying on the felt until the hand's over: beside
## each side bet on the outer side of its column (the Jackpot's on its disc),
## below the insurance mark, and beside the betting circle.
func payout_pos(seat: int, spot: String, _bonus := false) -> Vector2:
	match spot:
		"jackpot":
			return spot_pos(seat, "jackpot")
		"super_pairs":
			return spot_pos(seat, spot) + Vector2(-11, 0)
		"twenty_one_plus_three", "top_three":
			return spot_pos(seat, spot) + Vector2(11, 0)
		"insurance":
			return spot_pos(seat, spot) + Vector2(0, 12)
	return spot_pos(seat, "bet") + Vector2(17, 0)


func dealer_card_pos(index: int) -> Vector2:
	return Vector2(-8 + index * 14.0, DEALER_Y)


## How far apart split hands sit: each about a card's width, so they barely overlap.
func _spacing(n: int) -> float:
	return [0.0, 0.0, 16.0, 15.0, 14.7, 11.0][clampi(n, 0, 5)]


## Where hand `idx` of a box with `n` hands lines up.
func _hand_x(seat: int, idx: int, n: int) -> float:
	return seat_x(seat) + (idx - (n - 1) / 2.0) * _spacing(n)


## Where card k of a hand of `count` cards lies. One hand fans out to the right
## (each card's corner index showing); split hands each keep to one card's
## width and cascade downwards, so neighbouring hands barely overlap.
func card_pos(seat: int, idx: int, n: int, k: int, count := 2) -> Vector2:
	if n <= 1:
		var step := 6.0 if count <= 4 else 24.0 / (count - 1)
		var stagger := minf(1.5, (LAST_CARD_Y - CARD_Y) / maxf(1.0, count - 1))
		return Vector2(seat_x(seat) - 3.0 + k * step, CARD_Y + k * stagger)
	var drop := minf(5.5, (LAST_CARD_Y - SPLIT_CARD_Y) / maxf(1.0, count - 1))
	return Vector2(_hand_x(seat, idx, n) + k * 0.8, SPLIT_CARD_Y + k * drop)


func _bet_pos(seat: int, idx: int, n: int) -> Vector2:
	return spot_pos(seat, "bet") if n <= 1 else Vector2(_hand_x(seat, idx, n), SPLIT_BET_Y)


func _double_pos(seat: int, idx: int, n: int) -> Vector2:
	return _bet_pos(seat, idx, n) + (Vector2(5, 3) if n <= 1 else Vector2(3.5, -2.5))


func _hand_payout_pos(seat: int, idx: int, n: int) -> Vector2:
	return payout_pos(seat, "bet") if n <= 1 else _bet_pos(seat, idx, n) + Vector2(-3.5, -3)


## Where a hand's total sits: centred just above its first card, which doesn't move
## as the hand draws (split hands: between the bets and the cards).
func label_pos(seat: int, idx: int, n: int) -> Vector2:
	return card_pos(seat, idx, n, 0) + Vector2(0, -13)


## The countdown sits at the right-hand end of the title's row, under the shoe.
func _countdown_x() -> float:
	return 90.0


# ------------------------------------------------------------------ hands
func _hands_for(seat: int) -> Array:
	if not _hands.has(seat):
		_hands[seat] = []
	return _hands[seat]


func _new_hand(seat: int, key := "") -> Dictionary:
	_uid += 1
	return {"cards": [], "key": key if key != "" else "h%d" % _uid, "dkey": "d%d" % _uid,
		"label": "", "done": false, "gone": false}


## Slide every card and bet of a box to where they belong for its hand count
## (`skip`: a card still flying in, which has its own way there).
func _relayout(seat: int, d: float, skip: Card2D = null) -> void:
	var hands := _hands_for(seat)
	var n := hands.size()
	var chips := _chips_for(seat)
	for idx in n:
		var hand: Dictionary = hands[idx]
		var count: int = hand.cards.size()
		for k in count:
			var card: Card2D = hand.cards[k]
			if card == skip:
				continue
			var sideways: bool = hand.get("doubled_card") == card
			_move_card(card, [card_pos(seat, idx, n, k, count) + (Vector2(2, 1) if sideways else Vector2.ZERO),
				PI / 2 if sideways else 0.0], 0.25 * d)
		if chips.has(hand.key):
			_tween().tween_property(chips[hand.key], "position", _bet_pos(seat, idx, n), 0.25 * d)
		if chips.has(hand.dkey):
			_tween().tween_property(chips[hand.dkey], "position", _double_pos(seat, idx, n), 0.25 * d)


func _cards_on_felt() -> Array:
	var cards := []
	for seat in _hands:
		for hand in _hands[seat]:
			cards += hand.cards
	return cards + _dealer_cards


## A card from the shoe to `to`, turned face up as it lands (unless it's the hole card).
func _deal_card(code: String, to: Vector2, delay: float, d: float, face_up := true, rot := 0.0) -> Card2D:
	var card := _new_card("??", shoe.mouth_point())
	card.visible = false
	var tw := _tween()
	tw.tween_interval(delay)
	tw.tween_callback(func():
		card.show()
		shoe.take_one()
		sfx_at("deal", to_global(shoe.mouth_point())))  # one card at a time out of the shoe: a swish each
	tw.tween_property(card, "position", to, 0.28 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	if rot != 0.0:
		tw.parallel().tween_property(card, "rotation", rot, 0.28 * d)
	if face_up:
		tw.tween_callback(card.flip_to.bind(code, 0.14 * d))
	return card


# ------------------------------------------------------------------ the HUD
func deciding() -> bool:
	return in_hand and phase in ["dealing", "side_bets", "insurance", "peek", "naturals", "playing"]


func seated_view(ctx: Dictionary) -> Dictionary:
	var left := ceili(timer_left())
	var info := ""
	var actions := []
	match phase:
		"betting":
			info = _betting_info(ctx)
		"dealing", "side_bets":
			info = "Dealing..."
		"insurance":
			var box := _insuring_seat()
			if box >= 0:
				var cost := int(insurance_costs.get(box, 0))
				info = box_prefix(box) + "Insurance? -- %ds" % left
				actions = [{"id": "insure", "label": "Insurance %s  [Space]" % Money.format(cost, true), "key": "Space"},
					{"id": "no_insurance", "label": "No insurance  [Backspace]", "key": "Backspace"}]
			else:
				info = "Insurance is open" if not in_hand else "Waiting for the others"
		"peek":
			info = "The dealer checks for Blackjack..."
		"naturals":
			info = "Paying Blackjacks"
		"playing":
			if is_mine(turn_seat) and in_hand:
				info = box_prefix(turn_seat) + "Your turn -- %ds" % left
				var bet := _hand_bet(turn_seat, turn_hand)
				for option in turn_options:
					var label: String = str(option).capitalize()
					if option in ["double", "split"]:
						label += " " + Money.format(bet, true)
					var a := {"id": option, "label": "%s  [%s]" % [label, ACTION_KEYS[option]], "key": ACTION_KEYS[option]}
					if option in FLANK:   # Hit and Stand stay put in the middle; Split and Double either side
						a.place = FLANK[option]
					actions.append(a)
			elif turn_seat >= 0 and occupants.has(turn_seat):
				info = "%s to play" % occupants[turn_seat].name
		"dealer":
			info = "Dealer's turn"
	return {"info": info, "actions": actions, "my_turn": not actions.is_empty()}


func _hand_bet(seat: int, idx: int) -> int:
	var hands := _hands_for(seat)
	if idx < 0 or idx >= hands.size():
		return 0
	var chips := _chips_for(seat)
	return int(chips[hands[idx].key].amount) if chips.has(hands[idx].key) else 0


## Which of the local player's boxes is still to say about insurance, or -1: their own first.
func _insuring_seat() -> int:
	for seat in my_seats():
		if insurance_seats.has(seat):
			return seat
	return -1


func action_message(id: String) -> Array:
	match id:
		"insure":
			return ["insure", {"take": true, "seat": _insuring_seat()}]
		"no_insurance":
			return ["insure", {"take": false, "seat": _insuring_seat()}]
	return ["act", {"action": id, "seat": turn_seat}]


# ------------------------------------------------------------------ snapshot
func _apply_game_snapshot(state: Dictionary) -> void:
	_hands.clear()
	insurance_seats.clear()
	insurance_costs.clear()
	var turn = state.get("turn")
	turn_seat = int(turn.seat) if turn != null else -1
	turn_hand = int(turn.hand) if turn != null else -1
	turn_options = []
	var sh: Dictionary = state.get("shoe", {})
	if not sh.is_empty():
		shoe.set_state(int(sh.remaining), int(sh.total), int(sh.cut), bool(sh.cut_out))
	discard_rack.count = int(state.get("discards", 0))
	var seats: Array = state.get("seats", [])
	for i in seats.size():
		var s = seats[i]
		if s == null or s.get("hands", []).is_empty():
			continue
		if is_mine(i):
			in_hand = true
		_set_stack(i, "bet", 0)
		var hands: Array = s.hands
		for idx in hands.size():
			var h: Dictionary = hands[idx]
			var hand := _new_hand(i)
			hand.label = h.label
			hand.done = h.done
			hand.gone = h.get("gone", false)
			for k in h.cards.size():
				hand.cards.append(_new_card(h.cards[k], card_pos(i, idx, hands.size(), k, h.cards.size())))
			if h.label != "Bust":  # a bust's bet went with it; a paid Blackjack's stays till the end
				var bet := int(h.bet) / (2 if h.doubled else 1)
				_set_stack(i, hand.key, bet, _bet_pos(i, idx, hands.size()))
				if h.doubled:
					_set_stack(i, hand.dkey, bet, _double_pos(i, idx, hands.size()))
			_hands_for(i).append(hand)
		if int(s.get("insurance", 0)) > 0:
			_set_stack(i, "insurance", int(s.insurance))
	var dealer_codes: Array = state.get("dealer", {}).get("cards", [])
	dealer_label = str(state.get("dealer", {}).get("label", "")) if state.get("dealer", {}).get("label") != null else ""
	for k in dealer_codes.size():
		_dealer_cards.append(_new_card(dealer_codes[k], dealer_card_pos(k)))


# ------------------------------------------------------------------ events -> animation
func _note_event(ev: Dictionary) -> void:
	if ev.kind == "betting_open":
		_hands.clear()
		turn_seat = -1
		turn_hand = -1
		dealer_label = ""
		insurance_seats.clear()


func _animate_game(ev: Dictionary, d: float) -> float:
	match ev.kind:
		"dealt":
			return _deal(ev, d)
		"cut_card":
			shoe.cut_out()
			return 0.4 * d
		"side_bets":
			return _side_bets(ev, d)
		"insurance_open":
			phase = "insurance"
			insurance_seats.clear()
			for seat in ev.seats:
				insurance_seats[int(seat)] = true
			for seat in ev.costs:
				insurance_costs[int(seat)] = int(ev.costs[seat])
			_start_timer(float(ev.seconds))
			return 0.0
		"insurance":
			var seat := int(ev.seat)
			insurance_seats.erase(seat)
			if ev.take:
				_add_stack_from(seat, "insurance", int(ev.amount), chair_pos(seat), d)
			return 0.1 * d
		"peek":
			return _peek(d)
		"insurance_settled":
			return _insurance_settled(ev, d)
		"blackjacks_paid":
			return _blackjacks_paid(ev, d)
		"dealer_reveal":
			phase = "dealer" if not ev.get("blackjack", false) else "settling"
			_timer_end = 0.0
			turn_seat = -1
			if _dealer_cards.size() > 1:
				_dealer_cards[1].flip_to(ev.cards[1], 0.3 * d)
			dealer_label = ev.label
			return 0.8 * d
		"turn":
			phase = "playing"
			turn_seat = int(ev.seat)
			turn_hand = int(ev.hand)
			turn_options = ev.options
			_start_timer(float(ev.seconds))
			return 0.0
		"action":
			return _action(ev, d)
		"bust":
			return _bust(ev, d)
		"dealer_draw":
			var card := _deal_card(ev.card, dealer_card_pos(_dealer_cards.size()), 0.0, d)
			_dealer_cards.append(card)
			_after(0.4 * d).timeout.connect(func(): dealer_label = ev.label)
			return 0.7 * d
		"dealer_done":
			phase = "settling"
			return (0.6 if ev.get("bust", false) else 0.3) * d  # a bust: let "Everyone's a winner!" land first
		"settle_seat":
			return _settle(ev, d)
		"shuffle":
			phase = "shuffling"
			var left := shoe.remaining
			shoe.set_state(0, shoe.total, shoe.cut, false)
			return _feed_shuffler(d, float(ev.seconds) * 0.7, left, shoe.mouth_point()) + 0.3 * d
		"shoe_loaded":
			return _load_shoe(ev, d)
	return 0.0


## One card at a time from the shoe: a card to every box from first base, the
## dealer's up-card, a second card each, then the hole card face down.
func _deal(ev: Dictionary, d: float) -> float:
	phase = "dealing"
	ready_seats.clear()
	_timer_end = 0.0
	var sh: Dictionary = ev.get("shoe", {})
	if not sh.is_empty():  # the shoe as it was before this deal
		shoe.set_state(int(sh.remaining) + ev.order.size(), int(sh.total), int(sh.cut), false)
	var interval := float(ev.interval) * d
	var cards: Dictionary = ev.cards
	var t := 0.0
	for entry in ev.order:
		var who = entry[0]
		var k := int(entry[1])
		if str(who) == "dealer":
			var up := k == 0
			_dealer_cards.append(_deal_card(ev.dealer_up if up else "??", dealer_card_pos(k), t, d, up))
		else:
			var seat := int(who)
			var hands := _hands_for(seat)
			if hands.is_empty():
				hands.append(_new_hand(seat, "bet"))  # the bet already in the circle is this hand's
			hands[0].cards.append(_deal_card(cards[str(seat)][k], card_pos(seat, 0, 1, k, 2), t, d))
		t += interval
	_after(t + 0.3 * d).timeout.connect(func():  # totals once the cards have landed
		for seat in ev.labels:
			_hands_for(int(seat))[0].label = ev.labels[seat])
	return t + 0.35 * d


## Side bets settle at once: a box's losers swept in one go, then its winners paid
## one by one beside their spots, where they stay with the stake until the hand's over.
func _side_bets(ev: Dictionary, d: float) -> float:
	phase = "side_bets"
	var step_t := float(ev.get("step", 0.45)) * d
	var gap := float(ev.get("sweep_gap", 0.12)) * d
	var t := float(ev.get("pause", 0.6)) * d
	for entry in ev.seats:
		var seat := int(entry.seat)
		var lost := 0
		for step in entry.steps:   # the server sends the losers first
			if step.action == "collect":
				var at := t + lost * gap
				_after(at).timeout.connect(_settle_step.bind(seat, step, d))
				if step.spot == "jackpot":  # a lost Jackpot's light goes off
					_after(at).timeout.connect(func(): jackpot_lights.erase(seat))
				lost += 1
				continue
			if lost > 0:   # the sweep's done
				t += step_t + (lost - 1) * gap
				lost = 0
			_after(t).timeout.connect(_settle_step.bind(seat, step, d))
			t += step_t
		if lost > 0:
			t += step_t + (lost - 1) * gap
		t += 0.2 * d
	return t


## The dealer checks the hole card: lifts its corner, looks, puts it back.
func _peek(d: float) -> float:
	phase = "peek"
	_timer_end = 0.0
	insurance_seats.clear()
	if _dealer_cards.size() > 1:
		var hole: Card2D = _dealer_cards[1]
		var home := hole.position
		var tw := _tween()
		tw.tween_property(hole, "position", home + Vector2(0, -4), 0.25 * d)
		tw.parallel().tween_property(hole, "rotation", -0.18, 0.25 * d)
		tw.tween_interval(0.45 * d)
		tw.tween_property(hole, "position", home, 0.2 * d)
		tw.parallel().tween_property(hole, "rotation", 0.0, 0.2 * d)
	return 1.1 * d


func _insurance_settled(ev: Dictionary, d: float) -> float:
	var t := 0.2 * d
	for entry in ev.seats:
		var seat := int(entry.seat)
		var step := {"spot": "insurance", "action": entry.action, "amount": entry.amount, "payout": entry.get("payout", 0)}
		_after(t).timeout.connect(_settle_step.bind(seat, step, d))
		t += 0.35 * d
	return t + 0.5 * d


## The dealer can't have Blackjack: each player Blackjack is paid 3:2 beside the
## bet at once (the chips stay till the hand's over) and its cards cleared away.
func _blackjacks_paid(ev: Dictionary, d: float) -> float:
	phase = "naturals"
	var pause := float(ev.get("pause", 0.8)) * d
	if str(ev.get("say", "")) != "":
		dealer.say(ev.say, 2.0 + pause * 2)
	var t := pause
	for entry in ev.seats:
		var seat := int(entry.seat)
		var hands := _hands_for(seat)
		if hands.is_empty():
			continue
		var hand: Dictionary = hands[0]
		_after(t).timeout.connect(func():
			var stack := _payout_from_tray(seat, int(entry.payout))
			_tween().tween_property(stack, "position", _hand_payout_pos(seat, 0, 1), 0.35 * d))
		_after(t + 0.45 * d).timeout.connect(func():
			var k := 0
			for card in hand.cards:
				_discard(card, d, k * 0.04 * d)
				k += 1
			hand.cards = []
			hand.gone = true)
		t += 0.6 * d
	return t + 0.3 * d


func _action(ev: Dictionary, d: float) -> float:
	var seat := int(ev.seat)
	var idx := int(ev.hand)
	var hands := _hands_for(seat)
	if idx >= hands.size():
		return 0.0
	var hand: Dictionary = hands[idx]
	var n := hands.size()
	match ev.action:
		"hit":
			var count: int = hand.cards.size() + 1
			var card := _deal_card(ev.card, card_pos(seat, idx, n, count - 1, count), 0.0, d)
			hand.cards.append(card)
			_relayout(seat, d, card)  # a long hand closes up so it stays on the felt
		"double":
			_add_stack_from(seat, hand.dkey, int(ev.amount), chair_pos(seat), d, _double_pos(seat, idx, n))
			var count: int = hand.cards.size() + 1
			var card := _deal_card(ev.card, card_pos(seat, idx, n, count - 1, count) + Vector2(2, 1), 0.3 * d, d, true, PI / 2)
			hand.cards.append(card)
			hand["doubled_card"] = card
		"split":
			var b := _new_hand(seat)
			b.cards.append(hand.cards.pop_back())
			hands.insert(idx + 1, b)
			n = hands.size()
			_add_stack_from(seat, b.key, int(ev.amount), chair_pos(seat), d, _bet_pos(seat, idx + 1, n))
			_relayout(seat, d)
			hand.cards.append(_deal_card(ev.hands[0][1], card_pos(seat, idx, n, 1, 2), 0.35 * d, d))
			b.cards.append(_deal_card(ev.hands[1][1], card_pos(seat, idx + 1, n, 1, 2), 0.65 * d, d))
	hand.done = ev.done
	if ev.done and turn_seat == seat:  # that hand's finished: the buttons and timer go now, not when the next turn comes
		turn_seat = -1
		turn_options = []
		_timer_end = 0.0
	var landed := (0.95 if ev.action == "split" else 0.6 if ev.action == "double" else 0.3) * d
	_after(landed).timeout.connect(func():  # the new total once the card has landed
		if ev.action == "split":
			hand.label = ev.labels[0]
			hands[idx + 1].label = ev.labels[1]
		else:
			hand.label = ev.total)
	return (0.95 if ev.action == "split" else 0.45) * d


## Bust: the dealer takes the hand's bet and its cards straight away.
func _bust(ev: Dictionary, d: float) -> float:
	var seat := int(ev.seat)
	var hands := _hands_for(seat)
	var idx := int(ev.hand)
	if idx >= hands.size():
		return 0.0
	var hand: Dictionary = hands[idx]
	_after(0.35 * d).timeout.connect(func():
		_take_stack(seat, hand.key, tray_pos(), d)
		_take_stack(seat, hand.dkey, tray_pos(), d)
		var k := 0
		for card in hand.cards:
			_discard(card, d, k * 0.04 * d)
			k += 1
		hand.cards = []
		hand.gone = true)
	return 0.9 * d


## Settle one box, hand by hand: losers swept, pushes nudged, winners paid
## beside the bet (they stay until the round ends); the cards go last.
func _settle(ev: Dictionary, d: float) -> float:
	phase = "settling"
	var seat := int(ev.seat)
	var pause := float(ev.get("pause", 0.51)) * d
	var hands := _hands_for(seat)
	var n := hands.size()
	if ev.has("sweep"):  # a Dealer Blackjack beat everyone or the dealer bust: hand after hand, no checking
		var gap := float(ev.sweep) * d
		var paid := 0
		for entry in ev.hands:
			if int(entry.hand) < n:
				_after(paid * gap).timeout.connect(_settle_hand.bind(seat, int(entry.hand), n, entry, d))
				paid += 1
		_after(maxf(paid - 1, 0) * gap + 0.15 * d).timeout.connect(func():
			var k := 0
			for hand in hands:
				for card in hand.cards:
					_discard(card, d, k * 0.04 * d)
					k += 1
				hand.cards = []
				hand.gone = true)
		return paid * gap
	var t := 0.19 * d
	if str(ev.get("say", "")) != "":
		_after(t).timeout.connect(dealer.say.bind(ev.say, 2.0 + pause * 2))
	t += pause
	for entry in ev.hands:
		var idx := int(entry.hand)
		if idx >= n:
			continue
		_after(t).timeout.connect(_settle_hand.bind(seat, idx, n, entry, d))
		t += 0.29 * d
	_after(t).timeout.connect(func():  # the cards go last
		var k := 0
		for hand in hands:
			for card in hand.cards:
				_discard(card, d, k * 0.04 * d)
				k += 1
			hand.cards = []
			hand.gone = true)
	t += 0.26 * d
	return t + pause


## One hand's settle: a loser's bets to the tray, a push nudged, a winner paid beside its bet.
func _settle_hand(seat: int, idx: int, n: int, entry: Dictionary, d: float) -> void:
	var hand: Dictionary = _hands_for(seat)[idx]
	match entry.action:
		"collect":
			_take_stack(seat, hand.key, tray_pos(), d)
			_take_stack(seat, hand.dkey, tray_pos(), d)
		"push":
			_settle_step(seat, {"spot": hand.key, "action": "push"}, d)
		"pay":
			var stack := _payout_from_tray(seat, int(entry.payout))
			var tw := _tween().set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
			tw.tween_property(stack, "position", _hand_payout_pos(seat, idx, n), 0.28 * d)


## A freshly shuffled shoe: the decks come out of the shuffler and go in the shoe.
func _load_shoe(ev: Dictionary, d: float) -> float:
	var sh: Dictionary = ev.get("shoe", {})
	for k in 6:
		var card := _new_card("??", shuffler.delivery_point())
		var tw := _tween()
		tw.tween_interval(k * 0.06 * d)
		tw.tween_property(card, "position", shoe.mouth_point() + Vector2(10, 0), 0.4 * d).set_trans(Tween.TRANS_QUAD)
		tw.tween_callback(card.queue_free)
	shoe.total = int(sh.get("total", shoe.total))
	shoe.cut = int(sh.get("cut", shoe.cut))
	_after(0.3 * d).timeout.connect(shoe.load_full.bind(0.6 * d))
	return 1.0 * d


# ------------------------------------------------------------------ overlays
func _needs_redraw() -> bool:
	return phase in ["insurance", "playing"]


func _draw_game(_now: float, pulse: float) -> void:
	if phase == "insurance":
		for seat in insurance_seats:
			if occupants.has(seat):
				_draw_thinking_ring(seat, pulse)
	if phase == "playing" and turn_seat >= 0 and occupants.has(turn_seat):
		_draw_thinking_ring(turn_seat, pulse)
		var hands := _hands_for(turn_seat)
		if turn_hand >= 0 and turn_hand < hands.size() and not hands[turn_hand].cards.is_empty():
			var box := Rect2(hands[turn_hand].cards[0].position, Vector2.ZERO)
			for card in hands[turn_hand].cards:
				box = box.expand(card.position)
			box = box.grow_individual(8.5, 11.5, 8.5, 11.5)
			draw_rect(box, Color(1, 0.85, 0.3, 0.35 + 0.35 * pulse), false, 0.9)
	# Each hand's total, above its first card. Split hands are only a card apart,
	# so theirs are short: "Soft 17" is 7/17.
	for seat in _hands:
		var n: int = _hands[seat].size()
		for idx in n:
			var hand: Dictionary = _hands[seat][idx]
			if hand.gone or hand.cards.is_empty() or hand.label == "":
				continue
			_label_pill(label_pos(seat, idx, n), _short_total(hand.label) if n > 1 else hand.label, true)
	if dealer_label != "" and not _dealer_cards.is_empty():
		_label_pill(_dealer_cards[-1].position + Vector2(9, -9), dealer_label)


func _short_total(label: String) -> String:
	if label.begins_with("Soft "):
		var total := int(label.substr(5))
		return "%d/%d" % [total - 10, total]
	return label


func _label_pill(at: Vector2, text: String, centred := false) -> void:
	var font := Card2D.FONT
	var width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 4).x + 3.0
	var r := Rect2(at - Vector2(width / 2 if centred else 0.0, 3), Vector2(width, 6))
	draw_rect(r, Color(0.05, 0.03, 0.02, 0.82))
	draw_rect(r, Color(1, 0.88, 0.5, 0.5), false, 0.3)
	draw_string(font, Vector2(r.position.x + 1.5, at.y + 1.45), text, HORIZONTAL_ALIGNMENT_LEFT, -1, 4, Color(1, 0.95, 0.8))


func _countdown_text(left: float) -> String:
	if phase == "insurance" and left > 0:
		return "INSURANCE  %d" % ceili(left)
	if phase == "playing" and left > 0 and turn_seat >= 0:
		return "TO PLAY  %d" % ceili(left)
	return super(left)
