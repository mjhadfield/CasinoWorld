@tool
class_name MsTable
extends CasinoTable
## A Mississippi Stud table: everything shared with the other games comes from
## CasinoTable; this adds the layout (Jackpot disc and 3 Card Bonus circle, the
## Ante, a row of 3rd/4th/5th Street circles, two cards per seat) and the
## round: two cards to each seat out of the shuffler, three community cards
## face down in front of the dealer, then three streets where everyone folds
## or bets 1x-3x at once, folds are swept and the next community card turned,
## and finally each player settled in turn.

const SIDE_Y := -74.5     # Jackpot and 3 Card Bonus
const ANTE_Y := -57.5
const STREET_Y := -37.5
const CARD_Y := -17.0     # 2 inside the front border
const STREET_R := 6.5
const SPOTS := ["ante", "bonus", "jackpot"]
const STREETS := ["third", "fourth", "fifth"]
const STREET_NAMES := ["3rd Street", "4th Street", "5th Street"]
const STREET_LABELS := ["3RD", "4TH", "5TH"]

var street := 0
var live_seats := {}     # seats still in this hand
var decided_seats := {}  # seats that have acted this street
var my_ante := 0


# ------------------------------------------------------------------ layout
func bet_spots() -> Array:
	return SPOTS


func spot_radius(spot: String) -> float:
	if spot == "ante":
		return 9.5
	return STREET_R if spot in STREETS else SPOT_R + 1.0


func spot_shape(seat: int, spot: String) -> Dictionary:
	if spot == "ante":
		return {"shape": "circle", "at": spot_pos(seat, spot), "r": 9.0}
	return super(seat, spot)


func main_spot() -> String:
	return "ante"


func max_cost(b: Dictionary) -> int:
	return int(b.get("ante", 0)) * 10 + int(b.get("bonus", 0)) + int(b.get("jackpot", 0))


func spot_pos(seat: int, spot: String) -> Vector2:
	var x := seat_x(seat)
	match spot:
		"jackpot":
			return Vector2(x - 10, SIDE_Y)
		"bonus":
			return Vector2(x + 10, SIDE_Y)
		"third":
			return Vector2(x - 15, STREET_Y)
		"fourth":
			return Vector2(x, STREET_Y)
		"fifth":
			return Vector2(x + 15, STREET_Y)
	return Vector2(x, ANTE_Y)


## Where the dealer puts each bet's winnings, inside the seat's own column:
## the Ante's beside it, the Bonus's beside its circle, each street's just
## below its circle, the Jackpot's on the (by then empty) disc.
func payout_pos(seat: int, spot: String, _bonus := false) -> Vector2:
	match spot:
		"jackpot":
			return spot_pos(seat, "jackpot")
		"bonus":
			return spot_pos(seat, "bonus") + Vector2(11, 0)
		"third", "fourth", "fifth":  # a second stack leaning on the stake: no room below, the cards are there
			return spot_pos(seat, spot) + Vector2(4.5, -5.5)
	return spot_pos(seat, "ante") + Vector2(17, 0)


func card_pos(seat: int, index: int) -> Vector2:
	return Vector2(seat_x(seat) + (index - 0.5) * 16.0, CARD_Y)


const _FOLD_MESS := [[Vector2(-2.0, 1.0), -0.14], [Vector2(2.0, -0.6), 0.12]]

## A folded hand: a slightly messy face-down pile where the cards were dealt.
func fold_pile(seat: int, index: int) -> Array:
	var mess: Array = _FOLD_MESS[index % 2]
	return [Vector2(seat_x(seat), CARD_Y) + mess[0], mess[1]]


# ------------------------------------------------------------------ the HUD
func deciding() -> bool:
	return acting_seat() >= 0


## Which of the local player's boxes is still to decide this street, or -1: their own first.
func acting_seat() -> int:
	if phase != "deciding":
		return -1
	for seat in my_seats():
		if live_seats.has(seat) and not decided_seats.has(seat):
			return seat
	return -1


func seated_view(ctx: Dictionary) -> Dictionary:
	var seat := acting_seat()
	var my_turn := seat >= 0
	var live := my_seats().any(func(x): return live_seats.has(x))
	var left := ceili(timer_left())
	var info := ""
	match phase:
		"betting":
			info = _betting_info(ctx)
		"dealing":
			info = "Dealing..."
		"deciding":
			if my_turn:
				info = box_prefix(seat) + "%s -- %ds" % [STREET_NAMES[street], left]
			elif live:
				info = "Waiting for the others"
			elif in_hand:
				info = "You've folded"
			else:
				info = "Watching this hand"
		"sweeping", "revealing":
			info = "" if in_hand else "Watching this hand"
	var actions := []
	if my_turn:
		var ante := my_ante if my_ante > 0 else int(ctx.get("my_bets", {}).get("ante", 0))
		actions = [{"id": "fold", "label": "Fold  [F]", "key": "F"}]
		for times in [1, 2, 3]:
			actions.append({"id": "bet%d" % times, "label": "%dx %s  [%d]" % [times, Money.format(ante * times, true), times],
				"key": str(times)})
	return {"info": info, "actions": actions, "my_turn": my_turn}


func action_message(id: String) -> Array:
	return ["act", {"action": id, "seat": acting_seat()}]


# ------------------------------------------------------------------ snapshot
func _apply_game_snapshot(state: Dictionary) -> void:
	live_seats.clear()
	decided_seats.clear()
	street = int(state.get("street", 0))
	var seats: Array = state.get("seats", [])
	for i in seats.size():
		var s = seats[i]
		if s == null:
			continue
		var streets: Array = s.get("streets", [0, 0, 0])
		for k in streets.size():
			if int(streets[k]) > 0:
				_set_stack(i, STREETS[k], int(streets[k]))
		var cards: Array = s.get("cards", [])
		if cards.is_empty() or s.get("result") != null:
			continue
		if is_mine(i):
			in_hand = true
			my_ante = int(s.get("bets", {}).get("ante", 0))
		if not s.get("folded"):
			live_seats[i] = true
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
	var community: Array = state.get("community", [])
	for k in community.size():
		_dealer_cards.append(_new_card(community[k], dealer_card_pos(k)))


# ------------------------------------------------------------------ events -> animation
func _note_event(ev: Dictionary) -> void:
	if ev.kind in ["bets_closed", "betting_open"]:
		decided_seats.clear()
	if ev.kind == "betting_open":
		live_seats.clear()
		street = 0
		my_ante = 0
	if ev.kind == "bets_closed":
		live_seats.clear()
		for seat in ev.seats:
			live_seats[int(seat)] = true
		if my_seat >= 0 and live_seats.has(my_seat):
			my_ante = int(_chips_for(my_seat)["ante"].amount) if _chips_for(my_seat).has("ante") else 0
	_note_hands(ev, func(seat): return live_seats.has(seat))


func _animate_game(ev: Dictionary, d: float) -> float:
	match ev.kind:
		"dealt":
			return _deal(ev, d)
		"decisions_open":
			phase = "deciding"
			street = int(ev.street)
			decided_seats.clear()
			_start_timer(float(ev.seconds))
			return 0.0
		"street_bet":
			return _street_bet(ev, d)
		"fold_sweep":
			return _fold_sweep(ev, d)
		"community":
			return _community(ev, d)
		"settle_seat":
			return _settle(ev, d)
		"bonus_settle":
			return _bonus_settle(ev, d)
	return 0.0


func handle_event(ev: Dictionary) -> void:
	if ev.kind == "bonus_settle" and ev.seats.any(func(e): return is_mine(int(e.seat))):
		Session.hold_balance(true)  # show the new balance when the chips reach you
	super(ev)


## The deal: hand by hand (two cards at a time, first base first), each comes
## out of the shuffler as a packet, rests a moment, then flies to its place;
## the three community cards come last, face down in front of the dealer.
func _deal(ev: Dictionary, d: float) -> float:
	phase = "dealing"
	ready_seats.clear()
	_timer_end = 0.0
	var interval := float(ev.interval) * d
	var hand_pause := float(ev.get("hand_pause", 0.0)) * d
	var hands: Array = []  # [[who, [card index, ...]], ...] in deal order
	for entry in ev.order:
		if hands.is_empty() or str(hands[-1][0]) != str(entry[0]):
			hands.append([entry[0], []])
		hands[-1][1].append(int(entry[1]))
	var start := 0.0
	for h in hands.size():
		var who = hands[h][0]
		var indices: Array = hands[h][1]
		var community := str(who) == "community"
		_after(start).timeout.connect(shuffler.deliver)
		_deal_sound(start + 0.38 * d)  # the packet leaves the machine together: one swish
		for k in indices.size():
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
	if mine != null and my_seat >= 0:  # you look at your own two cards
		var cards := _cards_for(my_seat)
		for k in cards.size():
			_after(total + k * 0.12 * d).timeout.connect(cards[k].flip_to.bind(mine.cards[k], 0.22 * d))
		total += 0.3 * d
	return total


## Fold (the cards go face down in a messy pile) or a bet of 1x-3x the Ante
## on this street's circle.
func _street_bet(ev: Dictionary, d: float) -> float:
	var seat := int(ev.seat)
	decided_seats[seat] = true
	if int(ev.times) > 0:
		_add_stack_from(seat, STREETS[int(ev.street)], int(ev.amount), chair_pos(seat), d)
		return 0.1 * d
	live_seats.erase(seat)
	if is_mine(seat):
		_show_hand(seat, "")
	var cards := _cards_for(seat)
	for k in cards.size():
		_move_card(cards[k], fold_pile(seat, k), 0.28 * d, k * 0.05 * d)
		_after((0.12 + k * 0.05) * d).timeout.connect(cards[k].set.bind("code", "??"))
	return 0.1 * d


## After a street: the dealer takes the folded hands (cards, Ante, street
## bets and Jackpot; a 3 Card Bonus stays) -- one at a time, with a pause
## before the first and between each.
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


## The dealer turns the next community card (or every one left, after a
## table-wide fold), and your hand's name updates.
func _community(ev: Dictionary, d: float) -> float:
	phase = "revealing"
	_timer_end = 0.0
	var first := int(ev.from)
	var codes: Array = ev.cards
	for k in codes.size():
		var index := first + k
		if index < _dealer_cards.size():
			_after(k * 0.35 * d).timeout.connect(_dealer_cards[index].flip_to.bind(codes[k], 0.3 * d))
	return (0.6 + 0.35 * codes.size()) * d


## Settle one player: their cards turned over and the hand announced, a
## pause, losing bets swept and winners paid beside their stakes, the cards
## cleared last. A fold with a Bonus riding just has the Bonus settled.
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
	for step in ev.steps:  # the server lists losing bets first, then pushes and winners
		_after(t).timeout.connect(_settle_step.bind(seat, step, d))
		t += 0.45 * d
	_after(t).timeout.connect(func():
		for card in _cards_for(seat):
			_discard(card, d)
		_seat_cards.erase(seat)
		jackpot_lights.erase(seat))
	t += 0.4 * d
	return t + pause + 0.05 * d


## Every folded hand's 3 Card Bonus at once -- they all ride on the same
## community cards: one announcement, then each swept or paid together.
func _bonus_settle(ev: Dictionary, d: float) -> float:
	phase = "settling"
	var pause := float(ev.get("pause", 0.9)) * d
	if str(ev.get("say", "")) != "":
		dealer.say(ev.say, 2.0 + pause)
	for entry in ev.seats:
		for step in entry.steps:
			_after(pause * 0.6).timeout.connect(_settle_step.bind(int(entry.seat), step, d))
	return pause * 0.6 + 0.6 * d


func _after_cards_cleared(d: float) -> void:
	_after(0.6 * d).timeout.connect(func(): _feed_shuffler(d))


# ------------------------------------------------------------------ overlays
func _needs_redraw() -> bool:
	return phase == "deciding"


func _draw_game(_now: float, pulse: float) -> void:
	if phase == "deciding":  # everyone decides at once: a ring on each player still thinking
		for seat in live_seats:
			if not decided_seats.has(seat) and occupants.has(seat):
				_draw_thinking_ring(seat, pulse)


func _countdown_text(left: float) -> String:
	if phase == "deciding" and left > 0:
		return "%s  %d" % [STREET_LABELS[street] + " STREET", ceili(left)]
	return super(left)
