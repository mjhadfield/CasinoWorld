@tool
extends StyledFelt
## The craps table in its table style (TableStyle "craps", designed on the admin page's Tables tab): the
## style's rail (leather on the dealers' side, all round or none) and felt, cut to the craps table's shape
## (CrapsTable.shape), the rubber pyramids lining both end walls and round their corners, the chip rack in the
## boxman's bay, the groove of the players' chip rail, and the double-ended layout, printed in the style's ink,
## accent and red: at each end the point boxes (each split Lay / Place / Buy), Don't Come, Come, the Field,
## Big 6/8, Don't Pass; in the middle, the proposition box, its rows level with the ends' lines; and the Pass
## Line (with the odds behind it) running the length of the front, through the middle, and curving up both
## ends. What a hovered bet covers lights up under the chips.

const HILITE := Color(0.94, 0.83, 0.55, 0.55)
const PIPS := CrapsDice.PIPS

var _ink: Color
var _rule: Color
var _gold: Color
var _red: Color
var _die_face: Color
var _pip: Color
var _font: Font


func _grown(by: float) -> PackedVector2Array:
	return CrapsTable.shape(by)


func _rail_w() -> float:
	return CrapsTable.RAIL_W


func _middle() -> Vector2:
	return Vector2(0, -60)


func _reach() -> float:
	return 460.0


func _straight(_p: Vector2, _half := 70.0) -> bool:
	return false


## "dealer": round the corners and down the ends to just above the chip rail's groove (the felt hides it across
## the middle), and all the way round the bay and across the ledge.
func _pad_area(arm: String) -> PackedVector2Array:
	if arm == "all":
		return PackedVector2Array()
	var pad_to := CrapsTable.GROOVE_TO - CrapsTable.GROOVE_W / 2 - 1.0
	var dealer_side := PackedVector2Array([Vector2(-400, -400), Vector2(400, -400),
		Vector2(400, pad_to), Vector2(-400, pad_to)])
	var bay := CrapsTable.BAY_HALF + CrapsTable.BAY_CORNER
	return Geometry2D.merge_polygons(dealer_side, PackedVector2Array([Vector2(-bay, -400), Vector2(bay, -400),
		Vector2(bay, CrapsTable.BAY_FLOOR + 1.5), Vector2(-bay, CrapsTable.BAY_FLOOR + 1.5)]))[0]


func paint() -> void:
	var t := _table() as CrapsTable
	if t == null:
		return
	d = t.style()
	_ink = ink()
	_rule = Color(_ink, 0.9)
	_gold = TableStyle.colour(d, "print.accent")
	_red = TableStyle.colour(d, "print.red")
	_die_face = Color(_ink, 0.92)
	_pip = TableStyle.colour(d, "felt.colour").darkened(0.37)
	_font = TableStyle.font(d)
	draw_set_transform(-position)
	var r := CrapsTable.RAIL_W
	# Its shadow on the carpet, the rail, the felt and the bead.
	draw_colored_polygon(_shifted(CrapsTable.shape(r + 4.0), _lit(Vector2(0, 3))), Color(0, 0, 0, 0.16))
	draw_colored_polygon(_shifted(CrapsTable.shape(r + 1.5), _lit(Vector2(0, 2))), Color(0, 0, 0, 0.3))
	var felt := CrapsTable.shape(0.0, true, 12)
	_rail(felt, false)
	_felt(felt)
	_bead(felt)
	# The rubber pyramids lining both end walls (the dice have to hit them), following the
	# rail round the corners to where it turns level: a lattice of ridges, seen as two zigzags.
	var rubber := TableStyle.colour(d, "rubber")
	var ridge := Color(1, 1, 1, 0.18 if rubber.get_luminance() < 0.3 else 0.3)
	var rw := CrapsTable.RUBBER_W
	for h in [1, -1]:
		var band := CrapsTable.rubber_path(h, 0.0)
		var inner := CrapsTable.rubber_path(h, rw)
		inner.reverse()
		band.append_array(inner)
		draw_colored_polygon(band, rubber)
		var zig := [PackedVector2Array(), PackedVector2Array()]
		var marks := _along(CrapsTable.rubber_path(h, rw / 2), rw * 0.75)
		for k in marks.size():
			var across: Vector2 = marks[k][1].orthogonal() * (rw / 2)
			zig[0].append(marks[k][0] + across * (1 if k % 2 == 0 else -1))
			zig[1].append(marks[k][0] - across * (1 if k % 2 == 0 else -1))
		for z in zig:
			draw_polyline(z, ridge, 0.35)
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
	# The rack, cut into the ledge: no frame of its own, just the bead round its edge.
	float_tray(t.tray_rect(), felt, str(d.rack), false)
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
			_loop(CrapsTable.zone_poly(id, h), _rule, 0.7)
	for id in CrapsTable.PROPS:
		draw_rect(CrapsTable.PROPS[id], _rule, false, 0.7)
	draw_rect(CrapsTable.PROP_BOX, _rule, false, 0.9)
	_loop(CrapsTable.pass_line(), _rule, 0.7)
	# Lettering last.
	for h in [1, -1]:
		var z := CrapsTable.zones(h)
		var dc: Vector2 = z.dont_come.get_center()
		_textf("DON'T", dc + Vector2(0, -6.5), 3.3, _ink, _font)
		_textf("COME", dc + Vector2(0, -2.5), 3.3, _ink, _font)
		_textf("BAR", dc + Vector2(0, 3), 2.6, _ink, _font)
		_mini_die(dc + Vector2(-3.2, 7.5), 6, 5.0)
		_mini_die(dc + Vector2(3.2, 7.5), 6, 5.0)
		for n in CrapsTable.NUMS:
			var label: String = {6: "SIX", 9: "NINE"}.get(n, str(n))
			_textf(label, z["place_%d" % n].get_center() + Vector2(0, 0.5), 5.2 if label.length() > 2 else 8.2,
				_gold if n in [6, 8] else _ink, _font)
			_textf("LAY", z["lay_%d" % n].get_center() + Vector2(0, 0.3), 2.6, _ink, _font)
			_textf("BUY", z["buy_%d" % n].get_center() + Vector2(0, 0.3), 2.6, _ink, _font)
		_textf("COME", z.come.get_center() + Vector2(0, 0.5), 13.0, _red, _font)
		var fi: Rect2 = z.field
		var fy := fi.get_center().y
		_textf("FIELD", Vector2(fi.get_center().x, fy + 5.5), 6.5, _gold, _font)
		var fnums := ["2", "3", "4", "9", "10", "11", "12"]
		var step := (fi.size.x - 12) / 6
		for i in fnums.size():
			var at := Vector2(fi.position.x + 6 + i * step, fy - 4)
			if fnums[i] in ["2", "12"]:
				draw_arc(at, 3.6, 0, TAU, 28, _gold, 0.5, true)
			_textf(fnums[i], at + Vector2(0, 0.2), 4.4, _ink, _font)
		_textf("PAYS DOUBLE", Vector2(fi.position.x + 13, fi.end.y - 2.6), 1.8, _gold, _font)
		_textf("PAYS TRIPLE", Vector2(fi.end.x - 13, fi.end.y - 2.6), 1.8, _gold, _font)
		var dp: Vector2 = z.dont_pass.get_center()
		_textf("DON'T PASS BAR", dp + Vector2(-6, 0.3), 3.8, _ink, _font)
		_mini_die(dp + Vector2(24, 0), 6, 5.0)
		_mini_die(dp + Vector2(30.5, 0), 6, 5.0)
		_textf("6", z.big6.get_center() + Vector2(-3 * h, -1), 8.0, _red, _font)
		_textf("8", z.big8.get_center() + Vector2(3 * h, 1), 8.0, _red, _font)
		_textf("PASS LINE", Vector2(CrapsTable.mx(110, h), -19.7), 4.6, _ink, _font)   # (between two players' bets)
		_textf("PASS LINE", Vector2(CrapsTable.mx(177, h), -61), 4.6, _ink, _font, h * PI / 2)
	_textf("PASS LINE", Vector2(0, -19.7), 4.6, _ink, _font)
	var pc := func(id: String) -> Vector2: return CrapsTable.PROPS[id].get_center()
	_textf("SEVEN  ·  4 TO 1", pc.call("any7") + Vector2(0, 0.3), 3.6, _red, _font)
	for e in [["hard6", 3, 3, "9 TO 1"], ["hard10", 5, 5, "7 TO 1"], ["hard8", 4, 4, "9 TO 1"], ["hard4", 2, 2, "7 TO 1"],
			["two", 1, 1, "30 TO 1"], ["twelve", 6, 6, "30 TO 1"], ["three", 1, 2, "15 TO 1"], ["eleven", 5, 6, "15 TO 1"]]:
		var box: Rect2 = CrapsTable.PROPS[e[0]]
		var c := box.get_center()
		var s := minf(7.0, box.size.y * 0.5)   # the dice and the odds, sized to the row
		_mini_die(c + Vector2(-s * 0.6, -box.size.y * 0.16), e[1], s)
		_mini_die(c + Vector2(s * 0.6, -box.size.y * 0.16), e[2], s)
		_textf(e[3], c + Vector2(0, box.size.y * 0.33), minf(2.5, box.size.y * 0.2), _ink, _font)
	_textf("HORN", pc.call("horn") + Vector2(0, 0.3), 4.0, _gold, _font)
	var ce: Vector2 = pc.call("ce")
	for side in [-1, 1]:
		draw_arc(ce + Vector2(5 * side, 0), 3.6, 0, TAU, 28, _ink, 0.5, true)
	_textf("C", ce + Vector2(-5, 0.3), 3.8, _ink, _font)
	_textf("E", ce + Vector2(5, 0.3), 3.8, _ink, _font)
	_textf("ANY CRAPS  ·  7 TO 1", pc.call("any_craps") + Vector2(0, 0.3), 3.6, _red, _font)


## Points every `step` along a path, each with the path's direction there: [[point, direction], ...].
static func _along(path: PackedVector2Array, step: float) -> Array:
	var out := []
	var into := 0.0   # how far into the current segment the next point is
	for i in path.size() - 1:
		var seg := path[i].distance_to(path[i + 1])
		if seg <= 0.0:
			continue
		var dir := (path[i + 1] - path[i]) / seg
		while into <= seg:
			out.append([path[i] + dir * into, dir])
			into += step
		into -= seg
	return out


## A small printed die (on the Don't bars and in the prop box).
func _mini_die(at: Vector2, n: int, s: float) -> void:
	draw_colored_polygon(_shifted(_rounded(Rect2(-s / 2, -s / 2, s, s), s * 0.18), at), _die_face)
	for pip in PIPS[n]:
		var pts := PackedVector2Array()
		for k in 10:
			pts.append(at + pip * s * 0.27 + Vector2.from_angle(k * TAU / 10) * s * 0.09)
		draw_colored_polygon(pts, _pip)


## Text centred on a point at any size and angle (fonts take whole sizes; the rest is scaled).
func _textf(s: String, at: Vector2, size: float, colour: Color, font: Font, angle := 0.0) -> void:
	var px := maxi(1, ceili(size))
	var k := size / px
	var w := font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x
	draw_set_transform(-position + at, angle, Vector2(k, k))
	draw_string(font, Vector2(-w / 2, px * 0.35), s, HORIZONTAL_ALIGNMENT_LEFT, -1, px, colour)
	draw_set_transform(-position)
