@tool
class_name SlotCabinet
extends FloorGame
## A slot cabinet on the floor (signed off on the slots mockup, docs/slots/mockup/floor.js):
## drawn in code in four orientations -- `facing` is where its screen faces -- with one
## stool on that side. Its little screen plays whatever its player spins, so the floor
## shows who's winning; the topper flashes on big wins, the candle on a jackpot. A
## cabinet whose screen faces away from the camera fades while someone sits behind it.
##
## Sitting down opens the full-screen game (SlotScreen); this only draws the cabinet and
## keeps the mini-screen in step with the server.

## Where the screen faces: the player sits on that side, facing it.
@export_enum("down", "up", "left", "right") var facing := "down":
	set(v):
		facing = v
		_place_children()
		redraw_chairs()
@export var variant := "armadillo"

const TRIM := Color("ffb347")
const TRIM_HI := Color("ffe0a3")
## A built slot's cabinet (from the welcome): its body, trim and topper-lettering colours and the topper's
## words. Empty: Armadillo Goes West's, exactly as signed off.
var look := {}
# The stool, from the cabinet's base centre (y is the base line), by facing.
const STOOL_AT := {"down": Vector2(0, 17), "up": Vector2(0, -15), "left": Vector2(-28, -5), "right": Vector2(28, -5)}
const STAND_AT := {"down": Vector2(0, 36), "up": Vector2(0, -34), "left": Vector2(-44, -1), "right": Vector2(44, -1)}
const SIT_FACING := {"down": "up", "up": "down", "left": "right", "right": "left"}

var grid: Array = []            # the last spin's symbols (cell = reel * 4 + row)
var _spin_until := 0.0          # the mini-screen's reels are blurred until then
var _pending_grid: Array = []
var _flash_until := 0.0         # a big win: the topper and trim flash
var _bonus := false             # a feature's on: the screen glows
var _jackpot_until := 0.0       # the candle spins
var _last_bet := 100
var _lively := false            # the art moved last frame (it's redrawn every frame only while it does)

@onready var _art: Node2D = $Art
@onready var _stool: Node2D = $Stool


func _ready() -> void:
	_place_children()
	if Engine.is_editor_hint():
		return
	grid = _random_grid()
	SlotArt.art_changed.connect(redraw_chairs)


func _place_children() -> void:
	if not is_inside_tree() or not has_node("Stool"):
		return
	$Stool.position = STOOL_AT[facing]
	place_chair_backs()
	var body := get_node_or_null("Body/Shape") as CollisionShape2D
	if body:
		var rect := RectangleShape2D.new()
		rect.size = Vector2(32, 14) if facing in ["down", "up"] else Vector2(22, 14)
		body.shape = rect
		body.position = Vector2(0, -6)


func _process(_delta: float) -> void:
	if Engine.is_editor_hint():
		return
	var now := Time.get_ticks_msec() / 1000.0
	if not _pending_grid.is_empty() and now >= _spin_until:
		grid = _pending_grid
		_pending_grid = []
		_art.queue_redraw()
	var fade := 0.62 if facing == "up" and occupants.has(0) else 1.0
	if _art.modulate.a != fade:
		_art.modulate.a = fade
	# Only a spin, a flash, the jackpot candle or a bonus's glow moves (and only on screen),
	# with one more frame as it stops.
	var lively := on_screen_now and (_bonus or now < maxf(_spin_until, maxf(_flash_until, _jackpot_until)))
	if lively or _lively:
		_art.queue_redraw()
	_lively = lively
	if breathes_now() and not occupants.has(0):   # (a glowing chair breathes)
		_stool.queue_redraw()


# ------------------------------------------------------------------ FloorGame
## The chair, and the cabinet with it (whatever's changed; on coming into view).
func redraw_chairs() -> void:
	super()
	if is_node_ready():
		_art.queue_redraw()
		_stool.queue_redraw()


func chair_pos(_seat: int) -> Vector2:
	return STOOL_AT[facing] + Vector2(0, 4)


func stand_pos(_seat: int) -> Vector2:
	return STAND_AT[facing]


func sit_facing(_seat: int) -> String:
	return SIT_FACING[facing]


func sit_z(_seat: int) -> int:
	return 0 if facing == "up" else 1


func focus_point() -> Vector2:
	return to_global(Vector2(0, -36))


## Where the cabinet's screen is, in global coordinates (the full-screen game grows out of it).
func screen_rect() -> Rect2:
	var r := Rect2(-13, -42.5, 26, 15) if facing != "left" and facing != "right" else Rect2(-4, -44, 12, 18)
	return Rect2(to_global(r.position), r.size * global_scale)


func apply_snapshot(state: Dictionary) -> void:
	_new_epoch()
	occupants.clear()
	var seats_list: Array = state.get("seats", [])
	if not seats_list.is_empty() and seats_list[0] != null:
		var s: Dictionary = seats_list[0]
		occupants[0] = {"entity": s.entity, "name": s.name, "human": s.human}
	phase = str(state.get("phase", "idle"))
	if state.get("last") != null:
		grid = state.last.grid
	_bonus = phase in ["trail", "free_games", "jackpot_pick", "battle"]
	_last_bet = int(state.get("bet", 100))
	redraw_chairs()


func handle_event(ev: Dictionary) -> void:
	var now := Time.get_ticks_msec() / 1000.0
	match ev.kind:
		"seated":
			occupants[0] = {"entity": ev.entity, "name": ev.name, "human": ev.human}
			redraw_chairs()
		"stood":
			occupants.erase(0)
			_bonus = false
			redraw_chairs()
		"spin", "free_game":
			var o: Dictionary = ev.outcome
			_last_bet = int(o.bet)
			_spin_until = now + 1.4
			_pending_grid = o.grid
			if float(o.total) >= 10.0 * float(o.bet) and not o.free:
				_flash_until = _spin_until + 3.0
				if int(ev.get("seat", 0)) != my_seat or mode == "":
					_after(1.4).timeout.connect(func(): sfx_at("big_win", global_position))
		"trail_start", "free_start", "jackpot_start", "battle_start":
			_bonus = true
		"features_done":
			_bonus = false
		"slot_jackpot_won":
			_jackpot_until = now + 6.0
			_flash_until = now + 6.0
			if mode == "":
				sfx_at("jackpot_win", global_position)


func _random_grid() -> Array:
	var syms := ["H1", "H2", "M1", "M2", "M3", "M4", "L1", "L2", "L3", "L4", "W"]
	var g := []
	for i in 20:
		g.append(syms.pick_random())
	return g


# ------------------------------------------------------------------ drawing (called by the Art and Stool children)
func draw_cabinet(ci: CanvasItem) -> void:
	var now := Time.get_ticks_msec() / 1000.0
	match facing:
		"down":
			_front(ci, now)
		"up":
			_back(ci, now)
		_:
			_side(ci, now, -1.0 if facing == "left" else 1.0)


## The chair, under its sitter (the Stool node sits 4px behind the chair's origin; its back is a ChairBack).
func draw_stool_node(ci: CanvasItem) -> void:
	draw_chair(ci, 0, "seat", Vector2(0, 4))


## A panel shaded top to bottom (two quads with per-corner colours: top -> mid -> low).
static func _box(ci: CanvasItem, r: Rect2, top: Color, mid: Color, low: Color) -> void:
	var x0 := r.position.x
	var x1 := r.end.x
	var y0 := r.position.y
	var ym := y0 + r.size.y * 0.5
	var y1 := r.end.y
	ci.draw_polygon(PackedVector2Array([Vector2(x0, y0), Vector2(x1, y0), Vector2(x1, ym), Vector2(x0, ym)]),
		PackedColorArray([top, top, mid, mid]))
	ci.draw_polygon(PackedVector2Array([Vector2(x0, ym), Vector2(x1, ym), Vector2(x1, y1), Vector2(x0, y1)]),
		PackedColorArray([mid, mid, low, low]))


func _shadow(ci: CanvasItem, w: float) -> void:
	ci.draw_set_transform(Vector2.ZERO, 0, Vector2(1, 0.27))
	ci.draw_circle(Vector2.ZERO, w, Color(0, 0, 0, 0.35))
	ci.draw_set_transform(Vector2.ZERO)


func _lid(ci: CanvasItem, x: float, w: float) -> void:
	ci.draw_rect(Rect2(x, -63, w, 4.5), _part("6b4223", 1.45))
	ci.draw_rect(Rect2(x, -58.5, w, 4.5), _part("4a2c18", 1.0))
	ci.draw_rect(Rect2(x, -63, w, 1.2), Color(1, 0.78, 0.55, 0.18))
	ci.draw_rect(Rect2(x, -54.6, w, 0.8), Color("1a0d05"))


func _candle(ci: CanvasItem, x: float, y: float, now: float) -> void:
	var lit := now < _flash_until
	var spinning := now < _jackpot_until
	ci.draw_rect(Rect2(x - 2.2, y - 1.5, 4.4, 1.5), Color("2a1408"))
	var c := Color("c97a2a")
	if lit:
		c = Color("fff1b0") if int(now * 8) % 2 else Color("ff5a48")
	ci.draw_rect(Rect2(x - 1.8, y - 6, 3.6, 4.5), c)
	if lit:
		ci.draw_circle(Vector2(x, y - 4), 5.0 + (2.0 * sin(now * 12.0) if spinning else 0.0), Color(1, 0.89, 0.48, 0.45))


func _trim(now: float) -> Color:
	var trim := Color(str(look.get("trim", "ffb347"))) if look.has("trim") else TRIM
	return (trim.lightened(0.5) if look.has("trim") else TRIM_HI) if now < _flash_until and int(now * 8) % 2 else trim


## A part's colour: Armadillo's own, or (a built slot) its body colour shaded by `k` (1 is the body itself).
func _part(armadillo: String, k: float) -> Color:
	if not look.has("body"):
		return Color(armadillo)
	var body := Color(str(look.body))
	return body.lightened(minf(0.9, (k - 1.0) * 0.45)) if k > 1.0 else body.darkened(1.0 - k)


func _mini_screen(ci: CanvasItem, r: Rect2, now: float) -> void:
	ci.draw_rect(r, Color("0b0604"))
	var cw := r.size.x / 5.0
	var ch := r.size.y / 4.0
	var spinning := now < _spin_until
	for reel in 5:
		var stop_at := _spin_until - 1.0 + reel * 0.2
		for row in 4:
			var cell := Rect2(r.position + Vector2(reel * cw, row * ch), Vector2(cw, ch))
			if spinning and now < stop_at:
				var hue := fmod(reel * 0.17 + row * 0.11 + now * 2.5, 1.0)
				ci.draw_rect(cell.grow(-0.2), Color.from_hsv(hue, 0.55, 0.45 + 0.1 * sin(now * 40.0 + row), 0.5))
			elif grid.size() == 20:
				var tex := SlotArt.tex(variant, str(grid[reel * 4 + row]))
				if tex:
					ci.draw_texture_rect(tex, cell.grow(-0.15), false)
	if _bonus:
		ci.draw_rect(r, Color(1, 0.78, 0.31, 0.35 + 0.25 * sin(now * 10.0)))
	ci.draw_rect(Rect2(r.position, Vector2(r.size.x, r.size.y * 0.3)), Color(1, 1, 1, 0.1))


func _front(ci: CanvasItem, now: float) -> void:
	_shadow(ci, 17.0)
	_box(ci, Rect2(-14, -8, 28, 8), _part("3a2416", 0.8), _part("24140b", 0.5), _part("140a05", 0.28))      # plinth
	_box(ci, Rect2(-15, -22, 30, 14), _part("4a2c18", 1.0), _part("2e1a0d", 0.62), _part("1c0f07", 0.38))    # lower cabinet
	ci.draw_rect(Rect2(-6, -18, 12, 7), _part("7a4a26", 1.65))                                    # belly door
	ci.draw_rect(Rect2(-6, -18, 12, 7), Color(str(look.get("trim", "d9a54a"))), false, 0.5)
	_box(ci, Rect2(-16, -26, 32, 5), _part("9a6a3e", 2.1), _part("6b4223", 1.45), _part("3c200d", 0.8))     # button deck
	var lights := [Color("4fb3ff"), Color("55d07a"), Color("c768ff"), Color("ff5a48"), Color("ffb347")]
	for i in 5:
		ci.draw_rect(Rect2(-12 + i * 5.2, -25, 3.4, 1.6), lights[i])
	_box(ci, Rect2(-15, -44, 30, 18), Color("2a1a10"), Color("1b0f08"), Color("120904"))    # bezel
	_mini_screen(ci, Rect2(-13, -42.5, 26, 15), now)
	_box(ci, Rect2(-14, -54, 28, 10), _part("3a2416", 0.8), _part("2a170b", 0.56), _part("1a0d05", 0.35))    # topper
	var title := Color("fff1b0") if now < _flash_until and int(now * 8) % 2 else Color(str(look.get("title", "e8a33a")))
	var words: Array = look.get("lines", ["ARMADILLO", "GOES WEST"])
	if words.size() >= 2:
		ci.draw_string(Card2D.FONT, Vector2(-14, -49.4), str(words[0]), HORIZONTAL_ALIGNMENT_CENTER, 28, 3, title)
		ci.draw_string(Card2D.FONT, Vector2(-14, -45.8), str(words[1]), HORIZONTAL_ALIGNMENT_CENTER, 28, 3, title)
	elif words.size() == 1:
		ci.draw_string(Card2D.FONT, Vector2(-14, -47.4), str(words[0]), HORIZONTAL_ALIGNMENT_CENTER, 28, 4, title)
	var trim := _trim(now)
	ci.draw_rect(Rect2(-15.8, -54, 1.2, 46), trim)
	ci.draw_rect(Rect2(14.6, -54, 1.2, 46), trim)
	_lid(ci, -15.8, 31.6)
	ci.draw_rect(Rect2(-15.8, -55.2, 31.6, 1), trim)
	_candle(ci, 0, -59, now)


func _back(ci: CanvasItem, now: float) -> void:
	_shadow(ci, 17.0)
	_box(ci, Rect2(-14, -8, 28, 8), _part("2a1a10", 0.58), _part("1c1008", 0.38), _part("100804", 0.22))
	_box(ci, Rect2(-15, -54, 30, 46), _part("3a2416", 0.8), _part("22130a", 0.47), _part("140a05", 0.28))
	for i in 6:
		ci.draw_rect(Rect2(-9, -46 + i * 3.2, 18, 1.2), Color("0e0704"))                    # vents
	ci.draw_rect(Rect2(-11, -24, 22, 12), _part("2c1a0e", 0.6))
	ci.draw_rect(Rect2(-11, -24, 22, 12), Color("5a3d27"), false, 0.6)
	var trim := _trim(now)
	ci.draw_rect(Rect2(-15.8, -54, 1.2, 46), trim)
	ci.draw_rect(Rect2(14.6, -54, 1.2, 46), trim)
	_lid(ci, -15.8, 31.6)
	ci.draw_rect(Rect2(-15, -64, 30, 1.6), Color(1, 0.78, 0.47, 0.35 + (0.3 if now < _flash_until else 0.0)))
	_candle(ci, 0, -59, now)


func _side(ci: CanvasItem, now: float, s: float) -> void:
	_shadow(ci, 13.0)
	ci.draw_set_transform(Vector2.ZERO, 0, Vector2(s, 1))
	var body := PackedVector2Array([Vector2(-11, 0), Vector2(-11, -54), Vector2(4, -54), Vector2(6, -44),
		Vector2(10, -27), Vector2(13, -24), Vector2(9, -21), Vector2(9, 0)])
	ci.draw_colored_polygon(body, _part("2e1a0d", 0.62))
	ci.draw_colored_polygon(PackedVector2Array([Vector2(-1, 0), Vector2(-1, -54), Vector2(4, -54), Vector2(6, -44),
		Vector2(10, -27), Vector2(13, -24), Vector2(9, -21), Vector2(9, 0)]), _part("4a2c18", 1.0))
	var lit := now < _flash_until
	ci.draw_line(Vector2(6, -44), Vector2(10, -27), Color("fff1b0") if lit else Color("ffcf8a"), 1.4)
	ci.draw_colored_polygon(PackedVector2Array([Vector2(10, -27), Vector2(13, -24), Vector2(9, -21), Vector2(8, -25)]), _part("9a6a3e", 2.1))
	var trim := _trim(now)
	ci.draw_rect(Rect2(-11, -55, 15, 1.2), trim)
	ci.draw_colored_polygon(PackedVector2Array([Vector2(4, -54), Vector2(5.2, -54), Vector2(7.2, -44), Vector2(6, -44)]), trim)
	ci.draw_rect(Rect2(-11, -8, 20, 8), _part("2a1a10", 0.58))
	ci.draw_rect(Rect2(-11, -63, 15, 9), _part("5a361c", 1.2))
	ci.draw_rect(Rect2(-11, -63, 15, 1.2), Color(1, 0.78, 0.55, 0.18))
	ci.draw_set_transform(Vector2.ZERO)
	_candle(ci, -s * 3.0, -59, now)
