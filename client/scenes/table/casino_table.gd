@tool
class_name CasinoTable
extends FloorGame
## What every table game on the casino floor shares: the swept-bay table and
## its seats, the dealer, the chips and cards on the felt, the Jackpot lights,
## the shuffler and discard rack, and the animation queue. A game's table
## (TcpTable, BlackjackTable) extends this and adds its own layout and events.
##
## It renders the server's table: apply_snapshot() draws a `table_state`
## instantly; handle_event() turns each `table_event` into animation, queued so
## they play in order however fast the events arrive. Nothing here decides an
## outcome.
##
## The table is Mike's "swept bay" (picked on the Table Shapes wireframe
## page): straight sides, big rounded dealer corners sweeping down to tight
## player corners that hug the outer seats, and a bay in the dealer's side for
## the dealer to stand in. Seat0..Seat5 markers are where the chairs are (seat
## 0 is first base, the dealer's left, on the right of the screen); each seat's
## spots and cards line up above its marker, so moving a marker in the editor
## moves the whole seat.

signal spot_clicked(spot: String)
signal spot_removed(spot: String)
## The local player's seat finished being paid out (or settled with nothing).
signal my_settle_done
## The local player's hand has a new name or total (for the HUD bar), "" when gone.
signal my_hand_changed(text: String)
## This table's cards have been cleared away (round over).
signal round_cleared

# Table shape (table coordinates; the front edge is at y≈0).
const HALF_W := 156.0                  # felt half-width
const TOP := -140.0                    # dealer's edge
const TOP_CURVE := -2.0                # ...which bows out this much in the middle
const FRONT := 1.0                     # players' edge
const TOP_CORNER := Vector2(91, 90)    # dealer-side corners: across, down
const FRONT_CORNER := Vector2(15, 43)  # player-side corners: across, up
const BAY_W := 31.0                    # the dealer's bay: half width,
const BAY_D := 12.0                    # depth
const BAY_R := 5.0                     # and corner radius
const RAIL := 7.0
const DEALER_Y := -106.5  # dealer's cards: clear of the chip tray, level with the shuffler and discard rack
const TITLE_Y := -88.0
const JACKPOT_Y := -78.0
const SPOT_R := 7.5       # circle spots: a chip (radius 6) plus a sliver of felt
const SEAT_GAP := 49.0
const CHAIR_Y := 40.0
const SEAT_COUNT := 6

## How the game is named on the floor ("Take a seat -- Three Card Poker").
@export var game_label := "Three Card Poker"

var ready_seats := {}
var in_hand := false      # the local player was dealt into this hand
var jackpot_lights := {}  # seat -> "flash" (bet on the disc) | "solid" (locked in)
var _timer_end := 0.0     # betting or decision countdown, in local seconds
var _timer_total := 1.0
var timer_quiet := false  # this countdown doesn't tick (a Rebet's 3 seconds)
var _seat_cards := {}     # seat -> [Card2D]
var _seat_chips := {}     # seat -> {spot: ChipStack2D}
var _payouts := {}        # seat -> [ChipStack2D] (winnings beside the stake)
var _queued := {}         # seat -> {spot: ChipStack2D}: bets for the next hand, put down during this one (faded)
const QUEUED_TINT := Color(1, 1, 1, 0.55)
var _dealer_cards := []

@onready var dealer: Avatar = $Dealer
@onready var _felt: Node2D = $Felt
@onready var _dyn: Node2D = $Felt/Dynamic
@onready var shuffler: CardShuffler = get_node_or_null("Felt/Machines/Shuffler")   # card games only
@onready var discard_rack: DiscardRack = get_node_or_null("Felt/Fixtures/DiscardRack")


func _init() -> void:
	phase = "betting"


func _ready() -> void:
	if Engine.is_editor_hint():
		return
	_dyn.position = -_felt.position  # Dynamic children use table coordinates
	for path in ["Felt/Lights", "Felt/Fixtures", "Felt/Machines"]:  # (Roulette has none of these)
		var layer := get_node_or_null(path) as Node2D
		if layer:
			layer.position = -_felt.position
	_build_collision()


# ------------------------------------------------------------------ what a game provides
## Where a seat's betting spot is.
func spot_pos(seat: int, spot: String) -> Vector2:
	return Vector2(seat_x(seat), -48)


## Where the dealer puts winnings for a spot.
func payout_pos(seat: int, spot: String, _bonus := false) -> Vector2:
	return spot_pos(seat, spot) + Vector2(17, 0)


## The spots a seated player can put chips on, and how close a click must be.
func bet_spots() -> Array:
	return []


func spot_radius(_spot: String) -> float:
	return SPOT_R + 1.0


## The bet that has to be down to play a hand, and spots that are a flat amount.
func main_spot() -> String:
	return ""


func flat_spots() -> Dictionary:
	return {"jackpot": 100}


## Whether a set of bets includes the one a hand needs.
func has_main_bet(bets: Dictionary) -> bool:
	return int(bets.get(main_spot(), 0)) > 0


## The most a set of bets could cost this round (for the "can you afford it" check).
func max_cost(bets: Dictionary) -> int:
	var total := 0
	for spot in bets:
		total += int(bets[spot])
	return total


func zero_bets() -> Dictionary:
	var bets := {}
	for spot in bet_spots():
		bets[spot] = 0
	return bets


## What the seated HUD bar shows and offers. `ctx` has can_bet, has_bets,
## my_ready, my_bets. Returns {info, actions: [{id, label, key}], my_turn}.
func seated_view(ctx: Dictionary) -> Dictionary:
	return {"info": _betting_info(ctx), "actions": [], "my_turn": false}


## The message an action button sends: [type, payload].
func action_message(_id: String) -> Array:
	return []


## True while the local player has a decision to make (standing up asks first).
func deciding() -> bool:
	return false


## What standing up then asks.
func stand_warning() -> String:
	return "You're in this hand -- standing up folds it. Stand up anyway?"


## Whether chips can go down now (Roulette also takes them as the ball spins).
func accepting_bets() -> bool:
	return phase == "betting"


## Whether Ready means anything now (not once Roulette's ball is spinning).
func can_ready() -> bool:
	return phase == "betting"


## Whether someone not in the hand being played can put bets down for the next one (not at Roulette).
func queues_bets() -> bool:
	return true


## Whether the local player can put chips down now: in the betting window, or
## (out of the hand being played) for the next hand.
func can_place_bets() -> bool:
	return accepting_bets() or (queues_bets() and not in_hand)


## A question for the local player as they sit down ({text, yes, no, message: [type, payload]}), or {}.
func on_seated_prompt() -> Dictionary:
	return {}


## What of these bets hasn't been paid for yet (shown off the balance until it is).
func pending_cost(bets: Dictionary) -> int:
	var total := 0
	for spot in bets:
		total += int(bets[spot])
	return total


## Whether the spots pulse while you can bet (not on a layout of 157 spots).
func pulse_spots() -> bool:
	return true


func dealer_card_pos(index: int) -> Vector2:
	return Vector2((index - 1) * 16.0, DEALER_Y)


func _apply_game_snapshot(_state: Dictionary) -> void:
	pass


## Every event, before it's animated: a game's own bookkeeping.
func _note_event(_ev: Dictionary) -> void:
	pass


func _animate_game(_ev: Dictionary, _d: float) -> float:
	return 0.0


func _draw_game(_now: float, _pulse: float) -> void:
	pass


func _countdown_text(left: float) -> String:
	return "BETS CLOSE IN %d" % ceili(left) if phase == "betting" and left > 0 else ""


## Every card still lying on the felt (cleared into the discard rack at the end).
func _cards_on_felt() -> Array:
	var cards := []
	for seat in _seat_cards:
		cards += _seat_cards[seat]
	return cards + _dealer_cards


## After the hand's cards are in the rack (Three Card Poker feeds the shuffler).
func _after_cards_cleared(_d: float) -> void:
	pass


func _betting_info(ctx: Dictionary) -> String:
	var left := ceili(timer_left())
	if ctx.get("my_ready", false):
		return "You're in -- waiting for the deal" if ctx.get("has_bets", false) else "Sitting out this hand"
	if left > 0:
		return "Place your bets -- %ds" % left
	return "Pick a chip, then tap a spot on the felt"


# ------------------------------------------------------------------ geometry
func chair_pos(seat: int) -> Vector2:
	var marker := get_node_or_null("Seat%d" % seat) as Node2D
	if marker:
		return marker.position
	return Vector2(SEAT_GAP * 2.5 - seat * SEAT_GAP, CHAIR_Y)


## Where a seat's column of spots and cards lines up.
func seat_x(seat: int) -> float:
	return chair_pos(seat).x


## The chip tray, set into the rail at the back of the bay: as wide as the bay
## and its rail, its back edge sunk into the rail, its front on the felt.
func tray_rect() -> Rect2:
	return Rect2(-(BAY_W + RAIL), bay_floor() - 3.6, (BAY_W + RAIL) * 2, 14)


func tray_pos() -> Vector2:
	return tray_rect().get_center()


## Where the card shuffler sits (the Shuffler node, movable in the editor).
func shoe_pos() -> Vector2:
	var node := get_node_or_null("Felt/Machines/Shuffler") as Node2D
	return node.position if node else Vector2(98, DEALER_Y - 6)


func discard_pos() -> Vector2:
	var node := get_node_or_null("Felt/Fixtures/DiscardRack") as Node2D
	return node.position if node else Vector2(-98, DEALER_Y - 4)


## The straight part of the dealer's edge (between the corners), ignoring the bay.
static func _edge_y(x: float) -> float:
	var xs := HALF_W - TOP_CORNER.x
	return TOP + TOP_CURVE * (1.0 - minf(1.0, pow(x / xs, 2)))


static func bay_floor() -> float:
	return _edge_y(BAY_W + BAY_R) + BAY_D


## The felt's top edge at x: the bay, the dealer's edge or a dealer corner.
static func top_y(x: float) -> float:
	var ax := absf(x)
	var xs := HALF_W - TOP_CORNER.x
	if ax < BAY_W:
		return bay_floor()
	if ax <= xs:
		return _edge_y(x)
	var dx := minf(ax - xs, TOP_CORNER.x)
	return TOP + TOP_CORNER.y * (1.0 - sqrt(1.0 - pow(dx / TOP_CORNER.x, 2)))


## The felt's outline, clockwise from the top-left corner.
## `detail` sets how many segments each corner gets (lower for collision
## shapes, so the navigation mesh isn't cluttered with tiny edges).
## `bay` false fills the dealer's bay in (for collision: nobody walks into it).
static func outline(detail := 16, bay := true) -> PackedVector2Array:
	var pts := PackedVector2Array()
	var xs := HALF_W - TOP_CORNER.x
	var xf := HALF_W - FRONT_CORNER.x
	var bay_steps := maxi(2, detail / 4)
	var edge_steps := maxi(2, detail / 2)
	var yb := _edge_y(BAY_W + BAY_R)
	var floor_y := yb + BAY_D
	_arc(pts, Vector2(-xs, TOP + TOP_CORNER.y), TOP_CORNER, PI, 1.5 * PI, detail)
	if not bay:
		_edge(pts, -xs, xs, edge_steps * 2)
		_arc(pts, Vector2(xs, TOP + TOP_CORNER.y), TOP_CORNER, 1.5 * PI, 2 * PI, detail)
		_arc(pts, Vector2(xf, FRONT - FRONT_CORNER.y), FRONT_CORNER, 0, 0.5 * PI, maxi(2, detail / 2))
		_arc(pts, Vector2(-xf, FRONT - FRONT_CORNER.y), FRONT_CORNER, 0.5 * PI, PI, maxi(2, detail / 2))
		return pts
	_edge(pts, -xs, -BAY_W - BAY_R, edge_steps)
	# The bay: in, down the left wall, across the back, up the right wall, out.
	_arc(pts, Vector2(-BAY_W - BAY_R, yb + BAY_R), Vector2(BAY_R, BAY_R), -0.5 * PI, 0, bay_steps)
	_arc(pts, Vector2(-BAY_W + BAY_R, floor_y - BAY_R), Vector2(BAY_R, BAY_R), PI, 0.5 * PI, bay_steps)
	_arc(pts, Vector2(BAY_W - BAY_R, floor_y - BAY_R), Vector2(BAY_R, BAY_R), 0.5 * PI, 0, bay_steps)
	_arc(pts, Vector2(BAY_W + BAY_R, yb + BAY_R), Vector2(BAY_R, BAY_R), PI, 1.5 * PI, bay_steps)
	_edge(pts, BAY_W + BAY_R, xs, edge_steps)
	_arc(pts, Vector2(xs, TOP + TOP_CORNER.y), TOP_CORNER, 1.5 * PI, 2 * PI, detail)
	# The straight right side, the front-right corner, the straight front edge...
	_arc(pts, Vector2(xf, FRONT - FRONT_CORNER.y), FRONT_CORNER, 0, 0.5 * PI, maxi(2, detail / 2))
	_arc(pts, Vector2(-xf, FRONT - FRONT_CORNER.y), FRONT_CORNER, 0.5 * PI, PI, maxi(2, detail / 2))
	return pts


static func _arc(pts: PackedVector2Array, centre: Vector2, radii: Vector2, from: float, to: float, steps: int) -> void:
	for i in steps + 1:
		var a := lerpf(from, to, float(i) / steps)
		pts.append(centre + Vector2(cos(a) * radii.x, sin(a) * radii.y))


## The dealer's edge between x0 and x1, leaving out both ends (the arcs either
## side supply those points).
static func _edge(pts: PackedVector2Array, x0: float, x1: float, steps: int) -> void:
	for i in range(1, steps):
		var x := lerpf(x0, x1, float(i) / steps)
		pts.append(Vector2(x, _edge_y(x)))


## The outline grown outwards by `grow` (the rail, its shadow, the collision
## shape, the zone where you can sit down).
static func grown(grow: float, detail := 16, join := Geometry2D.JOIN_ROUND, bay := true) -> PackedVector2Array:
	var polys := Geometry2D.offset_polygon(outline(detail, bay), grow, join)
	return polys[0] if not polys.is_empty() else outline(detail, bay)


func _build_collision() -> void:
	# The rail's outer edge, bay filled in. 8 segments a corner keeps every
	# chord within half a pixel of the drawn rail, so there are no gaps to
	# squeeze through at the corners.
	$Body/Shape.polygon = grown(RAIL + 0.5, 8, Geometry2D.JOIN_MITER, false)
	$SitZone/Shape.polygon = grown(92.0, 4, Geometry2D.JOIN_MITER)


# ------------------------------------------------------------------ state
func apply_snapshot(state: Dictionary) -> void:
	_new_epoch()   # cancel every step still pending from the animations it replaces
	_reset_felt()
	occupants.clear()
	phase = state.get("phase", "betting")
	if state.get("timer") != null:
		_start_timer(float(state.timer))
	var seats: Array = state.get("seats", [])
	in_hand = false
	for i in seats.size():
		var s = seats[i]
		if s == null:
			continue
		occupants[i] = {"entity": s.entity, "name": s.name, "human": s.human}
		if s.get("ready"):
			ready_seats[i] = true
		var locked: bool = phase != "betting"
		for spot in s.get("bets", {}):
			if spot == "jackpot" and locked:
				continue  # lifted off the table when the bets were locked in
			_set_stack(i, spot, int(s.bets[spot]))
		if s.get("queued") != null:
			_show_queued(i, s.queued, 0.0)
		if int(s.get("bets", {}).get("jackpot", 0)) > 0 and s.get("result") == null:
			jackpot_lights[i] = "solid" if locked else "flash"
	if state.get("on_duty") != null:
		_set_dealer(state.on_duty)
	_apply_game_snapshot(state)
	queue_redraw()


## Who's dealing (from the roster; they change on shifts).
func _set_dealer(d: Dictionary) -> void:
	dealer.look = str(d.get("look", "dealer"))
	dealer.display_name = str(d.get("name", "Dealer"))


## Everything off the felt (a snapshot, or a new hand) except `keep`.
func _reset_felt(keep := []) -> void:
	for child in _dyn.get_children():
		if not child in keep:
			child.queue_free()
	_queued.clear()
	_seat_cards.clear()
	_seat_chips.clear()
	_payouts.clear()
	_dealer_cards.clear()
	ready_seats.clear()
	jackpot_lights.clear()


func handle_event(ev: Dictionary) -> void:
	if ev.kind == "settle_seat" and int(ev.seat) == my_seat:
		Session.hold_balance(true)  # show the new balance when the chips reach you
	_queue.append(_animate.bind(ev))


func _process(_delta: float) -> void:
	if Engine.is_editor_hint():
		return
	var now := Time.get_ticks_msec() / 1000.0
	while not _queue.is_empty() and now >= _busy_until:
		var step: Callable = _queue.pop_front()
		var speed := 3.0 if _queue.size() > 6 else 1.0  # catch up if we fell behind
		_busy_until = now + float(step.call(speed)) / speed
	if mode != "" or _timer_end > now or _needs_redraw() or (offer_seats and occupants.size() < seat_count()):
		queue_redraw()


## A game that animates something in its overlay every frame says so here.
func _needs_redraw() -> bool:
	return false


# ------------------------------------------------------------------ events -> animation
## Runs one event's animation; returns how long to wait before the next one.
func _animate(speed: float, ev: Dictionary) -> float:
	var d := 1.0 / speed
	_note_event(ev)
	var sound := _sound_for(ev)
	if sound != "":
		sfx_at(sound, to_global(shoe_pos()))
	match ev.kind:
		"seated":
			occupants[int(ev.seat)] = {"entity": ev.entity, "name": ev.name, "human": ev.human}
			queue_redraw()
			return 0.0
		"stood":
			var seat := int(ev.seat)
			occupants.erase(seat)
			ready_seats.erase(seat)
			if phase == "betting":
				jackpot_lights.erase(seat)
				for spot in _chips_for(seat).keys():
					_take_stack(seat, spot, chair_pos(seat), d)
			for stack in _queued.get(seat, {}).values():
				_fly_and_free(stack, chair_pos(seat), 0.25 * d)
			_queued.erase(seat)
			queue_redraw()
			return 0.0
		"bet_changed":
			if ev.get("queued", false):
				_show_queued(int(ev.seat), ev.bets, d)
			else:
				_show_bets(int(ev.seat), ev.bets, d)
			return 0.05
		"queued_dropped":  # bets put down during the last hand that can't be covered now: back they come
			var dropped := int(ev.seat)
			for spot in _chips_for(dropped).keys():
				_take_stack(dropped, spot, chair_pos(dropped), d)
			return 0.0
		"betting_timer":
			_start_timer(float(ev.seconds), ev.get("quiet", false))
			return 0.0
		"ready":
			ready_seats[int(ev.seat)] = true
			queue_redraw()
			return 0.0
		"bets_closed":
			_timer_end = 0.0
			in_hand = my_seat in ev.seats.map(func(x): return int(x))
			return _lock_jackpots(ev.get("jackpots", []), d)
		"betting_reset":
			_timer_end = 0.0
			return 0.0
		"say":
			dealer.say(ev.text)
			return 0.0
		"dealer_change":  # a fresh dealer takes over: the old one steps away, the new one steps in
			var tw := dealer.create_tween()
			tw.tween_property(dealer, "modulate:a", 0.0, 0.35 * d)
			tw.tween_callback(_set_dealer.bind(ev.dealer))
			tw.tween_property(dealer, "modulate:a", 1.0, 0.35 * d)
			return 0.0
		"round_end":
			round_cleared.emit()
			in_hand = false
			return _return_chips(d)
		"betting_open":
			phase = "betting"
			in_hand = false
			# Bets put down during the last hand stay where they are and count now (the
			# server's bet_changed that follows finds them already there).
			var queued := _queued.duplicate()
			var keep := []
			for seat in queued:
				keep.append_array(queued[seat].values())
			_reset_felt(keep)
			for seat in queued:
				for spot in queued[seat]:
					var stack: ChipStack2D = queued[seat][spot]
					stack.modulate = Color.WHITE
					_chips_for(seat)[spot] = stack
			_queued_promoted(queued.keys())
			my_hand_changed.emit("")
			return 0.0
	return _animate_game(ev, d)


## The sound an event makes as it starts, if any. (Deals sound from the deal
## animations themselves: one swish per batch of cards that leaves together.)
func _sound_for(_ev: Dictionary) -> String:
	return ""


## A swish as cards leave the shoe or shuffler, `delay` seconds from now.
func _deal_sound(delay: float) -> void:
	_after(maxf(delay, 0.0)).timeout.connect(func(): sfx_at("deal", to_global(shoe_pos())))


func _move_card(card: Card2D, place: Array, duration: float, delay := 0.0) -> void:
	var tw := _tween()
	tw.tween_interval(delay)
	tw.tween_property(card, "position", place[0], duration).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tw.parallel().tween_property(card, "rotation", place[1], duration)


## Once every player is settled: all chips still on the felt -- stakes and
## winnings -- slide back to their owners, then the dealer clears the cards.
func _return_chips(d: float) -> float:
	var mine_back := false
	if my_seat >= 0:
		mine_back = _chips_for(my_seat).size() > 0 or _payouts.get(my_seat, []).size() > 0
	for seat in _seat_chips.keys():
		for spot in _seat_chips[seat].keys():
			_take_stack(seat, spot, chair_pos(seat), d)
	for seat in _payouts.keys():
		for stack in _payouts[seat]:
			_fly_and_free(stack, chair_pos(seat), 0.4 * d)
	_payouts.clear()
	if mine_back:
		_after(0.45 * d).timeout.connect(func():
			Session.hold_balance(false)
			my_settle_done.emit())
	elif mode == "seated":   # (only the table you're at holds your balance)
		Session.hold_balance(false)
	_after(0.6 * d).timeout.connect(_clear_cards.bind(d))
	return 2.0 * d


## A settle step on one spot: losing chips to the tray, winnings from the tray
## beside the stake (they stay until the round ends), a push gets a nudge.
func _settle_step(seat: int, step: Dictionary, d: float, payout_at := Vector2.INF) -> void:
	var spot: String = step.spot
	match step.action:
		"collect":
			_take_stack(seat, spot, tray_pos(), d)
		"pay", "bonus":
			var stack := _payout_from_tray(seat, int(step.payout))
			var to := payout_at if payout_at != Vector2.INF else payout_pos(seat, spot, step.action == "bonus")
			_tween().tween_property(stack, "position", to, 0.35 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
		"push":
			var stack: ChipStack2D = _chips_for(seat).get(spot)
			if stack:
				var tw := _tween()
				tw.tween_property(stack, "scale", Vector2(1.25, 1.25), 0.08 * d)
				tw.tween_property(stack, "scale", Vector2.ONE, 0.08 * d)


func _payout_from_tray(seat: int, amount: int) -> ChipStack2D:
	sfx_at("payout", to_global(tray_pos()))
	var stack := _make_stack(seat)
	stack.amount = amount
	stack.position = tray_pos()
	_dyn.add_child(stack)
	_payouts.get_or_add(seat, []).append(stack)
	return stack


## The hand is over: every card left on the felt goes in the discard rack.
func _clear_cards(d: float) -> float:
	for card in _cards_on_felt():
		if is_instance_valid(card):
			_discard(card, d)
	_seat_cards.clear()
	_dealer_cards.clear()
	_after_cards_cleared(d)
	return 1.4 * d


## A used card goes into the discard rack: turned face down (if it isn't
## already) and sideways, onto the top of the stack, where the rack takes over
## drawing it. It stays there until the cards go back through the shuffler.
func _discard(card: Card2D, d: float, delay := 0.0) -> void:
	if card.code != "??":
		card.flip_to("??", 0.16 * d)
	var place := discard_rack.slot(discard_rack.count)
	_dyn.move_child(card, -1)  # over the cards already on the felt
	var tw := card.create_tween()  # the card's own: if a new hand clears the felt mid-flight, it just stops
	tw.tween_interval(delay)
	tw.tween_property(card, "position", place[0], 0.32 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN_OUT)
	tw.parallel().tween_property(card, "rotation", place[1], 0.32 * d)
	tw.tween_callback(func():
		if is_instance_valid(card):  # a new hand may have cleared the felt mid-flight
			discard_rack.count += 1
			card.queue_free())


## The dealer lifts the discards out of the rack (and `extra` cards' worth from
## elsewhere, e.g. what's left in a shoe, from `extra_from`) and feeds them into
## the shuffler's intake a few at a time; the shuffler then shuffles.
func _feed_shuffler(d: float, seconds := 2.2, extra := 0, extra_from := Vector2.ZERO) -> float:
	sfx_at("shuffle", to_global(discard_rack.position))
	var batches := []
	var from_rack := discard_rack.take_all()
	if from_rack > 0:
		batches.append([discard_rack.position, mini(from_rack, 12)])
	if extra > 0:
		batches.append([extra_from, mini(extra, 8)])
	var k := 0
	for batch in batches:
		for i in int(batch[1]):
			var card := _new_card("??", batch[0])
			card.rotation = PI / 2
			var tw := card.create_tween()
			tw.tween_interval(k * 0.05 * d)  # in small batches, from the top of the stack
			tw.tween_property(card, "position", shuffler.intake_point(), 0.35 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
			tw.parallel().tween_property(card, "rotation", 0.0, 0.35 * d)
			tw.tween_callback(card.queue_free)
			k += 1
	var fed := maxi(k - 1, 0) * 0.05 * d + 0.35 * d
	_after(0.15 * d).timeout.connect(shuffler.take_in)
	_after(fed).timeout.connect(shuffler.shuffle.bind(seconds * d))
	return fed


# ------------------------------------------------------------------ chips & cards
func _cards_for(seat: int) -> Array:
	if not _seat_cards.has(seat):
		_seat_cards[seat] = []
	return _seat_cards[seat]


func _chips_for(seat: int) -> Dictionary:
	if not _seat_chips.has(seat):
		_seat_chips[seat] = {}
	return _seat_chips[seat]


## Bets for the next hand, faded on the seat's spots until betting opens.
func _show_queued(seat: int, bets: Dictionary, d: float) -> void:
	var chips: Dictionary = _queued.get_or_add(seat, {})
	var spots := {}
	for spot in chips:
		spots[spot] = true
	for spot in bets:
		spots[spot] = true
	for spot in spots:
		var new := int(bets.get(spot, 0))
		var old := int(chips[spot].amount) if chips.has(spot) else 0
		if new == old:
			continue
		if new <= 0:
			_fly_and_free(chips[spot], chair_pos(seat), 0.25 * d)
			chips.erase(spot)
			continue
		if not chips.has(spot):
			var stack := _make_stack(seat)
			stack.modulate = QUEUED_TINT
			_dyn.add_child(stack)
			chips[spot] = stack
			if d > 0.0:
				stack.position = chair_pos(seat)
				_tween().tween_property(stack, "position", spot_pos(seat, spot), 0.28 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
			else:
				stack.position = spot_pos(seat, spot)
		if new > old and d > 0.0:
			sfx_at("bet", to_global(spot_pos(seat, spot)))
		chips[spot].amount = new


## Bets put down during the last hand have just become this hand's.
func _queued_promoted(_seats: Array) -> void:
	pass


## A new stack of chips for a seat (Roulette's are in the seat's colour).
func _make_stack(_seat: int) -> ChipStack2D:
	return ChipStack2D.new()


func _new_card(code: String, pos: Vector2) -> Card2D:
	var card := Card2D.new()
	card.code = code
	card.position = pos
	card.rotation = 0.0
	_dyn.add_child(card)
	return card


func _set_stack(seat: int, spot: String, amount: int, at := Vector2.INF) -> void:
	var chips := _chips_for(seat)
	if amount <= 0:
		if chips.has(spot):
			chips[spot].queue_free()
			chips.erase(spot)
		return
	if not chips.has(spot):
		var stack := _make_stack(seat)
		stack.position = at if at != Vector2.INF else spot_pos(seat, spot)
		_dyn.add_child(stack)
		chips[spot] = stack
	chips[spot].amount = amount


## Chips worth `amount` slide from `from` onto a seat's spot (or `to`).
func _add_stack_from(seat: int, spot: String, amount: int, from: Vector2, d: float, to := Vector2.INF) -> void:
	var moving := _make_stack(seat)
	moving.amount = amount
	moving.position = from
	_dyn.add_child(moving)
	var total := amount + (int(_chips_for(seat)[spot].amount) if _chips_for(seat).has(spot) else 0)
	var dest := to if to != Vector2.INF else spot_pos(seat, spot)
	var tw := _tween()
	tw.tween_property(moving, "position", dest, 0.28 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tw.tween_callback(func():
		moving.queue_free()
		_set_stack(seat, spot, total, dest))


## A seat's whole stack on `spot` slides to `to` and disappears.
func _take_stack(seat: int, spot: String, to: Vector2, d: float) -> void:
	var chips := _chips_for(seat)
	if not chips.has(spot):
		return
	var stack: ChipStack2D = chips[spot]
	chips.erase(spot)
	if to == tray_pos():  # the dealer sweeping it in
		sfx_at("sweep", stack.global_position)
	_fly_and_free(stack, to, 0.3 * d)


func _fly_and_free(node: Node2D, to: Vector2, duration: float, delay := 0.0) -> void:
	var tw := _tween()
	tw.tween_interval(delay)
	tw.tween_property(node, "position", to, duration).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN_OUT)
	tw.tween_callback(node.queue_free)


func _show_bets(seat: int, bets: Dictionary, d: float) -> void:
	if int(bets.get("jackpot", 0)) > 0:
		jackpot_lights[seat] = "flash"
	else:
		jackpot_lights.erase(seat)
	var chips := _chips_for(seat)
	for spot in bet_spots():
		var new := int(bets.get(spot, 0))
		var old := int(chips[spot].amount) if chips.has(spot) else 0
		if new > old:
			sfx_at("bet", to_global(spot_pos(seat, spot)))
			_add_stack_from(seat, spot, new - old, chair_pos(seat), d)
		elif new < old:
			_set_stack(seat, spot, new)
			var back := _make_stack(seat)
			back.amount = old - new
			back.position = spot_pos(seat, spot)
			_dyn.add_child(back)
			_fly_and_free(back, chair_pos(seat), 0.25 * d)


## No more bets: the dealer presses the button (the Jackpot lights go solid red)
## and lifts the Jackpot chips off the table, leaving just the glowing lights.
func _lock_jackpots(seats: Array, d: float) -> float:
	if seats.is_empty():
		return 0.0
	_after(0.35 * d).timeout.connect(func():
		for seat in seats:
			jackpot_lights[int(seat)] = "solid")
	for k in seats.size():
		_after((0.85 + k * 0.12) * d).timeout.connect(
			_take_stack.bind(int(seats[k]), "jackpot", tray_pos(), d))
	return 1.6 * d


func _start_timer(seconds: float, quiet := false) -> void:
	timer_quiet = quiet
	_timer_total = maxf(seconds, 0.1)
	_timer_end = Time.get_ticks_msec() / 1000.0 + seconds


## Seconds left on the betting/turn countdown (0 when none).
func timer_left() -> float:
	return maxf(0.0, _timer_end - Time.get_ticks_msec() / 1000.0)


# ------------------------------------------------------------------ input
func _unhandled_input(event: InputEvent) -> void:
	if Engine.is_editor_hint() or mode == "":
		return
	if not (event is InputEventMouseButton and event.pressed):
		return
	var p := get_local_mouse_position()
	if mode == "seated" and my_seat >= 0:
		for spot in bet_spots():
			if p.distance_to(spot_pos(my_seat, spot)) < spot_radius(spot):
				if event.button_index == MOUSE_BUTTON_LEFT:
					spot_clicked.emit(spot)
				elif event.button_index == MOUSE_BUTTON_RIGHT:
					spot_removed.emit(spot)
				get_viewport().set_input_as_handled()
				return


# ------------------------------------------------------------------ overlays
func _draw() -> void:
	# Chairs (drawn under everything, so a seated avatar covers them). A free
	# stool glows with SIT on it while the local player is walking the floor.
	var now := Time.get_ticks_msec() / 1000.0
	var pulse := 0.55 + 0.45 * sin(now * 5.0)
	var glowing := free_seats() if offer_seats and not Engine.is_editor_hint() else []
	for seat in seat_count():
		_draw_stool(seat, seat in glowing, pulse)
	if Engine.is_editor_hint():
		return
	if mode == "seated" and my_seat >= 0 and phase == "betting" and pulse_spots():
		for spot in bet_spots():
			draw_arc(spot_pos(my_seat, spot), spot_radius(spot), 0, TAU, 32, Color(1, 1, 1, 0.25 + 0.25 * pulse), 0.8, true)
	for seat in ready_seats:
		var p := chair_pos(seat) + Vector2(13, -12)
		draw_circle(p, 3.5, Color("2e9e4f"))
		draw_polyline(PackedVector2Array([p + Vector2(-1.8, 0), p + Vector2(-0.4, 1.4), p + Vector2(1.9, -1.4)]), Color.WHITE, 0.8)
	_draw_game(now, pulse)
	var countdown := _countdown_text(timer_left())
	if countdown != "":
		var at := countdown_pos()
		draw_string(Card2D.FONT, Vector2(at.x - 45, at.y + 1.75), countdown, HORIZONTAL_ALIGNMENT_CENTER, 90, 5, Color(1, 0.88, 0.5))


## Where the countdown is printed on the felt (under the shuffler at Three Card Poker).
## The band between the dealer's cards and the players' first row of bets holds
## the table's title, centred in it -- and the countdown under the title where
## the band is roomy enough, or else level with the title beside the shuffler.
const DEALER_CARD_BOTTOM := DEALER_Y + 10.0
const ROOMY_BAND := 22.0


func _top_row_y() -> float:
	var top := 0.0
	for spot in bet_spots():
		top = minf(top, spot_pos(0, spot).y - spot_radius(spot))
	return top


func title_y() -> float:
	var mid := (DEALER_CARD_BOTTOM + _top_row_y()) / 2.0
	return mid - 4.0 if _top_row_y() - DEALER_CARD_BOTTOM >= ROOMY_BAND else mid


func countdown_pos() -> Vector2:
	if _top_row_y() - DEALER_CARD_BOTTOM >= ROOMY_BAND:
		return Vector2(0, title_y() + 9.0)
	return Vector2(_countdown_x(), title_y())


func _countdown_x() -> float:
	return 90.0  # clear of the title and inside the felt's curved border


## A ring around a seat's chair: who's thinking, with their time running down.
func _draw_thinking_ring(seat: int, pulse: float) -> void:
	var p := chair_pos(seat) + Vector2(0, -16)
	draw_arc(p, 15.0, 0, TAU, 40, Color(1, 0.85, 0.3, 0.3 + 0.3 * pulse), 1.6, true)
	var left := timer_left()
	if left > 0:
		draw_arc(p, 17.5, -PI / 2, -PI / 2 + TAU * left / _timer_total, 40, Color("ffd54a"), 1.2, true)
