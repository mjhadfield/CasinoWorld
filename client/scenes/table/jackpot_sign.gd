class_name JackpotSign
extends Node2D
## The progressive jackpot's sign, standing on the felt by the dealer: top left as the players see it, between
## the rail and the dealer's cards, clear of every game's machines (CasinoTable.JACKPOT_SIGN). It shows the
## casino's one jackpot as it grows (Session.jackpot_now()), a blinking blue light (where it has one: the twin,
## LED and screen) while the local player's Jackpot bet is on the disc, and a win's celebration (celebrate()) at the table it was won at. Every other table's sign
## just drops to the new amount; the winning table's holds the old one until the win is shown there
## (Session.jackpot_held()). It's powered off at a game with no Jackpot bet (Baccarat, a blank Master Table).
##
## Its design is the table style's `jackpotSign`: twin (the shuffler's housing and display), brass (a marquee
## with chasing bulbs), led (a red dot-matrix), screen (a floor screen with confetti), flap (a split-flap board
## in the rail's wood) or neon. The admin designer draws the same (jackpotSign() in render.js).
##
## Drawn in code in the mockup's units (MOCK: 220 across, the foot's shadow at the bottom), scaled down to
## WIDTH table units; the node sits where the shadow meets the felt. It redraws only on screen, when what it
## shows changes, or while it animates (4 frames a second).

const MOCK := Vector2(220, 80)
const WIDTH := 40.0
const K := WIDTH / 220.0
const WIN_SECONDS := 12.0

const VT323 := preload("res://assets/fonts/VT323-Regular.ttf")
const BARLOW := preload("res://assets/fonts/BarlowCondensed-Bold.ttf")
const MONTSERRAT := preload("res://assets/fonts/Montserrat-SemiBold.ttf")
const CINZEL := preload("res://assets/fonts/Cinzel-SemiBold.ttf")
const JOSEFIN := preload("res://assets/fonts/JosefinSans-SemiBold.ttf")
const BRASS := Color("c9a24a")
const BRASS_HI := Color("ecd396")
const GOLD := Color("ffd36b")
const OFF_RED := Color("ff2a1a")
const NEON := [Color("ff4fd8"), Color("3ee8ff"), Color("ffd23e"), Color("5bff7a")]
const LAMPS := [Color("38e06a"), Color("ffb02e"), Color("4aa8ff")]
const FLAP_GLYPHS := "0123456789£JACKPOT!"

static var _spaced := {}   # "font/spacing" -> FontVariation: letter-spaced lettering

var _table: CasinoTable
var _win_amount := 0
var _win_start := 0.0
var _win_until := 0.0
var _shown: Array = []       # what was last drawn: redraw when it changes
var _flap_text := ""         # the split-flap's tiles, and what they showed before they last changed
var _flap_prev := ""
var _flap_changed := -10.0


func _ready() -> void:
	texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED   # (the split-flap's wood)
	var n := get_parent()
	while n != null and not n is CasinoTable:
		n = n.get_parent()
	_table = n


## The jackpot was won at this table and the win is being shown: the sign celebrates with what was won.
## A second win in the same hand (Blackjack's boxes share the pool) carries the celebration on.
func celebrate(amount: int) -> void:
	var now := _now()
	if now >= _win_until:
		_win_start = now
	_win_amount = amount
	_win_until = now + WIN_SECONDS
	queue_redraw()


## Where it's drawn, in its parent's units (the table's).
func drawn_rect() -> Rect2:
	return Rect2(position + Vector2(-MOCK.x / 2, -MOCK.y) * K, MOCK * K)


## Where it stands on the felt: the bottom of its face down to its shadow (its face rises in front of what's behind).
func footprint() -> Rect2:
	return Rect2(position + Vector2(-MOCK.x / 2, -12) * K, Vector2(MOCK.x, 12) * K)


func _now() -> float:
	return Time.get_ticks_msec() / 1000.0


func _process(_delta: float) -> void:
	if _table == null:
		return
	var now := _now()
	if _win_until > 0.0 and now >= _win_until:
		_win_until = 0.0
		Session.release_jackpot(_table.table_id)
	if not _table.on_screen_now:
		return   # (coming back on screen, what it shows has moved on, so it redraws)
	var v := _view(now)
	var flap := _flap_string(v)
	if flap != _flap_text:
		_flap_prev = _flap_text
		_flap_text = flap
		_flap_changed = now
	var shown := [v.design, v.state, v.pence, v.anim]
	if shown != _shown:
		_shown = shown
		queue_redraw()


## What the sign shows right now: its design, state (live, in, win or off), amount and animation frame.
func _view(now: float) -> Dictionary:
	var look := _table.style() if _table else TableStyle.fill({})
	var design: String = look.get("jackpotSign", "brass")
	var state := "live"
	if _table and not "jackpot" in _table.bet_spots():
		state = "off"
	elif now < _win_until:
		state = "win"
	elif _table and _table.my_seats().any(func(s): return _table.jackpot_lights.has(s)):
		state = "in"
	var pence := 1248037.0
	if state == "win":
		pence = _win_amount
	elif _table:
		var held := Session.jackpot_held(_table.table_id)
		pence = held if held >= 0.0 else Session.jackpot_now()
	var tick := int((now - _win_start if state == "win" else now) * 4.0)
	var anim := 0
	if state == "win" or design == "brass" or (state == "in" and design in ["twin", "led", "screen"]):   # (a bet's light blinks)
		anim = tick
	elif design == "neon":
		anim = int(_flicker(tick))
	elif design == "flap" and now - _flap_changed < 0.25:
		anim = 1 + tick
	return {"look": look, "design": design, "state": state, "on": state != "off", "win": state == "win",
		"in": state == "in", "pence": int(pence), "money": Money.format(int(pence)), "tick": tick, "anim": anim,
		"flash": (tick / 2) % 2 == 0, "headline": state == "win" and (tick / 6) % 2 == 0, "now": now}


func _flicker(tick: int) -> bool:
	return tick % 29 == 0 or tick % 29 == 2


func _flap_string(v: Dictionary) -> String:
	if not v.on:
		return " ".repeat(10)
	if v.headline:
		return " JACKPOT! "
	return (v.money as String).lpad(10)


# ------------------------------------------------------------------ drawing
func _draw() -> void:
	var v := _view(_now())
	_base()
	if v.win:   # a pool of light on the felt round it
		var pool: Color = {"twin": Color("7dff9a"), "brass": GOLD, "led": Color("ff3b2f"), "screen": GOLD,
			"flap": Color("fff1c2"), "neon": NEON[0]}.get(v.design, GOLD)
		var a := 1.0 if v.flash else 0.45
		for i in range(6, 0, -1):
			_ellipse(Vector2(110, 44), 140.0 * i / 6.0, 56.0 * i / 6.0, Color(pool, 0.07 * a))
	_ellipse(Vector2(110, 72), 104, 9, Color(0, 0, 0, 0.16))   # its shadow, and the foot
	_ellipse(Vector2(110, 72), 94, 7, Color(0, 0, 0, 0.2))
	_ellipse(Vector2(110, 72), 82, 5, Color(0, 0, 0, 0.2))
	_fill(Rect2(80, 58, 60, 16), 4, _foot(v))
	draw_line(Vector2(83, 72.5), Vector2(137, 72.5), Color(0, 0, 0, 0.35), 2.0)
	match v.design:
		"twin":
			_twin(v)
		"led":
			_led(v)
		"screen":
			_screen(v)
		"flap":
			_flap(v)
		"neon":
			_neon(v)
		_:
			_brass(v)
	draw_set_transform(Vector2.ZERO)


func _foot(v: Dictionary) -> Color:
	match v.design:
		"twin":
			return TableStyle.colour(v.look, "shufflerTint").darkened(0.5)
		"brass":
			return Color("7d6328")
		"flap":
			return Color("3b2414")
		"neon":
			return Color("141418")
	return Color("18181b")


## A twin of the shuffler: its housing, its display's colours and its status light, a legend along the foot.
func _twin(v: Dictionary) -> void:
	var kind: String = v.look.shuffler
	var tint := TableStyle.colour(v.look, "shufflerTint")
	var lcd := Color("0b1a10")
	var lit := Color("7dff9a")
	if kind == "black":
		lcd = Color("06080a")
		lit = Color("e9f6ff")
	elif kind == "brass":
		lcd = Color("1b1206")
		lit = Color("ffcf6e")
	_fill(Rect2(0, 0, 220, 68), 7, tint.darkened(0.45))
	if kind == "brass":
		_wood(Rect2(1, 1, 218, 66), 6, TableStyle.wood_of(v.look, str(v.look.shufflerWood)))
		_outline(Rect2(1.5, 1.5, 217, 65), 6, BRASS, 1.2)
	else:
		_fill(Rect2(1, 1, 218, 66), 6, tint)
	draw_line(Vector2(7, 3), Vector2(213, 3), Color(1, 1, 1, 0.16), 3.0)
	draw_line(Vector2(7, 65), Vector2(213, 65), Color(0, 0, 0, 0.18), 2.0)
	var flash: bool = v.win and v.flash
	_fill(Rect2(8, 8, 204, 40), 3, Color("12161b"))
	_fill(Rect2(10, 10, 200, 36), 2, (lit if flash else lcd) if v.on else Color("050807"))
	if v.on:
		_text("JACKPOT!" if v.headline else v.money, Vector2(110, 28), 32, lcd if flash else lit, VT323, 0,
			Color.TRANSPARENT if flash else Color(lit, 0.55), 188)
	var light := tint.get_luminance() > 0.5 and kind != "brass"   # (dark lettering on a pale housing)
	var legend := "PROGRESSIVE JACKPOT"
	var legend_c := Color("2a2d31") if light else Color("a4aab2")
	var lamp: Color = LAMPS[0]
	var glow := true
	if not v.on:
		legend_c = Color(legend_c, 0.45)
		lamp = Color("7a1f1a")
		glow = false
	elif v.win:
		legend = "JACKPOT WINNER!"
		legend_c = (Color("8a5a00") if light else GOLD) if v.flash else (Color("1f7a3a") if light else lit)
		lamp = LAMPS[v.tick % 3]
	elif v.in:
		glow = v.flash
		lamp = _bet_light(v)
	_text(legend, Vector2(10, 57), 7, legend_c, _spacing(MONTSERRAT, 1), -1)
	if glow:
		draw_circle(Vector2(207, 57), 5.5, Color(lamp, 0.3))
	draw_circle(Vector2(207, 57), 3.0, lamp)


## A brass marquee: a dark panel in a brass frame, a row of bulbs along the top and bottom that chase (and
## flash in turn for a win), JACKPOT engraved over the amount.
func _brass(v: Dictionary) -> void:
	var flash: bool = v.win and v.flash
	if v.win:
		_glow_box(Rect2(0, 0, 220, 68), 9, GOLD, 1.0 if v.flash else 0.45)
	_fill(Rect2(0, 0, 220, 68), 9, Color("fff1c2") if flash else BRASS)
	_fill(Rect2(2, 2, 216, 64), 7, Color("1a1309"))
	draw_line(Vector2(9, 3.5), Vector2(211, 3.5), Color(BRASS_HI, 0.4), 2.0)
	var step: int = v.tick / 2
	for row in 2:
		for i in 17:
			var lit: bool = v.on and (((v.flash if row == 0 else not v.flash) if v.win
				else ((i if row == 0 else 16 - i) + step) % 3 == 0))
			var at := Vector2(11 + i * 12.375, 7 if row == 0 else 61)
			if lit:
				draw_circle(at, 4.5, Color(GOLD, 0.35))
			draw_circle(at, 2.0, Color("fff1c2") if lit else Color("7a6234") if v.on else Color("3a2f1f"))
	if v.win:
		_pill("JACKPOT WINNER", Vector2(110, 20), 8, Color.WHITE if not v.flash else BRASS_HI, Color("1b1307"))
	else:
		_text("JACKPOT", Vector2(110, 20), 10, BRASS if v.on else Color("5c4a28"), _spacing(CINZEL, 4))
	if v.on:
		_text("JACKPOT!" if v.headline else v.money, Vector2(110, 41.5), 25, Color.WHITE if flash else BRASS_HI,
			MONTSERRAT, 0, Color(GOLD, 0.9 if v.win else 0.35), 200)


## A pit LED: a matte black case, a JACKPOT plate, a red dot-matrix with its unlit 8s showing through. A win
## scrolls JACKPOT WINNER and the amount across it.
func _led(v: Dictionary) -> void:
	_fill(Rect2(0, 0, 220, 68), 4, Color("2a2a2d"))
	_fill(Rect2(1, 1, 218, 66), 3, Color("0e0e10"))
	draw_line(Vector2(5, 2.5), Vector2(215, 2.5), Color("2e2e33"), 3.0)
	var plate := Color("b3261e")
	var ink := Color.WHITE
	if not v.on:
		plate = Color("3a1310")
		ink = Color("6e423d")
	elif v.win:
		plate = Color.WHITE if v.flash else Color("b3261e")
		ink = Color("b3261e") if v.flash else Color.WHITE
	_fill(Rect2(7, 8, 44, 44), 3, plate)
	_text("JACK", Vector2(29, 23.8), 13, ink, BARLOW, 0, Color.TRANSPARENT, 40)
	_text("POT", Vector2(29, 36.2), 13, ink, BARLOW, 0, Color.TRANSPARENT, 40)
	_fill(Rect2(57, 8, 156, 44), 2, Color.BLACK)
	_fill(Rect2(58, 9, 154, 42), 1.5, Color("140303"))
	var px := _fit("888,888.88", 28, VT323, 144)
	_text("888,888.88", Vector2(205, 30), px, Color("2e0907"), VT323, 1)
	if v.on:
		var show: String = v.money
		if v.win:
			var loop := "JACKPOT WINNER %s   " % v.money
			show = (loop + loop).substr(v.tick % loop.length(), 10)
		var red := Color("ffb02e") if v.win and not v.flash else Color("ff3b2f")
		_text(show, Vector2(205, 30), px, red, VT323, 1, Color(red, 0.75))
	var grid := PackedVector2Array()   # the dot pitch
	for y in range(10, 51, 3):
		grid.append_array([Vector2(58, y), Vector2(212, y)])
	for x in range(59, 212, 3):
		grid.append_array([Vector2(x, 9), Vector2(x, 51)])
	draw_multiline(grid, Color(0, 0, 0, 0.3), 1.0)
	var power: Color = OFF_RED if not v.on else LAMPS[v.tick % 3] if v.win else _bet_light(v) if v.in else Color("3ad35f")
	if not (v.in and not v.flash):
		draw_circle(Vector2(209, 60), 4.0, Color(power, 0.3))
	draw_circle(Vector2(209, 60), 2.0, power)


## A floor screen: a thin black bezel, a navy screen, PROGRESSIVE JACKPOT over the amount. A win flashes it
## gold and rains confetti down it.
func _screen(v: Dictionary) -> void:
	var flash: bool = v.win and v.flash
	_fill(Rect2(0, 0, 220, 68), 6, Color("0a0a0c"))
	draw_line(Vector2(6, 2.5), Vector2(214, 2.5), Color("2a2a30"), 3.0)
	_fill(Rect2(6, 6, 208, 50), 3, Color("5a3c00") if flash else Color("141c52") if v.on else Color("050507"))
	if v.win:
		var colours := [GOLD, Color("ff5ea0"), Color("5ee0ff"), Color.WHITE]
		for i in 16:
			var at := Vector2(6 + (i * 53 + 7) % 204, 6 + (i * 29 + v.tick * 5) % 64 - 8)
			if at.y < 4 or at.y > 54:
				continue
			var turn := deg_to_rad((v.tick * 40 + i * 30) % 360)
			var piece := PackedVector2Array()
			for c in [Vector2(-1.5, -2.5), Vector2(1.5, -2.5), Vector2(1.5, 2.5), Vector2(-1.5, 2.5)]:
				piece.append(at + c.rotated(turn))
			draw_colored_polygon(piece, colours[i % 4])
	if v.on:
		_text("JACKPOT WINNER" if v.win else "PROGRESSIVE JACKPOT", Vector2(110, 15.5), 9,
			Color.WHITE if flash else GOLD, _spacing(BARLOW, 2))
		_text("JACKPOT!" if v.headline else v.money, Vector2(110, 37.5), 30,
			Color("ffe9a8") if v.win and not v.flash else Color.WHITE, BARLOW, 0,
			Color(GOLD, 0.9) if v.win else Color("6e96ff", 0.7), 196)
	draw_colored_polygon(PackedVector2Array([Vector2(8, 6), Vector2(86, 6), Vector2(62, 56), Vector2(8, 56)]),
		Color(1, 1, 1, 0.06))   # the glass's sheen
	var power := _bet_light(v) if v.in else Color(1, 1, 1, 0.25) if v.on else OFF_RED
	if v.in and v.flash:
		draw_rect(Rect2(106, 59.5, 8, 6), Color(power, 0.3))
	draw_rect(Rect2(108, 61, 4, 3), power)


## A split-flap board in the rail's wood: ten tiles that flip as the amount changes (and scramble at each
## switch of a win), on a brass plate.
func _flap(v: Dictionary) -> void:
	var flash: bool = v.win and v.flash
	if flash:
		_glow_box(Rect2(0, 0, 220, 68), 6, GOLD, 0.6)
	_fill(Rect2(0, 0, 220, 68), 6, Color("2e1c10"))
	_wood(Rect2(1, 1, 218, 66), 5, TableStyle.wood_of(v.look, "match"))
	draw_line(Vector2(6, 3), Vector2(214, 3), Color(1, 1, 1, 0.14), 4.0)
	draw_line(Vector2(6, 65), Vector2(214, 65), Color(0, 0, 0, 0.25), 2.0)
	var text := _flap_string(v)
	var flipping: bool = v.now - _flap_changed < 0.25
	var scramble: bool = v.win and v.tick % 6 < 2
	for i in 10:
		var x := 11.0 + i * 20.0
		var flip := scramble or (flipping and i < _flap_prev.length() and _flap_prev[i] != text[i])
		var ch := FLAP_GLYPHS[(v.tick * 7 + i * 5) % FLAP_GLYPHS.length()] if scramble else text[i]
		_fill(Rect2(x, 9, 18, 34), 2, Color("151515"))
		draw_rect(Rect2(x + 0.5, 9.5, 17, 16.5), Color("2c2c2c") if flip else Color("1b1b1b"))
		draw_line(Vector2(x + 1, 9.6), Vector2(x + 17, 9.6), Color(1, 1, 1, 0.08), 1.0)
		if ch != " ":
			_text(ch, Vector2(x + 9, 26), 26, GOLD if flash else Color("f2ede0"), BARLOW, 0, Color.TRANSPARENT, 0.0,
				0.7 if flip else 1.0)
		draw_line(Vector2(x, 25.5), Vector2(x + 18, 25.5), Color.BLACK, 1.0)
	var plate := Color("1c130a")
	var ink := BRASS
	if not v.on:
		plate = Color("2a1d10")
		ink = Color("5c4a28")
	elif v.win:
		plate = Color("fff1c2") if v.flash else BRASS
		ink = Color("1b1307")
	_fill(Rect2(38, 47, 144, 13), 2, plate)
	_outline(Rect2(38.5, 47.5, 143, 12), 2, Color(BRASS, 0.55), 1.0)
	var words := "JACKPOT WINNER" if v.win else "PROGRESSIVE JACKPOT"
	_text(words, Vector2(110, 53.5), 7, ink, _spacing(CINZEL, 1), 0, Color.TRANSPARENT, 136)


## Neon: a tube round a black box, JACKPOT in pink over the amount in cyan. It flickers now and then; a win
## cycles the tubes through their colours.
func _neon(v: Dictionary) -> void:
	_fill(Rect2(0, 0, 220, 68), 6, Color("26262e"))
	_fill(Rect2(1, 1, 218, 66), 5, Color("0b0b10"))
	draw_line(Vector2(6, 2.5), Vector2(214, 2.5), Color("24242c"), 3.0)
	var tube := TableFelt._rounded(Rect2(6, 6, 208, 55), 6)
	tube.append(tube[0])
	if not v.on:
		draw_polyline(tube, Color("2e2b33"), 1.5, true)
		_text("JACKPOT", Vector2(110, 19.5), 11, Color("3b3742"), _spacing(JOSEFIN, 4))
		return
	var frame: Color = NEON[v.tick % 4] if v.win else NEON[0]
	var label: Color = NEON[(v.tick + 2) % 4] if v.win else NEON[0]
	draw_polyline(tube, Color(frame, 0.12), 7.0, true)
	draw_polyline(tube, Color(frame, 0.3), 4.0, true)
	draw_polyline(tube, frame.lerp(Color.WHITE, 0.35), 1.5, true)
	var flicker: bool = not v.win and _flicker(v.tick)
	_text("WINNER!" if v.win else "JACKPOT", Vector2(110, 19.5), 11,
		Color("6a3560") if flicker else Color("fff2fb"), _spacing(JOSEFIN, 4), 0,
		Color.TRANSPARENT if flicker else label)
	_text("JACKPOT!" if v.headline else v.money, Vector2(110, 40), 25, Color("effdff"), JOSEFIN, 0,
		NEON[2] if v.win and v.flash else NEON[1], 196)


# ------------------------------------------------------------------ helpers (all in the mockup's units)
## A sign's light while the local player's Jackpot bet is on: blinking blue.
func _bet_light(v: Dictionary) -> Color:
	return LAMPS[2] if v.flash else Color("1d3a55")


## Draws in the mockup's units from here on: 220 across, the shadow's foot at this node's origin.
func _base() -> void:
	draw_set_transform(Vector2(-MOCK.x / 2, -MOCK.y) * K, 0, Vector2(K, K))


func _fill(rect: Rect2, radius: float, colour: Color) -> void:
	draw_colored_polygon(TableFelt._rounded(rect, radius), colour)


func _outline(rect: Rect2, radius: float, colour: Color, width: float) -> void:
	var pts := TableFelt._rounded(rect, radius)
	pts.append(pts[0])
	draw_polyline(pts, colour, width, true)


## A soft glow round a box: a few widening, fading rounded rects behind it.
func _glow_box(rect: Rect2, radius: float, colour: Color, strength: float) -> void:
	for i in range(4, 0, -1):
		_fill(rect.grow(i * 3.0), radius + i * 3.0, Color(colour, 0.1 * strength))


func _ellipse(centre: Vector2, rx: float, ry: float, colour: Color) -> void:
	var pts := PackedVector2Array()
	for i in 28:
		var a := TAU * i / 28.0
		pts.append(centre + Vector2(cos(a) * rx, sin(a) * ry))
	draw_colored_polygon(pts, colour)


func _wood(rect: Rect2, radius: float, wood: String) -> void:
	var pts := TableFelt._rounded(rect, radius)
	var uv := PackedVector2Array()
	var tile: float = TableStyle.WOOD_TILE.get(wood, 52.0) / K
	for p in pts:
		uv.append(p / tile)
	draw_colored_polygon(pts, Color(0.85, 0.85, 0.85), uv, TableStyle.WOODS.get(wood, TableStyle.WOODS.walnut))


## Lettering on a rounded pill.
func _pill(words: String, centre: Vector2, size: int, fill: Color, ink: Color) -> void:
	var w := MONTSERRAT.get_string_size(words, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	_fill(Rect2(centre.x - w / 2 - 7, centre.y - 6, w + 14, 12), 6, fill)
	_text(words, centre, size, ink, MONTSERRAT)


## A font letter-spaced by `spacing` (in the mockup's units).
static func _spacing(font: Font, spacing: int) -> Font:
	var key := "%s/%d" % [font.resource_path, spacing]
	if not _spaced.has(key):
		var v := FontVariation.new()
		v.base_font = font
		v.spacing_glyph = spacing
		_spaced[key] = v
	return _spaced[key]


## The biggest whole size up to `size` at which `s` fits in `max_w`.
func _fit(s: String, size: int, font: Font, max_w: float) -> int:
	var w := font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	return size if w <= max_w else maxi(1, int(size * max_w / w))


## One line of lettering with its middle at `at.y`: centred on `at.x` (align 0), ending there (1) or starting
## there (-1). A glow is drawn as soft outlines under it; `squash` flattens it (a flap mid-flip).
func _text(s: String, at: Vector2, size: int, colour: Color, font: Font, align := 0, glow := Color.TRANSPARENT,
		max_w := 0.0, squash := 1.0) -> void:
	var px := _fit(s, size, font, max_w) if max_w > 0.0 else size
	var w := font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x
	var x := at.x - w / 2.0 if align == 0 else at.x - w if align == 1 else at.x
	var y := at.y + (font.get_ascent(px) - font.get_descent(px)) / 2.0
	if squash != 1.0:   # (flattened about its middle)
		draw_set_transform((Vector2(-MOCK.x / 2, -MOCK.y) + Vector2(0, at.y)) * K, 0, Vector2(K, K * squash))
		y -= at.y
	if glow.a > 0.0:
		draw_string_outline(font, Vector2(x, y), s, HORIZONTAL_ALIGNMENT_LEFT, -1, px, 4, Color(glow, glow.a * 0.3))
		draw_string_outline(font, Vector2(x, y), s, HORIZONTAL_ALIGNMENT_LEFT, -1, px, 2, Color(glow, glow.a * 0.5))
	draw_string(font, Vector2(x, y), s, HORIZONTAL_ALIGNMENT_LEFT, -1, px, colour)
	if squash != 1.0:
		_base()
