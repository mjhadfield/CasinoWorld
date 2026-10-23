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
## colour, as at the roulette table. Each number box is split as in a casino:
## Lay along the top, Place across the number, Buy along the bottom, and a click
## on one is that bet. A click on your own come (or don't come) bet on its number
## backs it with odds; after the point, a click on the Pass Line (or just behind
## it) puts odds down, on Don't Pass lays them. Each player's chips wait in the
## rail in front of them, in the denominations they bet in.
##
## A roll: "Dice are out", the throw (the server's plan, played by CrapsDice),
## the stickman's call, the losers swept into the rack, the winners paid beside
## their bets a player at a time, winnings back to the players, come bets off
## to their numbers, the puck over, the dice hooked back to the middle.
##
## Everything pays in whole pounds, so chips go down in each bet's proper unit
## (step_bet()). The vig is chips you can see: a lay bet's goes from the player
## past the bet into the rack as the dice go out (it comes back if the bet comes
## down), and a winning buy or lay bet is paid in full and then the dealer takes
## the vig off the payout.

# The table (table coordinates: the players' edge of the felt is y = 0).
const FELT_HALF := 189.0
const FELT_TOP := -121.0
const FELT_FRONT := 0.0
const RAIL_W := 9.0
const CORNER := 17.0
const RUBBER_W := 4.0            # the pyramids lining the end walls, round the corners to where the rail turns level
# The chip rail: a groove along the players' rail, each side of the stickman. A player's
# chips start just inboard of them (towards the stickman), clear of their head.
const GROOVE_FROM := 20.0       # the chip rail's groove: from this far either side of the middle,
const GROOVE_OUT := 4.5         # this far out from the felt (its middle),
const GROOVE_W := 4.6           # this wide,
const GROOVE_TO := -100.0       # round the corners and up the ends to here
const RAIL_HEAD := 12.0         # how far either side of a player their head hides the rail
const RAIL_MAX := 15             # chips in one player's run (the gap to the next player's head)
const BAY_HALF := 35.0           # the boxman's bay: half its width at the felt,
const BAY_FLOOR := -107.0        # how far into the table it reaches,
const BAY_CORNER := 5.0          # and its corners
const LEDGE := 8.0               # how much deeper the rail is across the bay's floor (the rack is cut into it)
const RACK_AT := Vector2(0, -115.0)   # the boxman's chip rack, cut into the ledge across the bay's floor
const TITLE_AT := Vector2(0, -12.5)
# The layout. Each end is the same, mirrored; these are the right-hand end's x.
const NUMS := [4, 5, 6, 8, 9, 10]
const BOXW := 124.0 / 6.0
const NUM_TOP := -117.0
const NUM_H := 30.0
const LAY_H := 8.0               # each number box's Lay strip along the top,
const BUY_H := 8.0               # and its Buy strip along the bottom (Place is the number between)
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
const MIN_MAIN := 500            # engines/craps.MIN_MAIN (hardways, props and odds go lower)
const SEAT_COLOURS := [Color("5ab0e8"), Color("f2c14e"), Color("ef7aa0"), Color("5fd3a0"),
	Color("a98ef2"), Color("e8935a"), Color("e85a5a"), Color("9ad94f")]
const CHIP_SCALE := 0.6
const BOX_CHIP_SCALE := 0.5      # smaller on the number boxes, so the rows clear each other and the number
const ODDS_DX := 2.7             # come odds sit on the come bet, half a chip in towards the box's middle
const PUCK_R := 3.4
const OFF_AT := Vector2(2.6, -3.4)   # the dealer's OFF button on a bet, from it (for a CHIP_SCALE chip)
# The settle's pace (the server's Timings).
const T_CALL := 1.4
const T_SWEEP := 1.0
const T_PAY_STEP := 0.32
const T_PAY_PAUSE := 0.6
const T_VIG := 0.45              # a payout's vig comes off this long after it's put down,
const T_VIG_PAUSE := 0.5         # and the winnings wait this much longer to go back
const T_BACK := 0.9
const T_MOVE := 0.7
const T_FETCH := 0.85

static var _spots := []

var point := -1
var shooter := -1
var human_shooter := false
var want_dice := []
var working := {}                # seat -> bool
var hover := {}                  # {id, h} under the pointer while you can bet
var chip_value := 100
var result_text := ""
var _locked := {}                # the local player's bets that are already paid for
var _puck := {1: Vector2(49, -106), -1: Vector2(-49, -106)}
var _bet_size := {}              # seat -> the biggest bet (not odds) they've had down since sitting
var _marks: Node2D               # over the chips: the OFF buttons and the come-and-odds tags
var _off_drawn := []             # the OFF buttons shown: [[at, radius], ...]
var _tags_drawn := []            # the tags shown: [[at, text, seat], ...]
var _rail_drawn := {}            # what the chip rail shows: seat -> bet size
var _rail: Node2D                # the chips in the rail (redrawn only when they change)

@onready var dice: CrapsDice = $Felt/Dice
@onready var sign_board: CrapsSign = $Sign


func _ready() -> void:
	super._ready()
	if Engine.is_editor_hint():
		return
	dice.position = -_felt.position
	_stand_sign(sign_board, $Body/SignBase)
	_dice_tone()
	dice.z_index = 2   # over the chips (which sit over cards at z 1); the dice only rest where no one's head reaches
	_rail = Node2D.new()
	_rail.position = -_felt.position
	_rail.draw.connect(_draw_rail)
	_felt.add_child(_rail)
	_marks = Node2D.new()   # (over the chips, which are drawn over the table's own drawing)
	_marks.position = -_felt.position
	_marks.z_index = 1
	_marks.draw.connect(_draw_marks)
	_felt.add_child(_marks)
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
		return ["Buy %d" % n, "%s; £1 vig per £20 bet, out of a win" % odds[n]]
	if spot.begins_with("lay_"):
		return ["Lay %d" % n, "%s; £1 vig per £20 it wins, paid with the bet" % lay[n]]
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


## What the local player has down that isn't paid for yet (it's paid for when the dice go out),
## with the vig on new lay bets.
func pending_cost(bets: Dictionary) -> int:
	var total := 0
	for spot in bets:
		total += maxi(0, int(bets[spot]) - int(_locked.get(spot, 0)))
	return total + maxi(0, vig_up_front(bets) - vig_up_front(_locked))


# ------------------------------------------------------------------ whole pounds and the vig
## A bet's proper unit: in multiples of it, it's paid (and its vig taken) in whole pounds.
## The server's engines/craps.unit().
static func unit(spot: String, the_point: int) -> int:
	var n := the_point if spot in ["pass_odds", "dont_odds"] else number_of(spot)
	if spot.begins_with("place_"):
		return 600 if n in [6, 8] else 500
	if n > 0 and (spot.begins_with("buy_") or spot == "pass_odds" or spot.begins_with("come_odds_")):
		return {4: 100, 10: 100, 5: 200, 9: 200, 6: 500, 8: 500}[n]
	if n > 0 and (spot.begins_with("lay_") or spot == "dont_odds" or spot.begins_with("dcome_odds_")):
		return {4: 200, 10: 200, 5: 300, 9: 300, 6: 600, 8: 600}[n]
	return {"horn": 400, "ce": 200}.get(spot, 100)


## Chips go on and come off in the bet's proper unit, as a dealer would make them up: a £5
## chip places the 6 for £6, a £25 one buys the 9 for £26, a £1 chip on the Horn makes it £4.
func step_bet(spot: String, old: int, chip: int, adding: bool) -> int:
	var u := unit(spot, point)
	if not adding:
		return maxi(0, old - chip) / u * u
	var low := 0 if PROPS.has(spot) or "odds" in spot else MIN_MAIN
	return (maxi(old + chip, low) + u - 1) / u * u


## 5% in whole pounds: £1 for every £20, rounded down, never less than £1 (engines/craps.vig()).
static func vig(pence: int) -> int:
	return maxi(100, pence / 2000 * 100) if pence > 0 else 0


## What a lay bet on n wins, in whole pounds.
static func lay_win(n: int, amount: int) -> int:
	var win := amount / 2 if n in [4, 10] else amount * 2 / 3 if n in [5, 9] else amount * 5 / 6
	return win / 100 * 100


## The vig paid with these bets, up front (the lay bets').
static func vig_up_front(bets: Dictionary) -> int:
	var total := 0
	for spot in bets:
		if spot.begins_with("lay_") and int(bets[spot]) > 0:
			total += vig(lay_win(number_of(spot), int(bets[spot])))
	return total


## A seat hands the dealer a lay bet's vig: a chip from the player, past the bet, into the rack.
func _vig_to_rack(seat: int, spot: String, amount: int, d: float) -> void:
	var chip := _vig_stack(seat, amount, chair_pos(seat))
	var tw := _tween()
	tw.tween_property(chip, "position", payout_pos(seat, spot), 0.3 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tw.tween_interval(0.25 * d)
	tw.tween_callback(sfx_at.bind("sweep", to_global(payout_pos(seat, spot))))
	tw.tween_property(chip, "position", tray_pos(), 0.35 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN_OUT)
	tw.tween_callback(chip.queue_free)


func _vig_stack(seat: int, amount: int, at: Vector2) -> ChipStack2D:
	var chip := _make_stack(seat)
	chip.amount = amount
	chip.caption = "VIG"
	chip.position = at
	_dyn.add_child(chip)
	return chip


## A winning buy or lay bet: paid in full beside the bet, then the dealer takes the vig off
## the payout into the rack.
func _pay_less_vig(seat: int, spot: String, win: int, vig_taken: int, d: float) -> void:
	var stack := _payout_from_tray(seat, win + vig_taken)
	var to := payout_pos(seat, spot)
	_tween().tween_property(stack, "position", to, 0.35 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	_after(T_VIG * d).timeout.connect(func():
		if not is_instance_valid(stack):
			return
		stack.amount = win
		var chip := _vig_stack(seat, vig_taken, to)
		sfx_at("sweep", to_global(to))
		var tw := _tween()   # lifted off the payout, held a moment, then into the rack
		tw.tween_property(chip, "position", to + Vector2(4.5, -4), 0.14 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
		tw.tween_interval(0.18 * d)
		tw.tween_property(chip, "position", tray_pos(), 0.32 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN_OUT)
		tw.tween_callback(chip.queue_free))


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


## Each end's printed areas: region id -> Rect2. A number box's three strips are
## named for the bet a click there makes (lay_6, place_6, buy_6).
static func zones(h: int) -> Dictionary:
	var z := {"dont_come": _r(38, -117, 60, -87, h), "come": _r(38, -87, 170, -59, h), "field": _r(38, -59, 148, -37, h),
		"big6": _r(148, -59, 170, -43, h), "big8": _r(148, -43, 170, -27, h), "dont_pass": _r(38, -37, 148, -27, h)}
	for n in NUMS:
		var x := box_x(n, h)
		z["lay_%d" % n] = Rect2(x, NUM_TOP, BOXW, LAY_H)
		z["place_%d" % n] = Rect2(x, NUM_TOP + LAY_H, BOXW, NUM_H - LAY_H - BUY_H)
		z["buy_%d" % n] = Rect2(x, NUM_TOP + NUM_H - BUY_H, BOXW, BUY_H)
	return z


## A number's whole box (all three strips).
static func number_box(n: int, h: int) -> Rect2:
	return Rect2(box_x(n, h), NUM_TOP, BOXW, NUM_H)


## The rubber lining an end wall (h: which end), `inset` in from the felt's edge: from where
## the rail turns level at the back, round the corner, down the wall and round to the front.
## The middle of the chip rail's groove on one side, or a line `out` from the felt alongside
## it: along the players' rail from beside the stickman, round the corner and up the end.
static func groove_path(h: int, out: float) -> PackedVector2Array:
	var pts := PackedVector2Array([Vector2(mx(GROOVE_FROM, h), FELT_FRONT + out)])
	var centre := Vector2(FELT_HALF - CORNER, FELT_FRONT - CORNER)
	for i in 13:
		var a := lerpf(0.5 * PI, 0.0, i / 12.0)
		var p := centre + Vector2(cos(a), sin(a)) * (CORNER + out)
		pts.append(Vector2(mx(p.x, h), p.y))
	pts.append(Vector2(mx(FELT_HALF + out, h), GROOVE_TO))
	return pts


static func rubber_path(h: int, inset: float) -> PackedVector2Array:
	var rad := Vector2(CORNER - inset, CORNER - inset)
	var x := FELT_HALF - CORNER
	var pts := PackedVector2Array()
	_arc(pts, Vector2(x, FELT_TOP + CORNER), rad, -PI / 2, 0, 10)
	_arc(pts, Vector2(x, FELT_FRONT - CORNER), rad, 0, PI / 2, 10)
	if h == -1:
		for i in pts.size():
			pts[i].x = -pts[i].x
	return pts


## The felt inside the rubber: what the layout is printed on.
static func _printable() -> PackedVector2Array:
	if _printable_poly.is_empty():
		_printable_poly = shape(-RUBBER_W, true, 12)
	return _printable_poly


static var _printable_poly := PackedVector2Array()


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
## follows the curve of the Pass Line, and the outside number box's the corner of the rail.
static func zone_poly(id: String, h: int) -> PackedVector2Array:
	var r: Rect2 = zones(h)[id]
	if id != "big8":
		var pts := PackedVector2Array([r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)])
		if maxf(absf(r.position.x), absf(r.end.x)) > FELT_HALF - CORNER:
			var inside := Geometry2D.intersect_polygons(pts, _printable())
			if not inside.is_empty():
				return inside[0]
		return pts
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


## What's under the pointer for the local player: their own come (or don't come) bet on a
## number, which a click backs with odds (come_odds_6); otherwise the printed region there.
func region_here(p: Vector2) -> Dictionary:
	if my_seat >= 0:
		for spot in _chips_for(my_seat):
			if not (spot.begins_with("come_") or spot.begins_with("dcome_")):
				continue
			var odds: String = spot.replace("come_", "come_odds_") if not "odds" in spot else spot
			var stack: ChipStack2D = _chips_for(my_seat)[spot]
			var top := stack.position - Vector2(0, stack.lift * stack.scale.y)   # (the odds, sitting on it)
			if p.distance_to(top) <= ChipStack2D.TINT_RADIUS * stack.scale.x + 0.5:
				return {"id": odds, "h": half(my_seat)}
	return region_at(p)


## The bet a click on `region` makes for the local player.
func spot_for(region: String) -> String:
	if region == "pass":
		return "pass" if point < 0 else "pass_odds"
	if region == "dont_pass":
		return "dont_pass" if point < 0 else "dont_odds"
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
	# A number box: lay bets and don't come bets in the Lay strip, come bets and place bets
	# on the number, buy bets in the Buy strip.
	if spot.begins_with("lay_"):
		return Vector2(box_cx(n, h) + fan, -113.5)
	if spot.begins_with("dcome_odds_"):
		return Vector2(box_cx(n, h) + fan - signf(fan) * ODDS_DX, -111.5)
	if spot.begins_with("dcome_"):
		return Vector2(box_cx(n, h) + fan, -111.5)
	if spot.begins_with("come_odds_"):
		return Vector2(box_cx(n, h) + fan - signf(fan) * ODDS_DX, -106)
	if spot.begins_with("come_"):
		return Vector2(box_cx(n, h) + fan, -106)
	if spot.begins_with("buy_"):
		return Vector2(box_cx(n, h) + fan, -91)
	return Vector2(box_cx(n, h) + fan, -98)   # place


## How big a stack is drawn at `p`: smaller on the number boxes (it shrinks as a come bet travels there).
func chip_scale_at(p: Vector2) -> float:
	for n in NUMS:
		for h in [1, -1]:
			if number_box(n, h).has_point(p):
				return BOX_CHIP_SCALE
	return CHIP_SCALE


## Odds on a come (or don't come) bet sit on top of it, with one tag for both ("5+10").
func _dress_chips(delta: float) -> void:
	for child in _dyn.get_children():
		if child is ChipStack2D:
			var want := chip_scale_at(child.position)
			var k := move_toward(child.scale.x, want, delta * 0.6) if child.has_meta("dressed") else want
			child.set_meta("dressed", true)
			if k != child.scale.x:
				child.scale = Vector2(k, k)
	for seat in _seat_chips:
		var chips: Dictionary = _seat_chips[seat]
		for spot in chips:
			if not "odds_" in spot or not (spot.begins_with("come_") or spot.begins_with("dcome_")):
				continue
			var odds: ChipStack2D = chips[spot]
			var base: ChipStack2D = chips.get(spot.replace("odds_", ""))
			if not is_instance_valid(odds):
				continue
			if base and is_instance_valid(base):
				base.label = "-"   # (the pair's tag says both: _odds_tags)
				odds.label = "-"
				odds.lift = ChipStack2D.tint_layers(base.amount) * ChipStack2D.TINT_LAYER
				if odds.get_index() < base.get_index():
					_dyn.move_child(odds, base.get_index())
			elif odds.label == "-":
				odds.label = ""
				odds.lift = 0.0
		for spot in chips:   # (a come bet whose odds have gone shows its own label again)
			var stack: ChipStack2D = chips[spot]
			if is_instance_valid(stack) and stack.label == "-" and not chips.has(spot.replace("come_", "come_odds_")):
				stack.label = ""


func _set_stack(seat: int, spot: String, amount: int, at := Vector2.INF) -> void:
	super._set_stack(seat, spot, amount, at)
	var stack: ChipStack2D = _chips_for(seat).get(spot)
	if stack and not stack.has_meta("dressed"):   # (put down at its size, not grown and shrunk)
		var k := chip_scale_at(stack.position)
		stack.scale = Vector2(k, k)
		stack.set_meta("dressed", true)


## The dealer's OFF buttons on bets that aren't working this come-out: [[at, radius], ...].
func _off_buttons() -> Array:
	var out := []
	if point > 0:
		return out
	for seat in _seat_chips:
		if working.get(seat, false):
			continue
		for spot in _seat_chips[seat]:
			var stack: ChipStack2D = _seat_chips[seat][spot]
			if off_on_come_out(spot) and is_instance_valid(stack):
				out.append(_off_button(stack))
	return out


## A tag over each come (or don't come) bet with odds on it, saying both: [[at, "5+10", seat], ...].
func _odds_tags() -> Array:
	var out := []
	for seat in _seat_chips:
		var chips: Dictionary = _seat_chips[seat]
		for spot in chips:
			var odds: ChipStack2D = chips[spot]
			var base: ChipStack2D = chips.get(spot.replace("odds_", ""))
			if not "odds_" in spot or base == odds or not base or not is_instance_valid(base) or not is_instance_valid(odds):
				continue
			var top := func(stack: ChipStack2D) -> Vector2:
				return stack.position - Vector2(0, (stack.lift + (ChipStack2D.tint_layers(stack.amount) - 1) * ChipStack2D.TINT_LAYER) * stack.scale.y)
			out.append([(top.call(base) + top.call(odds)) / 2,
				"%s+%s" % [ChipStack2D._label(base.amount), ChipStack2D._label(odds.amount)], seat])
	return out


func _draw_marks() -> void:
	for tag in _tags_drawn:
		var size := 2.4   # (a bit bigger than a chip's own number at full size, whatever the chips' scale)
		var px := ceili(size * 4)
		var k := size / px
		var w := Card2D.FONT.get_string_size(tag[1], HORIZONTAL_ALIGNMENT_LEFT, -1, px).x * k
		var box := TableFelt._rounded(Rect2(tag[0] - Vector2(w / 2 + 0.8, 1.75), Vector2(w + 1.6, 3.5)), 1.6)
		_marks.draw_colored_polygon(box, Color(0.07, 0.05, 0.04, 0.88))
		box.append(box[0])
		_marks.draw_polyline(box, SEAT_COLOURS[int(tag[2]) % SEAT_COLOURS.size()], 0.35, true)
		_marks.draw_set_transform(tag[0], 0, Vector2(k, k))
		_marks.draw_string(Card2D.FONT, Vector2(-w / k / 2, px * 0.36), tag[1], HORIZONTAL_ALIGNMENT_LEFT, -1, px, Color("f6f2e8"))
		_marks.draw_set_transform(Vector2.ZERO)
	for button in _off_drawn:
		var at: Vector2 = button[0]
		var r: float = button[1]
		_marks.draw_circle(at, r, Color("111111"))
		_marks.draw_arc(at, r, 0, TAU, 16, BRASS_RING, 0.3, true)
		var px := maxi(1, ceili(2.4 * r / 1.9))
		var k := 1.2 * r / 1.9 / px
		var w := Card2D.FONT.get_string_size("OFF", HORIZONTAL_ALIGNMENT_LEFT, -1, px).x
		_marks.draw_set_transform(at + Vector2(0, 0.1), 0, Vector2(k, k))
		_marks.draw_string(Card2D.FONT, Vector2(-w / 2, px * 0.36), "OFF", HORIZONTAL_ALIGNMENT_LEFT, -1, px, Color.WHITE)
		_marks.draw_set_transform(Vector2.ZERO)


## Where a stack's OFF button goes, and how big it is, by the stack's size.
func _off_button(stack: ChipStack2D) -> Array:
	var k := stack.scale.x / CHIP_SCALE
	return [stack.position + OFF_AT * k - Vector2(0, stack.lift * stack.scale.y), 1.9 * k]


func payout_pos(seat: int, spot: String, _bonus := false) -> Vector2:
	return spot_pos(seat, spot) + Vector2(4.5, -3.5)


## Craps has its own kind of table style (and keeps today's chips).
func styled() -> bool:
	return false


func style_kind() -> String:
	return "craps"


func restyle() -> void:
	super.restyle()
	_dice_tone()


## The dice, on the table and on the sign, in the style's colour.
func _dice_tone() -> void:
	var tone: Array = TableStyle.DICE.get(str(style().dice), TableStyle.DICE.red)
	dice.tone = tone
	dice.queue_redraw()
	sign_board.tone = tone
	sign_board.queue_redraw()


func _make_stack(seat: int) -> ChipStack2D:
	var stack := ChipStack2D.new()
	stack.tint = SEAT_COLOURS[seat % SEAT_COLOURS.size()]
	stack.scale = Vector2(CHIP_SCALE, CHIP_SCALE)
	return stack


## The rack's well (it has no frame: it's cut straight into the ledge).
func tray_rect() -> Rect2:
	return Rect2(RACK_AT - Vector2(23, 6.5), Vector2(46, 13))


func tray_pos() -> Vector2:
	return RACK_AT


func shoe_pos() -> Vector2:
	return Vector2(0, -60)


func focus_point() -> Vector2:
	return to_global(Vector2(10, -46))


func title_y() -> float:
	return TITLE_AT.y


func countdown_pos() -> Vector2:
	return Vector2(-36, -7.5)   # behind the line, left of the dice and the stickman's speech bubble


func stool_pos(seat: int) -> Vector2:
	return chair_pos(seat) + on_screen(Vector2(0, 3))


## The players stand at the rail, 34.5 below it: past its far side their feet come to 8 behind
## it, and on its side to 14.5 beside it (see CasinoTable.chair_tuck()).
func tuck_far() -> float:
	return 26.5


func tuck_side() -> float:
	return 20.0


## The dealer here is the stickman, who stands among the players, so turning the table moves
## him only as far as them (chair_tuck()); the boxman already stands just outside the bay's ledge.
func dealer_near_pos() -> Vector2:
	return _dealer_home + chair_tuck()


## Beside a table on its side, the boxman draws over the rail as the stickman does.
func _turned_on_screen() -> void:
	super._turned_on_screen()
	$Boxman.z_index = dealer.z_index


func _countdown_text(left: float) -> String:
	if phase != "betting" or left <= 0:
		return ""
	if shooter == my_seat and my_seat >= 0:
		return "YOUR ROLL  %d" % ceili(left)
	return ("SHOOTER TO ROLL  %d" if human_shooter else "DICE OUT IN %d") % ceili(left)


# ------------------------------------------------------------------ the table's shape
## The outline, grown outwards from the felt by `grow` (RAIL_W: the rail's outer edge).
## `bay` false fills the boxman's bay in (for collision). Across the bay's floor the rail is
## a ledge LEDGE deeper, reaching back towards the boxman, so the outlines of its edge
## and its grain spread out over it.
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
		var floor_y := BAY_FLOOR - grow - LEDGE * clampf(grow / (RAIL_W - 2.0), 0.0, 1.0)
		var c := minf(BAY_CORNER, (floor_y - top) / 2.0)   # the bay is shallower behind the ledge
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
			info_text += "  ·  you have «%s» on it" % Money.format(mine)
			if not removable(spot, point):
				info_text += " (it stays until decided)"
		elif point < 0 and off_on_come_out(spot) and not working.get(my_seat, false):
			info_text += "  ·  off on the come-out"
	else:
		var who: String = str(occupants[shooter].name) if occupants.has(shooter) else "Nobody"
		var where := "Point is «%d»" % point if point > 0 else "Coming out"
		var left := ceili(timer_left())
		match phase:
			"betting":
				if my_roll:
					var line := int(ctx.get("my_bets", {}).get("pass", 0)) + int(ctx.get("my_bets", {}).get("dont_pass", 0))
					info_text = "%s  ·  Your roll  ·  %s" % [where, "Roll when your bets are down" if line > 0 or point > 0
						else "Put a Pass Line or Don't Pass bet down, then roll"]
				else:
					info_text = "%s  ·  %s shooting" % [where, who]
				if left > 0:
					info_text += "  ·  %s«%d»" % ["" if my_roll else "Dice out in ", left]
			"throwing":
				info_text = "Dice are out  ·  No more bets"
			_:
				info_text = result_text
	# the dice sit left of the chips (where Ready is at the other tables); Working is the switch beside Undo and Clear
	var actions := []
	if my_roll:
		actions.append({"id": "pass_dice", "label": "Pass dice", "place": "commit", "kind": "quiet"})
		actions.append({"id": "roll", "label": "Roll  [R]", "key": "R", "place": "commit", "kind": "primary"})
	elif my_seat >= 0 and shooter != my_seat:
		var coming: bool = my_seat in want_dice
		actions.append({"id": "take_dice", "label": "Dice coming" if coming else "Take dice  [T]", "key": "T", "place": "commit",
			"kind": "done" if coming else "quiet", "pressed": coming})
	actions.append({"id": "working", "label": "Working  [W]", "key": "W", "pressed": working.get(my_seat, false), "place": "switch"})
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
	return Vector2(seat_x(seat) + 2 * half(seat), CrapsDice.HAND_Y) if seat >= 0 else CrapsDice.HOME[0]


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
			_bet_size.erase(seat)
		"seated":
			_bet_size.erase(int(ev.seat))
		"bet_changed":
			if int(ev.seat) == my_seat:
				for spot in _locked.keys():
					_locked[spot] = mini(int(_locked[spot]), int(ev.bets.get(spot, 0)))
			if int(ev.get("vig_back", 0)) > 0:   # a lay bet's come down: the dealer hands its vig back
				var seat := int(ev.seat)
				_fly_and_free(_vig_stack(seat, int(ev.vig_back), tray_pos()), chair_pos(seat), 0.45)


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
			var vigs: Dictionary = ev.get("vig", {})
			for key in vigs:
				for spot in vigs[key]:
					_vig_to_rack(int(key), spot, int(vigs[key][spot]), d)
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
			if st.kind == "win" and int(st.get("vig", 0)) > 0:
				_after(t).timeout.connect(_pay_less_vig.bind(seat, st.spot, int(st.win), int(st.vig), d))
				paid = true
			elif st.kind == "win":
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
	if steps.values().any(func(list): return list.any(func(st): return st.kind == "win" and int(st.get("vig", 0)) > 0)):
		t += T_VIG_PAUSE * d
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
		h = region_here(get_local_mouse_position())
	if h != hover:
		hover = h
		_felt.queue_redraw()
	_dress_chips(delta)
	var buttons := _off_buttons()
	var tags := _odds_tags()
	if buttons != _off_drawn or tags != _tags_drawn:
		_off_drawn = buttons
		_tags_drawn = tags
		_marks.queue_redraw()
	var rail := _rail_contents()
	if rail != _rail_drawn:
		_rail_drawn = rail
		_rail.queue_redraw()
	sign_board.footer = _countdown_text(timer_left()) if phase == "betting" else ("DICE ARE OUT" if phase == "throwing" else "")


func _needs_redraw() -> bool:
	return not hover.is_empty() or dice.is_moving() or _puck_moving()


func clickable_at(local: Vector2) -> bool:
	if mode != "seated":
		return super(local)
	return my_seat >= 0 and not region_here(local).is_empty()


func _unhandled_input(event: InputEvent) -> void:
	if Engine.is_editor_hint() or mode != "seated" or my_seat < 0:
		return
	if not (event is InputEventMouseButton and event.pressed):
		return
	var h := region_here(get_local_mouse_position())
	if h.is_empty():
		return
	var spot := spot_for(h.id)
	if event.button_index == MOUSE_BUTTON_LEFT:
		spot_clicked.emit(spot)
	elif event.button_index == MOUSE_BUTTON_RIGHT:
		spot_removed.emit(spot)
	get_viewport().set_input_as_handled()


# ------------------------------------------------------------------ the chip rail
## What the rail shows: seat -> the bet size that player's chips are for. That's the biggest
## bet (odds aside) they've had down since they came to the table; before their first, the
## chip you've picked, or the table minimum for anyone else.
func _rail_contents() -> Dictionary:
	var out := {}
	for seat in occupants:
		var size := int(_bet_size.get(seat, 0))
		var chips := _chips_for(seat)
		for spot in chips:
			if not "odds" in spot:
				size = maxi(size, int(chips[spot].amount))
		_bet_size[seat] = size
		out[seat] = size if size > 0 else (chip_value if seat == my_seat else 500)
	return out


## A player's run of chips in the rail, highest first: mostly the chip they bet in, a couple
## of the next one up, and some smaller ones for change (a few more or less player to player).
static func rail_chips(seat: int, bet: int) -> Array:
	var denoms: Array = ChipButton.COLOURS.keys()
	denoms.sort()
	var i := 0
	while i + 1 < denoms.size() and denoms[i + 1] <= bet:
		i += 1
	var counts := {denoms[i]: 6 + (seat * 3) % 4}
	if i + 1 < denoms.size():
		counts[denoms[i + 1]] = 1 + seat % 2 + (1 if bet >= 3 * denoms[i] else 0)
	if i > 0:
		counts[denoms[i - 1]] = 3 + (seat + 1) % 3
	var out := []
	for k in range(denoms.size() - 1, -1, -1):
		for c in counts.get(denoms[k], 0):
			out.append(denoms[k])
	return out.slice(0, RAIL_MAX)


## The chips in the rail, on their edges in the groove: each player's run starts by their
## head and goes on in towards the stickman.
func _draw_rail() -> void:
	var w := TableFelt.CHIP_EDGE
	for seat in _rail_drawn:
		var side := signf(seat_x(seat))
		var from := seat_x(seat) - side * RAIL_HEAD
		var chips := rail_chips(seat, _rail_drawn[seat])
		for k in chips.size():
			var x := from - side * (k + 0.5) * w
			var chip := Rect2(x - (w - 0.12) / 2, GROOVE_OUT - GROOVE_W / 2 + 0.4, w - 0.12, GROOVE_W - 0.8)
			TableFelt.edge_chip(_rail, chip, chips[k], k, true)


# ------------------------------------------------------------------ overlays
func _puck_target(h: int) -> Vector2:
	if point < 0:
		return Vector2(mx(49, h), -106)   # OFF, in the Don't Come box
	var inner := box_x(point, h) if h == 1 else box_x(point, h) + BOXW   # ON: the number box's top corner nearer the middle
	return Vector2(inner + mx(PUCK_R + 0.6, h), -112.5)


func _puck_moving() -> bool:
	return _puck[1].distance_to(_puck_target(1)) > 0.05 or _puck[-1].distance_to(_puck_target(-1)) > 0.05


## A standing spot on the floor by the rail, in the seating style's look (Seating.draw_spot):
## it glows while it's free and you're walking; a taken one wears its player's colour. While
## you're at the table the free ones aren't shown.
func _draw_stool(seat: int, glow: bool, pulse: float) -> void:
	if mode == "seated" and not occupants.has(seat):
		return
	Seating.draw_spot(self, chair_pos(seat) + on_screen(Vector2(0, 4)), str(Seating.style(table_id).craps_spot), glow, pulse,
		SEAT_COLOURS[seat % SEAT_COLOURS.size()] if occupants.has(seat) else null, -screen_turn())


func _draw_game(now: float, _pulse: float) -> void:
	# The pucks: OFF in the Don't Come box, ON on the point -- they slide across.
	for h in [1, -1]:
		_puck[h] = _puck[h].lerp(_puck_target(h), 0.12)
		var p: Vector2 = _puck[h]
		var on := point > 0
		_disc(p + Vector2(0.4, 0.7), PUCK_R, Color(0, 0, 0, 0.4))
		_disc(p, PUCK_R, Color("f6f2e8") if on else Color("121010"))
		draw_arc(p, PUCK_R - 0.7, 0, TAU, 32, Color("121010") if on else Color("f6f2e8"), 0.4, true)
		_label(p + Vector2(0, 0.15), "ON" if on else "OFF", 2.2 if on else 1.8, Color("121010") if on else Color("f6f2e8"))
	# The stickman's stick, out towards the dice.
	var hand := dealer.position + on_screen(Vector2(7, -1))
	var tip := Vector2(9.5, -14) if phase != "throwing" else Vector2(7, -5)
	draw_line(hand, tip, Color("d8c49a"), 0.9, true)
	draw_polyline(PackedVector2Array([tip, tip + Vector2(2.4, -0.4), tip + Vector2(2.2, 2)]), Color("d8c49a"), 1.1, true)
	# The shooter's badge, at their feet.
	if shooter >= 0 and occupants.has(shooter):
		var b := chair_pos(shooter) + on_screen(Vector2(0, 17))
		draw_colored_polygon(TableFelt._rounded(Rect2(b.x - 11, b.y - 2.8, 22, 5.6), 2.8), Color(0, 0, 0, 0.6))
		_label(b + on_screen(Vector2(0, 0.1)), "SHOOTER", 3.0, Color("ecd08a"), -screen_turn())
	for seat in want_dice:
		if occupants.has(seat) and seat != shooter:
			_label(chair_pos(seat) + on_screen(Vector2(0, 17)), "next shooter", 2.8, Color("ecd08a"), -screen_turn())
	# A ghost of your chip where it would go.
	if not hover.is_empty() and my_seat >= 0:
		var at := spot_pos(my_seat, spot_for(hover.id)) - Vector2(0, 1.2)
		var r := ChipStack2D.TINT_RADIUS * chip_scale_at(at)
		var c: Color = SEAT_COLOURS[my_seat % SEAT_COLOURS.size()]
		_disc(at, r, Color(c, 0.55))
		draw_arc(at, r - 0.4, 0, TAU, 24, Color(1, 1, 1, 0.5), 0.6, true)
		var aim := spot_for(hover.id)   # (what the click adds, in the bet's proper unit)
		var old := int(_chips_for(my_seat)[aim].amount) if _chips_for(my_seat).has(aim) else 0
		_label(at + Vector2(0, 0.1), ChipStack2D._label(maxi(step_bet(aim, old, chip_value, true) - old, 0)), 2.4,
			Color(0.1, 0.05, 0.02, 0.8))


const BRASS_RING := Color("c9a24a")


func _disc(at: Vector2, radius: float, colour: Color) -> void:
	var pts := PackedVector2Array()
	for k in 20:
		pts.append(at + Vector2.from_angle(k * TAU / 20) * radius)
	draw_colored_polygon(pts, colour)


## Text centred on a point at any size (fonts take whole sizes; the rest is scaled).
func _label(at: Vector2, s: String, size: float, colour: Color, turn := 0.0) -> void:
	var px := maxi(1, ceili(size * 2))
	var k := size / px
	var w := Card2D.FONT.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x
	draw_set_transform(at, turn, Vector2(k, k))
	draw_string(Card2D.FONT, Vector2(-w / 2, px * 0.36), s, HORIZONTAL_ALIGNMENT_LEFT, -1, px, colour)
	draw_set_transform(Vector2.ZERO)
