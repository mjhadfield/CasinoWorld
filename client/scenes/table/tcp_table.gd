@tool
class_name TcpTable
extends CasinoTable
## A Three Card Poker table: everything shared with the other games comes from
## CasinoTable; this adds the layout (Jackpot disc, Pair Plus and Prime, Ante
## diamond, Play box per seat) and the round: hands out of the shuffler three
## cards at a time, everyone deciding at once, folds swept, the dealer's hand
## turned over, then each player settled in turn.

## The local player's cards have been dealt and turned over (for the HUD's big view).
signal my_cards_shown(cards: Array, hand: String)

const SIDE_Y := -63.0     # Pair Plus and Prime
const ANTE_Y := -48.0
const PLAY_Y := -33.0
const CARD_Y := -16.0
const SPOTS := ["ante", "pair_plus", "prime", "jackpot"]

var decided_seats := {}  # seats that have acted this hand
var round_seats := []    # seats dealt into this hand
var my_decided := false


# ------------------------------------------------------------------ layout
func bet_spots() -> Array:
	return SPOTS


func spot_radius(spot: String) -> float:
	return SPOT_R + 1.0 if spot != "ante" else 10.5


## The Ante is a diamond.
func spot_shape(seat: int, spot: String) -> Dictionary:
	if spot == "ante":
		return {"shape": "diamond", "at": spot_pos(seat, spot), "hw": 9.0, "hh": 7.5}
	return super(seat, spot)


func main_spot() -> String:
	return "ante"


func max_cost(b: Dictionary) -> int:
	return int(b.get("ante", 0)) * 2 + int(b.get("pair_plus", 0)) + int(b.get("prime", 0)) + int(b.get("jackpot", 0))


func spot_pos(seat: int, spot: String) -> Vector2:
	var x := seat_x(seat)
	match spot:
		"jackpot":
			return Vector2(x, JACKPOT_Y)
		"pair_plus":
			return Vector2(x - 9.5, SIDE_Y)
		"prime":
			return Vector2(x + 9.5, SIDE_Y)
		"ante":
			return Vector2(x, ANTE_Y)
		"play":
			return Vector2(x, PLAY_Y)
	return Vector2(x, ANTE_Y)


## Where the dealer puts winnings for a spot. Each seat's winnings stay
## inside its own column, so neighbours' never overlap and the outer seats'
## stay on the felt: Pair Plus and Prime winnings go diagonally above their
## circles (either side of the Jackpot disc), the Ante's beside the diamond
## (the Ante bonus on the other side), the Play's beside the box, and the
## Jackpot's on the disc itself -- it's empty once the bets are locked in.
func payout_pos(seat: int, spot: String, bonus := false) -> Vector2:
	var x := seat_x(seat)
	match spot:
		"jackpot":
			return spot_pos(seat, "jackpot")
		"pair_plus":
			return Vector2(x - 17, JACKPOT_Y)
		"prime":
			return Vector2(x + 17, JACKPOT_Y)
		"ante":
			return Vector2(x + (-17.0 if bonus else 17.0), ANTE_Y)
	return Vector2(x + 17.5, PLAY_Y)


func card_pos(seat: int, index: int) -> Vector2:
	return Vector2(seat_x(seat) + (index - 1) * 15.0, CARD_Y)


## A played hand: face down, turned sideways, squarely on the Play box (the Play
## bet goes on top). Returns [position, rotation].
func play_pile(seat: int, index: int) -> Array:
	return [spot_pos(seat, "play") + Vector2(index * 0.4, -index * 0.4), PI / 2]


## A fold held under a winning Prime bet: the same, under the Prime circle.
func prime_pile(seat: int, index: int) -> Array:
	return [spot_pos(seat, "prime") + Vector2(index * 0.4, -index * 0.4), PI / 2]


const _FOLD_MESS := [[Vector2(-2.5, 1.0), -0.14], [Vector2(0.5, -0.8), 0.05], [Vector2(2.5, 0.6), 0.17]]

## A folded hand: a slightly messy face-down pile where the cards were dealt,
## pushed forward a touch (it's gathered FOLD_SLIDE lower, then slides up here).
const FOLD_SLIDE := 4.0

func fold_pile(seat: int, index: int) -> Array:
	var mess: Array = _FOLD_MESS[index % 3]
	return [Vector2(seat_x(seat), CARD_Y) + mess[0], mess[1]]


# ------------------------------------------------------------------ the HUD
func deciding() -> bool:
	return in_hand and not my_decided


func seated_view(ctx: Dictionary) -> Dictionary:
	var my_turn := phase == "deciding" and in_hand and not my_decided  # everyone decides at once
	var left := ceili(timer_left())
	var info := ""
	match phase:
		"betting":
			info = _betting_info(ctx)
		"dealing":
			info = "Dealing..."
		"deciding":
			if my_turn:
				info = "Play or fold? -- %ds" % left
			elif in_hand:
				info = "Waiting for the others to decide"
			else:
				info = "Watching this hand"
	var actions := []
	if my_turn:
		var ante := int(ctx.get("my_bets", {}).get("ante", 0))
		actions = [{"id": "play", "label": "Play %s  [P]" % Money.format(ante, true), "key": "P"},
			{"id": "fold", "label": "Fold  [F]", "key": "F"}]
	return {"info": info, "actions": actions, "my_turn": my_turn}


func action_message(id: String) -> Array:
	return ["decide", {"play": id == "play"}]


# ------------------------------------------------------------------ snapshot
func _apply_game_snapshot(state: Dictionary) -> void:
	decided_seats.clear()
	round_seats.clear()
	my_decided = false
	var seats: Array = state.get("seats", [])
	for i in seats.size():
		var s = seats[i]
		if s == null:
			continue
		if not s.get("cards", []).is_empty():
			round_seats.append(i)
			if i == my_seat:
				in_hand = true
			if s.get("decided"):
				decided_seats[i] = true
				if i == my_seat:
					my_decided = true
		var cards: Array = s.get("cards", [])
		for k in cards.size():
			var card := _new_card(cards[k], card_pos(i, k))
			if s.get("decided"):  # until their settle, a decided hand lies face down where they put it
				card.code = "??"
				var place: Array = play_pile(i, k)
				if s.get("folded"):
					place = prime_pile(i, k) if s.get("held") else fold_pile(i, k)
				card.position = place[0]
				card.rotation = place[1]
			_cards_for(i).append(card)
	var dealer_codes: Array = state.get("dealer", {}).get("cards", [])
	for k in dealer_codes.size():
		_dealer_cards.append(_new_card(dealer_codes[k], dealer_card_pos(k)))


# ------------------------------------------------------------------ events -> animation
func _note_event(ev: Dictionary) -> void:
	if ev.kind in ["bets_closed", "betting_open"]:
		my_decided = false
		decided_seats.clear()
	if ev.kind == "betting_open":
		round_seats.clear()


func _animate_game(ev: Dictionary, d: float) -> float:
	match ev.kind:
		"dealt":
			return _deal(ev, d)
		"decisions_open":
			phase = "deciding"
			round_seats = ev.seats.map(func(x): return int(x))
			decided_seats.clear()
			_start_timer(float(ev.seconds))
			return 0.0
		"decision":
			decided_seats[int(ev.seat)] = true
			if int(ev.seat) == my_seat:
				my_decided = true
				if not ev.play:
					my_hand_changed.emit("")
			return _decision(ev, d)
		"fold_sweep":
			return _fold_sweep(ev, d)
		"dealer_reveal":
			return _dealer_reveal(ev, d)
		"settle_seat":
			return _settle(ev, d)
	return 0.0


## The deal: hand by hand (three cards at a time, first base first, the
## dealer's own hand last), each hand comes out of the shuffler's delivery
## slot as a packet, rests there a moment, then flies across to its place.
func _deal(ev: Dictionary, d: float) -> float:
	phase = "dealing"
	ready_seats.clear()
	_timer_end = 0.0
	var order: Array = ev.order
	var interval := float(ev.interval) * d
	var hand_pause := float(ev.get("hand_pause", 0.0)) * d
	var hands: Array = []  # [[who, [card index, ...]], ...] in deal order
	for entry in order:
		if hands.is_empty() or str(hands[-1][0]) != str(entry[0]):
			hands.append([entry[0], []])
		hands[-1][1].append(int(entry[1]))
	var start := 0.0
	var hand_time := 0.0
	for h in hands.size():
		var who = hands[h][0]
		var indices: Array = hands[h][1]
		hand_time = indices.size() * interval + hand_pause
		start = h * hand_time
		_after(start).timeout.connect(shuffler.deliver)
		_deal_sound(start + 0.38 * d)  # the packet leaves the machine together: one swish for the three
		for k in indices.size():
			var target := dealer_card_pos(indices[k]) if str(who) == "dealer" else card_pos(int(who), indices[k])
			var card := _new_card("??", shuffler.slot_point())  # inside the machine, under its lid
			card.visible = false
			if str(who) == "dealer":
				_dealer_cards.append(card)
			else:
				_cards_for(int(who)).append(card)
			var tw := _tween()
			tw.tween_interval(start + k * 0.03 * d)
			tw.tween_callback(card.show)
			# Out of the delivery slot onto the felt in front of the machine...
			tw.tween_property(card, "position", shuffler.delivery_point() + Vector2(k * 0.5, -k * 0.5), 0.2 * d) \
				.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
			# ...a moment there as a packet, then across to its place.
			tw.tween_interval((0.18 + k * 0.01) * d)  # so the packet leaves together, 0.04s apart
			tw.tween_property(card, "position", target, 0.26 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	var total := start + 0.72 * d + 0.25 * d
	var mine = ev.get("mine")
	if mine != null and my_seat >= 0:
		var cards := _cards_for(my_seat)
		for k in cards.size():
			_after(total + k * 0.12 * d).timeout.connect(cards[k].flip_to.bind(mine.cards[k], 0.22 * d))
		_after(total + 0.5 * d).timeout.connect(func():
			my_cards_shown.emit(mine.cards, mine.hand)
			my_hand_changed.emit(mine.hand))
	return total


func _decision(ev: Dictionary, d: float) -> float:
	var seat := int(ev.seat)
	var cards := _cards_for(seat)
	for k in cards.size():
		var place: Array
		if ev.play:
			place = play_pile(seat, k)       # face down on the Play box...
		elif ev.get("held", false):
			place = prime_pile(seat, k)      # ...under a winning Prime...
		else:
			place = fold_pile(seat, k)       # ...or a messy folded pile, slid forward a touch
			var gathered: Array = [place[0] + Vector2(0, FOLD_SLIDE), place[1]]
			_move_card(cards[k], gathered, 0.28 * d, k * 0.05 * d)
			_move_card(cards[k], place, 0.25 * d, (0.45 + k * 0.03) * d)
			_after((0.12 + k * 0.05) * d).timeout.connect(cards[k].set.bind("code", "??"))
			continue
		_move_card(cards[k], place, 0.28 * d, k * 0.05 * d)
		_after((0.12 + k * 0.05) * d).timeout.connect(cards[k].set.bind("code", "??"))
	if ev.play:  # the Play bet goes on top of the cards
		_after(0.4 * d).timeout.connect(
			_add_stack_from.bind(seat, "play", int(ev.amount), chair_pos(seat), d))
	return 0.1 * d


## Once everyone has decided: the dealer takes the folded hands and their bets
## (a fold held under a winning Prime keeps its cards and the Prime) -- one
## hand at a time, with a pause before the first and between each.
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
		if entry.muck:
			_after(t + k * 0.1 * d).timeout.connect(func():
				for card in _cards_for(seat):
					_discard(card, d)
				_seat_cards.erase(seat))
		t += 0.5 * d + pause
	return t - pause + 0.2 * d


## The dealer turns their own cards over (the announcement is a `say` that follows).
func _dealer_reveal(ev: Dictionary, d: float) -> float:
	phase = "reveal"
	for k in _dealer_cards.size():
		_after(k * 0.12 * d).timeout.connect(_dealer_cards[k].flip_to.bind(ev.cards[k], 0.3 * d))
	return 0.9 * d


## Settle one player: their cards slide out from under the bet back to where
## they were dealt and are turned over, and the dealer announces the hand.
## A pause; then losing bets are swept and winnings placed beside the stakes
## (where they stay until the whole table is settled, see _return_chips); the
## cards are cleared away last. Another pause before the next player.
func _settle(ev: Dictionary, d: float) -> float:
	phase = "settling"
	var seat := int(ev.seat)
	var pause := float(ev.get("pause", 1.0)) * d
	var cards := _cards_for(seat)
	for k in cards.size():
		_move_card(cards[k], [card_pos(seat, k), 0.0], 0.3 * d)
		_after((0.32 + k * 0.05) * d).timeout.connect(cards[k].flip_to.bind(ev.cards[k], 0.28 * d))
	var t := 0.65 * d
	if str(ev.get("say", "")) != "":
		_after(t).timeout.connect(dealer.say.bind(ev.say, 2.0 + pause * 2))
	t += pause
	var steps: Array = ev.steps
	var ordered := steps.filter(func(x): return x.action == "collect") + steps.filter(func(x): return x.action != "collect")
	for step in ordered:  # losing bets swept first, then winners paid
		_after(t).timeout.connect(_settle_step.bind(seat, step, d))
		t += 0.45 * d
	_after(t).timeout.connect(func():  # the cards go last
		for card in _cards_for(seat):
			_discard(card, d)
		_seat_cards.erase(seat)
		jackpot_lights.erase(seat))
	t += 0.4 * d
	return t + pause + 0.05 * d


## The hand's over and its cards are in the rack: the dealer feeds them into
## the shuffler, ready for the next hand.
func _after_cards_cleared(d: float) -> void:
	_after(0.6 * d).timeout.connect(func(): _feed_shuffler(d))


# ------------------------------------------------------------------ overlays
func _needs_redraw() -> bool:
	return phase == "deciding"


func _draw_game(_now: float, pulse: float) -> void:
	if phase == "deciding":  # everyone decides at once: a ring on each player still thinking
		for seat in round_seats:
			if not decided_seats.has(seat) and occupants.has(seat):
				_draw_thinking_ring(seat, pulse)


func _countdown_text(left: float) -> String:
	if phase == "deciding" and left > 0:
		return "DECIDE  %d" % ceili(left)
	return super(left)
