@tool
class_name PaiGowTable
extends CasinoTable
## A Pai Gow Poker table -- Fortune Pai Gow, or Face Up Pai Gow with
## `face_up` on. Everything shared with the other games comes from
## CasinoTable; this adds the layout and the round.
##
## The shuffler's display shows a number from 1 to 7: counting the dealer as 1
## and the seats from first base as 2-7, that position gets the first of seven
## 7-card hands, out of the shuffler one packet at a time; hands for empty
## seats go straight to the discard rack. Players' packets lie face down until
## they're picked up: yours goes into the sorter (HandSorter, in the HUD),
## where you set your Low and High hands; once set, each player's cards go back
## down face down: the Low hand upright in the LOW box, the High hand sideways
## in the HIGH box below it. The dealer's hand is revealed (Fortune: once all
## have set; Face Up: straight after the deal): all seven turned over as dealt,
## then sorted, then the two Low cards pushed forward and slid off to the left.
## Each player is then settled from third base: their hands turned over and
## fanned in their column, losers swept, winnings paid. After a Face Up dealer
## Ace-high Pai Gow, players claim a side-bet win or fold instead of setting.
##
## Each seat, top to bottom: the Jackpot disc and the Fortune circle (with an
## ENVY button when £5+ is on it), the Ante circle, the upright
## LOW box and the sideways HIGH box.

## Your packet has been picked up: open the sorter with these cards.
signal sort_requested(cards: Array)
## Your hand is set (or folded, or claimed): close the sorter.
signal sort_finished
## A Face Up dealer Ace-high Pai Gow: claim your side-bet win (`bonus`) or fold.
signal claim_requested(cards: Array, bonus)

const ANTE_Y := -59.5
const ANTE_R := 9.5
const LOW_BOX := Vector2(18, 24)    # upright, for the Low hand (and the dealt packet)...
const LOW_Y := -36.0
const HIGH_BOX := Vector2(26, 16)   # ...sideways below it, for the High hand
const HIGH_Y := -14.0
const MARK_GAP := 0.45              # the beat between the cards turning over and each hand's mark
const MARK_BUMP := 0.3              # how long a mark takes to pop in
const ENVY_MIN := 500               # a Fortune bet this big qualifies for the Envy Bonus
const ENVY_OFFSET := Vector2(9.5, 8.0)  # where its ENVY button sits, off the Fortune circle's lower right
const SPOTS := ["ante", "fortune", "jackpot"]

@export var face_up := false

var _piles := {}          # seat -> {all: [Card2D], low: [Card2D], high: [Card2D]}
var _dealer_low: Array = []
var _dealer_high: Array = []
var dealer_label := ""
var setting_seats := {}   # seats still setting
var my_set := false
var _results := {}        # seat -> {"front"/"back": [won, shown at]} as settled (the little win/lose marks)
var _bump_until := 0.0    # a mark is still popping in until then
var claim_seats := {}     # Face Up Ace-high push: seats still to claim or fold
var _my_cards: Array = [] # your seven, as dealt


# ------------------------------------------------------------------ layout
func bet_spots() -> Array:
	return SPOTS


func spot_radius(spot: String) -> float:
	return ANTE_R if spot == "ante" else SPOT_R + 1.0


func main_spot() -> String:
	return "ante"


func spot_pos(seat: int, spot: String) -> Vector2:
	var x := seat_x(seat)
	match spot:
		"jackpot":
			return Vector2(x - 9.5, JACKPOT_Y)
		"fortune":
			return Vector2(x + 9.5, JACKPOT_Y)
		"envy":
			return Vector2(x - 20.5, -65)
	return Vector2(x, ANTE_Y)


func payout_pos(seat: int, spot: String, _bonus := false) -> Vector2:
	match spot:
		"jackpot":
			return spot_pos(seat, "jackpot")
		"fortune":
			return spot_pos(seat, spot) + Vector2(11, 0)
		"envy":
			return spot_pos(seat, "envy")
	return spot_pos(seat, "ante") + Vector2(17, 0)


func box_pos(seat: int, which: String) -> Vector2:
	return Vector2(seat_x(seat), HIGH_Y if which == "high" else LOW_Y)


## Where a seat's hand lands from the shuffler: between the LOW and HIGH boxes,
## half over each, until it's set.
func deal_pos(seat: int) -> Vector2:
	return Vector2(seat_x(seat), (LOW_Y + HIGH_Y) / 2)


## A face-down pile: each card a hair off the one below (the High hand lies sideways).
func _pile_pos(at: Vector2, k: int) -> Vector2:
	return at + Vector2(k * 0.35, -k * 0.35)


## A hand as it comes out of the shuffler: seven cards dropped in a loose,
## messy pile -- each a little off and askew. [position, rotation]; the same for
## the same place and card, so a snapshot rebuilds the pile as it was.
func _messy_pos(at: Vector2, k: int) -> Array:
	var rng := RandomNumberGenerator.new()
	rng.seed = hash([snappedf(at.x, 1), snappedf(at.y, 1), k])
	var jitter := Vector2(rng.randf_range(-3.0, 3.0), rng.randf_range(-2.5, 2.5))
	return [at + jitter + Vector2(0, -k * 0.3), rng.randf_range(-0.35, 0.35)]


func _new_messy_card(at: Vector2, k: int) -> Card2D:
	var place := _messy_pos(at, k)
	var card := _new_card("??", place[0])
	card.rotation = place[1]
	return card


## A hand turned over at its settle, fanned in the seat's own column: the Low
## hand over its box, the High hand below.
func _fan_pos(seat: int, which: String, k: int, count: int) -> Vector2:
	var step := 8.0 if which == "low" else 7.0
	return Vector2(seat_x(seat) + (k - (count - 1) / 2.0) * step, HIGH_Y if which == "high" else LOW_Y)


func dealer_pile_pos() -> Vector2:
	return Vector2(0, DEALER_Y)


## The dealer's seven in a row, as they're turned over and sorted...
func _dealer_row_pos(k: int) -> Vector2:
	return Vector2(-32 + k * 9.0, DEALER_Y)


## ...and once set: the Low hand off to the left, the High hand beside it.
func _dealer_fan_pos(which: String, k: int) -> Vector2:
	return Vector2(-46 + k * 9.0, DEALER_Y) if which == "low" else Vector2(-14 + k * 9.0, DEALER_Y)


# ------------------------------------------------------------------ the HUD
func deciding() -> bool:
	return in_hand and phase in ["dealing", "setting", "claiming"] and not my_set


func seated_view(ctx: Dictionary) -> Dictionary:
	var left := ceili(timer_left())
	var info := ""
	match phase:
		"betting":
			info = _betting_info(ctx)
		"dealing":
			info = "Dealing..."
		"setting":
			if in_hand and not my_set:
				info = "Set your hand -- %ds" % left
			else:
				info = "Waiting for the others to set" if in_hand else "Watching this hand"
		"dealer":
			info = "The dealer sets their hand"
		"claiming":
			info = ("Ace-high Pai Gow: your Ante pushes -- %ds" % left) if claim_seats.has(my_seat) \
				else "Ace-high Pai Gow: every Ante pushes"
	return {"info": info, "actions": [], "my_turn": false}


# ------------------------------------------------------------------ snapshot
func _apply_game_snapshot(state: Dictionary) -> void:
	_piles.clear()
	_dealer_low.clear()
	_dealer_high.clear()
	_results.clear()
	setting_seats.clear()
	dealer_label = ""
	my_set = false
	claim_seats.clear()
	var seats: Array = state.get("seats", [])
	var my_cards: Array = []
	var my_bonus = null
	for i in seats.size():
		var s = seats[i]
		if s == null or s.get("hand") == null:
			continue
		var hand: Dictionary = s.hand
		if i == my_seat:
			in_hand = true
		var pile := _new_pile(i)
		for k in 7:
			pile.all.append(_new_messy_card(deal_pos(i), k))
		match hand.state:
			"set":
				_split_pile(i, 0.0, true)
				if i == my_seat:
					my_set = true
			"folded":
				_fold_pile(i, 0.0, true)
				if i == my_seat:
					my_set = true
			"claimed":
				if i == my_seat:
					my_set = true
			_:
				if phase == "claiming":
					claim_seats[i] = true
				else:
					setting_seats[i] = true
				if i == my_seat:
					my_cards = hand.get("cards", [])
					my_bonus = hand.get("bonus")
	var dealer: Dictionary = state.get("dealer", {})
	if dealer.get("shown", false):
		_reveal_dealer(dealer, 0.0, true)
	elif not dealer.get("cards", []).is_empty():
		for k in 7:
			_dealer_cards.append(_new_messy_card(dealer_pile_pos(), k))
	if not my_cards.is_empty() and phase == "setting":
		_pick_up(my_cards)
	elif not my_cards.is_empty() and phase == "claiming":
		claim_requested.emit(my_cards, my_bonus)


func _new_pile(seat: int) -> Dictionary:
	_piles[seat] = {"all": [], "low": [], "high": []}
	return _piles[seat]


func _cards_on_felt() -> Array:
	var cards := []
	for seat in _piles:
		cards += _piles[seat].all
	return cards + _dealer_cards


# ------------------------------------------------------------------ events -> animation
func _note_event(ev: Dictionary) -> void:
	if ev.kind in ["bets_closed", "betting_open"]:
		my_set = false
		_results.clear()
		dealer_label = ""
	if ev.kind == "betting_open":
		_piles.clear()
		_dealer_low.clear()
		_dealer_high.clear()
		setting_seats.clear()
		claim_seats.clear()


func _animate_game(ev: Dictionary, d: float) -> float:
	match ev.kind:
		"dealt":
			return _deal(ev, d)
		"ace_high_pai_gow":
			return 0.6 * d
		"claim_open":
			phase = "claiming"
			claim_seats.clear()
			for seat in ev.seats:
				claim_seats[int(seat)] = true
			_start_timer(float(ev.seconds))
			var mine = ev.get("mine")
			if mine != null and my_seat >= 0 and _piles.has(my_seat):
				claim_requested.emit(_my_cards, mine.get("bonus"))
			return 0.0
		"claimed":
			var seat := int(ev.seat)
			claim_seats.erase(seat)
			if seat == my_seat:
				my_set = true
				sort_finished.emit()
			if not ev.claimed and _piles.has(seat):
				_fold_pile(seat, d)
			return 0.2 * d
		"setting_open":
			phase = "setting"
			setting_seats.clear()
			for seat in ev.seats:
				setting_seats[int(seat)] = true
			_start_timer(float(ev.seconds))
			return 0.0
		"hand_set":
			return _hand_set(ev, d)
		"dealer_set":
			phase = "dealer"
			_timer_end = 0.0
			return _reveal_dealer(ev, d)
		"settle_seat":
			return _settle(ev, d)
	return 0.0


## The shuffler shows its number, then seven 7-card packets come out one at a
## time from that position on: to each player, to the dealer, or (an empty
## seat) straight to the discard rack.
func _deal(ev: Dictionary, d: float) -> float:
	phase = "dealing"
	ready_seats.clear()
	_timer_end = 0.0
	shuffler.show_number(int(ev.start), 3.0 * d)
	var interval := float(ev.interval) * d
	var t := 0.7 * d
	var mine = ev.get("mine")
	var unclaimed := []  # hands dealt to empty seats: cleared to the rack once the deal's done
	for k in ev.order.size():
		var who = ev.order[k]
		_after(t).timeout.connect(shuffler.deliver)
		_deal_sound(t + 0.26 * d)  # the hand leaves the machine together: one swish for the seven
		var target := Vector2.ZERO
		var pile: Dictionary = {}
		if who == null:  # an empty seat still gets its hand, at its box, like a real deal
			var place_no: int = (int(ev.start) - 1 + k) % 7 + 1  # 1 is the dealer, 2-7 are seats 0-5
			target = deal_pos(place_no - 2)
		elif str(who) == "dealer":
			target = dealer_pile_pos()
		else:
			pile = _new_pile(int(who))
			target = deal_pos(int(who))
		for i in 7:
			var card := _new_card("??", shuffler.slot_point())
			card.visible = false
			var tw := _tween()
			tw.tween_interval(t + i * 0.012 * d)
			tw.tween_callback(card.show)
			tw.tween_property(card, "position", shuffler.delivery_point() + Vector2(i * 0.3, -i * 0.3), 0.16 * d)
			tw.tween_interval(0.1 * d)
			var place := _messy_pos(target, i)
			tw.tween_property(card, "position", place[0], 0.24 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
			tw.parallel().tween_property(card, "rotation", place[1], 0.24 * d)
			if who == null:
				unclaimed.append(card)
				continue
			if str(who) == "dealer":
				_dealer_cards.append(card)
			else:
				pile.all.append(card)
		t += interval
	var total := t + 0.4 * d
	if not unclaimed.is_empty():  # the deal's done: the empty seats' hands go in the rack
		_after(total).timeout.connect(func():
			var n := 0
			for card in unclaimed:
				if is_instance_valid(card):
					_discard(card, d, n * 0.025 * d)
					n += 1)
		# ...and nothing else happens (the reveal, picking your hand up) till the last is in.
		total += ((unclaimed.size() - 1) * 0.025 + 0.32 + 0.2) * d
	if mine != null:
		_my_cards = mine.cards
	if face_up and ev.has("dealer"):  # the dealer's hand is revealed before anyone sets theirs
		var reveal := ev.dealer as Dictionary
		_after(total).timeout.connect(func(): _reveal_dealer(reveal, d))
		total += 3.1 * d
	if mine != null and my_seat >= 0 and _piles.has(my_seat) and not ev.get("ace_high", false):
		_after(total).timeout.connect(_pick_up.bind(mine.cards))
	return total + 0.2 * d


## You pick your cards up: they leave the felt and open in the sorter.
func _pick_up(cards: Array) -> void:
	if not _piles.has(my_seat):
		return
	for card in _piles[my_seat].all:
		card.visible = false
	sort_requested.emit(cards)


## The dealer's hand is revealed: all seven turned over in the order they were
## dealt; a pause; sorted high to low; a pause; then the two Low cards pushed
## forward a touch and slid off to the left as their own hand. Returns how long
## that takes (the announcement follows it).
func _reveal_dealer(dealer: Dictionary, d: float, instant := false) -> float:
	if _dealer_cards.is_empty():
		for k in 7:
			_dealer_cards.append(_new_messy_card(dealer_pile_pos(), k))
	var codes: Array = dealer.get("cards", [])
	var front: Array = dealer.get("front", [])
	var sorted := codes.duplicate()
	sorted.sort_custom(func(a, b): return Card2D.rank_value(a) > Card2D.rank_value(b))
	var high := sorted.filter(func(c): return c not in front)
	var low := sorted.filter(func(c): return c in front)
	_dealer_low.clear()
	_dealer_high.clear()
	for k in _dealer_cards.size():
		var card: Card2D = _dealer_cards[k]
		var code: String = codes[k]
		var is_low := code in low
		(_dealer_low if is_low else _dealer_high).append(card)
		var final := _dealer_fan_pos("low", low.find(code)) if is_low else _dealer_fan_pos("high", high.find(code))
		if instant:
			card.position = final
			card.rotation = 0.0
			card.code = code
			continue
		var tw := card.create_tween()
		# Turned over, in the order dealt.
		tw.tween_interval(k * 0.06 * d)
		tw.tween_property(card, "position", _dealer_row_pos(k), 0.25 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
		tw.parallel().tween_property(card, "rotation", 0.0, 0.25 * d)  # straightened out of the pile
		tw.tween_callback(card.flip_to.bind(code, 0.18 * d))
		# A pause; sorted.
		tw.tween_interval((1.0 - k * 0.06) * d)
		tw.tween_property(card, "position", _dealer_row_pos(sorted.find(code)), 0.35 * d).set_trans(Tween.TRANS_QUAD)
		# A pause; the Low hand pushed forward, then off to the left (the High closes up).
		tw.tween_interval(0.55 * d)
		if is_low:
			tw.tween_property(card, "position", _dealer_row_pos(sorted.find(code)) + Vector2(0, 5), 0.2 * d)
			tw.tween_property(card, "position", final + Vector2(0, 5), 0.35 * d).set_trans(Tween.TRANS_QUAD)
			tw.tween_property(card, "position", final, 0.15 * d)
		else:
			tw.tween_interval(0.2 * d)
			tw.tween_property(card, "position", final, 0.35 * d).set_trans(Tween.TRANS_QUAD)
	var label := "%s / %s" % [dealer.get("front_label", ""), dealer.get("back_label", "")]  # low / high
	if instant:
		_restack(_dealer_low + _dealer_high)
		dealer_label = label
		return 0.0
	# Each card drawn over the one to its left, so every corner index shows:
	# as dealt, then as sorted (when they slide into order), then as set.
	var by_sorted := _dealer_cards.duplicate()
	by_sorted.sort_custom(func(a, b): return sorted.find(codes[_dealer_cards.find(a)]) < sorted.find(codes[_dealer_cards.find(b)]))
	var by_final := _dealer_low.duplicate()
	by_final.sort_custom(func(a, b): return low.find(codes[_dealer_cards.find(a)]) < low.find(codes[_dealer_cards.find(b)]))
	var high_final := _dealer_high.duplicate()
	high_final.sort_custom(func(a, b): return high.find(codes[_dealer_cards.find(a)]) < high.find(codes[_dealer_cards.find(b)]))
	by_final += high_final
	_restack(_dealer_cards)
	_after(1.43 * d).timeout.connect(_restack.bind(by_sorted))
	_after(2.33 * d).timeout.connect(_restack.bind(by_final))
	_after(2.9 * d).timeout.connect(func(): dealer_label = label)
	return 3.0 * d


## Draws these cards in this order, each over the one before.
func _restack(cards: Array) -> void:
	for card in cards:
		if is_instance_valid(card):
			_dyn.move_child(card, -1)


func _hand_set(ev: Dictionary, d: float) -> float:
	var seat := int(ev.seat)
	setting_seats.erase(seat)
	if not _piles.has(seat):
		return 0.0
	if seat == my_seat:
		my_set = true
		for card in _piles[seat].all:  # back down on the felt
			card.visible = true
		sort_finished.emit()
		var mine = ev.get("mine")
		if mine != null:
			my_hand_changed.emit("Low: %s  ·  High: %s" % [mine.front_label, mine.back_label])
		elif ev.folded:
			my_hand_changed.emit("Folded")
	if ev.folded:
		_fold_pile(seat, d)
	else:
		_split_pile(seat, d)
	return 0.25 * d


## A set hand goes down as two face-down piles: two cards in LOW, five in HIGH.
func _split_pile(seat: int, d: float, instant := false) -> void:
	var pile: Dictionary = _piles[seat]
	pile.low = pile.all.slice(0, 2)
	pile.high = pile.all.slice(2)
	for which in ["low", "high"]:
		var cards: Array = pile[which]
		var rot := PI / 2 if which == "high" else 0.0  # the High hand lies sideways in its box
		for k in cards.size():
			var to := _pile_pos(box_pos(seat, which), k)
			if instant:
				cards[k].position = to
				cards[k].rotation = rot
			else:
				_move_card(cards[k], [to, rot], 0.25 * d, k * 0.02 * d)


## Face Up: a folded hand is pushed forward in an untidy pile.
func _fold_pile(seat: int, d: float, instant := false) -> void:
	var cards: Array = _piles[seat].all
	for k in cards.size():
		var to := [Vector2(seat_x(seat) + sin(k * 2.1) * 2.5, LOW_Y - 6 + cos(k * 1.7) * 1.5), sin(k * 3.3) * 0.2]
		if instant:
			cards[k].position = to[0]
			cards[k].rotation = to[1]
		else:
			_move_card(cards[k], to, 0.3 * d, k * 0.03 * d)


## Settle one player: their hands turned over and fanned in their column, the
## dealer's verdict, losing bets swept and winnings placed; the cards go last.
func _settle(ev: Dictionary, d: float) -> float:
	phase = "settling"
	var seat := int(ev.seat)
	var pause := float(ev.get("pause", 0.9)) * d
	if _piles.has(seat):
		var pile: Dictionary = _piles[seat]
		if ev.has("front"):
			var hands := {"low": [pile.low, ev.front], "high": [pile.high, ev.back]}
			for which in hands:
				var cards: Array = hands[which][0]
				var codes: Array = hands[which][1]
				for k in cards.size():
					var card: Card2D = cards[k]
					card.visible = true
					_move_card(card, [_fan_pos(seat, which, k, cards.size()), 0.0], 0.3 * d, k * 0.03 * d)
					_after((0.3 + k * 0.04) * d).timeout.connect(card.flip_to.bind(codes[k], 0.2 * d))
		elif not ev.cards.is_empty():  # never set (a fold, or an Ace-high claim): the seven in one row for the bonus
			var cards: Array = pile.all
			for k in cards.size():
				var card: Card2D = cards[k]
				card.visible = true
				_move_card(card, [Vector2(seat_x(seat) + (k - 3) * 6.0, HIGH_Y), 0.0], 0.3 * d, k * 0.03 * d)
				_after((0.3 + k * 0.04) * d).timeout.connect(card.flip_to.bind(ev.cards[k], 0.2 * d))
	var t := 0.75 * d
	if ev.has("front"):  # once the cards are over: a beat, the Low hand's mark pops in, a beat, then the High's
		t += MARK_GAP * d
		_after(t).timeout.connect(_show_mark.bind(seat, "front", ev.front_win))
		t += MARK_GAP * d
		_after(t).timeout.connect(_show_mark.bind(seat, "back", ev.back_win))
	_after(t).timeout.connect(func():
		if str(ev.get("say", "")) != "":
			dealer.say(ev.say, 2.0 + pause * 2))
	t += pause
	for step in ev.steps:  # losing bets swept first, then winners paid
		_after(t).timeout.connect(_settle_step.bind(seat, step, d))
		t += 0.45 * d
	_after(t).timeout.connect(func():  # the cards go last
		if _piles.has(seat):
			var k := 0
			for card in _piles[seat].all:
				_discard(card, d, k * 0.03 * d)
				k += 1
			_piles.erase(seat)
		_results.erase(seat)
		jackpot_lights.erase(seat))
	t += 0.4 * d
	return t + pause


## The deck goes back through the shuffler after every hand.
func _after_cards_cleared(d: float) -> void:
	_dealer_low.clear()
	_dealer_high.clear()
	dealer_label = ""
	_piles.clear()
	_after(0.6 * d).timeout.connect(func(): _feed_shuffler(d))


# ------------------------------------------------------------------ overlays
func _needs_redraw() -> bool:
	return phase in ["setting", "claiming"] or Time.get_ticks_msec() / 1000.0 < _bump_until


func _draw_game(now: float, pulse: float) -> void:
	for seat in (setting_seats if phase == "setting" else claim_seats if phase == "claiming" else {}):
		if occupants.has(seat):
			_draw_thinking_ring(seat, pulse)
	# A settled player's hands: a little tick or cross beside each (won/lost against the dealer).
	for seat in _results:
		var r: Dictionary = _results[seat]
		if r.has("front"):
			_mark(Vector2(seat_x(seat) + 12.0, LOW_Y - 8.0), r.front[0], _bump(now - r.front[1]))
		if r.has("back"):
			_mark(Vector2(seat_x(seat) + 19.0, HIGH_Y - 8.0), r.back[0], _bump(now - r.back[1]))
	# An ENVY button beside a Fortune bet big enough for the Envy Bonus.
	for seat in _seat_chips:
		var fortune: ChipStack2D = _seat_chips[seat].get("fortune")
		if fortune != null and is_instance_valid(fortune) and int(fortune.amount) >= ENVY_MIN:
			_envy_button(spot_pos(seat, "fortune") + ENVY_OFFSET)
	if dealer_label != "" and not _dealer_high.is_empty() and is_instance_valid(_dealer_high[-1]):
		_label_pill(_dealer_high[-1].position + Vector2(9, -9), dealer_label)


## The little round green ENVY button, half a chip across.
func _envy_button(at: Vector2) -> void:
	var r := ChipStack2D.RADIUS / 2.0
	draw_circle(at + Vector2(0.3, 0.4), r, Color(0, 0, 0, 0.3))
	draw_circle(at, r, Color("2e9e4f"))
	draw_arc(at, r - 0.25, 0, TAU, 24, Color("9be3a9"), 0.4, true)
	# Lettering 1.5 units tall, laid out large and scaled down (as on the chips) so it sits dead centre.
	var big := ChipButton.LABEL_SIZE
	var width := Card2D.FONT.get_string_size("ENVY", HORIZONTAL_ALIGNMENT_LEFT, -1, big).x
	draw_set_transform(at, 0, Vector2.ONE * 1.5 / big)
	draw_string(Card2D.FONT, Vector2(-width / 2, big * ChipButton.DIGIT_HEIGHT / 2), "ENVY", HORIZONTAL_ALIGNMENT_LEFT, -1, big, Color.WHITE)
	draw_set_transform(Vector2.ZERO)


## A settled hand's tick (won) or cross (lost), drawn at `size` (it bumps in from nothing).
func _mark(at: Vector2, won: bool, size := 1.0) -> void:
	if size <= 0.0:
		return
	draw_set_transform(at, 0, Vector2(size, size))
	draw_circle(Vector2.ZERO, 2.6, Color("2e9e4f") if won else Color("b3261e"))
	if won:
		draw_polyline(PackedVector2Array([Vector2(-1.3, 0), Vector2(-0.3, 1.0), Vector2(1.4, -1.0)]), Color.WHITE, 0.6)
	else:
		draw_line(Vector2(-1, -1), Vector2(1, 1), Color.WHITE, 0.6)
		draw_line(Vector2(1, -1), Vector2(-1, 1), Color.WHITE, 0.6)
	draw_set_transform(Vector2.ZERO)


## One hand's mark pops into place.
func _show_mark(seat: int, which: String, won: bool) -> void:
	if not _results.has(seat):
		_results[seat] = {}
	_results[seat][which] = [won, Time.get_ticks_msec() / 1000.0]
	var at := Vector2(seat_x(seat) + 12.0, LOW_Y - 8.0) if which == "front" else Vector2(seat_x(seat) + 19.0, HIGH_Y - 8.0)
	sfx_at("result", to_global(at))
	_bump_until = Time.get_ticks_msec() / 1000.0 + MARK_BUMP


## The pop: from nothing, overshooting a little, settling at full size (an ease-out-back).
static func _bump(age: float) -> float:
	var k := clampf(age / MARK_BUMP, 0.0, 1.0) - 1.0
	return 1.0 + 2.7 * k * k * k + 1.7 * k * k


func _label_pill(at: Vector2, text: String) -> void:
	var font := Card2D.FONT
	var width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 4).x + 3.0
	var r := Rect2(at - Vector2(0, 3), Vector2(width, 6))
	draw_rect(r, Color(0.05, 0.03, 0.02, 0.82))
	draw_rect(r, Color(1, 0.88, 0.5, 0.5), false, 0.3)
	draw_string(font, Vector2(r.position.x + 1.5, at.y + 1.45), text, HORIZONTAL_ALIGNMENT_LEFT, -1, 4, Color(1, 0.95, 0.8))


func _countdown_text(left: float) -> String:
	if phase == "setting" and left > 0:
		return "SET HANDS  %d" % ceili(left)
	if phase == "claiming" and left > 0:
		return "CLAIMS  %d" % ceili(left)
	return super(left)
