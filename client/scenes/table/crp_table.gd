@tool
class_name CrapsTable
extends CasinoTable
## The craps table (Vegas rules), signed off on Mike's Craps mockup (v1): a
## long double-ended table in the house Mahogany & Brass. The boxman sits in
## the bay over the chip rack with a base dealer either side; the stickman --
## the rostered dealer -- stands opposite them on the near rail, with eight
## standing spots for players, four each side of him. Each end has its own
## layout (Pass Line, Don't Pass, Come, Don't Come, the Field, Big 6/8 and the
## point boxes) and a player bets the end on their side; the proposition box
## in the middle, in front of the stickman, is shared.
##
## Bets stay on the layout from roll to roll; each seat's chips are its own
## colour, as at the roulette table. A click on a number box is a Place, Buy,
## Lay or Come odds bet depending on the Numbers button; after the point, a
## click on the Pass Line (or just behind it) puts odds down, on Don't Pass lays
## them.
##
## A roll: "Dice are out", the throw (the server's plan, played by CrapsDice),
## the stickman's call, the losers swept into the rack, the winners paid beside
## their bets a player at a time, winnings back to the players, come bets off
## to their numbers, the puck over, the dice hooked back to the middle.

# The table (table coordinates: the players' edge of the felt is y = 0).
const FELT_HALF := 189.0
const FELT_TOP := -121.0
const FELT_FRONT := 0.0
const RAIL_W := 9.0
const CORNER := 17.0
const BAY_HALF := 35.0           # the boxman's bay: half its width at the felt,
const BAY_FLOOR := -107.0        # how far into the table it reaches,
const BAY_CORNER := 5.0          # and its corners
const RACK_AT := Vector2(0, -123.5)
const TITLE_AT := Vector2(0, -12.5)
# The layout. Each end is the same, mirrored; these are the right-hand end's x.
const NUMS := [4, 5, 6, 8, 9, 10]
const BOXW := 124.0 / 6.0
const NUM_TOP := -117.0
const NUM_H := 30.0
# The proposition box in the middle: its rows line up with the lines at each end
# (the bottom of the point boxes, the Come, the Field and the Don't Pass Bar).
const PROPS := {
	"any7": Rect2(-38, -106.5, 76, 7.5), "hard6": Rect2(-38, -99, 38, 12), "hard10": Rect2(0, -99, 38, 12),
	"hard8": Rect2(-38, -87, 38, 14), "hard4": Rect2(0, -87, 38, 14), "two": Rect2(-38, -73, 38, 14),
	"twelve": Rect2(0, -73, 38, 14), "three": Rect2(-38, -59, 38, 11), "eleven": Rect2(0, -59, 38, 11),
	"any_craps": Rect2(-38, -48, 76, 11), "horn": Rect2(-38, -37, 38, 10), "ce": Rect2(0, -37, 38, 10),
}
const PROP_BOX := Rect2(-38, -106.5, 76, 79.5)
# The Pass Line runs the whole length of the front, through the middle, and curves
# up each end round these centres; the odds ("behind the line") follow it outside.
const CURVE_AT := Vector2(162, -35)
const PASS_IN := 8.0             # the radius of its inside edge,
const PASS_OUT := 22.0           # its outside edge,
const ODDS_OUT := 33.0           # and the odds strip's outside edge
const ODDS_END := 0.9            # where the odds strip stops on the curve (radians from the end wall)
const ODDS_X := {4: 3, 5: 4, 6: 5, 8: 5, 9: 4, 10: 3}
const SEAT_COLOURS := [Color("5ab0e8"), Color("f2c14e"), Color("ef7aa0"), Color("5fd3a0"),
	Color("a98ef2"), Color("e8935a"), Color("e85a5a"), Color("9ad94f")]
const CHIP_SCALE := 0.6
const MODES := ["place", "buy", "lay", "odds"]
const MODE_LABELS := {"place": "Place", "buy": "Buy", "lay": "Lay", "odds": "Come odds"}
# The settle's pace (the server's Timings).
const T_CALL := 1.4
const T_SWEEP := 1.0
const T_PAY_STEP := 0.32
const T_PAY_PAUSE := 0.6
const T_BACK := 0.9
const T_MOVE := 0.7
const T_FETCH := 0.85

static var _spots := []

var point := -1
var shooter := -1
var human_shooter := false
var want_dice := []
var working := {}                # seat -> bool
var number_mode := "place"
var hover := {}                  # {id, h} under the pointer while you can bet
var chip_value := 100
var result_text := ""
var _locked := {}                # the local player's bets that are already paid for
var _puck := {1: Vector2(49, -106), -1: Vector2(-49, -106)}

@onready var dice: CrapsDice = $Felt/Dice
@onready var sign_board: CrapsSign = $Sign


func _ready() -> void:
	super._ready()
	if Engine.is_editor_hint():
		return
	dice.position = -_felt.position
	dice.z_index = 2   # over the chips (which sit over cards at z 1)
	dice.knock.connect(func(kind: String, strength: float):
		sfx_at("dice_land" if kind == "land" else "dice_bounce", to_global(Vector2(0, -60)), lerpf(-12.0, 0.0, strength)))
	dealer.set_action("idle", "up")
	dealer.name_below = true


# ------------------------------------------------------------------ the bets
static func spots() -> Array:
	if _spots.is_empty():
		_spots = ["pass", "pass_odds", "dont_pass", "dont_odds", "come", "dont_come", "field", "big6", "big8"]
		for kind in ["place", "buy", "lay", "come", "come_odds", "dcome", "dcome_odds"]:
			for n in NUMS:
				_spots.append("%s_%d" % [kind, n])
		_spots += ["hard4", "hard6", "hard8", "hard10", "any7", "any_craps", "two", "three", "eleven", "twelve", "horn", "ce"]
	return _spots


static func number_of(spot: String) -> int:
	var tail := spot.get_slice("_", spot.get_slice_count("_") - 1)
	if tail.is_valid_int():
		return int(tail)
	if spot.begins_with("hard"):
		return int(spot.substr(4))
	if spot.begins_with("big"):
		return int(spot.substr(3))
	return -1


static func info(spot: String) -> Array:
	var n := number_of(spot)
	var fixed := {
		"pass": ["Pass Line", "1 to 1"], "pass_odds": ["Odds behind your Pass Line bet", "true odds"],
		"dont_pass": ["Don't Pass Bar 12", "1 to 1"], "dont_odds": ["Lay odds on your Don't Pass bet", "true odds"],
		"come": ["Come", "1 to 1"], "dont_come": ["Don't Come Bar 12", "1 to 1"],
		"field": ["Field: 3, 4, 9, 10, 11", "1 to 1, 2 pays double, 12 triple"], "big6": ["Big 6", "1 to 1"], "big8": ["Big 8", "1 to 1"],
		"hard4": ["Hard 4 (2-2)", "7 to 1"], "hard10": ["Hard 10 (5-5)", "7 to 1"], "hard6": ["Hard 6 (3-3)", "9 to 1"],
		"hard8": ["Hard 8 (4-4)", "9 to 1"], "any7": ["Any Seven, one roll", "4 to 1"],
		"any_craps": ["Any Craps (2, 3 or 12), one roll", "7 to 1"], "two": ["Aces (2), one roll", "30 to 1"],
		"twelve": ["Twelve, one roll", "30 to 1"], "three": ["Ace-deuce (3), one roll", "15 to 1"],
		"eleven": ["Yo-leven (11), one roll", "15 to 1"], "horn": ["Horn: 2, 3, 11 and 12", "27 to 4 or 3 to 1"],
		"ce": ["C & E: craps or 11", "3 to 1 or 7 to 1"],
	}
	if fixed.has(spot):
		return fixed[spot]
	var place := {4: "9 to 5", 10: "9 to 5", 5: "7 to 5", 9: "7 to 5", 6: "7 to 6", 8: "7 to 6"}
	var odds := {4: "2 to 1", 10: "2 to 1", 5: "3 to 2", 9: "3 to 2", 6: "6 to 5", 8: "6 to 5"}
	var lay := {4: "1 to 2", 10: "1 to 2", 5: "2 to 3", 9: "2 to 3", 6: "5 to 6", 8: "5 to 6"}
	if spot.begins_with("place_"):
		return ["Place %d" % n, place[n]]
	if spot.begins_with("buy_"):
		return ["Buy %d" % n, "%s, less 5%% of the bet" % odds[n]]
	if spot.begins_with("lay_"):
		return ["Lay %d" % n, "%s, less 5%% of the win" % lay[n]]
	if spot.begins_with("come_odds_"):
		return ["Odds on your come bet on %d" % n, odds[n]]
	if spot.begins_with("dcome_odds_"):
		return ["Lay odds on your don't come bet on %d" % n, lay[n]]
	if spot.begins_with("come_"):
		return ["Come bet on %d" % n, "1 to 1"]
	if spot.begins_with("dcome_"):
		return ["Don't come bet on %d" % n, "1 to 1"]
	return [spot, ""]


func bet_spots() -> Array:
	return spots()


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
	return phase == "betting"


func can_ready() -> bool:
	return phase == "betting" and shooter == my_seat and my_seat >= 0   # Space rolls, for the shooter


func pulse_spots() -> bool:
	return false


func queues_bets() -> bool:
	return false


func seat_pose() -> String:
	return "idle"


## What the local player has down that isn't paid for yet (it's paid for when the dice go out).
func pending_cost(bets: Dictionary) -> int:
	var total := 0
	for spot in bets:
		total += maxi(0, int(bets[spot]) - int(_locked.get(spot, 0)))
	return total


func max_cost(bets: Dictionary) -> int:
	return pending_cost(bets)


## Contract bets: a Pass Line bet once the point's on, come bets on their numbers.
static func removable(spot: String, the_point: int) -> bool:
	if spot == "pass":
		return the_point < 0
	return not (spot.begins_with("come_") and not spot.begins_with("come_odds"))


static func off_on_come_out(spot: String) -> bool:
	return spot.begins_with("place_") or spot.begins_with("buy_") or spot.begins_with("hard") or spot.begins_with("come_odds_")


func deciding() -> bool:
	if my_seat < 0:
		return false
	for spot in _chips_for(my_seat):
		if not removable(spot, point):
			return true
	return false


func stand_warning() -> String:
	return "Your Pass Line and come bets stay on the table until they're decided -- walk away now and they're lost. Walk away anyway?"


func on_seated_prompt() -> Dictionary:
	if shooter < 0 or shooter == my_seat or not occupants.has(shooter):
		return {}   # (a quiet table: the dice are yours anyway)
	var name: String = occupants[shooter].name
	var text := "%s is shooting. Do you want the dice? You'd get them %s." % [
		name, "now" if point < 0 and not occupants[shooter].human else "once this point is decided"]
	return {"text": text, "yes": "Take the dice", "no": "Just play", "message": ["take_dice", {"on": true}]}


# ------------------------------------------------------------------ geometry
static func mx(x: float, h: int) -> float:
	return x if h == 1 else -x


static func _r(x0: float, y0: float, x1: float, y1: float, h: int) -> Rect2:
	var a := mx(x0, h)
	var b := mx(x1, h)
	return Rect2(minf(a, b), y0, absf(b - a), y1 - y0)


static func box_x(n: int, h: int) -> float:
	return (60.0 if h == 1 else -184.0) + NUMS.find(n) * BOXW


static func box_cx(n: int, h: int) -> float:
	return box_x(n, h) + BOXW / 2


## Each end's printed areas: region id -> Rect2.
static func zones(h: int) -> Dictionary:
	var z := {"dont_come": _r(38, -117, 60, -87, h), "come": _r(38, -87, 170, -59, h), "field": _r(38, -59, 148, -37, h),
		"big6": _r(148, -59, 170, -43, h), "big8": _r(148, -43, 170, -27, h), "dont_pass": _r(38, -37, 148, -27, h)}
	for n in NUMS:
		z["box_%d" % n] = Rect2(box_x(n, h), NUM_TOP, BOXW, NUM_H)
	return z


static var _pass_poly := PackedVector2Array()
static var _odds_poly := PackedVector2Array()


## The Pass Line: one band from end to end, along the front and up both ends.
static func pass_line() -> PackedVector2Array:
	if _pass_poly.is_empty():
		var c := CURVE_AT
		var m := Vector2(-c.x, c.y)
		var pts := PackedVector2Array([Vector2(184, -87)])
		_arc(pts, c, Vector2(PASS_OUT, PASS_OUT), 0, PI / 2, 10)
		_arc(pts, m, Vector2(PASS_OUT, PASS_OUT), PI / 2, PI, 10)
		pts.append(Vector2(-184, -87))
		pts.append(Vector2(-170, -87))
		_arc(pts, m, Vector2(PASS_IN, PASS_IN), PI, PI / 2, 6)
		_arc(pts, c, Vector2(PASS_IN, PASS_IN), PI / 2, 0, 6)
		pts.append(Vector2(170, -87))
		_pass_poly = pts
	return _pass_poly


## Behind the line: the strip outside the Pass Line, along the front and round the curves.
static func odds_strip() -> PackedVector2Array:
	if _odds_poly.is_empty():
		var c := CURVE_AT
		var m := Vector2(-c.x, c.y)
		var pts := PackedVector2Array()
		_arc(pts, c, Vector2(PASS_OUT, PASS_OUT), ODDS_END, PI / 2, 6)
		_arc(pts, m, Vector2(PASS_OUT, PASS_OUT), PI / 2, PI - ODDS_END, 6)
		_arc(pts, m, Vector2(ODDS_OUT, ODDS_OUT), PI - ODDS_END, PI / 2, 8)
		_arc(pts, c, Vector2(ODDS_OUT, ODDS_OUT), PI / 2, ODDS_END, 8)
		_odds_poly = pts
	return _odds_poly


## An end's printed area as a polygon: its rectangle, but Big 8's outside corner
## follows the curve of the Pass Line.
static func zone_poly(id: String, h: int) -> PackedVector2Array:
	var r: Rect2 = zones(h)[id]
	if id != "big8":
		return PackedVector2Array([r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)])
	var pts := PackedVector2Array([Vector2(148, -43), Vector2(170, -43)])
	_arc(pts, CURVE_AT, Vector2(PASS_IN, PASS_IN), 0, PI / 2, 6)
	pts.append(Vector2(148, -27))
	if h == -1:
		for i in pts.size():
			pts[i].x = -pts[i].x
	return pts


## The region (and which end) a point on the felt is in, or {}.
static func region_at(p: Vector2) -> Dictionary:
	for id in PROPS:
		if PROPS[id].has_point(p):
			return {"id": id, "h": 0}
	var side := 1 if p.x >= 0 else -1
	if Geometry2D.is_point_in_polygon(p, pass_line()):
		return {"id": "pass", "h": side}
	if Geometry2D.is_point_in_polygon(p, odds_strip()):
		return {"id": "pass_odds", "h": side}
	for h in [1, -1]:
		if mx(p.x, h) < 38:
			continue
		var z := zones(h)
		for id in z:
			if z[id].has_point(p):
				return {"id": id, "h": h}
	return {}


## The bet a click on `region` makes for the local player.
func spot_for(region: String) -> String:
	if region == "pass":
		return "pass" if point < 0 else "pass_odds"
	if region == "dont_pass":
		return "dont_pass" if point < 0 else "dont_odds"
	if region.begins_with("box_"):
		var n := int(region.substr(4))
		if number_mode == "odds":
			var mine := _chips_for(my_seat) if my_seat >= 0 else {}
			return "dcome_odds_%d" % n if mine.has("dcome_%d" % n) and not mine.has("come_%d" % n) else "come_odds_%d" % n
		return "%s_%d" % [number_mode, n]
	return region


func half(seat: int) -> int:
	return 1 if seat < 4 else -1


## Where a seat's chips go: in front of the player on their end's layout; in the
## number boxes and the prop box, fanned across by where the player stands.
func spot_pos(seat: int, spot: String) -> Vector2:
	var h := half(seat)
	var x := seat_x(seat)
	var rank := 3 - seat % 4
	var fan := (rank - 1.5) * 4.4
	var n := number_of(spot)
	var clamp_to := func(a: float, b: float, v: float) -> float: return clampf(v, minf(mx(a, h), mx(b, h)), maxf(mx(a, h), mx(b, h)))
	match spot:
		"pass":
			return Vector2(x, -20)
		"pass_odds":
			return Vector2(x, -7.5)
		"dont_pass":
			return Vector2(clamp_to.call(44, 142, x), -32)
		"dont_odds":
			return Vector2(clamp_to.call(44, 142, x) + 6, -34)
		"come":
			return Vector2(clamp_to.call(46, 162, x), -72)
		"dont_come":
			return Vector2(mx(49, h) + (rank - 1.5) * 2.2, -97)
		"field":
			return Vector2(clamp_to.call(44, 142, x), -48)
		"big6":
			return Vector2(mx(159, h) + (rank - 1.5) * 2.2, -50.5)
		"big8":
			return Vector2(mx(159, h) + (rank - 1.5) * 2.2, -34.5)
	if PROPS.has(spot):
		var r: Rect2 = PROPS[spot]
		return r.get_center() + Vector2((7 - seat - 3.5) * 3.6, 1)
	if spot.begins_with("lay_"):
		return Vector2(box_cx(n, h) + fan, -113.5)
	if spot.begins_with("dcome_odds_"):
		return Vector2(box_cx(n, h) + fan + 1.4, -113)
	if spot.begins_with("dcome_"):
		return Vector2(box_cx(n, h) + fan, -111.5)
	if spot.begins_with("come_odds_"):
		return Vector2(box_cx(n, h) + fan + 1.4, -103)
	if spot.begins_with("come_"):
		return Vector2(box_cx(n, h) + fan, -101.5)
	return Vector2(box_cx(n, h) + fan, -92)   # place, buy


func payout_pos(seat: int, spot: String, _bonus := false) -> Vector2:
	return spot_pos(seat, spot) + Vector2(4.5, -3.5)


func _make_stack(seat: int) -> ChipStack2D:
	var stack := ChipStack2D.new()
	stack.tint = SEAT_COLOURS[seat % SEAT_COLOURS.size()]
	stack.scale = Vector2(CHIP_SCALE, CHIP_SCALE)
	return stack


func tray_rect() -> Rect2:
	return Rect2(RACK_AT - Vector2(24, 5.5), Vector2(48, 11))


func tray_pos() -> Vector2:
	return RACK_AT


func shoe_pos() -> Vector2:
	return Vector2(0, -60)


func focus_point() -> Vector2:
	return to_global(Vector2(10, -46))


func title_y() -> float:
	return TITLE_AT.y


func countdown_pos() -> Vector2:
	return Vector2(-22, -7.5)   # behind the line, left of the stickman's speech bubble


func stool_pos(seat: int) -> Vector2:
	return chair_pos(seat) + Vector2(0, 3)


func _countdown_text(left: float) -> String:
	if phase != "betting" or left <= 0:
		return ""
	if shooter == my_seat and my_seat >= 0:
		return "YOUR ROLL  %d" % ceili(left)
	return ("SHOOTER TO ROLL  %d" if human_shooter else "DICE OUT IN %d") % ceili(left)


# ------------------------------------------------------------------ the table's shape
## The outline, grown outwards from the felt by `grow` (RAIL_W: the rail's outer edge).
## `bay` false fills the boxman's bay in (for collision).
static func shape(grow := 0.0, bay := true, steps := 8) -> PackedVector2Array:
	var pts := PackedVector2Array()
	var left := -FELT_HALF - grow
	var right := FELT_HALF + grow
	var top := FELT_TOP - grow
	var front := FELT_FRONT + grow
	var rc := maxf(4.0, CORNER + grow)
	_arc(pts, Vector2(left + rc, top + rc), Vector2(rc, rc), PI, 1.5 * PI, steps)
	if bay:
		var bl := -(BAY_HALF - grow)
		var brx := BAY_HALF - grow
		var floor_y := BAY_FLOOR - grow
		var c := BAY_CORNER
		var q := Vector2(c, c)
		var bs := maxi(2, steps / 2)
		_arc(pts, Vector2(bl - c, top + c), q, -0.5 * PI, 0, bs)
		_arc(pts, Vector2(bl + c, floor_y - c), q, PI, 0.5 * PI, bs)
		_arc(pts, Vector2(brx - c, floor_y - c), q, 0.5 * PI, 0, bs)
		_arc(pts, Vector2(brx + c, top + c), q, PI, 1.5 * PI, bs)
	_arc(pts, Vector2(right - rc, top + rc), Vector2(rc, rc), 1.5 * PI, 2 * PI, steps)
	_arc(pts, Vector2(right - rc, front - rc), Vector2(rc, rc), 0, 0.5 * PI, steps)
	_arc(pts, Vector2(left + rc, front - rc), Vector2(rc, rc), 0.5 * PI, PI, steps)
	return pts


func _build_collision() -> void:
	$Body/Shape.polygon = shape(RAIL_W + 0.5, false, 6)


# ------------------------------------------------------------------ the HUD
func seated_view(ctx: Dictionary) -> Dictionary:
	var info_text := ""
	var my_roll := phase == "betting" and shooter == my_seat and my_seat >= 0
	if not hover.is_empty():
		var spot := spot_for(hover.id)
		var i := info(spot)
		info_text = "%s  ·  pays %s" % [i[0], i[1]]
		var mine := int(ctx.get("my_bets", {}).get(spot, 0))
		if mine > 0:
			info_text += "  ·  you have %s on it" % Money.format(mine)
			if not removable(spot, point):
				info_text += " (stays until decided)"
		elif point < 0 and off_on_come_out(spot) and not working.get(my_seat, false):
			info_text += "  ·  off on the come-out"
	else:
		var who: String = "You're" if shooter == my_seat else ("%s is" % occupants[shooter].name if occupants.has(shooter) else "Nobody's")
		var where := "Point is %d" % point if point > 0 else "Coming out"
		match phase:
			"betting":
				if my_roll:
					var line := int(ctx.get("my_bets", {}).get("pass", 0)) + int(ctx.get("my_bets", {}).get("dont_pass", 0))
					info_text = "%s  ·  Your roll -- %s" % [where, "Roll [R] when your bets are down" if line > 0 or point > 0
						else "put a Pass Line or Don't Pass bet down, then Roll [R]"]
				else:
					info_text = "%s  ·  %s shooting" % [where, who]
			"throwing":
				info_text = "Dice are out -- no more bets"
			_:
				info_text = result_text
	var actions := []
	if my_roll:
		actions.append({"id": "roll", "label": "Roll  [R]", "key": "R"})
		actions.append({"id": "pass_dice", "label": "Pass dice"})
	elif my_seat >= 0 and shooter != my_seat:
		actions.append({"id": "take_dice", "label": "Dice coming" if my_seat in want_dice else "Take dice  [T]", "key": "T",
			"pressed": my_seat in want_dice})
	actions.append({"id": "mode", "label": "%s  [N]" % MODE_LABELS[number_mode], "key": "N"})
	actions.append({"id": "working", "label": "Working  [W]", "key": "W", "pressed": working.get(my_seat, false)})
	return {"info": info_text, "actions": actions, "my_turn": my_roll, "hide": ["ready", "rebet", "auto_rebet"],
		"quiet_betting": true}


func action_message(id: String) -> Array:
	match id:
		"roll":
			return ["shoot", {}]
		"pass_dice":
			return ["pass_dice", {}]
		"take_dice":
			return ["take_dice", {"on": not my_seat in want_dice}]
		"working":
			return ["working", {"on": not working.get(my_seat, false)}]
		"mode":
			number_mode = MODES[(MODES.find(number_mode) + 1) % MODES.size()]
	return []


# ------------------------------------------------------------------ snapshot
func _apply_game_snapshot(state: Dictionary) -> void:
	point = int(state.point) if state.get("point") != null else -1
	shooter = int(state.shooter) if state.get("shooter") != null else -1
	human_shooter = state.get("human_shooter", false)
	want_dice = state.get("want_dice", []).map(func(s): return int(s))
	working = {}
	_locked = {}
	var seats: Array = state.get("seats", [])
	for i in seats.size():
		if seats[i] != null:
			working[i] = seats[i].get("working", false)
			if i == my_seat:
				for spot in seats[i].get("locked", {}):
					_locked[spot] = int(seats[i].locked[spot])
	var history: Array = state.get("history", [])
	if not history.is_empty():
		sign_board.history = history
	sign_board.point = point
	sign_board.rolls = int(state.get("rolls", 0)) + (1 if phase == "betting" else 0)
	var throw = state.get("throw")
	if throw != null:
		dice.throw(throw.plan, float(throw.out), _hand(shooter), float(throw.elapsed))
	elif state.get("rest") != null:
		dice.rest(state.rest)
	else:
		dice.home()
	_felt.queue_redraw()


func _hand(seat: int) -> Vector2:
	return Vector2(seat_x(seat) + 2 * half(seat), -2) if seat >= 0 else CrapsDice.HOME[0]


# ------------------------------------------------------------------ events -> animation
func _note_event(ev: Dictionary) -> void:
	match ev.kind:
		"stood":   # once the dice are out, a leaver's chips just go (the server's done with them)
			var seat := int(ev.seat)
			if phase != "betting":
				for spot in _chips_for(seat).keys():
					_take_stack(seat, spot, chair_pos(seat), 1.0)
			working.erase(seat)
			want_dice.erase(seat)
		"bet_changed":
			if int(ev.seat) == my_seat:
				for spot in _locked.keys():
					_locked[spot] = mini(int(_locked[spot]), int(ev.bets.get(spot, 0)))


func _animate_game(ev: Dictionary, d: float) -> float:
	match ev.kind:
		"roll_open":
			phase = "betting"
			point = int(ev.point) if ev.get("point") != null else -1
			shooter = int(ev.shooter) if ev.get("shooter") != null else -1
			human_shooter = ev.get("human_shooter", false)
			_start_timer(float(ev.seconds))
			sign_board.point = point
			sign_board.rolls += 1
			if not dice.is_moving():
				dice.home()
			return 0.0
		"throw":
			phase = "throwing"
			_timer_end = 0.0
			shooter = int(ev.shooter)
			if my_seat >= 0:
				_locked = {}
				for spot in _chips_for(my_seat):
					_locked[spot] = int(_chips_for(my_seat)[spot].amount)
			sfx_at("dice_out", to_global(_hand(shooter)))
			dice.throw(ev.plan, float(ev.out) * d, _hand(shooter))
			return 0.0
		"roll_result":
			return _roll_result(ev, d)
		"shooter_change":
			shooter = int(ev.shooter) if ev.get("shooter") != null else -1
			point = int(ev.point) if ev.get("point") != null else point
			want_dice.erase(shooter)
			return 0.0
		"dice_queued":
			var seat := int(ev.seat)
			if ev.on and not seat in want_dice:
				want_dice.append(seat)
			elif not ev.on:
				want_dice.erase(seat)
			return 0.0
		"working":
			working[int(ev.seat)] = ev.on
			return 0.0
	return 0.0


## The roll's decided: the call (said just before this), the losers swept, the winners
## paid seat by seat, winnings and come bets' stakes back to the players, come bets to
## their numbers, the puck over, the dice fetched. Returns how long all that takes.
func _roll_result(ev: Dictionary, d: float) -> float:
	phase = "settling"
	var was := point
	point = int(ev.point) if ev.get("point") != null else -1
	shooter = int(ev.shooter) if ev.get("shooter") != null else -1
	sign_board.show_roll(ev.history)
	sign_board.point = point
	sign_board.rolls = int(ev.rolls)
	result_text = _describe(ev, was)
	if ev.get("rest") != null:
		dice.rest(ev.rest)
	var steps: Dictionary = ev.get("seats", {})
	var mine_paid := false
	var t := T_CALL * d
	# The base dealers sweep the losers into the rack...
	var k := 0
	for key in steps:
		for st in steps[key]:
			if st.kind == "lose":
				_after(t + k * 0.04 * d).timeout.connect(_settle_step.bind(int(key), {"spot": st.spot, "action": "collect"}, d))
				k += 1
	if k > 0:
		t += T_SWEEP * d
	# ...pay the winners beside their bets, a player at a time...
	var paid_seats := []
	for key in steps:
		var seat := int(key)
		var paid := false
		for st in steps[key]:
			if st.kind == "win":
				_after(t).timeout.connect(_settle_step.bind(seat, {"spot": st.spot, "action": "pay", "payout": int(st.win)}, d))
				paid = true
			if st.kind in ["win", "return"]:
				mine_paid = mine_paid or seat == my_seat
		if paid:
			paid_seats.append(seat)
			t += T_PAY_STEP * d
	if mine_paid:
		Session.hold_balance(true)   # show the new balance when the chips reach you
	if not paid_seats.is_empty():
		t += T_PAY_PAUSE * d
	# ...the winnings go back, with the stakes that come off (come bets, odds).
	var back := mine_paid or not paid_seats.is_empty()
	_after(t).timeout.connect(func():
		for key in steps:
			var seat := int(key)
			for st in steps[key]:
				if (st.kind == "win" and not st.stays) or st.kind == "return":
					_take_stack(seat, st.spot, chair_pos(seat), d)
		for seat in _payouts.keys():
			for stack in _payouts[seat]:
				_fly_and_free(stack, chair_pos(seat), 0.4 * d)
		_payouts.clear())
	if back:
		t += T_BACK * d
	if mine_paid:
		_after(t).timeout.connect(Session.hold_balance.bind(false))
	# Come bets travel to their numbers.
	var moves := 0
	for key in steps:
		for st in steps[key]:
			if st.kind == "move":
				_after(t).timeout.connect(_move_bet.bind(int(key), st.spot, st.to, d))
				moves += 1
	if moves > 0:
		t += T_MOVE * d
	_after(t).timeout.connect(func(): dice.fetch(T_FETCH * d))
	return t + T_FETCH * d


func _move_bet(seat: int, from: String, to: String, d: float) -> void:
	var chips := _chips_for(seat)
	if not chips.has(from):
		return
	var stack: ChipStack2D = chips[from]
	chips.erase(from)
	if chips.has(to):   # (already a bet there: they join up)
		var total := int(chips[to].amount) + int(stack.amount)
		var tw := _tween()
		tw.tween_property(stack, "position", spot_pos(seat, to), 0.4 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN_OUT)
		tw.tween_callback(func():
			stack.queue_free()
			_set_stack(seat, to, total))
		return
	chips[to] = stack
	_tween().tween_property(stack, "position", spot_pos(seat, to), 0.45 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN_OUT)


static func _describe(ev: Dictionary, was: int) -> String:
	var words: String = ev.get("words", "")
	match ev.get("what", ""):
		"point_set":
			return "%s  ·  the point is %d" % [words, int(ev.total)]
		"point_made":
			return "%s  ·  the point! Pass Line wins" % words
		"seven_out":
			return "Seven out  ·  new shooter"
		"natural":
			return "%s  ·  winner on the line" % words
		"craps":
			return "%s  ·  craps" % words
	return "%s  ·  the point is still %d" % [words, was] if was > 0 else words


# ------------------------------------------------------------------ input
func _process(delta: float) -> void:
	super._process(delta)
	if Engine.is_editor_hint():
		return
	var h := {}
	if mode == "seated" and my_seat >= 0 and accepting_bets():
		h = region_at(get_local_mouse_position())
	if h != hover:
		hover = h
		_felt.queue_redraw()
	sign_board.footer = _countdown_text(timer_left()) if phase == "betting" else ("DICE ARE OUT" if phase == "throwing" else "")


func _needs_redraw() -> bool:
	return not hover.is_empty() or dice.is_moving() or _puck_moving()


func _unhandled_input(event: InputEvent) -> void:
	if Engine.is_editor_hint() or mode != "seated" or my_seat < 0:
		return
	if not (event is InputEventMouseButton and event.pressed):
		return
	var h := region_at(get_local_mouse_position())
	if h.is_empty():
		return
	var spot := spot_for(h.id)
	if event.button_index == MOUSE_BUTTON_LEFT:
		spot_clicked.emit(spot)
	elif event.button_index == MOUSE_BUTTON_RIGHT:
		spot_removed.emit(spot)
	get_viewport().set_input_as_handled()


# ------------------------------------------------------------------ overlays
func _puck_target(h: int) -> Vector2:
	return Vector2(box_cx(point, h), -107.5) if point > 0 else Vector2(mx(49, h), -106)


func _puck_moving() -> bool:
	return _puck[1].distance_to(_puck_target(1)) > 0.05 or _puck[-1].distance_to(_puck_target(-1)) > 0.05


## A standing spot on the floor by the rail, in the seating style's look (Seating.draw_spot):
## it glows while it's free and you're walking; a taken one wears its player's colour.
func _draw_stool(seat: int, glow: bool, pulse: float) -> void:
	Seating.draw_spot(self, chair_pos(seat) + Vector2(0, 4), str(Seating.style(table_id).craps_spot), glow, pulse,
		SEAT_COLOURS[seat % SEAT_COLOURS.size()] if occupants.has(seat) else null)


func _draw_game(now: float, _pulse: float) -> void:
	# The pucks: OFF in the Don't Come box, ON on the point -- they slide across.
	for h in [1, -1]:
		_puck[h] = _puck[h].lerp(_puck_target(h), 0.12)
		var p: Vector2 = _puck[h]
		var on := point > 0
		_disc(p + Vector2(0.5, 0.9), 4.4, Color(0, 0, 0, 0.4))
		_disc(p, 4.4, Color("f6f2e8") if on else Color("121010"))
		draw_arc(p, 3.6, 0, TAU, 32, Color("121010") if on else Color("f6f2e8"), 0.5, true)
		_label(p + Vector2(0, 0.2), "ON" if on else "OFF", 2.8 if on else 2.3, Color("121010") if on else Color("f6f2e8"))
	# The dealer's buttons on bets: OFF (not working this come-out), BUY, LAY.
	for seat in _seat_chips:
		for spot in _seat_chips[seat]:
			var marker := ""
			if point < 0 and off_on_come_out(spot) and not working.get(seat, false):
				marker = "OFF"
			elif spot.begins_with("buy_"):
				marker = "BUY"
			elif spot.begins_with("lay_"):
				marker = "LAY"
			if marker != "":
				var at: Vector2 = _seat_chips[seat][spot].position + Vector2(2.6, -3.4)
				_disc(at, 1.9, Color("111111") if marker == "OFF" else Color("f4efe4"))
				draw_arc(at, 1.9, 0, TAU, 16, BRASS_RING, 0.3, true)
				_label(at + Vector2(0, 0.1), marker, 1.2, Color.WHITE if marker == "OFF" else Color("111111"))
	# The stickman's stick, out towards the dice.
	var hand := dealer.position + Vector2(7, -1)
	var tip := Vector2(10, -6) if phase != "throwing" else Vector2(7, 1)
	draw_line(hand, tip, Color("d8c49a"), 0.9, true)
	draw_polyline(PackedVector2Array([tip, tip + Vector2(2.4, -0.4), tip + Vector2(2.2, 2)]), Color("d8c49a"), 1.1, true)
	# The shooter's badge, at their feet.
	if shooter >= 0 and occupants.has(shooter):
		var b := chair_pos(shooter) + Vector2(0, 17)
		draw_colored_polygon(TableFelt._rounded(Rect2(b.x - 11, b.y - 2.8, 22, 5.6), 2.8), Color(0, 0, 0, 0.6))
		_label(b + Vector2(0, 0.1), "SHOOTER", 3.0, Color("ecd08a"))
	for seat in want_dice:
		if occupants.has(seat) and seat != shooter:
			_label(chair_pos(seat) + Vector2(0, 17), "next shooter", 2.8, Color("ecd08a"))
	# A ghost of your chip where it would go.
	if not hover.is_empty() and my_seat >= 0:
		var at := spot_pos(my_seat, spot_for(hover.id)) - Vector2(0, 1.2)
		var c: Color = SEAT_COLOURS[my_seat % SEAT_COLOURS.size()]
		_disc(at, ChipStack2D.TINT_RADIUS * CHIP_SCALE, Color(c, 0.55))
		draw_arc(at, ChipStack2D.TINT_RADIUS * CHIP_SCALE - 0.4, 0, TAU, 24, Color(1, 1, 1, 0.5), 0.6, true)
		_label(at + Vector2(0, 0.1), ChipStack2D._label(chip_value), 2.4, Color(0.1, 0.05, 0.02, 0.8))


const BRASS_RING := Color("c9a24a")


func _disc(at: Vector2, radius: float, colour: Color) -> void:
	var pts := PackedVector2Array()
	for k in 20:
		pts.append(at + Vector2.from_angle(k * TAU / 20) * radius)
	draw_colored_polygon(pts, colour)


## Text centred on a point at any size (fonts take whole sizes; the rest is scaled).
func _label(at: Vector2, s: String, size: float, colour: Color) -> void:
	var px := maxi(1, ceili(size * 2))
	var k := size / px
	var w := Card2D.FONT.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x
	draw_set_transform(at, 0, Vector2(k, k))
	draw_string(Card2D.FONT, Vector2(-w / 2, px * 0.36), s, HORIZONTAL_ALIGNMENT_LEFT, -1, px, colour)
	draw_set_transform(Vector2.ZERO)
