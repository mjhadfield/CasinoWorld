@tool
class_name HcfTable
extends CasinoTable
## A High Card Flush table (five seats, spread out): everything shared with the
## other games comes from CasinoTable; this adds the layout (Jackpot disc,
## Flush and Straight Flush circles, Ante and Raise, a fan of seven cards per
## seat; the dealer's seven across the middle) and the round: seven cards each,
## everyone folds or raises at once. A raise puts the flush face down in front
## and the other cards aside; a straight flush riding on the Straight Flush bet
## (or the Jackpot) is tucked under that bet, as with a Prime at Three Card
## Poker. The dealer sweeps the folds and the cards set aside, turns their own
## hand (the flush slides forward, the rest is swept), then settles each player.

const SIDE_Y := -61.0     # Jackpot, Flush, Straight Flush
const ANTE_Y := -40.0
const FLUSH_Y := -17.0    # a raised hand's flush, face down where the fan was
const CARD_Y := -17.0     # the fan as dealt: 2 inside the front border
const FAN := 7.0
const FLUSH_GAP := 4.5
const DEALER_CARD_Y := DEALER_Y
const SPOTS := ["ante", "flush", "straight_flush", "jackpot"]

var decided_seats := {}
var round_seats := {}
var my_ante := 0
var max_raises := {}  # each of the local player's boxes -> how far its flush lets it raise
var _flush := {}    # seat -> [Card2D] face down in front
var _held := {}     # seat -> [Card2D] tucked under the Straight Flush bet
var _aside := {}    # seat -> [Card2D] waiting to be swept


# ------------------------------------------------------------------ layout
func bet_spots() -> Array:
	return SPOTS


func spot_radius(spot: String) -> float:
	return 8.0 if spot in ["ante", "raise"] else SPOT_R + 0.5


func _ready() -> void:
	super()
	if not Engine.is_editor_hint():
		Settings.changed.connect(func(key, _v):
			if key == "hcf_four_colour" and styled():
				_restyle_under(_dyn, card_look()))


## A flush is easier to read with four suit colours, so this device's Settings can put them over the
## table style's (its front stays the style's).
func card_look() -> Dictionary:
	if Engine.is_editor_hint() or not Settings.value("hcf_four_colour"):
		return style()
	var four := style().duplicate()
	four.suits = "four"
	return four


func spot_shape(seat: int, spot: String) -> Dictionary:
	if spot in ["ante", "raise"]:
		return {"shape": "circle", "at": spot_pos(seat, spot), "r": 8.0}
	return super(seat, spot)


func main_spot() -> String:
	return "ante"


func max_cost(b: Dictionary) -> int:
	return int(b.get("ante", 0)) * 4 + int(b.get("flush", 0)) + int(b.get("straight_flush", 0)) + int(b.get("jackpot", 0))


func spot_pos(seat: int, spot: String) -> Vector2:
	var x := seat_x(seat)
	match spot:
		"jackpot":
			return Vector2(x - 19, SIDE_Y)
		"flush":
			return Vector2(x, SIDE_Y)
		"straight_flush":
			return Vector2(x + 19, SIDE_Y)
		"raise":
			return Vector2(x + 12, ANTE_Y)
	return Vector2(x - 12, ANTE_Y)


func payout_pos(seat: int, spot: String, _bonus := false) -> Vector2:
	match spot:
		"jackpot":
			return spot_pos(seat, "jackpot")
		"ante", "raise":  # a second stack leaning on the stake: the cards are just below
			return spot_pos(seat, spot) + Vector2(5, -5)
	return spot_pos(seat, spot) + Vector2(10, -4)


func card_pos(seat: int, index: int) -> Vector2:
	return Vector2(seat_x(seat) + (index - 3) * FAN, CARD_Y)


## A raised hand's flush: a tidy face-down row in front of the player.
func flush_pos(seat: int, index: int, count: int) -> Array:
	return [Vector2(seat_x(seat) - 6 + (index - (count - 1) / 2.0) * FLUSH_GAP, FLUSH_Y), 0.0]


## A straight flush tucked sideways under the Straight Flush bet.
func held_pos(seat: int, index: int) -> Array:
	return [spot_pos(seat, "straight_flush") + Vector2(index * 0.5, -index * 0.5), PI / 2]


## Cards set aside (or a folded hand), in a messy pile to be swept.
func aside_pos(seat: int, index: int) -> Array:
	var mess := [Vector2(-1.5, 0.8), Vector2(0.8, -0.6), Vector2(1.8, 1.0), Vector2(-0.6, -1.2)]
	return [Vector2(seat_x(seat) + 21, CARD_Y - 1) + mess[index % 4], -0.15 + (index % 4) * 0.1]


func dealer_card_pos(index: int) -> Vector2:
	return Vector2(-36 + index * 12.0, DEALER_CARD_Y)


## The dealer's flush, slid forward into a centred row once their hand is shown.
func dealer_flush_pos(index: int, count: int) -> Vector2:
	return Vector2((index - (count - 1) / 2.0) * 15.0, DEALER_CARD_Y)


## Your own seven, face up: grouped by suit (your flush first), high to low.
static func sort_hand(codes: Array, flush: Array) -> Array:
	var rest := codes.filter(func(c): return not c in flush)
	rest.sort_custom(func(a, b):
		if a.right(1) != b.right(1):
			return a.right(1) < b.right(1)
		return Card2D.rank_value(a) > Card2D.rank_value(b))
	return flush + rest


# ------------------------------------------------------------------ the HUD
func deciding() -> bool:
	return acting_seat() >= 0


## Which of the local player's boxes is still to decide, or -1: their own first.
func acting_seat() -> int:
	if phase != "deciding":
		return -1
	for seat in my_seats():
		if round_seats.has(seat) and not decided_seats.has(seat):
			return seat
	return -1


func seated_view(ctx: Dictionary) -> Dictionary:
	var seat := acting_seat()
	var my_turn := seat >= 0
	var left := ceili(timer_left())
	var info := ""
	match phase:
		"betting":
			info = _betting_info(ctx)
		"dealing":
			info = "Dealing..."
		"deciding":
			if my_turn:
				info = box_prefix(seat) + "Raise or fold -- %ds" % left
			elif my_seats().any(func(x): return round_seats.has(x)):
				info = "Waiting for the others"
			else:
				info = "Watching this hand"
	var actions := []
	if my_turn:
		var ante := my_ante if my_ante > 0 else int(ctx.get("my_bets", {}).get("ante", 0))
		for times in range(int(max_raises.get(seat, 1)), 0, -1):
			actions.append({"id": "raise%d" % times, "label": "Raise %dx %s  [%d]" % [times, Money.format(ante * times, true), times],
				"key": str(times)})
		actions.append({"id": "fold", "label": "Fold  [F]", "key": "F"})
	return {"info": info, "actions": actions, "my_turn": my_turn}


func action_message(id: String) -> Array:
	return ["act", {"action": id, "seat": acting_seat()}]


# ------------------------------------------------------------------ snapshot
func _apply_game_snapshot(state: Dictionary) -> void:
	decided_seats.clear()
	round_seats.clear()
	_flush.clear()
	_held.clear()
	_aside.clear()
	var seats: Array = state.get("seats", [])
	for i in seats.size():
		var s = seats[i]
		if s == null:
			continue
		if int(s.get("raise", 0)) > 0:
			_set_stack(i, "raise", int(s.raise))
		var cards: Array = s.get("cards", [])
		if cards.is_empty() or s.get("result") != null:
			continue
		round_seats[i] = true
		if is_mine(i):
			in_hand = true
			my_ante = int(s.get("bets", {}).get("ante", 0))
		if not s.get("decided"):
			for k in cards.size():
				_cards_for(i).append(_new_card(cards[k], card_pos(i, k)))
			continue
		decided_seats[i] = true
		var fc := int(s.get("flush_count", 0))
		var hc := int(s.get("held_count", 0))
		for k in cards.size():
			var card := _new_card("??", Vector2.ZERO)
			var place: Array
			if k < fc:
				place = flush_pos(i, k, fc)
				_flush.get_or_add(i, []).append(card)
			elif k < fc + hc:
				place = held_pos(i, k - fc)
				_held.get_or_add(i, []).append(card)
			else:
				place = aside_pos(i, k - fc - hc)
				_aside.get_or_add(i, []).append(card)
			card.position = place[0]
			card.rotation = place[1]
			_cards_for(i).append(card)
	var dealer: Array = state.get("dealer", {}).get("cards", [])
	var shown: bool = not dealer.is_empty() and dealer[0] != "??"
	for k in dealer.size():
		_dealer_cards.append(_new_card(dealer[k], dealer_flush_pos(k, dealer.size()) if shown else dealer_card_pos(k)))


# ------------------------------------------------------------------ events -> animation
func _note_event(ev: Dictionary) -> void:
	if ev.kind == "betting_open":
		round_seats.clear()
		decided_seats.clear()
		my_ante = 0
		max_raises.clear()
	if ev.kind == "bets_closed":
		round_seats.clear()
		decided_seats.clear()
		for seat in ev.seats:
			round_seats[int(seat)] = true
		if my_seat >= 0 and round_seats.has(my_seat):
			my_ante = int(_chips_for(my_seat)["ante"].amount) if _chips_for(my_seat).has("ante") else 0
	for seat in my_seats():
		var mine = mine_for(ev, seat)
		if mine is Dictionary and mine.has("max_raise"):
			max_raises[seat] = int(mine.max_raise)
	_note_hands(ev, func(seat): return round_seats.has(seat))


func _animate_game(ev: Dictionary, d: float) -> float:
	match ev.kind:
		"dealt":
			return _deal(ev, d)
		"decisions_open":
			phase = "deciding"
			decided_seats.clear()
			_start_timer(float(ev.seconds))
			return 0.0
		"hcf_action":
			return _action(ev, d)
		"fold_sweep":
			return _fold_sweep(ev, d)
		"dealer_reveal":
			return _dealer_reveal(ev, d)
		"settle_seat":
			return _settle(ev, d)
	return 0.0


func _deal(ev: Dictionary, d: float) -> float:
	phase = "dealing"
	ready_seats.clear()
	_timer_end = 0.0
	_flush.clear()
	_held.clear()
	_aside.clear()
	var interval := float(ev.interval) * d
	var hand_pause := float(ev.get("hand_pause", 0.0)) * d
	var hands: Array = []
	for entry in ev.order:
		if hands.is_empty() or str(hands[-1][0]) != str(entry[0]):
			hands.append([entry[0], []])
		hands[-1][1].append(int(entry[1]))
	var start := 0.0
	for h in hands.size():
		var who := str(hands[h][0])
		var indices: Array = hands[h][1]
		_after(start).timeout.connect(shuffler.deliver)
		_deal_sound(start + 0.38 * d)
		for k in indices.size():
			var to_dealer := who == "dealer"
			var target := dealer_card_pos(indices[k]) if to_dealer else card_pos(int(who), indices[k])
			var card := _new_card("??", shuffler.slot_point())
			card.visible = false
			if to_dealer:
				_dealer_cards.append(card)
			else:
				_cards_for(int(who)).append(card)
			var tw := _tween()
			tw.tween_interval(start + k * 0.02 * d)
			tw.tween_callback(card.show)
			tw.tween_property(card, "position", shuffler.delivery_point() + Vector2(k * 0.4, -k * 0.4), 0.2 * d) \
				.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
			tw.tween_interval((0.18 + k * 0.008) * d)
			tw.tween_property(card, "position", target, 0.26 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
		start += indices.size() * interval + hand_pause
	var total := start + 0.5 * d
	var mine = ev.get("mine")
	if mine != null and my_seat >= 0:  # you look at your seven, sorted with your flush first
		var cards := _cards_for(my_seat)
		var sorted_codes := sort_hand(mine.cards, mine.get("flush", []))
		for k in cards.size():
			_after(total + k * 0.06 * d).timeout.connect(cards[k].flip_to.bind(sorted_codes[k], 0.2 * d))
		total += 0.5 * d
	return total


## Your second box, turned over now your own hand's decided: sorted with its flush first, like your own.
func _reveal_box(seat: int, mine, d: float) -> float:
	if not mine is Dictionary or not mine.has("cards") or decided_seats.has(seat):
		return 0.0
	if mine.has("max_raise"):
		max_raises[seat] = int(mine.max_raise)
	var cards := _cards_for(seat)
	var sorted_codes := sort_hand(mine.cards, mine.get("flush", []))
	for k in mini(cards.size(), sorted_codes.size()):
		_after(k * 0.06 * d).timeout.connect(cards[k].flip_to.bind(sorted_codes[k], 0.2 * d))
	_show_hand(seat, str(mine.get("hand", "")))
	return 0.5 * d


## A raise (chips onto Raise, the flush face down in front) or a fold; either
## way a tucked straight flush goes under its bet and the rest is set aside.
func _action(ev: Dictionary, d: float) -> float:
	var seat := int(ev.seat)
	decided_seats[seat] = true
	var times := int(ev.times)
	if times > 0:
		_add_stack_from(seat, "raise", int(ev.amount), chair_pos(seat), d)
	elif is_mine(seat):
		_show_hand(seat, "")
	var cards: Array = _cards_for(seat).duplicate()
	var flush_cards := []
	var held_cards := []
	var mine = mine_for(ev, seat)
	if mine is Dictionary:  # your own: pick them out by face
		for code in mine.get("flush", []):
			flush_cards.append(_take_code(cards, code))
		for code in mine.get("held", []):
			held_cards.append(_take_code(cards, code))
	else:  # someone else's, all face down: any will do
		for k in int(ev.get("flush_count", 0)):
			flush_cards.append(cards.pop_front())
		for k in int(ev.get("held_count", 0)):
			held_cards.append(cards.pop_front())
	_flush[seat] = flush_cards.filter(func(c): return c != null)
	_held[seat] = held_cards.filter(func(c): return c != null)
	_aside[seat] = cards
	var k := 0
	for card in _flush[seat]:
		_move_card(card, flush_pos(seat, k, _flush[seat].size()), 0.28 * d, k * 0.03 * d)
		k += 1
	k = 0
	for card in _held[seat]:
		_move_card(card, held_pos(seat, k), 0.3 * d, 0.1 * d + k * 0.04 * d)
		k += 1
	k = 0
	for card in _aside[seat]:
		_move_card(card, aside_pos(seat, k), 0.28 * d, 0.15 * d + k * 0.03 * d)
		k += 1
	for card in _cards_for(seat):  # all face down now
		_after(0.12 * d).timeout.connect(card.set.bind("code", "??"))
	return 0.15 * d


static func _take_code(cards: Array, code: String) -> Card2D:
	for card in cards:
		if card.code == code:
			cards.erase(card)
			return card
	return null


## The folds (with their bets) and every hand's set-aside cards, swept away.
func _fold_sweep(ev: Dictionary, d: float) -> float:
	phase = "sweeping"
	_timer_end = 0.0
	var pause := float(ev.get("pause", 1.0)) * d
	var t := pause
	for entry in ev.seats:
		var seat := int(entry.seat)
		var k := 0
		for step in entry.steps:
			_after(t + k * 0.08 * d).timeout.connect(_take_stack.bind(seat, step.spot, tray_pos(), d))
			k += 1
		if not entry.steps.is_empty():
			_after(t).timeout.connect(func(): jackpot_lights.erase(seat))
		_after(t + k * 0.08 * d).timeout.connect(_sweep_cards.bind(seat, d))
		t += (0.4 if not entry.steps.is_empty() or int(entry.get("cards", 0)) > 0 else 0.0) * d + pause * 0.5
	return t + 0.2 * d


func _sweep_cards(seat: int, d: float) -> void:
	var k := 0
	for card in _aside.get(seat, []):
		if is_instance_valid(card):
			_discard(card, d, k * 0.03 * d)
			_cards_for(seat).erase(card)
		k += 1
	_aside.erase(seat)


## The dealer turns their seven, then slides the flush forward and sweeps the rest.
func _dealer_reveal(ev: Dictionary, d: float) -> float:
	phase = "reveal"
	var flush: Array = ev.get("flush", [])
	var codes := sort_hand(ev.cards, flush)
	for k in mini(codes.size(), _dealer_cards.size()):
		_after(k * 0.08 * d).timeout.connect(_dealer_cards[k].flip_to.bind(codes[k], 0.25 * d))
	_after(1.1 * d).timeout.connect(func():
		var keep := []
		var k := 0
		for card in _dealer_cards.duplicate():
			if not is_instance_valid(card):
				continue
			if card.code in flush:
				keep.append(card)
			else:
				_discard(card, d, k * 0.04 * d)
				_dealer_cards.erase(card)
				k += 1
		for i in keep.size():
			_move_card(keep[i], [dealer_flush_pos(i, keep.size()), 0.0], 0.3 * d, 0.2 * d))
	return 1.8 * d


## Settle one player: their flush (and any tucked straight flush) turned over,
## the hand announced, losing bets swept, winners paid, the cards cleared.
func _settle(ev: Dictionary, d: float) -> float:
	phase = "settling"
	var seat := int(ev.seat)
	var pause := float(ev.get("pause", 1.0)) * d
	var flush_cards: Array = _flush.get(seat, [])
	var held_cards: Array = _held.get(seat, [])
	var flush_codes: Array = ev.get("flush", [])
	var held_codes: Array = ev.get("held", [])
	for k in mini(flush_cards.size(), flush_codes.size()):
		_after((0.1 + k * 0.05) * d).timeout.connect(flush_cards[k].flip_to.bind(flush_codes[k], 0.25 * d))
	for k in mini(held_cards.size(), held_codes.size()):
		_after((0.3 + k * 0.05) * d).timeout.connect(held_cards[k].flip_to.bind(held_codes[k], 0.25 * d))
	var t := 0.6 * d
	if str(ev.get("say", "")) != "":
		_after(t).timeout.connect(dealer.say.bind(ev.say, 2.0 + pause * 2))
	t += pause
	for step in ev.steps:
		_after(t).timeout.connect(_settle_step.bind(seat, step, d))
		t += 0.45 * d
	_after(t).timeout.connect(func():
		for card in _cards_for(seat):
			if is_instance_valid(card):
				_discard(card, d)
		_seat_cards.erase(seat)
		_flush.erase(seat)
		_held.erase(seat)
		jackpot_lights.erase(seat))
	t += 0.4 * d
	return t + pause + 0.05 * d


func _after_cards_cleared(d: float) -> void:
	_flush.clear()
	_held.clear()
	_aside.clear()
	_after(0.6 * d).timeout.connect(func(): _feed_shuffler(d))


# ------------------------------------------------------------------ overlays
func _needs_redraw() -> bool:
	return phase == "deciding"


func _draw_game(_now: float, pulse: float) -> void:
	if phase == "deciding":
		for seat in round_seats:
			if not decided_seats.has(seat) and occupants.has(seat):
				_draw_thinking_ring(seat, pulse)


func _countdown_text(left: float) -> String:
	if phase == "deciding" and left > 0:
		return "DECIDE  %d" % ceili(left)
	return super(left)
