@tool
class_name RouTable
extends CasinoTable
## The roulette table (single zero, La Partage): a long table rounded at the
## wheel end, with a bay in the far side where the dealer stands between the
## wheel and the layout; the float (for paying winners) and the chip hole (where
## losing chips go) either side of the bay; and the results sign standing at the
## other end. Signed off on Mike's Roulette mockup (v6).
##
## One layout for the whole table: every seat bets on the same 157 spots, so
## each seat has its own colour of chips, and several seats' stacks on one spot
## fan out so every colour shows. Hovering the layout lights up the numbers a
## bet would cover: the middle of a box is a straight up, a side a split, a
## corner a corner, the bottom edge of the 1-4-7 row a street (between two
## streets, a six line), the zero's edge the 0 splits, trios and first four.
##
## The round: chips go down ("Spinning in ..."), and keep going down as the ball
## goes round ("Final bets!") until just before it reaches the pockets; "No more
## bets", the ball lands, the dolly goes on the number,
## losing chips fly down the hole, winners are paid from the float beside their
## stakes, everything goes back to the players, the dolly comes off.

# The table (table coordinates: the players' edge of the felt is y = 0).
const FELT_LEFT := -168.0
const FELT_RIGHT := 168.0
const FELT_TOP := -114.0
const FELT_FRONT := 0.0
const RAIL_W := 9.0
const CORNER_WHEEL := 37.0       # the felt's corners at the wheel end...
const CORNER_FAR := 11.0         # ...and the other end
const BAY_X := -56.0             # the dealer's bay: centre,
const BAY_HALF := 29.0           # half its width at the felt,
const BAY_FLOOR := -101.0        # how far into the table it reaches,
const BAY_CORNER := 5.0          # and its corners
# What's on it.
const WHEEL_AT := Vector2(-118, -52)
const FLOAT_AT := Vector2(-112, -105.5)
const HOLE_AT := Vector2(-16, -105)
const HOLE_R := 6.5
const TITLE_AT := Vector2(108, -106)
# The layout: the zero box points at the wheel, the 1-4-7 row nearest the players.
const ZX := -66.0
const GX := -52.0
const GY := -90.0
const BW := 16.0
const BH := 19.0
const DY := GY + 3 * BH
const DH := 13.0
const EY := DY + DH
const EH := 13.0
const EVENS := ["low", "even", "red", "black", "odd", "high"]
const RED := [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
const EDGE := 4.0                # how near a line counts as on it
const SEAT_COLOURS := [Color("5ab0e8"), Color("f2c14e"), Color("ef7aa0"), Color("5fd3a0"), Color("a98ef2"), Color("e8935a")]

static var _bets := {}           # bet id -> {name, numbers, pays}

var hover_spot := ""             # the bet under the pointer while you can bet
var chip_value := 100            # the chip you've picked (its ghost follows the pointer)
var dolly := -1                  # the number the dolly's on (-1: none)
var result_text := ""
var _dolly_drop := 0.0           # when the dolly went down (it drops in)

@onready var wheel: RouletteWheel = $Felt/Wheel
@onready var sign_board: RouletteSign = $Sign


func _ready() -> void:
	super._ready()
	if Engine.is_editor_hint():
		return
	$Felt/Wheel.position = WHEEL_AT - _felt.position
	wheel.ball_sound.connect(_ball_sound)


## The ball landing: the skid's clatter, repeated while the skid lasts, and a click
## for every hop (quieter for a little one) until it's settled in its pocket.
func _ball_sound(kind: String, value: float) -> void:
	var at := to_global(WHEEL_AT)
	if kind == "hop":
		sfx_at("ball_hop", at, lerpf(-14.0, 0.0, value))
		return
	var t := 0.0
	while t == 0.0 or t < value - 1.2:   # the clip is ~1.8s: again every 1.6s (a seamless clatter) while the skid lasts
		_after(t).timeout.connect(func(): sfx_at("ball_rattle", at))
		t += 1.6


# ------------------------------------------------------------------ the bets
static func bets() -> Dictionary:
	if _bets.is_empty():
		var add := func(id: String, name: String, numbers: Array):
			_bets[id] = {"name": name, "numbers": numbers, "pays": 36 / numbers.size() - 1}
		for n in 37:
			add.call("n%d" % n, "Straight up %d" % n, [n])
		for k in [1, 2, 3]:
			add.call("sp_0_%d" % k, "Split 0/%d" % k, [0, k])
		for n in range(1, 37):
			if n <= 33:
				add.call("sp_%d_%d" % [n, n + 3], "Split %d/%d" % [n, n + 3], [n, n + 3])
			if n % 3:
				add.call("sp_%d_%d" % [n, n + 1], "Split %d/%d" % [n, n + 1], [n, n + 1])
		for s in range(1, 37, 3):
			add.call("st_%d" % s, "Street %d-%d-%d" % [s, s + 1, s + 2], [s, s + 1, s + 2])
		add.call("tr_0_1_2", "Trio 0-1-2", [0, 1, 2])
		add.call("tr_0_2_3", "Trio 0-2-3", [0, 2, 3])
		for a in range(1, 33):
			if a % 3:
				add.call("co_%d_%d" % [a, a + 4], "Corner %d/%d/%d/%d" % [a, a + 1, a + 3, a + 4], [a, a + 1, a + 3, a + 4])
		add.call("ff", "First four 0-1-2-3", [0, 1, 2, 3])
		for s in range(1, 32, 3):
			add.call("ln_%d" % s, "Six line %d-%d" % [s, s + 5], range(s, s + 6))
		for k in [1, 2, 3]:
			add.call("col%d" % k, "%s column" % ["1st", "2nd", "3rd"][k - 1], range(k, 37, 3))
			add.call("doz%d" % k, "%s dozen (%d-%d)" % [["1st", "2nd", "3rd"][k - 1], 12 * k - 11, 12 * k], range(12 * k - 11, 12 * k + 1))
		var blacks := []
		for n in range(1, 37):
			if not n in RED:
				blacks.append(n)
		add.call("red", "Red", RED)
		add.call("black", "Black", blacks)
		add.call("odd", "Odd", range(1, 37, 2))
		add.call("even", "Even", range(2, 37, 2))
		add.call("low", "1-18", range(1, 19))
		add.call("high", "19-36", range(19, 37))
	return _bets


static func col_of(n: int) -> int:
	return (n - 1) / 3


static func row_of(n: int) -> int:   # 0 is the top row (3, 6, 9 ...), 2 the row nearest the players
	return 2 - (n - 1) % 3


static func number_at(c: int, r: int) -> int:
	return c * 3 + (3 - r)


func bet_spots() -> Array:
	return bets().keys()


func flat_spots() -> Dictionary:
	return {}


func main_spot() -> String:
	return ""


func has_main_bet(b: Dictionary) -> bool:
	for spot in b:
		if int(b[spot]) > 0:
			return true
	return false


func accepting_bets() -> bool:
	return phase == "betting" or phase == "spinning"


func can_ready() -> bool:
	return phase == "betting"


func pulse_spots() -> bool:
	return false


func queues_bets() -> bool:
	return false   # Mike: at the wheel you wait for the next spin


## Where a bet's chips go on the layout.
static func chip_pos(spot: String) -> Vector2:
	var parts := spot.split("_")
	var row_mid := func(r: int) -> float: return GY + r * BH + BH / 2
	var col_mid := func(c: int) -> float: return GX + c * BW + BW / 2
	if spot == "n0":
		return Vector2((ZX + GX) / 2 + 1, GY + 1.5 * BH)
	if spot.begins_with("n"):
		var n := int(spot.substr(1))
		return Vector2(col_mid.call(col_of(n)), row_mid.call(row_of(n)))
	if spot == "ff":
		return Vector2(GX, GY + 3 * BH)
	if parts[0] == "tr":
		return Vector2(GX, GY + BH if parts[2] == "2" else GY + 2 * BH)
	if parts[0] == "sp" and parts[1] == "0":
		return Vector2(GX, row_mid.call(3 - int(parts[2])))
	if parts[0] == "sp":
		var a := int(parts[1])
		if int(parts[2]) - a == 3:
			return Vector2(GX + (col_of(a) + 1) * BW, row_mid.call(row_of(a)))
		return Vector2(col_mid.call(col_of(a)), GY + row_of(a) * BH)
	if parts[0] == "co":
		var a := int(parts[1])
		return Vector2(GX + (col_of(a) + 1) * BW, GY + row_of(a) * BH)
	if parts[0] == "st":
		return Vector2(col_mid.call(col_of(int(parts[1]))), GY + 3 * BH)
	if parts[0] == "ln":
		return Vector2(GX + (col_of(int(parts[1])) + 1) * BW, GY + 3 * BH)
	if spot.begins_with("col"):
		return Vector2(GX + 12.5 * BW, row_mid.call(3 - int(spot.substr(3))))
	if spot.begins_with("doz"):
		return Vector2(GX + (int(spot.substr(3)) - 1) * 4 * BW + 2 * BW, DY + DH / 2)
	return Vector2(GX + EVENS.find(spot) * 2 * BW + BW, EY + EH / 2)


## The bet a point on the felt (table coordinates) would place, or "".
static func spot_at(p: Vector2) -> String:
	var e := EDGE
	if p.y >= GY and p.y < GY + 3 * BH + 3.5 and p.x >= ZX and p.x < GX + 12 * BW:
		var fy0 := p.y - GY
		if p.x < GX - e:
			return "n0" if fy0 < 3 * BH else ""
		if p.x < GX + e:
			if fy0 > 3 * BH - e:
				return "ff"
			if absf(fy0 - BH) < e:
				return "tr_0_2_3"
			if absf(fy0 - 2 * BH) < e:
				return "tr_0_1_2"
			return "sp_0_%d" % (3 - mini(2, int(fy0 / BH)))
		var c := int((p.x - GX) / BW)
		var r := mini(2, int(fy0 / BH))
		var fx := p.x - GX - c * BW
		var fy := fy0 - r * BH
		var right := fx > BW - e
		var below := fy > BH - e
		if fx < e:
			c -= 1
			right = true
		if fy < e and r > 0:
			r -= 1
			below = true
		if r == 2 and below:
			return ("ln_%d" if right and c < 11 else "st_%d") % (3 * c + 1)
		var n := number_at(c, r)
		if right and below and c < 11:
			return "co_%d_%d" % [n - 1, n + 3]
		if right and c < 11:
			return "sp_%d_%d" % [n, n + 3]
		if below and r < 2:
			return "sp_%d_%d" % [n - 1, n]
		return "n%d" % n
	if p.x >= GX + 12 * BW and p.x < GX + 13 * BW and p.y >= GY and p.y < GY + 3 * BH:
		return "col%d" % (3 - int((p.y - GY) / BH))
	if p.x >= GX and p.x < GX + 12 * BW and p.y >= DY + 3.5 and p.y < DY + DH:
		return "doz%d" % (1 + int((p.x - GX) / (4 * BW)))
	if p.x >= GX and p.x < GX + 12 * BW and p.y >= EY and p.y < EY + EH:
		return EVENS[int((p.x - GX) / (2 * BW))]
	return ""


## The seats with chips on `spot`, plus `seat` (whose chips may be on their way).
func _seats_on(spot: String, seat := -1) -> Array:
	var on := []
	for s in _seat_chips:
		if _seat_chips[s].has(spot):
			on.append(s)
	if seat >= 0 and not seat in on:
		on.append(seat)
	on.sort()
	return on


## A seat's stack on a spot: fanned out beside the other seats' stacks there.
func spot_pos(seat: int, spot: String) -> Vector2:
	var on := _seats_on(spot, seat)
	var k := on.find(seat)
	return chip_pos(spot) + Vector2((k - (on.size() - 1) / 2.0) * 3.4, -k * 0.6)


func payout_pos(seat: int, spot: String, _bonus := false) -> Vector2:
	return spot_pos(seat, spot) + Vector2(7, -5)


## Every seat's stack on `spot` slides to its place in the fan.
func _relayout(spot: String, d: float) -> void:
	var on := _seats_on(spot)
	for k in on.size():
		var stack: ChipStack2D = _seat_chips[on[k]][spot]
		stack.z_index = 1 + k
		var to := spot_pos(on[k], spot)
		if d <= 0.0:
			stack.position = to
		elif stack.position != to:
			_tween().tween_property(stack, "position", to, 0.15 * d)


## Chips going down or coming back: then every stack on a touched spot finds its place in the fan.
func _show_bets(seat: int, b: Dictionary, d: float) -> void:
	var touched := {}
	for spot in _chips_for(seat):
		touched[spot] = true
	for spot in b:
		touched[spot] = true
	super._show_bets(seat, b, d)
	_after(0.3 * d).timeout.connect(func():
		for spot in touched:
			if not _seats_on(spot).is_empty():
				_relayout(spot, d))


## Roulette keeps its own look for now (no table style).
func styled() -> bool:
	return false


func _make_stack(seat: int) -> ChipStack2D:
	var stack := ChipStack2D.new()
	stack.tint = SEAT_COLOURS[seat % SEAT_COLOURS.size()]
	return stack


func tray_rect() -> Rect2:
	return Rect2(FLOAT_AT - Vector2(22, 5.5), Vector2(44, 11))


func tray_pos() -> Vector2:
	return FLOAT_AT


func shoe_pos() -> Vector2:
	return WHEEL_AT


func focus_point() -> Vector2:
	return to_global(Vector2(20, -50))


func title_y() -> float:
	return TITLE_AT.y


func countdown_pos() -> Vector2:
	return Vector2(32, -104)


func _countdown_text(left: float) -> String:
	if left <= 0:
		return ""
	if phase == "betting":
		return "SPINNING IN %d" % ceili(left)
	return "FINAL BETS!" if phase == "spinning" else ""


# ------------------------------------------------------------------ the table's shape
## The outline, grown outwards from the felt by `grow` (RAIL_W: the rail's outer
## edge). `bay` false fills the dealer's bay in (for collision).
static func shape(grow := 0.0, bay := true, steps := 8) -> PackedVector2Array:
	var pts := PackedVector2Array()
	var left := FELT_LEFT - grow
	var right := FELT_RIGHT + grow
	var top := FELT_TOP - grow
	var front := FELT_FRONT + grow
	var rl := CORNER_WHEEL + grow
	var rr := CORNER_FAR + grow
	_arc(pts, Vector2(left + rl, top + rl), Vector2(rl, rl), PI, 1.5 * PI, steps)
	if bay:
		var bl := BAY_X - (BAY_HALF - grow)
		var brx := BAY_X + (BAY_HALF - grow)
		var floor_y := BAY_FLOOR - grow
		var c := BAY_CORNER
		var q := Vector2(c, c)
		var bs := maxi(2, steps / 2)
		_arc(pts, Vector2(bl - c, top + c), q, -0.5 * PI, 0, bs)
		_arc(pts, Vector2(bl + c, floor_y - c), q, PI, 0.5 * PI, bs)
		_arc(pts, Vector2(brx - c, floor_y - c), q, 0.5 * PI, 0, bs)
		_arc(pts, Vector2(brx + c, top + c), q, PI, 1.5 * PI, bs)
	_arc(pts, Vector2(right - rr, top + rr), Vector2(rr, rr), 1.5 * PI, 2 * PI, steps)
	_arc(pts, Vector2(right - rr, front - rr), Vector2(rr, rr), 0, 0.5 * PI, steps)
	_arc(pts, Vector2(left + rl, front - rl), Vector2(rl, rl), 0.5 * PI, PI, steps)
	return pts


func _build_collision() -> void:
	$Body/Shape.polygon = shape(RAIL_W + 0.5, false, 6)


# ------------------------------------------------------------------ the HUD
func seated_view(ctx: Dictionary) -> Dictionary:
	var info := ""
	if hover_spot != "" and bets().has(hover_spot):
		var b: Dictionary = bets()[hover_spot]
		info = "%s  ·  pays %d to 1" % [b.name, b.pays]
		var mine := int(ctx.get("my_bets", {}).get(hover_spot, 0))
		if mine > 0:
			info += "  ·  you have %s on it" % Money.format(mine)
	else:
		match phase:
			"betting":
				info = _betting_info(ctx)
			"spinning":
				info = "Final bets!"
			"rolling":
				info = "No more bets"
			"result", "sweeping", "settling", "clearing":
				info = result_text
	var total := 0
	var count := 0
	for spot in ctx.get("my_bets", {}):
		if int(ctx.my_bets[spot]) > 0:
			total += int(ctx.my_bets[spot])
			count += 1
	if total > 0 and accepting_bets():
		info += "  ·  Your bets: %s on %d spot%s" % [Money.format(total), count, "" if count == 1 else "s"]
	return {"info": info, "actions": [], "my_turn": false}


# ------------------------------------------------------------------ snapshot
func _apply_game_snapshot(state: Dictionary) -> void:
	var history: Array = state.get("history", [])
	if not history.is_empty():
		sign_board.history = history
	dolly = int(state.dolly) if state.get("dolly") != null else -1
	result_text = _describe(dolly) if dolly >= 0 else ""
	var spin = state.get("spin")
	if spin != null:
		wheel.launch(float(spin.track), float(spin.elapsed), float(spin.get("ball", 0.0)))
		if spin.get("number") != null:
			wheel.land_on(int(spin.number), spin.landing)
	elif not history.is_empty():
		wheel.rest_on(int(history[0]))
	for spot in bets():
		if not _seats_on(spot).is_empty():
			_relayout(spot, 0.0)
	_felt.queue_redraw()


static func _describe(n: int) -> String:
	if n == 0:
		return "Zero  ·  La Partage on the even chances"
	return "%d  ·  %s  ·  %s  ·  %s" % [n, "red" if n in RED else "black", "odd" if n % 2 else "even", "low" if n <= 18 else "high"]


# ------------------------------------------------------------------ events -> animation
func handle_event(ev: Dictionary) -> void:
	if ev.kind == "spin":
		ev["_rx"] = Time.get_ticks_msec() / 1000.0   # the ball's timing runs from when the spin arrived
	super.handle_event(ev)


func _note_event(ev: Dictionary) -> void:
	if ev.kind == "betting_open":
		dolly = -1
		result_text = ""


func _animate_game(ev: Dictionary, d: float) -> float:
	match ev.kind:
		"spin":
			return _spin(ev)
		"no_more_bets":
			phase = "rolling"
			_timer_end = 0.0
			in_hand = my_seat in ev.seats.map(func(x): return int(x))
			wheel.land_on(int(ev.number), ev.landing)
			return 0.0
		"ball_landed":
			phase = "result"
			var n := int(ev.number)
			result_text = _describe(n)
			sign_board.show_result(ev.history)
			if not wheel.is_spinning():   # (normally it's just settled there by itself)
				wheel.rest_on(n)
			_after(0.45 * d).timeout.connect(func():
				dolly = n
				_dolly_drop = Time.get_ticks_msec() / 1000.0
				sfx_at("bet", to_global(chip_pos("n%d" % n))))
			return 0.9 * d
		"sweep":
			return _sweep(ev, d)
		"settle_seat":
			return _settle(ev, d)
		"round_end":
			_after(0.9 * d).timeout.connect(func(): dolly = -1)
			return 0.0
	return 0.0


## The dealer spins: the ball rolls round the track ("Final bets!" until just before it reaches the pockets).
func _spin(ev: Dictionary) -> float:
	phase = "spinning"
	ready_seats.clear()
	var elapsed := maxf(0.0, Time.get_ticks_msec() / 1000.0 - float(ev.get("_rx", 0.0)))
	var track := float(ev.get("track", RouletteWheel.BALL_TRACK))
	var scale := track / RouletteWheel.BALL_TRACK
	_start_timer(maxf(0.0, float(ev.open) - elapsed))
	wheel.launch(track, elapsed, float(ev.get("ball", 0.0)))
	var at := to_global(WHEEL_AT)
	sfx_at("ball_spin", at)
	var drop := (RouletteWheel.T_TRACK + 0.48 * (RouletteWheel.BALL_TRACK - RouletteWheel.T_TRACK)) * scale - elapsed
	_after(maxf(0.0, drop)).timeout.connect(func(): sfx_at("ball_drop", at))
	return 0.0


## Every losing chip goes down the hole, in one sweep (half of each even-money
## stake on a zero; the other half stays to be returned).
func _sweep(ev: Dictionary, d: float) -> float:
	phase = "sweeping"
	var k := 0
	var touched := {}
	for seat_key in ev.seats:
		var seat := int(seat_key)
		for item in ev.seats[seat_key]:
			var spot: String = item.spot
			var chips := _chips_for(seat)
			if not chips.has(spot):
				continue
			var stack: ChipStack2D = chips[spot]
			var lost := int(item.amount)
			var going: ChipStack2D = stack
			if lost < stack.amount:   # La Partage: half goes, half stays
				stack.amount -= lost
				going = _make_stack(seat)
				going.amount = lost
				going.position = stack.position
				_dyn.add_child(going)
			else:
				chips.erase(spot)
			touched[spot] = true
			_down_the_hole(going, k * 0.035 * d, d)
			k += 1
	if k > 0:
		sfx_at("sweep", to_global(HOLE_AT))
	for spot in touched:
		_relayout(spot, d)
	return (0.75 + k * 0.035) * d if k > 0 else 0.2 * d


## A stack flies over the hole, then drops in: shrinking and darkening as it goes.
func _down_the_hole(stack: ChipStack2D, delay: float, d: float) -> void:
	stack.z_index = 5
	var tw := _tween()
	tw.tween_interval(delay)
	tw.tween_property(stack, "position", HOLE_AT + Vector2(0, 1.2), 0.45 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN_OUT)
	tw.tween_property(stack, "scale", Vector2(0.35, 0.35), 0.16 * d).set_ease(Tween.EASE_IN)
	tw.parallel().tween_property(stack, "modulate", Color(0.15, 0.1, 0.08, 0.0), 0.16 * d)
	tw.tween_callback(stack.queue_free)


## A winning seat is paid: from the float, beside each winning stake (outside bets first).
func _settle(ev: Dictionary, d: float) -> float:
	phase = "settling"
	var seat := int(ev.seat)
	var t := 0.05 * d
	for step in ev.steps:
		if step.action == "pay":
			_after(t).timeout.connect(_settle_step.bind(seat, step, d))
			t += 0.22 * d
		elif step.action == "half":   # La Partage: what's left of the stake gets a nudge
			_after(t).timeout.connect(_settle_step.bind(seat, {"spot": step.spot, "action": "push"}, d))
	return t + 0.3 * d


# ------------------------------------------------------------------ input
func _process(delta: float) -> void:
	super._process(delta)
	if Engine.is_editor_hint():
		return
	var spot := ""
	if mode == "seated" and my_seat >= 0 and accepting_bets():
		spot = spot_at(get_local_mouse_position())
	if spot != hover_spot:
		hover_spot = spot
		_felt.queue_redraw()


func _needs_redraw() -> bool:
	return dolly >= 0 or hover_spot != ""


func _unhandled_input(event: InputEvent) -> void:
	if Engine.is_editor_hint() or mode != "seated" or my_seat < 0:
		return
	if not (event is InputEventMouseButton and event.pressed):
		return
	var spot := spot_at(get_local_mouse_position())
	if spot == "":
		return
	if event.button_index == MOUSE_BUTTON_LEFT:
		spot_clicked.emit(spot)
	elif event.button_index == MOUSE_BUTTON_RIGHT:
		spot_removed.emit(spot)
	get_viewport().set_input_as_handled()


# ------------------------------------------------------------------ overlays
func _draw_game(now: float, _pulse: float) -> void:
	# Each taken chair has its seat's chip colour on the floor round its base.
	for seat in occupants:
		draw_set_transform(chair_pos(seat) + Vector2(0, 0.8), 0, Vector2(1, 0.34))
		draw_arc(Vector2.ZERO, 13.0, 0, TAU, 40, SEAT_COLOURS[seat % SEAT_COLOURS.size()], 1.8, true)
		draw_set_transform(Vector2.ZERO)
	# A ghost of your chip where it would go.
	if hover_spot != "" and mode == "seated" and my_seat >= 0:
		var at := spot_pos(my_seat, hover_spot) - Vector2(0, 2)
		var c: Color = SEAT_COLOURS[my_seat % SEAT_COLOURS.size()]
		draw_circle(at, ChipStack2D.TINT_RADIUS, Color(c, 0.55))
		draw_arc(at, ChipStack2D.TINT_RADIUS - 0.6, 0, TAU, 24, Color(1, 1, 1, 0.5), 0.8, true)
		var label := ChipStack2D._label(chip_value)
		var w := Card2D.FONT.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, 4).x
		draw_string(Card2D.FONT, at + Vector2(-w / 2, 1.4), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 4, Color(0.1, 0.05, 0.02, 0.8))
	# The dolly on the winning number (it drops in).
	if dolly >= 0:
		var p := chip_pos("n%d" % dolly) - Vector2(0, 2)
		var fall := clampf((now - _dolly_drop) / 0.18, 0.0, 1.0)
		p.y -= (1.0 - fall) * 8.0
		draw_set_transform(p + Vector2(0.8, 4.2), 0, Vector2(1, 0.45))
		draw_circle(Vector2.ZERO, 4.2, Color(0, 0, 0, 0.4 * fall))
		draw_set_transform(Vector2.ZERO)
		draw_rect(Rect2(p.x - 3.2, p.y - 4, 6.4, 7), Color("b8923a"))
		draw_rect(Rect2(p.x - 1.4, p.y - 4, 1.6, 7), Color(1, 0.95, 0.75, 0.6))
		draw_set_transform(p + Vector2(0, 3), 0, Vector2(1, 0.44))
		draw_circle(Vector2.ZERO, 3.2, Color("b8923a"))
		draw_set_transform(p + Vector2(0, -4), 0, Vector2(1, 0.44))
		draw_circle(Vector2.ZERO, 3.2, Color("f6e3a6"))
		draw_set_transform(Vector2.ZERO)
