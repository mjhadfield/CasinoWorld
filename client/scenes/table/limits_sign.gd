class_name LimitsSign
extends Node2D
## The table limits sign, standing on the felt at the other end of the dealer's ledge from the jackpot sign: top
## right as the players see it, between the rail and the dealer's cards, clear of every game's machines
## (CasinoTable.LIMITS_SIGN). It shows the table's limits (CasinoTable.limits, from the floor plan): MAIN BETS and
## SIDE BETS, each a minimum and a maximum, the figures in columns so the two rows line up.
##
## Its design is the table style's `limitsSign`: plaque (engraved brass on a wooden easel), tent (a smoked acrylic
## tent card with a band of the printing's trim colour), digital (a black display lit in the table's LED colour,
## with MIN and MAX columns) or deco (a gilt frame round a panel of the felt, in the layout's lettering). The admin
## designer draws the same (limitsSign() in render.js; the signed-off mockup is docs/limits_sign/mockup/).
##
## Drawn in code in the jackpot sign's units and scale (JackpotSign.K, 68 high) but narrower (MOCK_W across), its
## shadow's foot at this node's origin. It doesn't animate: it redraws when its table's limits or style change.

const MOCK_W := 154.0
const H := 80.0
const K := JackpotSign.K
const ROW_Y := [33.0, 51.0]

const VT323 := preload("res://assets/fonts/VT323-Regular.ttf")
const BARLOW := preload("res://assets/fonts/BarlowCondensed-Bold.ttf")
const MONTSERRAT := preload("res://assets/fonts/Montserrat-SemiBold.ttf")
const CINZEL := preload("res://assets/fonts/Cinzel-SemiBold.ttf")

var _table: CasinoTable


func _ready() -> void:
	texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED   # (the easel's wood)
	var n := get_parent()
	while n != null and not n is CasinoTable:
		n = n.get_parent()
	_table = n


## Where it's drawn, in its parent's units (the table's).
func drawn_rect() -> Rect2:
	return Rect2(position + Vector2(-MOCK_W / 2, -H) * K, Vector2(MOCK_W, H) * K)


## Where it stands on the felt: the bottom of its face down to its shadow (its face rises in front of what's behind).
func footprint() -> Rect2:
	return Rect2(position + Vector2(-MOCK_W / 2, -12) * K, Vector2(MOCK_W, 12) * K)


## Its two rows: [label, min, max, role] (pence; role "primary" or "side", the printing's colour on the deco).
func _rows() -> Array:
	var limits: Dictionary = _table.limits if _table else CasinoTable.DEFAULT_LIMITS
	return [["MAIN BETS", int(limits.main[0]), int(limits.main[1]), "primary"],
		["SIDE BETS", int(limits.side[0]), int(limits.side[1]), "side"]]


static func pounds(pence: int) -> String:
	return Money.format(pence, true)


# ------------------------------------------------------------------ drawing
func _draw() -> void:
	var look := _table.style() if _table else TableStyle.fill({})
	var rows := _rows()
	_base()
	var m := MOCK_W / 2
	for e in [[0.48, 9.0, 0.16], [0.43, 7.0, 0.2], [0.375, 5.0, 0.2]]:   # its shadow
		_ellipse(Vector2(m, 72), MOCK_W * e[0], e[1], Color(0, 0, 0, e[2]))
	match str(look.get("limitsSign", "plaque")):
		"tent":
			_tent(look, rows)
		"digital":
			_digital(look, rows)
		"deco":
			_deco(look, rows)
		_:
			_plaque(look, rows)
	draw_set_transform(Vector2.ZERO)


## Engraved brushed brass, screwed to a little easel in the rail's wood.
func _plaque(look: Dictionary, rows: Array) -> void:
	var w := MOCK_W
	var m := w / 2
	_wood(Rect2(m - 26, 56, 52, 18), 3, TableStyle.wood_of(look, "match"))
	draw_line(Vector2(m - 24, 57), Vector2(m + 24, 57), Color(1, 1, 1, 0.14), 1.0)
	_fill(Rect2(0, 0, w, 68), 5, Color("5e4318"))
	_gradient(Rect2(1.4, 1.4, w - 2.8, 65.2), 4, [[0.0, Color("f4dc98")], [0.45, Color("d2a748")], [0.8, Color("b48a33")],
		[1.0, Color("e2bf68")]])
	var brushed := PackedVector2Array()
	var y := 3.0
	while y < 66.0:
		brushed.append_array([Vector2(2, y), Vector2(w - 2, y)])
		y += 1.6
	draw_multiline(brushed, Color(1, 1, 1, 0.06), 0.5)
	_outline(Rect2(6.5, 6.5, w - 13, 55), 2.5, Color(0.37, 0.26, 0.09, 0.55), 1.0)
	_outline(Rect2(7.3, 7.3, w - 13, 55), 2.5, Color(1, 0.96, 0.82, 0.35), 0.6)
	for at in [Vector2(3.8, 3.8), Vector2(w - 3.8, 3.8), Vector2(3.8, 64.2), Vector2(w - 3.8, 64.2)]:
		draw_circle(at, 1.6, Color("7a5a22"))
		draw_line(at + Vector2(-1, 1), at + Vector2(1, -1), Color("3b2a0e"), 0.5)
	var ink := Color("33230a")
	var lift := Color(1, 0.95, 0.81, 0.55)
	_text("TABLE LIMITS", Vector2(m, 15), 9, ink, _spacing(CINZEL, 3), 0, lift)
	draw_line(Vector2(m - 46, 22.5), Vector2(m + 46, 22.5), Color(0.2, 0.14, 0.04, 0.5), 0.7)
	draw_line(Vector2(m - 46, 23.3), Vector2(m + 46, 23.3), Color(1, 0.95, 0.81, 0.4), 0.5)
	var f := _figures(rows, CINZEL, 14, w - 13, _room(13)[1])
	for i in rows.size():
		_text(rows[i][0], Vector2(13, ROW_Y[i] + 1), 10, ink, _spacing(CINZEL, 1), -1, lift, _room(13)[0])
		_draw_figures(f, rows[i], ROW_Y[i] + 1, ink, lift)


## A smoked acrylic tent card, printed in white, a band of the printing's trim colour along the top.
func _tent(look: Dictionary, rows: Array) -> void:
	var w := MOCK_W
	var m := w / 2
	_fill(Rect2(m - 40, 58, 80, 14), 2.5, Color(0.75, 0.84, 0.91, 0.22))
	draw_line(Vector2(m - 38, 59), Vector2(m + 38, 59), Color(1, 1, 1, 0.35), 1.0)
	_fill(Rect2(0, 0, w, 68), 4, Color(0.055, 0.063, 0.078, 0.9))
	_outline(Rect2(0.6, 0.6, w - 1.2, 66.8), 4, Color(0.84, 0.91, 0.96, 0.38), 1.2)
	var band := _colour(look, "accent")
	_fill(Rect2(5, 5, w - 10, 15), 2, band)
	_text("TABLE LIMITS", Vector2(m, 12.8), 9, Color("15171b") if band.get_luminance() > 0.55 else Color.WHITE,
		_spacing(MONTSERRAT, 2))
	draw_line(Vector2(10, 42), Vector2(w - 10, 42), Color(1, 1, 1, 0.13), 0.8)
	var f := _figures(rows, MONTSERRAT, 16, w - 10, _room(10)[1])
	for i in rows.size():
		_text(rows[i][0], Vector2(10, ROW_Y[i]), 10, Color(1, 1, 1, 0.66), _spacing(MONTSERRAT, 1), -1,
			Color.TRANSPARENT, _room(10)[0])
		_draw_figures(f, rows[i], ROW_Y[i], Color.WHITE)
	draw_colored_polygon(PackedVector2Array([Vector2(w - 64, 1), Vector2(w - 24, 1), Vector2(w - 74, 67), Vector2(w - 114, 67)]),
		Color(1, 1, 1, 0.06))   # the acrylic's sheen


## A black limit display on a post, lit in the table's LED colour: MIN and MAX columns.
func _digital(look: Dictionary, rows: Array) -> void:
	var w := MOCK_W
	var m := w / 2
	_fill(Rect2(m - 10, 54, 20, 14), 1.5, Color("2a2c31"))
	draw_line(Vector2(m - 8, 55), Vector2(m - 8, 67), Color(1, 1, 1, 0.12), 1.0)
	_fill(Rect2(m - 32, 64, 64, 8), 3.5, Color("1b1c20"))
	_fill(Rect2(0, 0, w, 68), 6, Color("25272c"))
	_fill(Rect2(1, 1, w - 2, 66), 5, Color("0d0e11"))
	draw_line(Vector2(6, 2.5), Vector2(w - 6, 2.5), Color("2c2e34"), 3.0)
	_fill(Rect2(7, 7, w - 14, 52), 2.5, Color("020304"))
	var led := TableStyle.colour(look, "led")
	var dim := Color(led, 0.62)
	var hot := led.lerp(Color.WHITE, 0.55)
	var x_min := w - 50
	var x_max := w - 10
	_text("TABLE LIMITS", Vector2(12, 15), 10, dim, _spacing(BARLOW, 1), -1, Color.TRANSPARENT, x_min - 48)
	_text("MIN", Vector2(x_min, 15), 10, dim, _spacing(BARLOW, 2), 1)
	_text("MAX", Vector2(x_max, 15), 10, dim, _spacing(BARLOW, 2), 1)
	draw_line(Vector2(11, 22), Vector2(w - 11, 22), Color(led, 0.22), 0.8)
	var widest := 0.0   # every figure one size: the biggest that lets the widest fit its column
	for r in rows:
		for p in [r[1], r[2]]:
			widest = maxf(widest, VT323.get_string_size(pounds(p), HORIZONTAL_ALIGNMENT_LEFT, -1, 21).x)
	var size := mini(21, int(21 * 34 / widest))
	for i in rows.size():
		var y: float = ROW_Y[i] + 1
		_text(rows[i][0], Vector2(12, y), 13, led, _spacing(BARLOW, 1), -1, Color(led, 0.6), x_min - 52)
		_text(pounds(rows[i][1]), Vector2(x_min, y + 0.5), size, hot, VT323, 1, Color(led, 0.8))
		_text(pounds(rows[i][2]), Vector2(x_max, y + 0.5), size, hot, VT323, 1, Color(led, 0.8))
	var scan := PackedVector2Array()
	var sy := 8.0
	while sy < 59.0:
		scan.append_array([Vector2(7, sy), Vector2(w - 7, sy)])
		sy += 2.0
	draw_multiline(scan, Color(0, 0, 0, 0.28), 0.6)
	draw_colored_polygon(PackedVector2Array([Vector2(9, 7), Vector2(56, 7), Vector2(40, 59), Vector2(9, 59)]),
		Color(1, 1, 1, 0.04))   # the glass's sheen
	draw_circle(Vector2(m, 63.5), 3.0, Color(led, 0.25))
	draw_circle(Vector2(m, 63.5), 1.5, led)


## A gilt frame with stepped corners round a panel of the table's felt, in the layout's lettering and colours,
## dotted leaders from each label to its figures.
func _deco(look: Dictionary, rows: Array) -> void:
	var w := MOCK_W
	var m := w / 2
	_wood(Rect2(m - 26, 56, 52, 18), 3, TableStyle.wood_of(look, "match"))
	var gilt := _colour(look, "accent")
	_gradient(Rect2(0, 0, w, 68), 2, [[0.0, gilt.lerp(Color.WHITE, 0.4)], [0.5, gilt], [1.0, gilt.darkened(0.35)]])
	_fill(Rect2(3.5, 3.5, w - 7, 61), 1, TableStyle.colour(look, "felt.colour").darkened(0.12))
	for i in range(5, 0, -1):   # the felt's vignette
		_outline(Rect2(3.5 + i * 1.6, 3.5 + i * 1.6, w - 7 - i * 3.2, 61 - i * 3.2), 1, Color(0, 0, 0, 0.07), 3.2)
	var c := 7.0
	var n := 5.0
	var x0 := 8.0
	var y0 := 8.0
	var x1 := w - 8
	var y1 := 60.0
	var line := PackedVector2Array([Vector2(x0 + c, y0), Vector2(x1 - c, y0), Vector2(x1 - c, y0 + n), Vector2(x1, y0 + n),
		Vector2(x1, y1 - n), Vector2(x1 - c, y1 - n), Vector2(x1 - c, y1), Vector2(x0 + c, y1), Vector2(x0 + c, y1 - n),
		Vector2(x0, y1 - n), Vector2(x0, y0 + n), Vector2(x0 + c, y0 + n), Vector2(x0 + c, y0)])
	draw_polyline(line, Color(gilt, 0.85), 0.9, true)
	var font := TableStyle.font(look)
	var ink := _colour(look, "ink")
	var title := _spacing(font, 2)
	var tw := title.get_string_size("TABLE LIMITS", HORIZONTAL_ALIGNMENT_LEFT, -1, 9).x
	_text("TABLE LIMITS", Vector2(m, 17), 9, ink, title)
	for sd in [-1, 1]:   # a small fan of rays either side of the title
		var cx: float = m + sd * (tw / 2 + 8)
		for k in range(-2, 3):
			var a := k * 0.32
			draw_line(Vector2(cx, 17), Vector2(cx + sd * cos(a) * 5, 17 + sin(a) * 5), Color(gilt, 0.8), 0.7)
	var f := _figures(rows, font, 14, w - 16, _room(16)[1])
	var label := _spacing(font, 1)
	for i in rows.size():
		var y: float = ROW_Y[i] + 1
		var lw := _text(rows[i][0], Vector2(16, y), 10, _colour(look, rows[i][3]), label, -1, Color.TRANSPARENT, _room(16)[0])
		_draw_figures(f, rows[i], y, ink)
		var x := 16 + lw + 4
		while x < _min_left(f, rows[i]) - 4:
			draw_circle(Vector2(x, y + 2.5), 0.55, Color(ink, 0.4))
			x += 3.2


# ------------------------------------------------------------------ the figures, in columns
## The most a row's label and its figures may take, inside `pad` at each side.
func _room(pad: float) -> Array:
	return [(MOCK_W - 2 * pad) * 0.42, (MOCK_W - 2 * pad) * 0.52]


## Where the figures go, both rows alike: the minimums right-aligned to the dashes, the maximums left-aligned from
## them and ending by `right`, all at one size (`size0`, or smaller if the widest need more than `room`).
func _figures(rows: Array, font: Font, size0: int, right: float, room: float) -> Dictionary:
	var size := size0
	var wd := _widths(rows, font, size)
	if wd.total > room:
		size = maxi(1, int(size0 * room / wd.total))
		wd = _widths(rows, font, size)
	var dash: float = right - wd.wx - wd.g - wd.wd / 2
	return {"font": font, "size": size, "dash": dash, "min_r": dash - wd.wd / 2 - wd.g, "max_l": dash + wd.wd / 2 + wd.g}


func _widths(rows: Array, font: Font, size: int) -> Dictionary:
	var wn := 0.0
	var wx := 0.0
	for r in rows:
		wn = maxf(wn, font.get_string_size(pounds(r[1]), HORIZONTAL_ALIGNMENT_LEFT, -1, size).x)
		wx = maxf(wx, font.get_string_size(pounds(r[2]), HORIZONTAL_ALIGNMENT_LEFT, -1, size).x)
	var wd := font.get_string_size("–", HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	var g := size * 0.3
	return {"wn": wn, "wx": wx, "wd": wd, "g": g, "total": wn + wx + wd + 2 * g}


func _draw_figures(f: Dictionary, row: Array, y: float, colour: Color, lift := Color.TRANSPARENT) -> void:
	_text(pounds(row[1]), Vector2(f.min_r, y), f.size, colour, f.font, 1, lift)
	_text("–", Vector2(f.dash, y), f.size, colour, f.font, 0, lift)
	_text(pounds(row[2]), Vector2(f.max_l, y), f.size, colour, f.font, -1, lift)


func _min_left(f: Dictionary, row: Array) -> float:
	return f.min_r - (f.font as Font).get_string_size(pounds(row[1]), HORIZONTAL_ALIGNMENT_LEFT, -1, f.size).x


# ------------------------------------------------------------------ helpers (all in the mockup's units)
## The printing's colour for a role (ink, primary, side or accent), as StyledFelt has them.
func _colour(look: Dictionary, role: String) -> Color:
	var pr: Dictionary = look.get("print", {})
	return Color(str(pr.get(role, pr.get("ink", "#f1e4c4"))))


## Draws in the mockup's units from here on: MOCK_W across, the shadow's foot at this node's origin.
func _base() -> void:
	draw_set_transform(Vector2(-MOCK_W / 2, -H) * K, 0, Vector2(K, K))


func _fill(rect: Rect2, radius: float, colour: Color) -> void:
	draw_colored_polygon(TableFelt._rounded(rect, radius), colour)


func _outline(rect: Rect2, radius: float, colour: Color, width: float) -> void:
	var pts := TableFelt._rounded(rect, radius)
	pts.append(pts[0])
	draw_polyline(pts, colour, width, true)


## A rounded box shaded top to bottom through `stops` ([offset, colour]).
func _gradient(rect: Rect2, radius: float, stops: Array) -> void:
	var pts := TableFelt._rounded(rect, radius)
	var colours := PackedColorArray()
	for p in pts:
		var t := clampf((p.y - rect.position.y) / rect.size.y, 0.0, 1.0)
		var c: Color = stops[0][1]
		for i in range(1, stops.size()):
			if t <= stops[i][0]:
				var a: Array = stops[i - 1]
				c = (a[1] as Color).lerp(stops[i][1], (t - a[0]) / maxf(0.001, stops[i][0] - a[0]))
				break
		colours.append(c)
	draw_polygon(pts, colours)


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


static func _spacing(font: Font, spacing: int) -> Font:
	return JackpotSign._spacing(font, spacing)


## One line of lettering with its middle at `at.y`: centred on `at.x` (align 0), ending there (1) or starting
## there (-1), shrunk to fit `max_w` if given. `under` is a glow (soft outlines), or for the plaque's engraving a
## light copy just below it. Returns its width.
func _text(s: String, at: Vector2, size: int, colour: Color, font: Font, align := 0, under := Color.TRANSPARENT,
		max_w := 0.0) -> float:
	var px := size
	if max_w > 0.0:
		var full := font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
		if full > max_w:
			px = maxi(1, int(size * max_w / full))
	var w := font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x
	var x := at.x - w / 2.0 if align == 0 else at.x - w if align == 1 else at.x
	var y := at.y + (font.get_ascent(px) - font.get_descent(px)) / 2.0
	if under.a > 0.0:
		if colour.get_luminance() < 0.3:   # (dark ink: an engraving's lit lower edge)
			draw_string(font, Vector2(x, y + 0.9), s, HORIZONTAL_ALIGNMENT_LEFT, -1, px, under)
		else:
			draw_string_outline(font, Vector2(x, y), s, HORIZONTAL_ALIGNMENT_LEFT, -1, px, 3, Color(under, under.a * 0.35))
	draw_string(font, Vector2(x, y), s, HORIZONTAL_ALIGNMENT_LEFT, -1, px, colour)
	return w
