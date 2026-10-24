@tool
class_name LirTable
extends CasinoTable
## A Let It Ride table (five seats, spread out): everything shared with the other games comes from
## CasinoTable; this adds the layout (Jackpot disc, the £1 Bonus and 3 Card
## Bonus circles, the three equal bets 1, 2 and $, three cards per seat; two
## community cards in front of the dealer) and the round: the deal, then twice
## everyone decides at once whether to let a bet ride or pull it back, a
## community card is turned after each, and every player is settled in turn.

const SIDE_Y := -59.0     # Jackpot, Bonus, 3 Card Bonus
const BET_Y := -39.0
const CARD_Y := -17.0     # 2 inside the front border
const SPOTS := ["bet1", "bet2", "ante", "bonus", "three_card", "jackpot"]
const BASE := ["bet1", "bet2", "ante"]
const DECISION_SPOTS := ["bet1", "bet2"]

var stage := 0
var decided_seats := {}
var round_seats := {}
var my_unit := 0


# ------------------------------------------------------------------ layout
func bet_spots() -> Array:
	return SPOTS


func spot_radius(spot: String) -> float:
	return 7.0 if spot in BASE else SPOT_R + 0.5


func spot_shape(seat: int, spot: String) -> Dictionary:
	if spot in BASE:
		return {"shape": "circle", "at": spot_pos(seat, spot), "r": 7.0}
	return super(seat, spot)


func main_spot() -> String:
	return "ante"


## The three bets go down together.
func primary_spots() -> Array:
	return BASE


func flat_spots() -> Dictionary:
	return {"bonus": 100, "jackpot": 100}


func max_cost(b: Dictionary) -> int:
	return int(b.get("ante", 0)) * 3 + int(b.get("bonus", 0)) + int(b.get("three_card", 0)) + int(b.get("jackpot", 0))


func spot_pos(seat: int, spot: String) -> Vector2:
	var x := seat_x(seat)
	match spot:
		"jackpot":
			return Vector2(x - 19, SIDE_Y)
		"bonus":
			return Vector2(x, SIDE_Y)
		"three_card":
			return Vector2(x + 19, SIDE_Y)
		"bet1":
			return Vector2(x - 19, BET_Y)
		"bet2":
			return Vector2(x, BET_Y)
	return Vector2(x + 19, BET_Y)  # £


## Winnings as a second stack leaning on each stake (the cards are just below
## the three bets); the Jackpot's on the (by then empty) disc.
func payout_pos(seat: int, spot: String, _bonus := false) -> Vector2:
	if spot in BASE:
		return spot_pos(seat, spot) + Vector2(5, -5)
	if spot == "jackpot":
		return spot_pos(seat, "jackpot")
	return spot_pos(seat, spot) + Vector2(10, -4)


func card_pos(seat: int, index: int) -> Vector2:
	return Vector2(seat_x(seat) + (index - 1) * 17.0, CARD_Y)


func dealer_card_pos(index: int) -> Vector2:
	return Vector2((index - 0.5) * 16.0, DEALER_Y)


# ------------------------------------------------------------------ the HUD
func deciding() -> bool:
	return acting_seat() >= 0


## Which of the local player's boxes is still to decide on this bet, or -1: their own first.
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
				info = box_prefix(seat) + "Bet %d -- %ds" % [stage + 1, left]
			elif my_seats().any(func(x): return round_seats.has(x)):
				info = "Waiting for the others"
			else:
				info = "Watching this hand"
	var actions := []
	if my_turn:
		var unit := my_unit if my_unit > 0 else int(ctx.get("my_bets", {}).get("ante", 0))
		actions = [{"id": "ride", "label": "Let it ride  [R]", "key": "R"},
			{"id": "pull", "label": "Pull back %s  [P]" % Money.format(unit, true), "key": "P"}]
	return {"info": info, "actions": actions, "my_turn": my_turn}


func action_message(id: String) -> Array:
	return ["act", {"action": id, "seat": acting_seat()}]


# ------------------------------------------------------------------ snapshot
func _apply_game_snapshot(state: Dictionary) -> void:
	decided_seats.clear()
	round_seats.clear()
	stage = int(state.get("stage", 0))
	var seats: Array = state.get("seats", [])
	for i in seats.size():
		var s = seats[i]
		if s == null:
			continue
		var cards: Array = s.get("cards", [])
		if cards.is_empty() or s.get("result") != null:
			continue
		round_seats[i] = true
		if s.get("decided"):
			decided_seats[i] = true
		if is_mine(i):
			in_hand = true
			my_unit = int(s.get("bets", {}).get("ante", 0))
		for k in cards.size():
			_cards_for(i).append(_new_card(cards[k], card_pos(i, k)))
	var community: Array = state.get("community", [])
	for k in community.size():
		_dealer_cards.append(_new_card(community[k], dealer_card_pos(k)))


# ------------------------------------------------------------------ events -> animation
func _note_event(ev: Dictionary) -> void:
	if ev.kind == "betting_open":
		round_seats.clear()
		decided_seats.clear()
		stage = 0
		my_unit = 0
	if ev.kind == "bets_closed":
		round_seats.clear()
		decided_seats.clear()
		for seat in ev.seats:
			round_seats[int(seat)] = true
		if my_seat >= 0 and round_seats.has(my_seat):
			my_unit = int(_chips_for(my_seat)["ante"].amount) if _chips_for(my_seat).has("ante") else 0
	_note_hands(ev, func(seat): return round_seats.has(seat))


func _animate_game(ev: Dictionary, d: float) -> float:
	match ev.kind:
		"dealt":
			return _deal(ev, d)
		"decisions_open":
			phase = "deciding"
			stage = int(ev.stage)
			decided_seats.clear()
			_start_timer(float(ev.seconds))
			return 0.0
		"lir_decision":
			var seat := int(ev.seat)
			decided_seats[seat] = true
			if not ev.ride:  # pulled back: the chips go straight back to the player
				_take_stack(seat, str(ev.spot), chair_pos(seat), d)
			return 0.1 * d
		"community":
			return _community(ev, d)
		"settle_seat":
			return _settle(ev, d)
	return 0.0


func _deal(ev: Dictionary, d: float) -> float:
	phase = "dealing"
	ready_seats.clear()
	_timer_end = 0.0
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
			var community := who == "community"
			var target := dealer_card_pos(indices[k]) if community else card_pos(int(who), indices[k])
			var card := _new_card("??", shuffler.slot_point())
			card.visible = false
			if community:
				_dealer_cards.append(card)
			else:
				_cards_for(int(who)).append(card)
			var tw := _tween()
			tw.tween_interval(start + k * 0.03 * d)
			tw.tween_callback(card.show)
			tw.tween_property(card, "position", shuffler.delivery_point() + Vector2(k * 0.5, -k * 0.5), 0.2 * d) \
				.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
			tw.tween_interval((0.18 + k * 0.01) * d)
			tw.tween_property(card, "position", target, 0.26 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
		start += indices.size() * interval + hand_pause
	var total := start + 0.5 * d
	var mine = ev.get("mine")
	if mine != null and my_seat >= 0:
		var cards := _cards_for(my_seat)
		for k in cards.size():
			_after(total + k * 0.12 * d).timeout.connect(cards[k].flip_to.bind(mine.cards[k], 0.22 * d))
		total += 0.4 * d
	return total


func _community(ev: Dictionary, d: float) -> float:
	phase = "revealing"
	_timer_end = 0.0
	var first := int(ev.from)
	var codes: Array = ev.cards
	for k in codes.size():
		var index := first + k
		if index < _dealer_cards.size():
			_after(0.4 * d).timeout.connect(_dealer_cards[index].flip_to.bind(codes[k], 0.3 * d))
	return 1.0 * d


func _settle(ev: Dictionary, d: float) -> float:
	phase = "settling"
	var seat := int(ev.seat)
	var pause := float(ev.get("pause", 1.0)) * d
	var cards := _cards_for(seat)
	var codes: Array = ev.get("cards", [])
	for k in mini(cards.size(), codes.size()):
		_after((0.1 + k * 0.05) * d).timeout.connect(cards[k].flip_to.bind(codes[k], 0.28 * d))
	var t := 0.5 * d
	if str(ev.get("say", "")) != "":
		_after(t).timeout.connect(dealer.say.bind(ev.say, 2.0 + pause * 2))
	t += pause
	for step in ev.steps:
		_after(t).timeout.connect(_settle_step.bind(seat, step, d))
		t += 0.45 * d
	_after(t).timeout.connect(func():
		for card in _cards_for(seat):
			_discard(card, d)
		_seat_cards.erase(seat)
		jackpot_lights.erase(seat))
	t += 0.4 * d
	return t + pause + 0.05 * d


func _after_cards_cleared(d: float) -> void:
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
		return "BET %d  %d" % [stage + 1, ceili(left)]
	return super(left)
