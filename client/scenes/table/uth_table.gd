@tool
class_name UthTable
extends CasinoTable
## An Ultimate Texas Hold'em table: everything shared with the other games
## comes from CasinoTable; this adds the layout (Jackpot disc and Trips circle,
## Ante and Blind side by side, the Play box, two cards per seat; the dealer's
## two cards beside the five community cards) and the round: the deal, then
## three decisions everyone makes at once -- 4x/3x or check before the flop,
## 2x or check after it, 1x or fold after the river -- folds swept, the dealer's
## hand turned over, and each player settled in turn.

const SIDE_Y := -75.5     # Jackpot and Trips
const ANTE_Y := -55.0
const PLAY_Y := -37.0
const CARD_Y := -17.0     # 2 inside the front border
const SPOTS := ["ante", "blind", "trips", "jackpot"]
const STAGE_NAMES := ["Before the flop", "The flop", "The river"]
const STAGE_LABELS := ["PRE-FLOP", "FLOP", "RIVER"]

var stage := 0
var live_seats := {}     # seats still in the hand
var waiting_seats := {}  # seats still to make a Play bet
var decided_seats := {}  # seats that have acted at this stage
var my_ante := 0


# ------------------------------------------------------------------ layout
func bet_spots() -> Array:
	return SPOTS


func spot_radius(spot: String) -> float:
	return 8.0 if spot in ["ante", "blind"] else SPOT_R + 1.0


func spot_shape(seat: int, spot: String) -> Dictionary:
	if spot in ["ante", "blind"]:
		return {"shape": "circle", "at": spot_pos(seat, spot), "r": 8.0}
	return super(seat, spot)


func main_spot() -> String:
	return "ante"


## The Blind goes down with the Ante.
func primary_spots() -> Array:
	return ["ante", "blind"]


func max_cost(b: Dictionary) -> int:
	return int(b.get("ante", 0)) * 6 + int(b.get("trips", 0)) + int(b.get("jackpot", 0))


func spot_pos(seat: int, spot: String) -> Vector2:
	var x := seat_x(seat)
	match spot:
		"jackpot":
			return Vector2(x - 10, SIDE_Y)
		"trips":
			return Vector2(x + 10, SIDE_Y)
		"blind":
			return Vector2(x + 10, ANTE_Y)
		"play":
			return Vector2(x, PLAY_Y)
	return Vector2(x - 10, ANTE_Y)


## Winnings stay in the seat's own column: the Ante's and Blind's either side of
## the Play box, the Play's leaning on its stake (the cards are just below), the
## Trips' beside its circle, the Jackpot's on the (by then empty) disc.
func payout_pos(seat: int, spot: String, _bonus := false) -> Vector2:
	var x := seat_x(seat)
	match spot:
		"jackpot":
			return spot_pos(seat, "jackpot")
		"trips":
			return spot_pos(seat, "trips") + Vector2(11, 0)
		"ante":
			return Vector2(x - 17, PLAY_Y)
		"blind":
			return Vector2(x + 17, PLAY_Y)
	return Vector2(x + 6, PLAY_Y - 3)


func card_pos(seat: int, index: int) -> Vector2:
	return Vector2(seat_x(seat) + (index - 0.5) * 16.0, CARD_Y)


## Indices 0-1 are the dealer's own cards (left of centre), 2-6 the board.
func dealer_card_pos(index: int) -> Vector2:
	if index < 2:
		return Vector2(-64 + index * 15.0, DEALER_Y)
	return Vector2(-30 + (index - 2) * 15.0, DEALER_Y)


const _FOLD_MESS := [[Vector2(-2.0, 1.0), -0.14], [Vector2(2.0, -0.6), 0.12]]

func fold_pile(seat: int, index: int) -> Array:
	var mess: Array = _FOLD_MESS[index % 2]
	return [Vector2(seat_x(seat), CARD_Y) + mess[0], mess[1]]


# ------------------------------------------------------------------ the HUD
func deciding() -> bool:
	return acting_seat() >= 0


## Which of the local player's boxes is still to decide at this stage, or -1: their own first.
func acting_seat() -> int:
	if phase != "deciding":
		return -1
	for seat in my_seats():
		if waiting_seats.has(seat) and not decided_seats.has(seat):
			return seat
	return -1


func seated_view(ctx: Dictionary) -> Dictionary:
	var seat := acting_seat()
	var my_turn := seat >= 0
	var live: Array = my_seats().filter(func(x): return live_seats.has(x))
	var left := ceili(timer_left())
	var info := ""
	match phase:
		"betting":
			info = _betting_info(ctx)
		"dealing":
			info = "Dealing..."
		"deciding":
			if my_turn:
				info = box_prefix(seat) + "%s -- %ds" % [STAGE_NAMES[stage], left]
			elif not live.is_empty():
				info = "Waiting for the others" if live.any(func(x): return waiting_seats.has(x)) \
					else ("Your Play bets are down" if live.size() > 1 else "Your Play bet's down")
			elif in_hand:
				info = "You've folded"
			else:
				info = "Watching this hand"
	var actions := []
	if my_turn:
		var ante := my_ante if my_ante > 0 else int(ctx.get("my_bets", {}).get("ante", 0))
		match stage:
			0:
				actions = [_bet(4, ante), _bet(3, ante), {"id": "check", "label": "Check  [Backspace]", "key": "Backspace"}]
			1:
				actions = [_bet(2, ante), {"id": "check", "label": "Check  [Backspace]", "key": "Backspace"}]
			_:
				actions = [_bet(1, ante), {"id": "fold", "label": "Fold  [Backspace]", "key": "Backspace"}]
	return {"info": info, "actions": actions, "my_turn": my_turn}


## A bet of `times` the ante: Space for the smallest on offer (3x preflop), its number otherwise.
func _bet(times: int, ante: int) -> Dictionary:
	var key := "Space" if times == [3, 2, 1][mini(stage, 2)] else str(times)
	return {"id": "bet%d" % times, "label": "Bet %dx %s  [%s]" % [times, Money.format(ante * times, true), key], "key": key}


func action_message(id: String) -> Array:
	return ["act", {"action": id, "seat": acting_seat()}]


# ------------------------------------------------------------------ snapshot
func _apply_game_snapshot(state: Dictionary) -> void:
	live_seats.clear()
	waiting_seats.clear()
	decided_seats.clear()
	stage = int(state.get("stage", 0))
	var seats: Array = state.get("seats", [])
	for i in seats.size():
		var s = seats[i]
		if s == null:
			continue
		if int(s.get("play", 0)) > 0:
			_set_stack(i, "play", int(s.play))
		var cards: Array = s.get("cards", [])
		if cards.is_empty() or s.get("result") != null:
			continue
		if is_mine(i):
			in_hand = true
			my_ante = int(s.get("bets", {}).get("ante", 0))
		if not s.get("folded"):
			live_seats[i] = true
			if int(s.get("play", 0)) == 0:
				waiting_seats[i] = true
			if s.get("decided"):
				decided_seats[i] = true
		for k in cards.size():
			var card := _new_card(cards[k], card_pos(i, k))
			if s.get("folded"):
				card.code = "??"
				var place := fold_pile(i, k)
				card.position = place[0]
				card.rotation = place[1]
			_cards_for(i).append(card)
	var dealer: Array = state.get("dealer", {}).get("cards", [])
	var board: Array = state.get("community", [])
	for k in dealer.size():
		_dealer_cards.append(_new_card(dealer[k], dealer_card_pos(k)))
	for k in board.size():
		_dealer_cards.append(_new_card(board[k], dealer_card_pos(2 + k)))


# ------------------------------------------------------------------ events -> animation
func _note_event(ev: Dictionary) -> void:
	if ev.kind == "betting_open":
		live_seats.clear()
		waiting_seats.clear()
		decided_seats.clear()
		stage = 0
		my_ante = 0
	if ev.kind == "bets_closed":
		live_seats.clear()
		waiting_seats.clear()
		decided_seats.clear()
		for seat in ev.seats:
			live_seats[int(seat)] = true
			waiting_seats[int(seat)] = true
		if my_seat >= 0 and live_seats.has(my_seat):
			my_ante = int(_chips_for(my_seat)["ante"].amount) if _chips_for(my_seat).has("ante") else 0
	_note_hands(ev, func(seat): return live_seats.has(seat))


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
		"uth_action":
			return _action(ev, d)
		"community":
			return _community(ev, d)
		"fold_sweep":
			return _fold_sweep(ev, d)
		"dealer_reveal":
			return _dealer_reveal(ev, d)
		"settle_seat":
			return _settle(ev, d)
	return 0.0


## The deal, hand by hand out of the shuffler: two cards to each seat, two to
## the dealer, then the five community cards, all face down.
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
			var target: Vector2
			if who == "dealer":
				target = dealer_card_pos(indices[k])
			elif who == "community":
				target = dealer_card_pos(2 + indices[k])
			else:
				target = card_pos(int(who), indices[k])
			var card := _new_card("??", shuffler.slot_point())
			card.visible = false
			if who == "dealer" or who == "community":
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
		total += 0.3 * d
	return total


## A Play bet (chips onto the Play box), a check (a knock -- nothing moves) or
## a fold (the cards go face down in a messy pile).
func _action(ev: Dictionary, d: float) -> float:
	var seat := int(ev.seat)
	decided_seats[seat] = true
	match str(ev.action):
		"bet4", "bet3", "bet2", "bet1":
			waiting_seats.erase(seat)
			_add_stack_from(seat, "play", int(ev.amount), chair_pos(seat), d)
		"fold":
			waiting_seats.erase(seat)
			live_seats.erase(seat)
			if is_mine(seat):
				_show_hand(seat, "")
			var cards := _cards_for(seat)
			for k in cards.size():
				_move_card(cards[k], fold_pile(seat, k), 0.28 * d, k * 0.05 * d)
				_after((0.12 + k * 0.05) * d).timeout.connect(cards[k].set.bind("code", "??"))
	return 0.1 * d


## The flop, or the turn and river together.
func _community(ev: Dictionary, d: float) -> float:
	phase = "revealing"
	_timer_end = 0.0
	var first := int(ev.from)
	var codes: Array = ev.cards
	for k in codes.size():
		var index := 2 + first + k
		if index < _dealer_cards.size():
			_after(k * 0.2 * d).timeout.connect(_dealer_cards[index].flip_to.bind(codes[k], 0.3 * d))
	return (0.5 + 0.2 * codes.size()) * d


func _fold_sweep(ev: Dictionary, d: float) -> float:
	phase = "sweeping"
	_timer_end = 0.0
	var pause := float(ev.get("pause", 1.0)) * d
	var t := pause
	for entry in ev.seats:
		var seat := int(entry.seat)
		var k := 0
		for step in entry.steps:
			_after(t + k * 0.1 * d).timeout.connect(_take_stack.bind(seat, step.spot, tray_pos(), d))
			k += 1
		_after(t).timeout.connect(func(): jackpot_lights.erase(seat))
		_after(t + k * 0.1 * d).timeout.connect(func():
			for card in _cards_for(seat):
				_discard(card, d)
			_seat_cards.erase(seat))
		t += 0.5 * d + pause
	return t - pause + 0.2 * d


## The dealer turns their two cards (the announcement is a `say` that follows).
func _dealer_reveal(ev: Dictionary, d: float) -> float:
	phase = "reveal"
	for k in mini(2, _dealer_cards.size()):
		_after(k * 0.15 * d).timeout.connect(_dealer_cards[k].flip_to.bind(ev.cards[k], 0.3 * d))
	dealer_label = str(ev.hand)
	return 0.9 * d


func _settle(ev: Dictionary, d: float) -> float:
	phase = "settling"
	var seat := int(ev.seat)
	var pause := float(ev.get("pause", 1.0)) * d
	var cards := _cards_for(seat)
	var codes: Array = ev.get("cards", [])
	for k in mini(cards.size(), codes.size()):
		_move_card(cards[k], [card_pos(seat, k), 0.0], 0.3 * d)
		_after((0.32 + k * 0.05) * d).timeout.connect(cards[k].flip_to.bind(codes[k], 0.28 * d))
	var t := 0.65 * d
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


var dealer_label := ""

func _after_cards_cleared(d: float) -> void:
	dealer_label = ""
	_after(0.6 * d).timeout.connect(func(): _feed_shuffler(d))


# ------------------------------------------------------------------ overlays
func _needs_redraw() -> bool:
	return phase == "deciding" or dealer_label != ""


func _draw_game(_now: float, pulse: float) -> void:
	if phase == "deciding":
		for seat in waiting_seats:
			if not decided_seats.has(seat) and occupants.has(seat):
				_draw_thinking_ring(seat, pulse)
	if dealer_label != "":  # the dealer's hand, under their two cards
		var at := dealer_card_pos(0) + Vector2(7.5, 13.5)
		var w := Card2D.FONT.get_string_size(dealer_label, HORIZONTAL_ALIGNMENT_LEFT, -1, 4).x + 4.0
		draw_rect(Rect2(at - Vector2(w / 2, 3), Vector2(w, 6)), Color(0.08, 0.04, 0.02, 0.85))
		draw_string(Card2D.FONT, at + Vector2(-w / 2 + 2, 1.5), dealer_label, HORIZONTAL_ALIGNMENT_LEFT, -1, 4, Color("f1e4c4"))


func _countdown_text(left: float) -> String:
	if phase == "deciding" and left > 0:
		return "%s  %d" % [STAGE_LABELS[stage], ceili(left)]
	return super(left)
