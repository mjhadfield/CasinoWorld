@tool
extends StyledFelt
## The roulette table in its table style (TableStyle "roulette", designed on the admin page's Tables tab):
## the rail and felt of the style, cut to the roulette table's shape (RouTable.shape), with its bead where they
## meet. On it: the float (chip tray) left of the dealer's bay, the chip hole right of it, the title, and the
## layout: the zero box pointing at the wheel, every number's box filled in the style's number colours, the
## columns, dozens and even chances, with the printed grid drawn last as one set of lines so the joins are
## clean, all in the style's ink and lettering. The numbers a hovered bet covers light up under the chips.

const HILITE := Color(0.94, 0.83, 0.55, 0.72)

var _red: Color
var _black: Color
var _zero: Color
var _ink: Color
var _rule: Color
var _font: Font


func _grown(by: float) -> PackedVector2Array:
	return RouTable.shape(by)


func _rail_w() -> float:
	return RouTable.RAIL_W


func _middle() -> Vector2:
	return Vector2(30, -60)


func _reach() -> float:
	return 420.0


func _straight(_p: Vector2, _half := 70.0) -> bool:
	return false


func paint() -> void:
	var t := _table() as RouTable
	if t == null:
		return
	d = t.style()
	_red = TableStyle.colour(d, "numbers.red")
	_black = TableStyle.colour(d, "numbers.black")
	_zero = TableStyle.colour(d, "numbers.zero")
	_ink = ink()
	_rule = Color(_ink, 0.9)
	_font = TableStyle.font(d)
	draw_set_transform(-position)
	var r := RouTable.RAIL_W
	# Its shadow on the carpet, the rail, the felt, the border and the bead.
	draw_colored_polygon(_shifted(RouTable.shape(r + 4.0), Vector2(0, 3)), Color(0, 0, 0, 0.16))
	draw_colored_polygon(_shifted(RouTable.shape(r + 1.5), Vector2(0, 2)), Color(0, 0, 0, 0.3))
	var felt := RouTable.shape(0.0, true, 12)
	_rail(felt, false)
	_felt(felt)
	_border(false)
	_bead(felt)

	float_tray(t.tray_rect(), felt, str(d.float))
	_hole(RouTable.HOLE_AT, RouTable.HOLE_R)
	_textf("ROULETTE", RouTable.TITLE_AT, 8.0, _ink, _font)
	_textf("SINGLE ZERO · LA PARTAGE · £1 – £100 STRAIGHT UP", RouTable.TITLE_AT + Vector2(0, 7.5), 3.1, Color(_ink, 0.8), _font)
	_layout(t)
	draw_set_transform(-position)


## The hole the losing chips go down: dark, with a rim in the wheel's metal.
func _hole(at: Vector2, radius: float) -> void:
	var metal: Array = TableStyle.BEADS.get(str(d.wheel.metal), TableStyle.BEADS.brass)
	draw_circle(at + Vector2(0, 0.6), radius + 0.8, Color(0, 0, 0, 0.3))
	draw_circle(at, radius, Color("3a1a0c"))
	draw_circle(at, radius - 1.2, Color("120604"))
	draw_circle(at + Vector2(0, 0.6), radius - 2.4, Color.BLACK)
	draw_arc(at, radius, 0, TAU, 40, metal[0].lerp(metal[1], 0.6), 1.1, true)
	draw_arc(at, radius - 1.0, PI * 1.1, PI * 1.9, 12, Color(0, 0, 0, 0.5), 0.6, true)


func _layout(t: RouTable) -> void:
	var gx := RouTable.GX
	var gy := RouTable.GY
	var bw := RouTable.BW
	var bh := RouTable.BH
	var zx := RouTable.ZX
	var dy := RouTable.DY
	var ey := RouTable.EY
	var right := gx + 12 * bw
	var bottom := ey + RouTable.EH
	var lit := {}
	if t.hover_spot != "" and RouTable.bets().has(t.hover_spot):
		for n in RouTable.bets()[t.hover_spot].numbers:
			lit[n] = true
	# Fills first: the zero, each number's box in its colour, anything hovered.
	var zero := PackedVector2Array([Vector2(gx, gy), Vector2(zx + 5, gy), Vector2(zx, gy + 1.5 * bh),
		Vector2(zx + 5, gy + 3 * bh), Vector2(gx, gy + 3 * bh)])
	draw_colored_polygon(zero, _zero)
	if lit.has(0):
		draw_colored_polygon(zero, HILITE)
	for n in range(1, 37):
		var box := Rect2(gx + RouTable.col_of(n) * bw, gy + RouTable.row_of(n) * bh, bw, bh)
		draw_rect(box, _red if n in RouTable.RED else _black)
		if lit.has(n):
			draw_rect(box, HILITE)
	var h := t.hover_spot
	for r in 3:
		if h == "col%d" % (3 - r):
			draw_rect(Rect2(right, gy + r * bh, bw, bh), HILITE)
	for k in 3:
		if h == "doz%d" % (k + 1):
			draw_rect(Rect2(gx + k * 4 * bw, dy, 4 * bw, RouTable.DH), HILITE)
	for i in 6:
		if h == RouTable.EVENS[i]:
			draw_rect(Rect2(gx + i * 2 * bw, ey, 2 * bw, RouTable.EH), HILITE)
	# The red and black diamonds.
	for i in [2, 3]:
		var c := Vector2(gx + i * 2 * bw + bw, ey + RouTable.EH / 2)
		var diamond := PackedVector2Array([c + Vector2(0, -4.5), c + Vector2(9, 0), c + Vector2(0, 4.5), c + Vector2(-9, 0)])
		draw_colored_polygon(diamond, _red if i == 2 else _black)
		diamond.append(diamond[0])
		draw_polyline(diamond, Color(_ink, 0.7), 0.5, true)
	# Then the printed grid: the outline as one closed line, the rest edge to edge.
	var outline := PackedVector2Array([Vector2(zx + 5, gy), Vector2(right + bw, gy), Vector2(right + bw, gy + 3 * bh),
		Vector2(right, gy + 3 * bh), Vector2(right, bottom), Vector2(gx, bottom), Vector2(gx, gy + 3 * bh),
		Vector2(zx + 5, gy + 3 * bh), Vector2(zx, gy + 1.5 * bh), Vector2(zx + 5, gy)])
	draw_polyline(outline, _rule, 0.7, true)
	for r in [1, 2]:
		draw_line(Vector2(gx, gy + r * bh), Vector2(right + bw, gy + r * bh), _rule, 0.7, true)
	for y in [gy + 3 * bh, dy + RouTable.DH]:
		draw_line(Vector2(gx, y), Vector2(right, y), _rule, 0.7, true)
	for c in range(0, 13):
		draw_line(Vector2(gx + c * bw, gy), Vector2(gx + c * bw, gy + 3 * bh), _rule, 0.7, true)
	for k in [4, 8]:
		draw_line(Vector2(gx + k * bw, gy + 3 * bh), Vector2(gx + k * bw, bottom), _rule, 0.7, true)
	for k in [2, 6, 10]:
		draw_line(Vector2(gx + k * bw, ey), Vector2(gx + k * bw, bottom), _rule, 0.7, true)
	# Lettering last.
	_textf("0", Vector2((zx + gx) / 2 + 1, gy + 1.5 * bh), 8.0, _ink, _font)
	for n in range(1, 37):
		_textf(str(n), Vector2(gx + RouTable.col_of(n) * bw + bw / 2, gy + RouTable.row_of(n) * bh + bh / 2 + 0.3), 6.4, _ink, _font)
	for r in 3:
		_textf("2 to 1", Vector2(right + bw / 2, gy + r * bh + bh / 2), 3.3, _ink, _font)
	for k in 3:
		_textf(["1st 12", "2nd 12", "3rd 12"][k], Vector2(gx + k * 4 * bw + 2 * bw, dy + RouTable.DH / 2), 5.0, _ink, _font)
	for pair in [[0, "1 – 18"], [1, "EVEN"], [4, "ODD"], [5, "19 – 36"]]:
		_textf(pair[1], Vector2(gx + pair[0] * 2 * bw + bw, ey + RouTable.EH / 2), 4.6, _ink, _font)


## Text centred on a point at any size (fonts take whole sizes; the rest is scaled).
func _textf(s: String, at: Vector2, size: float, colour: Color, font: Font) -> void:
	var px := maxi(1, ceili(size))
	var k := size / px
	var w := font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x
	draw_set_transform(-position + at, 0, Vector2(k, k))
	draw_string(font, Vector2(-w / 2, px * 0.35), s, HORIZONTAL_ALIGNMENT_LEFT, -1, px, colour)
	draw_set_transform(-position)
