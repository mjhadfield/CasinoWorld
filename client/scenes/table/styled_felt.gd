@tool
class_name StyledFelt
extends TableFelt
## A card table drawn in its table style (TableStyle; designed on the admin page's Tables tab, whose renderer
## this matches): the rail (wood, leather or both, with a metal bead where it meets the felt), the felt (its
## colour, darker towards the rail, velvet or woven grain), a border line, the chip tray (a well cut into a
## dealer's ledge, or sunk in where today's tray was) and the game's printing, every spot in the style's
## artwork. A game's felt (tcp_felt.gd and the rest) extends this and lays its spots out in _draw_layout()
## with spot() and its shorthands, at exactly the places the game puts its chips and cards.
##
## Roulette and Craps aren't drawn with this: they keep TableFelt's Mahogany & Brass.

## The dealer's ledge, where the rail sweeps across the bay to hold the chip tray: half its width (the tray's),
## the fillets where it leaves the dealer's edge, the radius of its front corners. Its front is the tray's.
const LEDGE_HW := 38.0
const LEDGE_FILLET := 9.0
const LEDGE_CORNER := 4.0
const ARMREST_FROM := -94.0   # "Leather armrest": the padding runs round the players' side from here down
const SHEEN := Color(1.0, 0.886, 0.745)

var d: Dictionary   # the design being painted
var _gradients := {}


func _init() -> void:
	texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS


func paint() -> void:
	var t := _table()
	if t == null:
		return
	d = t.style()
	draw_set_transform(-position)  # draw in table coordinates
	var ledge: bool = d.tray.mode == "ledge"
	var felt := felt_outline(ledge)
	# Its shadow on the carpet.
	draw_colored_polygon(_shifted(CasinoTable.grown(CasinoTable.RAIL + 4.0), Vector2(0, 3)), Color(0, 0, 0, 0.16))
	draw_colored_polygon(_shifted(CasinoTable.grown(CasinoTable.RAIL + 1.5), Vector2(0, 2)), Color(0, 0, 0, 0.3))
	_rail(felt, ledge)
	_felt(felt)
	_border(ledge)
	_bead(felt)
	_tray(t, ledge)
	_draw_layout(t)
	draw_set_transform(-position)


# ------------------------------------------------------------------ the shape
## The ledge's edge against the felt, from the dealer's edge on the left round to it on the right, grown `grow` into the felt.
static func tongue(grow: float) -> PackedVector2Array:
	var hw := LEDGE_HW + grow
	var fy := CasinoTable.bay_floor() + 7.0 + grow   # the chip tray's front edge (CasinoTable.tray_rect)
	var f := maxf(1.0, LEDGE_FILLET - grow)
	var r := LEDGE_CORNER + grow
	var yl := CasinoTable._edge_y(-(hw + f))
	var p := PackedVector2Array()
	_arc_pts(p, Vector2(-(hw + f), yl + f), f, -90, 0, 10)
	_arc_pts(p, Vector2(-hw + r, fy - r), r, 180, 90, 6)
	_arc_pts(p, Vector2(hw - r, fy - r), r, 90, 0, 6)
	_arc_pts(p, Vector2(hw + f, yl + f), f, 180, 270, 10)
	return p


## The felt's outline: the table's own, or with the ledge in place of the felt behind the dealer's cards.
static func felt_outline(ledge: bool) -> PackedVector2Array:
	var o := CasinoTable.outline()
	if not ledge:
		return o
	var lim := LEDGE_HW + LEDGE_FILLET + 0.5
	var first := -1
	var last := -1
	for i in o.size():
		if o[i].y < -110 and absf(o[i].x) < lim:
			if first < 0:
				first = i
			last = i
	var out := o.slice(0, first)
	out.append_array(tongue(0.0))
	out.append_array(o.slice(last + 1))
	return out


static func _arc_pts(pts: PackedVector2Array, centre: Vector2, r: float, from_deg: float, to_deg: float, steps: int) -> void:
	for i in steps + 1:
		var a := deg_to_rad(lerpf(from_deg, to_deg, float(i) / steps))
		pts.append(centre + Vector2(cos(a), sin(a)) * r)


static func _uv(pts: PackedVector2Array, tile: float) -> PackedVector2Array:
	var uv := PackedVector2Array()
	for p in pts:
		uv.append(p / tile)
	return uv


# ------------------------------------------------------------------ the rail
func _rail(felt: PackedVector2Array, ledge: bool) -> void:
	var outer := CasinoTable.grown(CasinoTable.RAIL + 0.5)
	var arm: String = d.rail.armrest
	if arm != "all":
		_wood(outer)
	if arm != "none":
		_leather(outer, arm == "player", ledge and arm == "all")
	# The rounded profile: a dark outer edge, a lit crown, a shadow where it meets the felt.
	_loop(outer, Color(0, 0, 0, 0.6), 1.3)
	_loop(_shifted(CasinoTable.grown(4.0), Vector2(0, -1.0)), Color(SHEEN, 0.10), 2.4)
	_loop(_shifted(CasinoTable.grown(4.0), Vector2(0, -1.2)), Color(1.0, 0.9, 0.784, 0.2), 0.6)
	_loop(felt, Color(0, 0, 0, 0.5), 1.8)
	if ledge:
		draw_polyline(tongue(-2.4), Color(SHEEN, 0.12), 1.4, true)
	var b := TableStyle.bead(d)
	if arm == "player" and not b.is_empty():   # end caps where the padding stops
		for sx in [-1.0, 1.0]:
			draw_line(Vector2(sx * 155.5, ARMREST_FROM), Vector2(sx * 164.0, ARMREST_FROM), b[0], 0.7)


## Polished wood: one fill running left to right (the dealer's edge and the ledge), and strips laid round the
## curve over it, so the grain follows the rail.
func _wood(outer: PackedVector2Array) -> void:
	var key: String = d.rail.wood
	var tex: Texture2D = TableStyle.WOODS[key]
	var tile: float = TableStyle.WOOD_TILE[key]
	draw_colored_polygon(outer, Color("2a160b"))
	draw_colored_polygon(outer, Color.WHITE, _uv(outer, tile), tex)
	var c := CasinoTable.grown(3.5)   # the rail's centreline
	var s := 0.0
	for i in c.size():
		var p := c[i]
		var q := c[(i + 1) % c.size()]
		var seg := q - p
		var length := seg.length()
		if length < 1e-6:
			continue
		if not (absf(p.x) < 70.0 and p.y < -118.0):
			var along := seg / length
			var n := Vector2(-along.y, along.x)
			if n.dot(p - Vector2(0, -70)) < 0.0:
				n = -n   # (outwards)
			var a := p - along * 0.35
			var b := q + along * 0.35
			var quad := PackedVector2Array([a + n * 4.0, b + n * 4.0, b - n * 3.6, a - n * 3.6])
			var u0 := (s - 0.35) / tile
			var u1 := (s + length + 0.35) / tile
			var uv := PackedVector2Array([Vector2(u0, 4.0 / tile), Vector2(u1, 4.0 / tile), Vector2(u1, -3.6 / tile), Vector2(u0, -3.6 / tile)])
			draw_colored_polygon(quad, Color.WHITE, uv, tex)
		s += length
	if key == "ebony":   # lacquered: a gloss along the crown
		_loop(_shifted(CasinoTable.grown(4.0), Vector2(0, -1.4)), Color(1, 1, 1, 0.10), 1.6)


## Padded leather, all round or just the players' side: lit along its crown, stitched near both edges.
func _leather(outer: PackedVector2Array, players_side: bool, ledge_crest: bool) -> void:
	var col := TableStyle.colour(d, "rail.leather")
	var area := PackedVector2Array([Vector2(-220, ARMREST_FROM), Vector2(220, ARMREST_FROM), Vector2(220, 80), Vector2(-220, 80)])
	var parts: Array = Geometry2D.intersect_polygons(outer, area) if players_side else [outer]
	for part in parts:
		draw_colored_polygon(part, col)
		draw_colored_polygon(part, Color.WHITE, _uv(part, 22.0), TableStyle.LEATHER)
	var hi := Color(1, 1, 1, 0.18 if col.get_luminance() > 0.3 else 0.09)
	_band(_shifted(CasinoTable.grown(4.0), Vector2(0, -0.6)), hi, 3.2, area if players_side else PackedVector2Array())
	_band(_shifted(CasinoTable.grown(4.0), Vector2(0, -0.9)), hi, 1.2, area if players_side else PackedVector2Array())
	if ledge_crest:
		draw_polyline(tongue(-3.0), hi, 2.4, true)
	var thread := Color(col.lightened(0.35), 0.55)
	for edge in [CasinoTable.grown(1.2), CasinoTable.grown(5.9)]:
		for i in edge.size():
			var p: Vector2 = edge[i]
			var q: Vector2 = edge[(i + 1) % edge.size()]
			if (players_side and p.y < ARMREST_FROM) or (absf(p.x) < 60.0 and p.y < -118.0):
				continue   # (no stitching across the ledge, or above the armrest)
			draw_dashed_line(p, q, thread, 0.18, 0.8)


## A closed line, or just its pieces inside `within` when that's given.
func _band(pts: PackedVector2Array, colour: Color, width: float, within: PackedVector2Array) -> void:
	if within.is_empty():
		_loop(pts, colour, width)
		return
	var closed := pts.duplicate()
	closed.append(pts[0])
	for piece in Geometry2D.intersect_polyline_with_polygon(closed, within):
		draw_polyline(piece, colour, width, true)


# ------------------------------------------------------------------ the felt
func _felt(felt: PackedVector2Array) -> void:
	var uv := PackedVector2Array()
	for p in felt:
		uv.append((p - Vector2(0, -70)) / 400.0 + Vector2(0.5, 0.5))
	draw_colored_polygon(felt, Color.WHITE, uv, _gradient(TableStyle.colour(d, "felt.colour"), float(d.felt.vignette)))
	match str(d.felt.texture):
		"velvet":
			draw_colored_polygon(felt, Color(1, 1, 1, 0.85), _uv(felt, 70.0), TableStyle.VELVET)
		"weave":
			draw_colored_polygon(felt, Color(1, 1, 1, 0.7), _uv(felt, 16.0), TableStyle.WEAVE)
	# Its shadow under the rail.
	for shade in [[-1.5, 0.22, 3.0], [-0.65, 0.35, 1.3]]:
		var inner := Geometry2D.offset_polygon(felt, shade[0])
		if not inner.is_empty():
			_loop(inner[0], Color(0, 0, 0, shade[1]), shade[2])


## The felt gets lighter towards the middle and darker towards the rail, by the design's vignette.
func _gradient(colour: Color, vignette: float) -> GradientTexture2D:
	var key := "%s/%.2f" % [colour.to_html(), vignette]
	if not _gradients.has(key):
		var g := Gradient.new()
		g.offsets = PackedFloat32Array([0.0, 0.35, 1.0])
		g.colors = PackedColorArray([colour.lightened(0.07), colour, colour.darkened(0.25 + 0.45 * vignette)])
		var tex := GradientTexture2D.new()
		tex.gradient = g
		tex.fill = GradientTexture2D.FILL_RADIAL
		tex.fill_from = Vector2(0.5, 0.5)
		tex.fill_to = Vector2(1.0, 0.5)
		tex.width = 256
		tex.height = 256
		_gradients[key] = tex
	return _gradients[key]


## The border line inside the rail. With a ledge it runs into the ledge rather than round it.
func _border(ledge: bool) -> void:
	var b: String = d.border
	if b == "none":
		return
	var ink := TableStyle.colour(d, "print.ink")
	var acc := TableStyle.colour(d, "print.accent")
	var cut := PackedVector2Array()
	if ledge:
		cut = tongue(3.0)
		cut.append(Vector2(cut[cut.size() - 1].x, -170))
		cut.append(Vector2(cut[0].x, -170))
	var g := func(by: float) -> PackedVector2Array: return CasinoTable.grown(by)
	match b:
		"pinstripe":
			_line(g.call(-5.0), Color(ink, 0.7), 0.5, cut)
		"gilt":
			_line(_shifted(g.call(-5.0), Vector2(0, 0.25)), Color(0, 0, 0, 0.4), 0.8, cut)
			_line(g.call(-5.0), acc.lightened(0.15), 0.65, cut)
			_line(_shifted(g.call(-5.0), Vector2(0, -0.15)), Color(1, 0.96, 0.82, 0.5), 0.2, cut)
		"double":
			_line(g.call(-4.0), Color(acc, 0.85), 0.55, cut)
			_line(g.call(-6.0), Color(acc, 0.6), 0.3, cut)
		"deco":
			_line(g.call(-3.5), Color(acc, 0.9), 0.6, cut)
			_line(g.call(-6.0), Color(acc, 0.65), 0.3, cut)
			var p: PackedVector2Array = g.call(-4.75)
			var s := 0.0
			for i in p.size():
				var a := p[i]
				var q := p[(i + 1) % p.size()]
				var length := a.distance_to(q)
				if floorf((s + length) / 34.0) > floorf(s / 34.0):
					var m := (a + q) / 2
					if cut.is_empty() or not Geometry2D.is_point_in_polygon(m, cut):
						draw_colored_polygon(PackedVector2Array([m + Vector2(0, -1.3), m + Vector2(1.0, 0), m + Vector2(0, 1.3), m + Vector2(-1.0, 0)]), Color(acc, 0.95))
				s += length
		"led":
			var led := TableStyle.colour(d, "led")
			for wa in [[5.0, 0.06], [3.0, 0.1], [1.6, 0.2], [0.6, 0.7]]:
				_line(g.call(-2.0), Color(led, wa[1]), wa[0], cut)
			_line(g.call(-2.0), Color(1, 1, 1, 0.55), 0.2, cut)


## A closed line, less any of it inside `cut`.
func _line(pts: PackedVector2Array, colour: Color, width: float, cut: PackedVector2Array) -> void:
	if cut.is_empty():
		_loop(pts, colour, width)
		return
	var closed := pts.duplicate()
	closed.append(pts[0])
	for piece in Geometry2D.clip_polyline_with_polygon(closed, cut):
		draw_polyline(piece, colour, width, true)


func _bead(felt: PackedVector2Array) -> void:
	var b := TableStyle.bead(d)
	if b.is_empty():
		return
	_loop(felt, b[0], 0.75)
	_loop(_shifted(felt, Vector2(0, -0.18)), Color(b[1], 0.55), 0.22)


# ------------------------------------------------------------------ the chip tray
func _tray(t: CasinoTable, ledge: bool) -> void:
	var fin: String = d.tray.finish
	var b := TableStyle.bead(d)
	if b.is_empty():
		b = [Color("6d757c"), Color("cfd6dc")]
	if ledge:   # a well cut into the ledge
		var well := Rect2(-35.5, -132.2, 71.0, 7.9)
		draw_colored_polygon(_rounded(well.grow(0.6), 2.0), Color(0, 0, 0, 0.55))
		_channels(well, fin)
		draw_line(Vector2(well.position.x + 1.4, well.end.y + 0.35), Vector2(well.end.x - 1.4, well.end.y + 0.35), Color(SHEEN, 0.28), 0.35)
		if fin == "steel":
			_loop(_rounded(well.grow(0.4), 1.8), Color("c3cad1"), 0.45)
		elif fin == "lid":
			_lid(well.grow(0.3))
	else:   # sunk in where the tray has always been, with a metal lip
		var r := t.tray_rect()
		draw_colored_polygon(_rounded(r.grow(0.5), 2.8), Color(0, 0, 0, 0.6))
		var lip := _rounded(r, 2.4)
		var shades := PackedColorArray()
		for p in lip:   # lit along the top, shadowed along the bottom
			var f := inverse_lerp(r.position.y, r.end.y, p.y)
			shades.append(b[0].lightened(0.35 * (1.0 - f * 2.5)) if f < 0.4 else b[0].darkened(0.35 * (f - 0.4) / 0.6))
		draw_polygon(lip, shades)
		_channels(r.grow(-1.3), "steel" if fin == "steel" else "wood")
		if fin == "lid":
			_lid(r.grow(-0.8))


## The tray's well: ten lined channels with the chips lying in them on their edges, some full, some part-full,
## some empty; the back wall's shadow across the top.
func _channels(well: Rect2, fin: String) -> void:
	var lining := Color("3b4147") if fin == "steel" else Color("130806")
	var ridge := Color("7d868f") if fin == "steel" else Color("2a160b")
	draw_colored_polygon(_rounded(well, 1.4), ridge)
	var cw := well.size.x / TRAY_DENOMS.size()
	for i in TRAY_DENOMS.size():
		var ch := Rect2(well.position.x + i * cw + 0.3, well.position.y, cw - 0.6, well.size.y)
		draw_colored_polygon(_rounded(ch, 1.0), lining)
		var n := int(round(TRAY_FILL[i] * floorf((ch.size.y - 0.6) / CHIP_EDGE)))
		for k in n:
			ChipFace.edge(self, Rect2(ch.position.x + 0.35, ch.end.y - 0.3 - (k + 1) * CHIP_EDGE, ch.size.x - 0.7, CHIP_EDGE - 0.12), TRAY_DENOMS[i], k, str(d.chips))
	for band in [3.0, 2.0, 1.0]:
		draw_rect(Rect2(well.position, Vector2(well.size.x, band)), Color(0, 0, 0, 0.18))
	if fin == "steel":
		draw_rect(Rect2(well.position.x + well.size.x * 0.35, well.position.y, well.size.x * 0.3, well.size.y), Color(1, 1, 1, 0.05))


## A smoked acrylic lid over the well, with its lock.
func _lid(r: Rect2) -> void:
	draw_colored_polygon(_rounded(r, 1.6), Color(0.1, 0.07, 0.063, 0.42))
	var x := r.position.x
	var y := r.position.y
	var h := r.size.y
	draw_colored_polygon(PackedVector2Array([Vector2(x + 6, y), Vector2(x + 18, y), Vector2(x + 12, y + h), Vector2(x + 1, y + h)]), Color(1, 1, 1, 0.09))
	draw_colored_polygon(PackedVector2Array([Vector2(x + 22, y), Vector2(x + 25, y), Vector2(x + 19, y + h), Vector2(x + 16, y + h)]), Color(1, 1, 1, 0.06))
	_loop(_rounded(r, 1.6), Color(1, 1, 1, 0.28), 0.3)
	draw_rect(Rect2(-1.6, r.end.y - 1.2, 3.2, 0.9), Color("c9a24a"))


# ------------------------------------------------------------------ the printing
func ink() -> Color:
	return TableStyle.colour(d, "print.ink")


func role_colour(role: String) -> Color:
	match role:
		"accent":
			return TableStyle.colour(d, "print.accent")
		"jade":
			return TableStyle.JADE
	return ink()


## Lettering in the style's font. Gold foil gets a dark under-print.
func print_text(s: String, centre: Vector2, size: int, colour: Color) -> void:
	var f := TableStyle.font(d)
	if s == "£" and d.print.font == "cinzel":
		f = FONT   # (Cinzel has no £)
	if d.spots == "foil" and colour.a > 0.9:
		_text(s, centre + Vector2(0.12, 0.2), size, Color(0, 0, 0, 0.45), f)
	_text(s, centre, size, colour, f)


func title(s: String, y: float, size := 9) -> void:
	print_text(s, Vector2(0, y), size, ink())


## The dealer's rules, small, beside the dealer's cards.
func small(s: String, x: float, dy: float) -> void:
	print_text(s, Vector2(x, CasinoTable.DEALER_Y + dy), 3, Color(ink(), 0.85))


## A betting spot in the style's artwork. `s` says what it is:
##   shape "circle" (r), "diamond" (hw, hh) or "box" (w, h, rad); at; ring "ink" | "accent" | "jade"; alpha; width
##   inner {r, ring, alpha, width}: a second ring inside (the main bet circles)
##   lines: its words (one or two lines), size, dx/dy (moved from the centre), text_alpha
func spot(s: Dictionary) -> void:
	var style: String = d.spots
	var a: float = s.get("alpha", 1.0)
	var w: float = s.get("width", 0.8)
	var base := role_colour(s.get("ring", "ink"))
	var c := Color(base, a)
	match style:
		"printed":
			draw_colored_polygon(shape(s, 0.0), SPOT_FILL)
			_loop(shape(s, 0.4), c, w)
		"double":
			draw_colored_polygon(shape(s, 0.0), Color(0, 0, 0, 0.12))
			_loop(shape(s, 0.3), c, w * 0.55)
			_loop(shape(s, 1.5), Color(base, a * 0.75), w * 0.35)
		"foil":
			draw_colored_polygon(shape(s, 0.0), Color(0, 0, 0, 0.12))
			_loop(_shifted(shape(s, 0.45), Vector2(0, 0.25)), Color(0, 0, 0, 0.45), w + 0.25)
			_foil_loop(shape(s, 0.45), base, a, w * 1.05)
		"inlaid":
			draw_colored_polygon(shape(s, 0.0), Color(0, 0, 0, 0.26))
			_loop(_shifted(shape(s, 0.6), Vector2(0, -0.45)), Color(0, 0, 0, 0.45), 1.0)
			_loop(_shifted(shape(s, 0.5), Vector2(0, 0.45)), Color(1, 1, 1, 0.08), 0.6)
			_loop(shape(s, 0.35), c, w * 0.5)
		"deco":
			draw_colored_polygon(shape(s, 0.0), Color(0, 0, 0, 0.14))
			_loop(shape(s, 0.3), c, w * 0.55)
			_loop(shape(s, 1.6), Color(base, a * 0.6), 0.25)
			for tip in _tips(s):
				draw_colored_polygon(PackedVector2Array([tip + Vector2(0, -0.9), tip + Vector2(0.7, 0), tip + Vector2(0, 0.9), tip + Vector2(-0.7, 0)]), c)
	if s.has("inner"):
		var inner: Dictionary = s.inner
		var ic := Color(role_colour(inner.get("ring", "accent")), inner.get("alpha", 0.8))
		if style == "foil":
			ic = Color(role_colour(inner.get("ring", "accent")).lightened(0.15), 0.85)
		_loop(_circle_pts(s.at, inner.r), ic, inner.get("width", 0.4))
	var lines: Array = s.get("lines", [])
	var tc := Color(role_colour(s.get("text_ring", s.get("ring", "ink"))), s.get("text_alpha", 1.0))
	var size: int = s.get("size", 2)
	var centre: Vector2 = s.at + Vector2(s.get("dx", 0.0), s.get("dy", 0.0))
	if lines.size() == 1:
		print_text(lines[0], centre, size, tc)
	elif lines.size() == 2:
		print_text(lines[0], centre - Vector2(0, 1.3), size, tc)
		print_text(lines[1], centre + Vector2(0, 1.3), size, tc)


## A spot's outline, `inset` in from its edge.
func shape(s: Dictionary, inset: float) -> PackedVector2Array:
	var at: Vector2 = s.at
	match str(s.shape):
		"circle":
			return _circle_pts(at, maxf(0.3, float(s.r) - inset))
		"diamond":
			var hw: float = s.hw - inset * 1.2
			var hh: float = s.hh - inset * 1.2
			return PackedVector2Array([at + Vector2(0, -hh), at + Vector2(hw, 0), at + Vector2(0, hh), at + Vector2(-hw, 0)])
	var size := Vector2(s.w, s.h)
	return _rounded(Rect2(at - size / 2 + Vector2(inset, inset), size - Vector2(inset, inset) * 2), maxf(0.2, float(s.get("rad", 1.2)) - inset * 0.5))


func _tips(s: Dictionary) -> Array:
	var at: Vector2 = s.at
	match str(s.shape):
		"circle":
			var r: float = s.r
			return [at + Vector2(0, -r), at + Vector2(r, 0), at + Vector2(0, r), at + Vector2(-r, 0)]
		"box":
			var h := Vector2(s.w, s.h) / 2
			return [at - h, at + Vector2(h.x, -h.y), at + h, at + Vector2(-h.x, h.y)]
	return []


## A gold-foil line: lighter along the top, darker along the bottom.
func _foil_loop(pts: PackedVector2Array, base: Color, alpha: float, width: float) -> void:
	var closed := pts.duplicate()
	closed.append(pts[0])
	var top := INF
	var bottom := -INF
	for p in pts:
		top = minf(top, p.y)
		bottom = maxf(bottom, p.y)
	var colours := PackedColorArray()
	for p in closed:
		var f := inverse_lerp(top, bottom, p.y) if bottom > top else 0.5
		var col := base.lightened(0.5 * (1.0 - f * 2.0)) if f < 0.5 else base.darkened(0.35 * (f - 0.5) * 2.0)
		colours.append(Color(col, alpha))
	draw_polyline_colors(closed, colours, width, true)


static func _circle_pts(at: Vector2, r: float, n := 40) -> PackedVector2Array:
	var pts := PackedVector2Array()
	for i in n:
		pts.append(at + Vector2.from_angle(TAU * i / n) * r)
	return pts


# Shorthands for the layouts, matching the designer's.
func circle(at: Vector2, ring: String, lines: Array) -> void:
	spot({"shape": "circle", "at": at, "r": CasinoTable.SPOT_R, "ring": ring, "lines": lines, "size": 2})


## A main bet's circle: ink, with an accent ring inside it when `inner_r` is given.
func big(at: Vector2, r: float, lines: Array, size: int, inner_r := 0.0) -> void:
	var s := {"shape": "circle", "at": at, "r": r, "ring": "ink", "lines": lines, "size": size}
	if inner_r > 0.0:
		s["inner"] = {"r": inner_r, "ring": "accent", "alpha": 0.8, "width": 0.4}
	spot(s)


## Where the dealer's cards go (Mississippi Stud, Hold'em, Let It Ride, High Card Flush).
func card_box(at: Vector2, size: Vector2, alpha: float) -> void:
	spot({"shape": "box", "at": at, "w": size.x, "h": size.y, "rad": 1.5, "ring": "ink", "alpha": alpha, "width": 0.5})


# ------------------------------------------------------------------ the Jackpot disc
## The clear disc with the light under it (the Lights node lights it): a clear rim, a gold bezel or a ring of LEDs.
func jackpot_disc(at: Vector2) -> void:
	var r := CasinoTable.SPOT_R
	var k := rim_scale(d)
	draw_circle(at + Vector2(0, 0.7), r + 0.5, Color(0, 0, 0, 0.3))   # its shadow on the felt
	draw_circle(at, r, Color(0.84, 0.92, 0.96, 0.28))                 # clear plastic
	match str(d.jackpot):
		"clear":
			draw_arc(at, r - 0.4 * k, 0, TAU, 40, Color(1, 1, 1, 0.75), 0.8 * k, true)
		"gold":
			_ring(at, r - 0.6 * k, 1.2 * k, Color("fff0b8"), Color("d9b453"), Color("7a5a1c"))
			draw_arc(at, r - 1.2 * k - 0.1, 0, TAU, 40, Color(0, 0, 0, 0.35), 0.25, true)
		"led":
			_ring(at, r - 0.55 * k, 1.1 * k, Color.WHITE, Color("9aa3ab"), Color("4b535a"))
			for p in led_dots(d, at):
				draw_circle(p, 0.32, Color(TableStyle.colour(d, "led"), 0.8))
	draw_arc(at, r - 2.0, PI * 1.05, PI * 1.55, 10, Color(1, 1, 1, 0.6), 0.7, true)   # shine
	print_text("JACKPOT", at, 2, Color(1, 1, 1, 0.85))


## A metal ring lit from above: `hi` at the top, `mid` across the middle, `lo` at the bottom.
func _ring(at: Vector2, radius: float, width: float, hi: Color, mid: Color, lo: Color) -> void:
	var pts := _circle_pts(at, radius, 48)
	pts.append(pts[0])
	var colours := PackedColorArray()
	for p in pts:
		var f := inverse_lerp(at.y - radius, at.y + radius, p.y)
		colours.append(hi.lerp(mid, f / 0.45) if f < 0.45 else mid.lerp(lo, (f - 0.45) / 0.55))
	draw_polyline_colors(pts, colours, width, true)


## How thick the disc's rim is drawn (it grows inward; the disc's edge stays put).
static func rim_scale(design: Dictionary) -> float:
	return {"thin": 0.6, "standard": 1.0, "heavy": 1.8}.get(str(design.jackpotRim), 1.0)


## Inside the rim: the light fills this much of the disc.
static func rim_inner(design: Dictionary) -> float:
	var k := rim_scale(design)
	match str(design.jackpot):
		"gold":
			return CasinoTable.SPOT_R - 1.2 * k - 0.1
		"led":
			return CasinoTable.SPOT_R - 1.1 * k - 0.4
	return CasinoTable.SPOT_R - 0.8 * k


static func led_dots(design: Dictionary, at: Vector2) -> Array:
	var r := CasinoTable.SPOT_R - 1.1 * rim_scale(design) - 0.8
	var out := []
	for i in 16:
		out.append(at + Vector2.from_angle(i * PI / 8) * r)
	return out
