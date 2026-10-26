@tool
class_name CasinoTable
extends FloorGame
## What every table game on the casino floor shares: the swept-bay table and
## its seats, the dealer, the chips and cards on the felt, the Jackpot lights and sign,
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
## At a Master Table: the local player, sitting here, clicked the dealer (to choose or change the game).
signal dealer_clicked
## The local player clicked a chair's 2nd Box pill (a free seat beside them) or Drop Box (their second box's).
signal box_clicked(seat: int)

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
const JACKPOT_SIGN := Vector2(-64, -119.5)   # the jackpot sign's foot: between the rail and the dealer's cards, left of the ledge
const LIMITS_SIGN := Vector2(64, -119.5)     # the limits sign's: its mirror, right of the ledge
## A card table's limits when the floor plan sends none (the server's tables/base.py DEFAULT_LIMITS), in pence.
const DEFAULT_LIMITS := {"main": [500, 50000], "side": [100, 5000]}
const SPOT_R := 7.5       # circle spots: a chip (radius 6) plus a sliver of felt
const SEAT_GAP := 49.0
const CHAIR_Y := 40.0
const SEAT_COUNT := 6

## How the game is named on the floor ("Take a seat -- Three Card Poker").
@export var game_label := "Three Card Poker"
## The plan's game ("three_card_poker"; "master_table" for a Master Table, whatever it's playing), for the minimap.
var game := ""
## Which end its results sign stands past, as the players see it: "left", "right", or "" (the
## usual end: _stand_sign()). Only Roulette and Craps have one; the floor plan sets it.
@export var sign_side := ""
## Its limits from the floor plan: {"main": [min, max], "side": [min, max]} in pence (the limits sign shows them).
var limits := DEFAULT_LIMITS:
	set(v):
		limits = v
		if limits_sign:
			limits_sign.queue_redraw()

var ready_seats := {}
var auto_rebet_seats := {}  # seats with Auto rebet ticked (their spots don't glow: the bets go down by themselves)
var in_hand := false      # the local player was dealt into this hand (either of their boxes)
var my_box := -1          # the seat beside them the local player plays as a second box, or -1
var second_box_ok := false  # this table offers a second box (its game does)
var dealt_seats := []     # the seats dealt into the hand being played
var _my_hands := {}       # each of the local player's boxes -> its hand's name, for the bar
var jackpot_lights := {}  # seat -> "flash" (bet on the disc) | "solid" (locked in)
var _timer_end := 0.0     # betting or decision countdown, in local seconds
var _timer_total := 1.0
var timer_quiet := false  # this countdown doesn't tick (a Rebet's 3 seconds)
var _seat_cards := {}     # seat -> [Card2D]
var _seat_chips := {}     # seat -> {spot: ChipStack2D}
var _flying := {}         # seat -> {spot: amount}: chips still sliding onto the spot
var _payouts := {}        # seat -> [ChipStack2D] (winnings beside the stake)
var _queued := {}         # seat -> {spot: ChipStack2D}: bets for the next hand, put down during this one (faded)
const QUEUED_TINT := Color(1, 1, 1, 0.55)
var _dealer_cards := []
var _dealer_home := Vector2.ZERO  # where the dealer stands (the scene's spot), in the bay behind the felt
var _shown_turn := 0.0            # the screen_turn() last drawn
var look := {}                    # this table's style's design (TableStyle), filled in by style()
## A Master Table (server tables/master.py) is this game's table while it plays it, or MasterTable while it's blank:
## `master_game` is the game it's playing ("" blank), `master` the server's view of it (vote, queued change...).
var is_master := false
var master_game := ""
var master := {}
var master_revert_end := 0.0      # back to the crest at this time (local seconds), or 0
var _dealer_hot := false
var _glows := {}                  # "seat/spot" -> SpotGlow.prepare(): each spot's glow outlines, worked out once
var _glow_since := {}             # spot -> when it started glowing (local seconds), while it glows
var _ring_since := {}             # seat -> when its thinking ring appeared (it fades in), while it shows
var _ring_drawn := {}             # seats whose thinking ring this _draw drew
var _box_ring := false            # the local player's second box wants a ring this _draw (after their own seat's)
const RING_R := 16.0
const RING_FADE := 0.35

@onready var dealer: Avatar = $Dealer
@onready var _felt: Node2D = $Felt
@onready var _dyn: Node2D = $Felt/Dynamic
@onready var shuffler: CardShuffler = get_node_or_null("Felt/Machines/Shuffler")   # card games only
@onready var discard_rack: DiscardRack = get_node_or_null("Felt/Fixtures/DiscardRack")
var jackpot_sign: JackpotSign   # card games only: built in _ready()
var limits_sign: LimitsSign     # ...and its partner at the other end of the ledge


func _init() -> void:
	phase = "betting"


func _ready() -> void:
	if Engine.is_editor_hint():
		return
	_dealer_home = dealer.position
	_dyn.position = -_felt.position  # Dynamic children use table coordinates
	for path in ["Felt/Lights", "Felt/Fixtures", "Felt/Machines"]:  # (Roulette has none of these)
		var layer := get_node_or_null(path) as Node2D
		if layer:
			layer.position = -_felt.position
	var machines := get_node_or_null("Felt/Machines")
	if machines:   # (every card table: the sign's off at a game with no Jackpot bet)
		jackpot_sign = JackpotSign.new()
		jackpot_sign.position = JACKPOT_SIGN
		machines.add_child(jackpot_sign)
		limits_sign = LimitsSign.new()
		limits_sign.position = LIMITS_SIGN
		machines.add_child(limits_sign)
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


## A spot's printed outline, as StyledFelt.spot() takes it ("circle" r, "diamond" hw hh, or "box" w h rad, at
## `at`): what it glows round and where a click lands on it. Most are a circle a chip just fits in; a game gives
## its others.
func spot_shape(seat: int, spot: String) -> Dictionary:
	return {"shape": "circle", "at": spot_pos(seat, spot), "r": SPOT_R}


## The bet that has to be down to play a hand, and spots that are a flat amount.
func main_spot() -> String:
	return ""


## The bets a hand starts from (Baccarat's Banker and Player, Hold'em's Ante and Blind): they glow when you sit
## down, and the side bets glow once one of them has chips on it.
func primary_spots() -> Array:
	return [main_spot()]


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
## my_ready, my_bets. Returns {info, actions: [{id, label, key}], my_turn, prompt?}. The floor shows `info` only
## while you're up against a countdown (betting, your decision, the sorter) or when `prompt` is true.
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


## What a spot's bet becomes when a chip goes on it (or comes off). A table can step
## its bets in their own units (craps pays in whole pounds).
func step_bet(_spot: String, old: int, chip: int, adding: bool) -> int:
	return old + chip if adding else maxi(0, old - chip)


## What of these bets hasn't been paid for yet (shown off the balance until it is).
func pending_cost(bets: Dictionary) -> int:
	var total := 0
	for spot in bets:
		total += int(bets[spot])
	return total


## Whether the spots glow while you can bet (not on a layout of 157 spots).
func pulse_spots() -> bool:
	return true


## The local player's spots waiting for chips: the primary bets until one's down, then the side bets still empty.
func glowing_spots() -> Array:
	var chips := _chips_for(my_seat)
	var down := func(spot: String) -> bool: return chips.has(spot) and int(chips[spot].amount) > 0
	var spots := bet_spots()
	var primary := primary_spots().filter(func(spot): return spot in spots)
	if not primary.any(down):
		return primary
	return spots.filter(func(spot): return not spot in primary and not down.call(spot))


# ------------------------------------------------------------------ a second box
## The local player's seats: their own, then their second box if they have one.
func my_seats() -> Array:
	var seats := []
	if my_seat >= 0:
		seats.append(my_seat)
	if my_box >= 0:
		seats.append(my_box)
	return seats


func is_mine(seat: int) -> bool:
	return seat >= 0 and (seat == my_seat or seat == my_box)


## How many boxes the local player's bets go on (each bet is matched on a second box).
func boxes() -> int:
	return 2 if my_box >= 0 else 1


## The private part of an event for one of the local player's boxes: "mine" for their own seat, "mine_box" for
## their second box (which only comes once they may see it).
func mine_for(ev: Dictionary, seat: int):
	if seat >= 0 and seat == my_seat:
		return ev.get("mine")
	if seat >= 0 and seat == my_box:
		return ev.get("mine_box")
	return null


## "Box 1: " / "Box 2: " before what the bar says about a box -- once there are two.
func box_prefix(seat: int) -> String:
	if my_box < 0:
		return ""
	return "Box 1: " if seat == my_seat else "Box 2: "


## The local player's box `seat` has a new hand name ("" when gone): the bar shows it, or with two boxes
## "Box 1: Pair  ·  Box 2: Flush".
func _show_hand(seat: int, text: String) -> void:
	if text == "":
		_my_hands.erase(seat)
	else:
		_my_hands[seat] = text
	var parts := []
	for s in my_seats():
		if _my_hands.has(s):
			parts.append(box_prefix(s) + str(_my_hands[s]))
	my_hand_changed.emit("  ·  ".join(parts))


## The hand names in an event's private parts, for whichever of the local player's boxes `still_in` says is in.
func _note_hands(ev: Dictionary, still_in: Callable) -> void:
	for seat in my_seats():
		var mine = mine_for(ev, seat)
		if mine is Dictionary and mine.has("hand") and still_in.call(seat):
			_show_hand(seat, str(mine.hand))


## The local player's second box, turned over for them now their own hand's decided: its cards flip where they lie.
## (High Card Flush sorts them first.)
func _reveal_box(seat: int, mine, d: float) -> float:
	var decided = get("decided_seats")   # (a box that's gone already -- out of time -- stays face down)
	if not mine is Dictionary or not mine.has("cards") or (decided is Dictionary and decided.has(seat)):
		return 0.0
	var cards := _cards_for(seat)
	for k in mini(cards.size(), mine.cards.size()):
		_after(k * 0.12 * d).timeout.connect(cards[k].flip_to.bind(mine.cards[k], 0.22 * d))
	if mine.has("hand"):
		_show_hand(seat, str(mine.hand))
	return 0.3 * d


## Which chair shows a pill while the local player's sat here: a free seat beside them ("take"), or their second
## box's while it's not in the hand being played ("drop"). {} for none.
func box_pill(seat: int) -> Dictionary:
	if mode != "seated" or my_seat < 0 or not second_box_ok or Engine.is_editor_hint():
		return {}
	if seat == my_box:
		return {} if (phase != "betting" and seat in dealt_seats) else {"kind": "drop", "text": "DROP BOX"}
	if my_box < 0 and absi(seat - my_seat) == 1 and seat < seat_count() and not occupants.has(seat):
		return {"kind": "take", "text": "2ND BOX"}
	return {}


const PILL_SIZE := Vector2(30, 9)

## (2nd Box sits low enough to clear the seat back; Drop Box a little lower, clear of the RESERVED sign hung on that chair.)
func _pill_centre(seat: int) -> Vector2:
	return chair_pos(seat) + on_screen(Vector2(0, -2 if box_pill(seat).get("kind") == "drop" else -3))


## The chair whose pill is at `local` (table coordinates), or -1.
func box_pill_at(local: Vector2) -> int:
	for seat in seat_count():
		if not box_pill(seat).is_empty() and Rect2(_pill_centre(seat) - PILL_SIZE / 2 - Vector2(2, 2),
				PILL_SIZE + Vector2(4, 4)).has_point(local):
			return seat
	return -1


func _draw_box_pills(pulse: float) -> void:
	for seat in seat_count():
		var pill := box_pill(seat)
		if pill.is_empty():
			continue
		var c := _pill_centre(seat)
		var take: bool = pill.kind == "take"
		var rect := Rect2(c - PILL_SIZE / 2, PILL_SIZE)
		var fill := Color(0.08, 0.07, 0.06, 0.88)
		var edge := Color(1, 0.84, 0.45, 0.65 + 0.35 * pulse) if take else Color(0.85, 0.82, 0.78, 0.8)
		draw_rect(rect, fill)
		draw_rect(rect, edge, false, 0.7)
		# (laid out large and scaled down: Godot's centring is off at tiny font sizes)
		var k := 0.1
		draw_set_transform(c, 0.0, Vector2(k, k))
		draw_string(Card2D.FONT, Vector2(-PILL_SIZE.x / 2 / k, 16), str(pill.text), HORIZONTAL_ALIGNMENT_CENTER,
			PILL_SIZE.x / k, 46, edge)
		draw_set_transform(Vector2.ZERO)


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


## The betting line in the seated bar (BettingBar.format_info: «» is gold).
func _betting_info(ctx: Dictionary) -> String:
	var left := ceili(timer_left())
	if ctx.get("my_ready", false):
		return "You're in  ·  waiting for the deal" if ctx.get("has_bets", false) else "Sitting this one out"
	if left > 0:
		return "Bets close in «%d»  ·  %s" % [left, "Ready when you are" if ctx.get("has_bets", false) else "Pick a chip, then click a spot"]
	return "Place your bets"


## The table's name for the seated bar's corner.
func game_title() -> String:
	if is_master:
		return MasterPanel.name_of(master_game)
	return {"TcpTable": "Three Card Poker", "BlackjackTable": "Blackjack", "MsTable": "Mississippi Stud", "UthTable": "Ultimate Texas Hold'em",
		"LirTable": "Let It Ride", "HcfTable": "High Card Flush", "BacTable": "Baccarat", "RouTable": "Roulette", "CrapsTable": "Craps",
		"PaiGowTable": "Face Up Pai Gow" if get("face_up") else "Fortune Pai Gow"}.get(get_script().get_global_name(), "")


## The chips' design for the seated bar: the table style's (Roulette and Craps keep the game's own).
func chip_design() -> Dictionary:
	return style() if styled() else {}


## Whether Ready means "sit this one out" with no bets down (not at Roulette, which spins anyway).
func sit_out_ok() -> bool:
	return true


# ------------------------------------------------------------------ its style
## Whether the table takes a card table's style (TableStyle "cards"), so its chips and card backs follow it.
## Roulette and Craps have their own kinds of style (style_kind()) and keep their chips.
func styled() -> bool:
	return true


## Which kind of table style it takes: "cards", "roulette" or "craps".
func style_kind() -> String:
	return "cards"


## The design it's drawn in: its style's, or House before the server has said (and in the editor).
func style() -> Dictionary:
	if look.is_empty():
		look = TableStyle.design(table_id, style_kind())
	return look


## The look its cards are drawn in: its style (High Card Flush can put a four-colour deck over it).
func card_look() -> Dictionary:
	return style()


## Its chairs take its style's colours (Craps has standing spots, so none).
func chair_colours() -> Dictionary:
	return style().get("chairs", {})


## The table styles changed (the admin page's Tables tab): draw the table, its machines and what's on it again.
func restyle() -> void:
	look = TableStyle.design(table_id, style_kind())
	_felt.queue_redraw()
	redraw_chairs()
	for path in ["Felt/Fixtures", "Felt/Machines", "Felt/Lights"]:
		var layer := get_node_or_null(path)
		if layer:
			for n in layer.get_children():
				if n is CanvasItem:
					n.queue_redraw()
	if styled():
		_restyle_under(_dyn, card_look())


func _restyle_under(node: Node, cards: Dictionary) -> void:
	for n in node.get_children():
		if n is ChipStack2D:
			n.style = look
		elif n is Card2D:
			n.look = cards
		_restyle_under(n, cards)


# ------------------------------------------------------------------ geometry
func seat_pos(seat: int) -> Vector2:
	var marker := get_node_or_null("Seat%d" % seat) as Node2D
	if marker:
		return marker.position
	return Vector2(SEAT_GAP * 2.5 - seat * SEAT_GAP, CHAIR_Y)


## The chairs drawn in towards the table while it shows upside down or on its side. Chairs and
## their sitters are drawn upright from their feet, so at an upright table they rise towards it
## (the sitter leans over the rail); past its far side they'd rise away from it, leaving a gap,
## so there they come in until their feet are just behind the rail. On its side, in until the
## stool's edge is just clear of it.
func chair_tuck() -> Vector2:
	if is_zero_approx(screen_turn()):
		return Vector2.ZERO
	return Vector2(0, -(tuck_side() if sideways() else tuck_far()))


## How far in (see chair_tuck()): the seats are 30.5 below the rail, the feet come to 8.5 behind it.
func tuck_far() -> float:
	return 22.0


## ...and on its side, to 14.5 beside it (a stool is 10 across from its middle, a sitter about 8).
func tuck_side() -> float:
	return 16.0


## Where a seat's column of spots and cards lines up.
func seat_x(seat: int) -> float:
	return chair_pos(seat).x


## The chip tray, set into the rail at the back of the bay: as wide as the bay
## and its rail, its back edge sunk into the rail, its front on the felt, well
## clear of the dealer's cards.
func tray_rect() -> Rect2:
	return tray_box()


## The card tables' chip tray (tray_rect(), which Roulette and Craps give their own).
static func tray_box() -> Rect2:
	return Rect2(-(BAY_W + RAIL), bay_floor() - 5.0, (BAY_W + RAIL) * 2, 12)


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
	my_box = int(state.my_box) if state.get("my_box") != null else -1
	second_box_ok = bool(state.get("second_box", false))
	dealt_seats.clear()
	_my_hands.clear()
	auto_rebet_seats.clear()
	for i in seats.size():
		var s = seats[i]
		if s == null:
			continue
		occupants[i] = {"entity": s.entity, "name": s.name, "human": s.human}
		if s.get("box_of") != null:
			occupants[i].box_of = int(s.box_of)
		if s.get("ready"):
			ready_seats[i] = true
		if s.get("auto_rebet"):
			auto_rebet_seats[i] = true
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
	_flying.clear()
	_payouts.clear()
	_dealer_cards.clear()
	ready_seats.clear()
	jackpot_lights.clear()


func handle_event(ev: Dictionary) -> void:
	if ev.kind == "settle_seat" and is_mine(int(ev.seat)):
		Session.hold_balance(true)  # show the new balance when the chips reach you
	# (whose a second box is goes at once, as my_seat does: the bets you click are matched on it from now)
	if ev.kind == "box_taken" and int(ev.of) == my_seat and my_seat >= 0:
		my_box = int(ev.seat)
	elif ev.kind == "box_dropped" and int(ev.seat) == my_box:
		my_box = -1
	_queue.append(_animate.bind(ev))


func _process(_delta: float) -> void:
	if Engine.is_editor_hint():
		return
	var now := Time.get_ticks_msec() / 1000.0
	while not _queue.is_empty() and now >= _busy_until:
		var step: Callable = _queue.pop_front()
		var speed := 3.0 if _queue.size() > 6 else 1.0  # catch up if we fell behind
		_busy_until = now + float(step.call(speed)) / speed
	# (off screen, a countdown or a thinking ring waits: coming into view redraws it)
	if mode != "" or (on_screen_now and (_timer_end > now or master_revert_end > now or _needs_redraw()
			or (occupants.size() < seat_count() and breathes_now()))):  # (glowing chairs breathe)
		queue_redraw()
	var turn := screen_turn()
	if turn != _shown_turn:
		_shown_turn = turn
		_turned_on_screen()
	if is_master:   # (sitting here, the dealer lights up under the pointer: click them to change the game)
		var hot := mode == "seated" and over_dealer(get_local_mouse_position())
		if hot != _dealer_hot:
			_dealer_hot = hot
			dealer.modulate = Color(1.3, 1.2, 0.95) if hot else Color.WHITE


## The table shows a different way up (see screen_turn()). Upside down or on its side, the
## dealer is on our side of it or beside it: they stand on the floor at the felt's edge rather
## than in the bay behind it with the felt hiding their feet, and beside it they draw over its
## rail (z 1), as a sitter does. The stools move round, and the chip stacks stand up again.
func _turned_on_screen() -> void:
	dealer.position = _dealer_home if is_zero_approx(_shown_turn) else dealer_near_pos()
	dealer.z_index = 1 if sideways() else 0
	for node in _felt.find_children("*", "", true, false):
		if node is ChipStack2D:
			node.face_screen()
	place_chair_backs()   # (the chairs come in or go out: chair_tuck())
	move_sitters()
	_felt.queue_redraw()  # (its shadow falls down the screen whichever way up it shows)
	queue_redraw()


## A results sign that stands on the floor past one end of the table (Roulette, Craps), with its
## `base` (collision): the end `sign_side` says (the floor plan's choice), as the players see it.
## Unchosen, it's the right-hand end -- except on a table turned a quarter turn clockwise, where
## that end is the one nearest us and the sign would stand in front of the table hiding it.
func _stand_sign(sign: Node2D, base: Node2D) -> void:
	var side := sign_side
	if side == "":
		side = "left" if is_equal_approx(wrapf(rotation, -PI, PI), PI / 2) else "right"
	var sx := -1.0 if side == "left" else 1.0
	sign.position.x = sx * absf(sign.position.x)
	base.position.x = sx * absf(base.position.x)


## Where the dealer stands while the table shows upside down or on its side: at the dealer's edge.
func dealer_near_pos() -> Vector2:
	return Vector2(_dealer_home.x, TOP)


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
		"stood", "box_dropped":   # (a second box goes back like an empty seat; its chips to its player)
			var seat := int(ev.seat)
			var home := chip_home(int(ev.of)) if ev.kind == "box_dropped" else chip_home(seat)
			occupants.erase(seat)
			ready_seats.erase(seat)
			auto_rebet_seats.erase(seat)
			_my_hands.erase(seat)
			if phase == "betting":
				jackpot_lights.erase(seat)
				for spot in _chips_for(seat).keys():
					_take_stack(seat, spot, home, d)
			for stack in _queued.get(seat, {}).values():
				_fly_and_free(stack, home, 0.25 * d)
			_queued.erase(seat)
			queue_redraw()
			return 0.0
		"box_taken":
			occupants[int(ev.seat)] = {"entity": ev.entity, "name": ev.name, "human": true, "box_of": int(ev.of)}
			queue_redraw()
			return 0.0
		"box_revealed":
			return _reveal_box(int(ev.seat), ev.get("mine_box"), d)
		"bet_changed":
			if ev.get("queued", false):
				_show_queued(int(ev.seat), ev.bets, d)
			else:
				_show_bets(int(ev.seat), ev.bets, d)
			return 0.05
		"queued_dropped":  # bets put down during the last hand that can't be covered now: back they come
			var dropped := int(ev.seat)
			for spot in _chips_for(dropped).keys():
				_take_stack(dropped, spot, chip_home(dropped), d)
			return 0.0
		"betting_timer":
			_start_timer(float(ev.seconds), ev.get("quiet", false))
			return 0.0
		"ready":
			ready_seats[int(ev.seat)] = true
			queue_redraw()
			return 0.0
		"auto_rebet":
			if ev.on:
				auto_rebet_seats[int(ev.seat)] = true
			else:
				auto_rebet_seats.erase(int(ev.seat))
			queue_redraw()
			return 0.0
		"bets_closed":
			_timer_end = 0.0
			dealt_seats = ev.seats.map(func(x): return int(x))
			in_hand = my_seats().any(func(x): return x in dealt_seats)
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
		"settle_seat":
			var t := _animate_game(ev, d)
			if ev.has("round_net"):   # (as the chips move: the pays and sweeps sit in the middle of a seat's settle)
				_after(t * 0.5).timeout.connect(_float_net.bind(int(ev.seat), int(ev.round_net)))
			return t
		"round_end":
			for n in ev.get("round_nets", []):   # seats that had no settle of their own: bust, folded, paid early
				_float_net(int(n.seat), int(n.net))
			round_cleared.emit()
			in_hand = false
			return _return_chips(d)
		"betting_open":
			phase = "betting"
			in_hand = false
			dealt_seats.clear()
			_my_hands.clear()
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
		"jackpot_won":   # (only here: every other table's sign just takes the new amount)
			if jackpot_sign:
				jackpot_sign.celebrate(int(ev.amount))
			return 0.0
	return _animate_game(ev, d)


## What the hand won (green) or lost (red) a seat's player, rising off the back of their chair and fading.
func _float_net(seat: int, net: int) -> void:
	if net == 0 or not on_screen_now or not occupants.has(seat):
		return
	var tag := Label.new()
	tag.text = ("+" if net > 0 else "−") + Money.format(absi(net), true)
	tag.add_theme_font_override("font", BettingBar.FONT)
	tag.add_theme_font_size_override("font_size", 9)
	tag.add_theme_color_override("font_color", BettingBar.WIN if net > 0 else BettingBar.LOSS)
	tag.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	tag.add_theme_constant_override("outline_size", 3)
	tag.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tag.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	tag.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	tag.size = Vector2(80, 14)
	tag.position = -tag.size / 2
	var holder := Node2D.new()
	holder.z_index = 4   # over the sitter and their chair's back
	add_child(holder)
	holder.add_child(tag)
	holder.position = chair_pos(seat)
	holder.global_rotation = 0.0   # upright on screen, whichever way the table's turned
	holder.global_position += Vector2(0, 6)
	holder.modulate.a = 0.0
	var tw := holder.create_tween()
	tw.tween_property(holder, "modulate:a", 1.0, 0.2)
	tw.parallel().tween_property(holder, "global_position:y", holder.global_position.y - 14.0, 1.4) \
		.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tw.tween_interval(1.2)
	tw.tween_property(holder, "modulate:a", 0.0, 0.5)
	tw.tween_callback(holder.queue_free)


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
	for seat in my_seats():
		mine_back = mine_back or _chips_for(seat).size() > 0 or _payouts.get(seat, []).size() > 0
	for seat in _seat_chips.keys():
		for spot in _seat_chips[seat].keys():
			_take_stack(seat, spot, chip_home(seat), d)
	for seat in _payouts.keys():
		for stack in _payouts[seat]:
			_fly_and_free(stack, chip_home(seat), 0.4 * d)
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
			_fly_and_free(chips[spot], chip_home(seat), 0.25 * d)
			chips.erase(spot)
			continue
		if not chips.has(spot):
			var stack := _make_stack(seat)
			stack.modulate = QUEUED_TINT
			_dyn.add_child(stack)
			chips[spot] = stack
			if d > 0.0:
				stack.position = chip_home(seat)
				_tween().tween_property(stack, "position", spot_pos(seat, spot), 0.28 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
			else:
				stack.position = spot_pos(seat, spot)
		if new > old and d > 0.0:
			sfx_at("bet", to_global(spot_pos(seat, spot)))
		chips[spot].amount = new


## Bets put down during the last hand have just become this hand's.
func _queued_promoted(_seats: Array) -> void:
	pass


## A new stack of chips for a seat (Roulette's are in the seat's colour), in the table's style.
func _make_stack(_seat: int) -> ChipStack2D:
	var stack := ChipStack2D.new()
	if styled():
		stack.style = style()
	return stack


func _new_card(code: String, pos: Vector2) -> Card2D:
	var card := Card2D.new()
	if styled():
		card.look = card_look()
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
	_set_flying(seat, spot, _in_flight(seat, spot) + amount)
	var dest := to if to != Vector2.INF else spot_pos(seat, spot)
	var tw := _tween()
	tw.tween_property(moving, "position", dest, 0.28 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tw.tween_callback(func():
		moving.queue_free()
		_set_stack(seat, spot, _landed(seat, spot) + _land(seat, spot, amount), dest))


## What's sitting on a seat's spot, and what's on its way there.
func _landed(seat: int, spot: String) -> int:
	var chips := _chips_for(seat)
	return int(chips[spot].amount) if chips.has(spot) else 0


func _in_flight(seat: int, spot: String) -> int:
	return int(_flying.get(seat, {}).get(spot, 0))


## Chips arriving on a spot: how many of them still count (a bet taken back
## mid-slide has already been taken off what's in flight).
func _land(seat: int, spot: String, amount: int) -> int:
	var flying: Dictionary = _flying.get(seat, {})
	var landing := mini(amount, int(flying.get(spot, 0)))
	_set_flying(seat, spot, int(flying.get(spot, 0)) - landing)
	return landing


func _set_flying(seat: int, spot: String, amount: int) -> void:
	var flying: Dictionary = _flying.get_or_add(seat, {})
	if amount > 0:
		flying[spot] = amount
	else:
		flying.erase(spot)


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
		# Chips still sliding out from the last change count as down already (or a quick
		# second bet would send them out again).
		var old := _landed(seat, spot) + _in_flight(seat, spot)
		if new > old:
			sfx_at("bet", to_global(spot_pos(seat, spot)))
			_add_stack_from(seat, spot, new - old, chip_home(seat), d)
		elif new < old:
			var flying := mini(_in_flight(seat, spot), new)
			_set_flying(seat, spot, flying)
			_set_stack(seat, spot, new - flying)
			var back := _make_stack(seat)
			back.amount = old - new
			back.position = spot_pos(seat, spot)
			_dyn.add_child(back)
			_fly_and_free(back, chip_home(seat), 0.25 * d)


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


## How much of the countdown is left (1 to 0), for the bar's draining line.
func timer_fraction() -> float:
	return clampf(timer_left() / _timer_total, 0.0, 1.0)


# ------------------------------------------------------------------ input
func _unhandled_input(event: InputEvent) -> void:
	if Engine.is_editor_hint() or mode == "":
		return
	if not (event is InputEventMouseButton and event.pressed):
		return
	var p := get_local_mouse_position()
	if is_master and mode == "seated" and event.button_index == MOUSE_BUTTON_LEFT and over_dealer(p):
		dealer_clicked.emit()
		get_viewport().set_input_as_handled()
		return
	if mode == "seated" and my_seat >= 0:
		var pill := box_pill_at(p)
		if pill >= 0 and event.button_index == MOUSE_BUTTON_LEFT:
			box_clicked.emit(pill)
			get_viewport().set_input_as_handled()
			return
		for seat in my_seats():   # (a click on your second box's spot is a bet on yours: they're matched)
			for spot in bet_spots():
				if _on_spot(p, spot, seat):
					if event.button_index == MOUSE_BUTTON_LEFT:
						spot_clicked.emit(spot)
					elif event.button_index == MOUSE_BUTTON_RIGHT:
						spot_removed.emit(spot)
					get_viewport().set_input_as_handled()
					return


## Sat here: one of your spots, or the master table's dealer (what _unhandled_input takes a click on).
func clickable_at(local: Vector2) -> bool:
	if mode != "seated":
		return super(local)
	if is_master and over_dealer(local):
		return true
	if box_pill_at(local) >= 0:
		return true
	for seat in my_seats():
		for spot in bet_spots():
			if _on_spot(local, spot, seat):
				return true
	return false


## Whether `p` is on one of the local player's spots (at `seat`, one of their boxes): near its middle, or anywhere
## on its printed shape.
func _on_spot(p: Vector2, spot: String, seat := my_seat) -> bool:
	if p.distance_to(spot_pos(seat, spot)) < spot_radius(spot):
		return true
	var s := spot_shape(seat, spot)
	return s.shape != "circle" and Geometry2D.is_point_in_polygon(p, StyledFelt.shape(s, -1.0))


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
	_draw_spot_glows(now)
	_draw_box_pills(pulse)
	for seat in ready_seats:
		var p := chair_pos(seat) + on_screen(Vector2(13, -12))
		draw_circle(p, 3.5, Color("2e9e4f"))
		draw_polyline(PackedVector2Array([p + on_screen(Vector2(-1.8, 0)), p + on_screen(Vector2(-0.4, 1.4)),
			p + on_screen(Vector2(1.9, -1.4))]), Color.WHITE, 0.8)
	_ring_drawn.clear()
	_box_ring = false
	_draw_game(now, pulse)
	if _box_ring and not _ring_drawn.has(my_seat):   # one ring at a time: Box 2's once Box 1's has gone
		_draw_thinking_ring(my_box, pulse)
	for seat in _ring_since.keys():   # a ring that's gone fades in afresh next time
		if not _ring_drawn.has(seat):
			_ring_since.erase(seat)
	var countdown := _countdown_text(timer_left())
	if countdown == "" and master_revert_end > now:   # a Master Table nobody's at: back to the crest soon
		countdown = "MASTER TABLE IN %d" % ceili(master_revert_end - now)
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


## Whether `local` is on the dealer (the figure standing up from their feet, as the screen shows them).
func over_dealer(local: Vector2) -> bool:
	return Rect2(-13, -52, 26, 50).has_point((local - dealer.position).rotated(screen_turn()))


## While you're sat with chips to put down, the spots waiting for them glow in the style's glow colour (SpotGlow).
## Not with Auto rebet ticked: the bets go back down by themselves.
func _draw_spot_glows(now: float) -> void:
	var spots := glowing_spots() if (mode == "seated" and my_seat >= 0 and phase == "betting" and pulse_spots()
			and not auto_rebet_seats.has(my_seat)) else []
	for spot in _glow_since.keys():
		if not spot in spots:
			_glow_since.erase(spot)
	var colour := glow_colour()
	for spot in spots:
		var key := "%d/%s" % [my_seat, spot]
		if not _glows.has(key):
			_glows[key] = SpotGlow.prepare(spot_shape(my_seat, spot))
		SpotGlow.draw(self, _glows[key], colour, now, _glow_since.get_or_add(spot, now))


## The colour a table lights things up in: its style's `glow` (the spot glows, the thinking ring).
func glow_colour() -> Color:
	return TableStyle.colour(style(), "glow") if styled() else Color("ffdf9e")


## The light round a seat while its sitter decides: a soft pool on the floor under them (their avatar covers its
## middle) and a ring that runs down with their time, from the top as the screen sees it, with a spark at its
## running end. It warms from the style's glow colour to amber at half time and red near the end, breathing
## faster then. It fades in, closing in from a little wider, when their turn starts. The local player's second box
## waits for its ring until their own seat's has gone (_draw draws it after the game's).
func _draw_thinking_ring(seat: int, _pulse: float) -> void:
	if seat == my_box and seat >= 0 and not _box_ring:
		_box_ring = true
		return
	var now := Time.get_ticks_msec() / 1000.0
	_ring_drawn[seat] = true
	var t := clampf((now - float(_ring_since.get_or_add(seat, now))) / RING_FADE, 0.0, 1.0)
	t = t * t * (3.0 - 2.0 * t)
	var p := chair_pos(seat) + on_screen(Vector2(0, -16))
	var r := RING_R + 4.0 * (1.0 - t)
	var timed := timer_left() > 0
	var left := timer_fraction() if timed else 1.0
	var hot := clampf((0.2 - left) / 0.2, 0.0, 1.0)
	var colour := glow_colour().lerp(BettingBar.WARN, clampf((0.5 - left) / 0.3, 0.0, 1.0)).lerp(BettingBar.LOSS, hot)
	var breath := 0.5 + 0.5 * sin(now * TAU / (0.6 if hot > 0 else 2.4))
	for i in 5:   # the pool: stacked discs, so it's brightest in the middle
		draw_circle(p, r + 3.0 - i * 2.6, Color(colour, (0.03 + 0.02 * breath) * t))
	# The track the time runs round, dark under a faint tint so it reads on felt and carpet alike.
	draw_arc(p, r, 0, TAU, 48, Color(0, 0, 0, 0.4 * t), 2.8, true)
	draw_arc(p, r, 0, TAU, 48, Color(colour, (0.16 + (0 if timed else 0.4 * breath)) * t), 1.2, true)
	if not timed:
		return
	var top := -PI / 2 - screen_turn()
	var end := top + TAU * left
	draw_arc(p, r, top, end, 48, Color(colour, (0.2 + 0.14 * breath) * t), 4.4, true)   # its halo
	draw_arc(p, r, top, end, 48, Color(colour.lerp(Color.WHITE, 0.35), 0.95 * t), 1.5, true)
	var head := p + Vector2.from_angle(end) * r
	draw_circle(head, 2.3, Color(colour, 0.4 * t))
	draw_circle(head, 1.1, Color(1, 1, 1, 0.9 * t))
