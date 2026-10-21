@tool
extends TableFelt
## The craps table in the house Mahogany & Brass: the wood rail (leather padding
## on the dealers' side) and crimson felt of every table, cut to the craps
## table's shape (CrapsTable.shape), the rubber pyramids lining both end walls
## and round their corners, the chip rack in the boxman's bay, the groove of the
## players' chip rail, and the double-ended layout, printed in cream: at each end
## the point boxes (each split Lay / Place / Buy), Don't Come, Come, the Field, Big 6/8,
## Don't Pass; in the middle, the proposition box, its rows level with the ends'
## lines; and the Pass Line (with the odds behind it) running the length of the
## front, through the middle, and curving up both ends. What a hovered bet covers lights up under the chips.

const LINE := Color(0.945, 0.894, 0.769, 0.9)
const HILITE := Color(0.94, 0.83, 0.55, 0.55)
const GOLD := Color("f2cf6a")
const RED := Color("e0453d")
const DIE_FACE := Color(0.945, 0.894, 0.769, 0.92)
const PIPS := CrapsDice.PIPS


func paint() -> void:
	var t := _table() as CrapsTable
	if t == null:
		return
	draw_set_transform(-position)
	var r := CrapsTable.RAIL_W
	# Its shadow on the carpet, the rail, the leather on the dealers' side, the highlight.
	draw_colored_polygon(_shifted(CrapsTable.shape(r + 4.0), Vector2(0, 3)), Color(0, 0, 0, 0.16))
	draw_colored_polygon(_shifted(CrapsTable.shape(r + 1.5), Vector2(0, 2)), Color(0, 0, 0, 0.3))
	var rail := CrapsTable.shape(r + 0.5)
	draw_colored_polygon(rail, WOOD_DARK)
	draw_colored_polygon(CrapsTable.shape(r - 1.1), WOOD)
	for grain in [[1.6, 0.45], [2.9, 0.3], [4.3, 0.4], [5.4, 0.25]]:
		_loop(CrapsTable.shape(grain[0]), Color(WOOD_DARK, grain[1]), 0.35)
	var dealer_side := PackedVector2Array([Vector2(-400, -400), Vector2(400, -400),
		Vector2(400, CrapsTable.FELT_TOP + 1.5), Vector2(-400, CrapsTable.FELT_TOP + 1.5)])
	var ledge := CrapsTable.BAY_HALF - r   # the ledge across the bay's floor is polished wood, like the rack cut into it
	dealer_side = Geometry2D.clip_polygons(dealer_side, PackedVector2Array([Vector2(-ledge, CrapsTable.FELT_TOP - r),
		Vector2(ledge, CrapsTable.FELT_TOP - r), Vector2(ledge, 0), Vector2(-ledge, 0)]))[0]
	for part in Geometry2D.intersect_polygons(rail, dealer_side):
		draw_colored_polygon(part, WOOD_PAD)
	_loop(_shifted(CrapsTable.shape(r * 0.68), Vector2(0, -1.2)), WOOD_SHINE, 1.1)
	# The felt: crimson, darker towards the rail, with a woven grain; the brass bead.
	var felt := CrapsTable.shape(0.0, true, 12)
	var uv := PackedVector2Array()
	var grain_uv := PackedVector2Array()
	for p in felt:
		uv.append((p - Vector2(0, -60)) / 460.0 + Vector2(0.5, 0.5))
		grain_uv.append(p / 40.0)
	draw_colored_polygon(felt, Color.WHITE, uv, _felt_gradient())
	draw_colored_polygon(felt, Color(1, 1, 1, 0.25), grain_uv, GRAIN)
	_loop(CrapsTable.shape(-0.9), Color(0, 0, 0, 0.3), 1.4)
	_loop(CrapsTable.shape(-0.3), BRASS, 0.6)
	# The rubber pyramids lining both end walls (the dice have to hit them), following the
	# rail round the corners to where it turns level: a lattice of ridges, seen as two zigzags.
	var rw := CrapsTable.RUBBER_W
	for h in [1, -1]:
		var band := CrapsTable.rubber_path(h, 0.0)
		var inner := CrapsTable.rubber_path(h, rw)
		inner.reverse()
		band.append_array(inner)
		draw_colored_polygon(band, Color("1b1413"))
		var zig := [PackedVector2Array(), PackedVector2Array()]
		var marks := _along(CrapsTable.rubber_path(h, rw / 2), rw * 0.75)
		for k in marks.size():
			var across: Vector2 = marks[k][1].orthogonal() * (rw / 2)
			zig[0].append(marks[k][0] + across * (1 if k % 2 == 0 else -1))
			zig[1].append(marks[k][0] - across * (1 if k % 2 == 0 else -1))
		for z in zig:
			draw_polyline(z, Color(1, 1, 1, 0.18), 0.35)
	# The chip rail: a groove sunk into the players' rail, from beside the stickman round the
	# corners and up the ends. Its inner wall shades it; its outer lip catches the light.
	var hw := CrapsTable.GROOVE_W / 2
	for h in [1, -1]:
		var mid := CrapsTable.groove_path(h, CrapsTable.GROOVE_OUT)
		for part in Geometry2D.offset_polyline(mid, hw + 0.4, Geometry2D.JOIN_ROUND, Geometry2D.END_ROUND):
			draw_colored_polygon(part, Color(WOOD_DARK, 0.9))
		for part in Geometry2D.offset_polyline(mid, hw, Geometry2D.JOIN_ROUND, Geometry2D.END_ROUND):
			draw_colored_polygon(part, RECESS)
		draw_polyline(CrapsTable.groove_path(h, CrapsTable.GROOVE_OUT - hw + 0.5), Color(0, 0, 0, 0.6), 0.6, true)
		draw_polyline(CrapsTable.groove_path(h, CrapsTable.GROOVE_OUT + hw + 0.3), Color(WOOD_SHINE, 0.25), 0.4, true)
	_tray_well(t.tray_rect())   # the rack, cut into the ledge: no frame of its own
	_layout(t)
	draw_set_transform(-position)


func _layout(t: CrapsTable) -> void:
	# Fills first: anything hovered lights up under the chips.
	var hv := t.hover
	if not hv.is_empty():
		if int(hv.h) == 0:
			draw_rect(CrapsTable.PROPS[hv.id], HILITE)
		elif hv.id == "pass":
			draw_colored_polygon(CrapsTable.pass_line(), HILITE)
		elif hv.id == "pass_odds":
			draw_colored_polygon(CrapsTable.odds_strip(), Color(HILITE, 0.28))
		elif CrapsTable.zones(int(hv.h)).has(hv.id):   # (odds on your come bet: its ghost chip shows it)
			draw_colored_polygon(CrapsTable.zone_poly(hv.id, int(hv.h)), HILITE)
	# Then the printed lines: each end's boxes, the proposition box, and the Pass Line
	# round the front of the table joining them up.
	for h in [1, -1]:
		for id in CrapsTable.zones(h):
			_loop(CrapsTable.zone_poly(id, h), LINE, 0.7)
	for id in CrapsTable.PROPS:
		draw_rect(CrapsTable.PROPS[id], LINE, false, 0.7)
	draw_rect(CrapsTable.PROP_BOX, LINE, false, 0.9)
	_loop(CrapsTable.pass_line(), LINE, 0.7)
	# Lettering last.
	for h in [1, -1]:
		var z := CrapsTable.zones(h)
		var dc: Vector2 = z.dont_come.get_center()
		_textf("DON'T", dc + Vector2(0, -6.5), 3.3, CREAM, CINZEL)
		_textf("COME", dc + Vector2(0, -2.5), 3.3, CREAM, CINZEL)
		_textf("BAR", dc + Vector2(0, 3), 2.6, CREAM, CINZEL)
		_mini_die(dc + Vector2(-3.2, 7.5), 6, 5.0)
		_mini_die(dc + Vector2(3.2, 7.5), 6, 5.0)
		for n in CrapsTable.NUMS:
			var label: String = {6: "SIX", 9: "NINE"}.get(n, str(n))
			_textf(label, z["place_%d" % n].get_center() + Vector2(0, 0.5), 5.2 if label.length() > 2 else 8.2,
				GOLD if n in [6, 8] else CREAM, CINZEL)
			_textf("LAY", z["lay_%d" % n].get_center() + Vector2(0, 0.3), 2.6, CREAM, CINZEL)
			_textf("BUY", z["buy_%d" % n].get_center() + Vector2(0, 0.3), 2.6, CREAM, CINZEL)
		_textf("COME", z.come.get_center() + Vector2(0, 0.5), 13.0, RED, CINZEL)
		var fi: Rect2 = z.field
		var fy := fi.get_center().y
		_textf("FIELD", Vector2(fi.get_center().x, fy + 5.5), 6.5, GOLD, CINZEL)
		var fnums := ["2", "3", "4", "9", "10", "11", "12"]
		var step := (fi.size.x - 12) / 6
		for i in fnums.size():
			var at := Vector2(fi.position.x + 6 + i * step, fy - 4)
			if fnums[i] in ["2", "12"]:
				draw_arc(at, 3.6, 0, TAU, 28, GOLD, 0.5, true)
			_textf(fnums[i], at + Vector2(0, 0.2), 4.4, CREAM, CINZEL)
		_textf("PAYS DOUBLE", Vector2(fi.position.x + 13, fi.end.y - 2.6), 1.8, GOLD, CINZEL)
		_textf("PAYS TRIPLE", Vector2(fi.end.x - 13, fi.end.y - 2.6), 1.8, GOLD, CINZEL)
		var dp: Vector2 = z.dont_pass.get_center()
		_textf("DON'T PASS BAR", dp + Vector2(-6, 0.3), 3.8, CREAM, CINZEL)
		_mini_die(dp + Vector2(24, 0), 6, 5.0)
		_mini_die(dp + Vector2(30.5, 0), 6, 5.0)
		_textf("6", z.big6.get_center() + Vector2(-3 * h, -1), 8.0, RED, CINZEL)
		_textf("8", z.big8.get_center() + Vector2(3 * h, 1), 8.0, RED, CINZEL)
		_textf("PASS LINE", Vector2(CrapsTable.mx(110, h), -19.7), 4.6, CREAM, CINZEL)   # (between two players' bets)
		_textf("PASS LINE", Vector2(CrapsTable.mx(177, h), -61), 4.6, CREAM, CINZEL, h * PI / 2)
	_textf("PASS LINE", Vector2(0, -19.7), 4.6, CREAM, CINZEL)
	var pc := func(id: String) -> Vector2: return CrapsTable.PROPS[id].get_center()
	_textf("SEVEN  ·  4 TO 1", pc.call("any7") + Vector2(0, 0.3), 3.6, RED, CINZEL)
	for e in [["hard6", 3, 3, "9 TO 1"], ["hard10", 5, 5, "7 TO 1"], ["hard8", 4, 4, "9 TO 1"], ["hard4", 2, 2, "7 TO 1"],
			["two", 1, 1, "30 TO 1"], ["twelve", 6, 6, "30 TO 1"], ["three", 1, 2, "15 TO 1"], ["eleven", 5, 6, "15 TO 1"]]:
		var box: Rect2 = CrapsTable.PROPS[e[0]]
		var c := box.get_center()
		var s := minf(7.0, box.size.y * 0.5)   # the dice and the odds, sized to the row
		_mini_die(c + Vector2(-s * 0.6, -box.size.y * 0.16), e[1], s)
		_mini_die(c + Vector2(s * 0.6, -box.size.y * 0.16), e[2], s)
		_textf(e[3], c + Vector2(0, box.size.y * 0.33), minf(2.5, box.size.y * 0.2), CREAM, CINZEL)
	_textf("HORN", pc.call("horn") + Vector2(0, 0.3), 4.0, GOLD, CINZEL)
	var ce: Vector2 = pc.call("ce")
	for side in [-1, 1]:
		draw_arc(ce + Vector2(5 * side, 0), 3.6, 0, TAU, 28, CREAM, 0.5, true)
	_textf("C", ce + Vector2(-5, 0.3), 3.8, CREAM, CINZEL)
	_textf("E", ce + Vector2(5, 0.3), 3.8, CREAM, CINZEL)
	_textf("ANY CRAPS  ·  7 TO 1", pc.call("any_craps") + Vector2(0, 0.3), 3.6, RED, CINZEL)


## Points every `step` along a path, each with the path's direction there: [[point, direction], ...].
static func _along(path: PackedVector2Array, step: float) -> Array:
	var out := []
	var d := 0.0   # how far into the current segment the next point is
	for i in path.size() - 1:
		var seg := path[i].distance_to(path[i + 1])
		if seg <= 0.0:
			continue
		var dir := (path[i + 1] - path[i]) / seg
		while d <= seg:
			out.append([path[i] + dir * d, dir])
			d += step
		d -= seg
	return out


## A small printed die (on the Don't bars and in the prop box).
func _mini_die(at: Vector2, n: int, s: float) -> void:
	draw_colored_polygon(_shifted(_rounded(Rect2(-s / 2, -s / 2, s, s), s * 0.18), at), DIE_FACE)
	for pip in PIPS[n]:
		var pts := PackedVector2Array()
		for k in 10:
			pts.append(at + pip * s * 0.27 + Vector2.from_angle(k * TAU / 10) * s * 0.09)
		draw_colored_polygon(pts, Color("5c0a12"))


## Text centred on a point at any size and angle (fonts take whole sizes; the rest is scaled).
func _textf(s: String, at: Vector2, size: float, colour: Color, font: Font, angle := 0.0) -> void:
	var px := maxi(1, ceili(size))
	var k := size / px
	var w := font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x
	draw_set_transform(-position + at, angle, Vector2(k, k))
	draw_string(font, Vector2(-w / 2, px * 0.35), s, HORIZONTAL_ALIGNMENT_LEFT, -1, px, colour)
	draw_set_transform(-position)
