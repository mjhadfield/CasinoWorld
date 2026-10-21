@tool
extends TableFelt
## The roulette table in the house Mahogany & Brass: the same wood rail (leather
## padding on the dealer's side) and crimson felt as the card tables, cut to the
## roulette table's shape (RouTable.shape) -- a brass bead where they meet, no
## pinstripe. On it: the float (chip tray) left of the dealer's bay, the chip
## hole right of it, the title, and the layout: the zero box pointing at the
## wheel, every number's box filled in its colour, the columns, dozens and even
## chances, with the printed grid drawn last as one set of lines so the joins
## are clean. The numbers a hovered bet covers light up under the chips.

const NUM_RED := Color("e0453d")
const NUM_BLACK := Color("1a0d0b")
const NUM_GREEN := Color("1f8a52")
const LINE := Color(0.945, 0.894, 0.769, 0.9)
const HILITE := Color(0.94, 0.83, 0.55, 0.72)


func paint() -> void:
	var t := _table() as RouTable
	if t == null:
		return
	draw_set_transform(-position)
	var r := RouTable.RAIL_W
	# Its shadow on the carpet, the rail, the leather on the dealer's side, the highlight.
	draw_colored_polygon(_shifted(RouTable.shape(r + 4.0), Vector2(0, 3)), Color(0, 0, 0, 0.16))
	draw_colored_polygon(_shifted(RouTable.shape(r + 1.5), Vector2(0, 2)), Color(0, 0, 0, 0.3))
	var rail := RouTable.shape(r + 0.5)
	draw_colored_polygon(rail, WOOD_DARK)
	draw_colored_polygon(RouTable.shape(r - 1.1), WOOD)
	for grain in [[1.6, 0.45], [2.9, 0.3], [4.3, 0.4], [5.4, 0.25]]:
		_loop(RouTable.shape(grain[0]), Color(WOOD_DARK, grain[1]), 0.35)
	var dealer_side := PackedVector2Array([Vector2(-400, -400), Vector2(400, -400),
		Vector2(400, RouTable.FELT_TOP + 1.5), Vector2(-400, RouTable.FELT_TOP + 1.5)])
	for part in Geometry2D.intersect_polygons(rail, dealer_side):
		draw_colored_polygon(part, WOOD_PAD)
	_loop(_shifted(RouTable.shape(r * 0.68), Vector2(0, -1.2)), WOOD_SHINE, 1.1)
	# The felt: crimson, darker towards the rail, with a woven grain; the brass bead.
	var felt := RouTable.shape(0.0, true, 12)
	var centre := Vector2(30, -60)
	var uv := PackedVector2Array()
	var grain_uv := PackedVector2Array()
	for p in felt:
		uv.append((p - centre) / 420.0 + Vector2(0.5, 0.5))
		grain_uv.append(p / 40.0)
	draw_colored_polygon(felt, Color.WHITE, uv, _felt_gradient())
	draw_colored_polygon(felt, Color(1, 1, 1, 0.25), grain_uv, GRAIN)
	_loop(RouTable.shape(-0.9), Color(0, 0, 0, 0.3), 1.4)
	_loop(RouTable.shape(-0.3), BRASS, 0.6)

	_chip_tray(t)
	_hole(RouTable.HOLE_AT, RouTable.HOLE_R)
	_textf("ROULETTE", RouTable.TITLE_AT, 8.0, CREAM, CINZEL)
	_textf("SINGLE ZERO · LA PARTAGE · £1 – £100 STRAIGHT UP", RouTable.TITLE_AT + Vector2(0, 7.5), 3.1, Color(CREAM, 0.8), CINZEL)
	_layout(t)
	draw_set_transform(-position)


## The hole the losing chips go down: dark, with a brass rim.
func _hole(at: Vector2, radius: float) -> void:
	draw_circle(at + Vector2(0, 0.6), radius + 0.8, Color(0, 0, 0, 0.3))
	draw_circle(at, radius, Color("3a1a0c"))
	draw_circle(at, radius - 1.2, Color("120604"))
	draw_circle(at + Vector2(0, 0.6), radius - 2.4, Color.BLACK)
	draw_arc(at, radius, 0, TAU, 40, Color("ecd08a"), 1.1, true)
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
	draw_colored_polygon(zero, NUM_GREEN)
	if lit.has(0):
		draw_colored_polygon(zero, HILITE)
	for n in range(1, 37):
		var box := Rect2(gx + RouTable.col_of(n) * bw, gy + RouTable.row_of(n) * bh, bw, bh)
		draw_rect(box, NUM_RED if n in RouTable.RED else NUM_BLACK)
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
		draw_colored_polygon(diamond, NUM_RED if i == 2 else NUM_BLACK)
		diamond.append(diamond[0])
		draw_polyline(diamond, Color(CREAM, 0.7), 0.5, true)
	# Then the printed grid: the outline as one closed line, the rest edge to edge.
	var outline := PackedVector2Array([Vector2(zx + 5, gy), Vector2(right + bw, gy), Vector2(right + bw, gy + 3 * bh),
		Vector2(right, gy + 3 * bh), Vector2(right, bottom), Vector2(gx, bottom), Vector2(gx, gy + 3 * bh),
		Vector2(zx + 5, gy + 3 * bh), Vector2(zx, gy + 1.5 * bh), Vector2(zx + 5, gy)])
	draw_polyline(outline, LINE, 0.7, true)
	for r in [1, 2]:
		draw_line(Vector2(gx, gy + r * bh), Vector2(right + bw, gy + r * bh), LINE, 0.7, true)
	for y in [gy + 3 * bh, dy + RouTable.DH]:
		draw_line(Vector2(gx, y), Vector2(right, y), LINE, 0.7, true)
	for c in range(0, 13):
		draw_line(Vector2(gx + c * bw, gy), Vector2(gx + c * bw, gy + 3 * bh), LINE, 0.7, true)
	for k in [4, 8]:
		draw_line(Vector2(gx + k * bw, gy + 3 * bh), Vector2(gx + k * bw, bottom), LINE, 0.7, true)
	for k in [2, 6, 10]:
		draw_line(Vector2(gx + k * bw, ey), Vector2(gx + k * bw, bottom), LINE, 0.7, true)
	# Lettering last.
	_textf("0", Vector2((zx + gx) / 2 + 1, gy + 1.5 * bh), 8.0, CREAM, CINZEL)
	for n in range(1, 37):
		_textf(str(n), Vector2(gx + RouTable.col_of(n) * bw + bw / 2, gy + RouTable.row_of(n) * bh + bh / 2 + 0.3), 6.4, CREAM, CINZEL)
	for r in 3:
		_textf("2 to 1", Vector2(right + bw / 2, gy + r * bh + bh / 2), 3.3, CREAM, CINZEL)
	for k in 3:
		_textf(["1st 12", "2nd 12", "3rd 12"][k], Vector2(gx + k * 4 * bw + 2 * bw, dy + RouTable.DH / 2), 5.0, CREAM, CINZEL)
	for pair in [[0, "1 – 18"], [1, "EVEN"], [4, "ODD"], [5, "19 – 36"]]:
		_textf(pair[1], Vector2(gx + pair[0] * 2 * bw + bw, ey + RouTable.EH / 2), 4.6, CREAM, CINZEL)


## Text centred on a point at any size (fonts take whole sizes; the rest is scaled).
func _textf(s: String, at: Vector2, size: float, colour: Color, font: Font) -> void:
	var px := maxi(1, ceili(size))
	var k := size / px
	var w := font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x
	draw_set_transform(-position + at, 0, Vector2(k, k))
	draw_string(font, Vector2(-w / 2, px * 0.35), s, HORIZONTAL_ALIGNMENT_LEFT, -1, px, colour)
	draw_set_transform(-position)
