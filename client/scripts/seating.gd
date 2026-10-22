@tool
class_name Seating
extends RefCounted
## The chairs at every table and slot cabinet, how people sit down in them, and the craps
## rail's standing spots -- from the server's seating styles (server/casino_server/seating.py,
## sent in the welcome and in `seating` when the admin page changes them). Every table uses the
## "default" style unless the server gives it another. Signed off on the seating mockup (2026-10-21).
##
## A chair is drawn upright on screen however its table is turned, from its origin -- the
## sitter's feet, chair_pos() -- in two layers: "seat" (the base, the seat, and the back when
## it's beyond the sitter) under them, and "back" over them when it's between them and us.
## Angles are where the chair's back points: PI / 2 is towards the bottom of the screen.
##
## sit_down() and stand_up() are the same for you, other players and NPCs: the walk to the
## chair's side, the chair turning (or pulling out), the sit, and turning to the game.

const DEFAULT := {"chair": "stool", "upholstery": "#2a2320", "frame": "brass", "back": 1.4, "size": 1.0,
	"sit": "swivel", "sit_speed": 1.4, "slot_screen": "after_sit", "craps_spot": "footprints"}
## hi, mid, lo, piping
const METALS := {
	"brass": [Color("fbe7a1"), Color("c99a3c"), Color("6e4f1c"), Color("e2bb5c")],
	"chrome": [Color("ffffff"), Color("aeb6c0"), Color("4b525c"), Color("d5dbe2")],
	"gunmetal": [Color("9aa0a8"), Color("4a4e55"), Color("1d1f23"), Color("7e858f")],
}
const GOLD := Color("ffd56a")
const WALK_SPEED := 105.0

static var styles := {}   # style id -> the style, filled out (its geometry in _g, its colours in _p)
static var tables := {}   # table id -> style id, where it isn't the default


## The seating from the server: {styles, tables}.
static func configure(data: Dictionary) -> void:
	styles = {}
	var given: Dictionary = data.get("styles", {})
	for id in given:
		styles[id] = _fill(given[id])
	if not styles.has("default"):
		styles["default"] = _fill(DEFAULT)
	tables = data.get("tables", {})


static func style(table_id: String) -> Dictionary:
	if styles.is_empty():
		styles["default"] = _fill(DEFAULT)
	return styles.get(tables.get(table_id, "default"), styles["default"])


static func _fill(given: Dictionary) -> Dictionary:
	var st := DEFAULT.merged(given, true)
	var s := float(st.size)
	if st.chair == "lounge":   # a padded tub back, channel-stitched, on a wide disc base
		st._g = {"rx": 11.5 * s, "ry": 5.2 * s, "seat_y": -11.0 * s, "thick": 3.6 * s, "h": 13.0 * s * float(st.back),
			"hs": 1.22, "t": 2.4 * s, "inset": 1.0, "base_rx": 9.5 * s, "ring": false, "col": 3.2 * s}
	else:   # a low horseshoe back on a metal rail, a footring
		st._g = {"rx": 10.0 * s, "ry": 4.6 * s, "seat_y": -13.5 * s, "thick": 2.8 * s, "h": 7.5 * s * float(st.back),
			"hs": 1.0, "t": 1.7 * s, "inset": 0.6, "base_rx": 7.0 * s, "ring": true, "col": 2.4 * s}
	var u := Color(str(st.upholstery))
	st._p = {"main": u, "top": u.lightened(0.16), "edge": u.darkened(0.28), "side": u.darkened(0.5),
		"rear": u.darkened(0.32), "cap": u.lightened(0.26), "m": METALS.get(st.frame, METALS.brass)}
	st._ink = {}   # a drawn chair, by how it's drawn (see draw_chair)
	return st


## The chair's footprint for clicks, as the screen sees it from its origin.
static func hit_box(st: Dictionary) -> Rect2:
	var g: Dictionary = st._g
	var top: float = g.seat_y - g.h - g.ry - 3.0
	return Rect2(-g.rx - 3.0, top, 2.0 * g.rx + 6.0, 5.0 - top)


# ------------------------------------------------------------------ drawing a chair
## A chair in `ci` at `at`, turned `turn` to show upright, its back towards `theta` as the
## screen sees it; `press` (0-1) squashes the cushion as someone lands on it.
##
## Building a chair is the dear part (a hundred-odd points of trig), and a glowing one is
## redrawn a few times a second, so each way of drawing it is built once into Ink and kept
## in the style: drawing it again is a few calls.
static func draw_chair(ci: CanvasItem, at: Vector2, turn: float, theta: float, press: float, st: Dictionary,
		layer: String, glow: bool, pulse: float) -> void:
	var over := sin(theta) > 0.3
	if layer != "seat" and not over:
		return
	pulse = snappedf(pulse, 0.05) if glow else 0.0
	var key := [layer, glow, snappedf(theta, 0.001), snappedf(press, 0.01), pulse]
	var cache: Dictionary = st._ink
	var ink: Array = cache.get(key, [])
	if ink.is_empty():
		var rec := Ink.new()
		_build_chair(rec, theta, press, st, layer, over, glow, pulse)
		ink = rec.done()
		if cache.size() > 2000:   # (a chair turning as someone sits fills it with angles it won't need again)
			cache.clear()
		cache[key] = ink
	ci.draw_set_transform(at, turn)
	Ink.play(ci, ink)
	ci.draw_set_transform(Vector2.ZERO)


static func _build_chair(ci, theta: float, press: float, st: Dictionary, layer: String, over: bool, glow: bool, pulse: float) -> void:
	var g: Dictionary = st._g
	var p: Dictionary = st._p
	if layer == "seat":
		if glow:
			_halo(ci, g.rx + 9.0, pulse)
		_base(ci, g, p)
		_seat(ci, g, p, press, glow, pulse, st.chair == "lounge")
		if not over:
			_back(ci, g, p, theta, glow, pulse, st.chair == "lounge")
	elif over:
		_back(ci, g, p, theta, glow, pulse, st.chair == "lounge")


## Drawing calls written down as they're made, the CanvasItem draw_* calls a chair uses:
## the shapes, which are all convex, as one triangle list until a line breaks it, and the
## lines as they are. play() draws them back in the same order.
class Ink:
	var _batches := []   # [points, colours, indices] (triangles), or [points, colour, width] (a line)
	var _pts := PackedVector2Array()
	var _cols := PackedColorArray()
	var _idx := PackedInt32Array()

	func draw_polygon(pts: PackedVector2Array, cols: PackedColorArray) -> void:
		var at := _pts.size()
		_pts.append_array(pts)
		_cols.append_array(cols)
		for i in range(1, pts.size() - 1):
			_idx.append(at)
			_idx.append(at + i)
			_idx.append(at + i + 1)

	func draw_colored_polygon(pts: PackedVector2Array, c: Color) -> void:
		var cols := PackedColorArray()
		cols.resize(pts.size())
		cols.fill(c)
		draw_polygon(pts, cols)

	func draw_primitive(pts: PackedVector2Array, cols: PackedColorArray, _uvs: PackedVector2Array) -> void:
		draw_polygon(pts, cols)

	func draw_rect(r: Rect2, c: Color) -> void:
		draw_colored_polygon(PackedVector2Array([r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)]), c)

	func draw_polyline(pts: PackedVector2Array, c: Color, width: float, _antialiased: bool) -> void:
		_flush()
		_batches.append([pts, c, width])

	func draw_line(a: Vector2, b: Vector2, c: Color, width: float, antialiased: bool) -> void:
		draw_polyline(PackedVector2Array([a, b]), c, width, antialiased)

	func done() -> Array:
		_flush()
		return _batches

	func _flush() -> void:
		if not _idx.is_empty():
			_batches.append([_pts, _cols, _idx])
			_pts = PackedVector2Array()
			_cols = PackedColorArray()
			_idx = PackedInt32Array()

	static func play(ci: CanvasItem, batches: Array) -> void:
		var item := ci.get_canvas_item()
		for b in batches:
			if b[1] is Color:
				ci.draw_polyline(b[0], b[1], b[2], true)
			else:
				RenderingServer.canvas_item_add_triangle_array(item, b[2], b[0], b[1])


static func _ell(c: Vector2, rx: float, ry: float, n := 22) -> PackedVector2Array:
	var pts := PackedVector2Array()
	for i in n:
		var a := TAU * i / n
		pts.append(c + Vector2(cos(a) * rx, sin(a) * ry))
	return pts


static func _arc(c: Vector2, rx: float, ry: float, a0: float, a1: float, n := 16) -> PackedVector2Array:
	var pts := PackedVector2Array()
	for i in n + 1:
		var a := a0 + (a1 - a0) * i / n
		pts.append(c + Vector2(cos(a) * rx, sin(a) * ry))
	return pts


## A soft gold pool on the floor (a free seat, while you're walking).
## Drawing in a table's frame at `at`, squashed by `squash` up and down the screen (lying flat on
## the floor in perspective), the screen being turned `turn` from the table.
static func _on_floor(at: Vector2, turn: float, squash: float) -> Transform2D:
	return Transform2D(turn, at) * Transform2D.IDENTITY.scaled(Vector2(1, squash)) * Transform2D(-turn, Vector2.ZERO)


static func _halo(ci, r: float, pulse: float) -> void:
	var a := 0.1 * (0.6 + 0.4 * pulse)
	for i in 4:
		var k := 1.0 - i / 4.0
		ci.draw_colored_polygon(_ell(Vector2.ZERO, r * k, r * k * 0.42), Color(GOLD, a))


## Metal shaded across from x = 0 (its left edge) to 1, lit from the left.
static func _metal(m: Array, f: float) -> Color:
	return (m[1] as Color).lerp(m[0], f / 0.35) if f < 0.35 else (m[0] as Color).lerp(m[2], (f - 0.35) / 0.65)


static func _base(ci, g: Dictionary, p: Dictionary) -> void:
	var m: Array = p.m
	ci.draw_colored_polygon(_ell(Vector2(0, 1.2), g.rx + 1.5, 3.8), Color(0, 0, 0, 0.38))
	ci.draw_colored_polygon(_ell(Vector2(0, 0.7), g.base_rx, g.base_rx * 0.36), m[2])
	var disc := _ell(Vector2(0, -0.1), g.base_rx * 0.9, g.base_rx * 0.3)
	var shades := PackedColorArray()
	for q in disc:
		shades.append(_metal(m, (q.x / (g.base_rx * 0.9) + 1.0) / 2.0))
	ci.draw_polygon(disc, shades)
	var ring_y: float = -4.2 * g.rx / 10.0
	var rr: float = 0.76 * g.rx
	if g.ring:   # the back of the footring, behind the column
		ci.draw_polyline(_arc(Vector2(0, ring_y), rr, rr * 0.32, PI, TAU), m[2], 1.1, true)
	var top: float = g.seat_y + g.thick
	var w: float = g.col
	var stops := [[0.0, m[2]], [0.35, m[0]], [0.6, m[1]], [1.0, m[2]]]
	for i in 3:
		var x0: float = -w / 2 + w * stops[i][0]
		var x1: float = -w / 2 + w * stops[i + 1][0]
		ci.draw_primitive(PackedVector2Array([Vector2(x0, top), Vector2(x1, top), Vector2(x1, 0), Vector2(x0, 0)]),
			PackedColorArray([stops[i][1], stops[i + 1][1], stops[i + 1][1], stops[i][1]]), PackedVector2Array())
	if g.ring:
		ci.draw_polyline(_arc(Vector2(0, ring_y), rr, rr * 0.32, 0, PI), m[1], 1.2, true)
		ci.draw_polyline(_arc(Vector2(0, ring_y - 0.3), rr, rr * 0.32, 0.3, 1.6, 8), Color(m[0], 0.8), 0.4, true)
	else:   # the swivel under a lounge chair's seat
		ci.draw_colored_polygon(_ell(Vector2(0, top + 0.6), g.rx * 0.42, g.ry * 0.42), m[2])


static func _seat(ci, g: Dictionary, p: Dictionary, press: float, glow: bool, pulse: float, lounge: bool) -> void:
	var y: float = g.seat_y + press * 0.9
	var th: float = g.thick * (1.0 - 0.35 * press)
	var rx: float = g.rx
	var ry: float = g.ry
	ci.draw_colored_polygon(_ell(Vector2(0, y + th), rx, ry), p.side)
	ci.draw_rect(Rect2(-rx, y, 2 * rx, th), p.side)
	ci.draw_rect(Rect2(-rx, y + th * 0.55, 2 * rx, 0.35), Color(p.m[3], 0.55))   # a welt round the side
	ci.draw_colored_polygon(_ell(Vector2(0, y), rx, ry), p.edge)
	ci.draw_colored_polygon(_ell(Vector2(-rx * 0.06, y - ry * 0.1), rx * 0.88, ry * 0.8), p.main)
	ci.draw_colored_polygon(_ell(Vector2(-rx * 0.3, y - ry * 0.35), rx * 0.45, ry * 0.4), Color(p.top, 0.75))
	if lounge:
		ci.draw_polyline(_arc(Vector2(0, y + 0.2), rx * 0.62, ry * 0.58, 0, TAU, 22), Color((p.main as Color).darkened(0.5), 0.45), 0.4, true)
	var rim := _arc(Vector2(0, y), rx - 0.3, ry - 0.15, 0, TAU, 26)
	if glow:
		ci.draw_polyline(rim, Color(GOLD, 0.55 + 0.45 * pulse), 0.9 + 0.5 * pulse, true)
	else:
		ci.draw_polyline(rim, p.m[3], 0.6, true)


## The back: a curved band standing on the seat's edge round `th`, its faces shaded by
## which way they turn, then its ends, its top catching the light, and the piping (or a
## stool's metal rail) along the top.
static func _back(ci, g: Dictionary, p: Dictionary, th: float, glow: bool, pulse: float, lounge: bool) -> void:
	var n := 14
	var hs: float = g.hs
	var pt := func(a: float, inner: bool, up: bool) -> Vector2:
		var rb: float = g.rx - g.inset - (g.t if inner else 0.0)
		var rby: float = (g.ry - g.inset * 0.45) * rb / (g.rx - g.inset)
		return Vector2(rb * cos(a), g.seat_y + rby * sin(a) - (g.h if up else 0.0))
	var segs := []
	for i in n:
		var a1 := th - hs + 2.0 * hs * i / n
		var a2 := th - hs + 2.0 * hs * (i + 1) / n
		segs.append([a1, a2, (a1 + a2) / 2.0])
	segs.sort_custom(func(s, t): return sin(s[2]) < sin(t[2]))
	for s in segs:   # the far ones first
		var outer := sin(s[2]) > 0.0
		var k := -cos(s[2]) * 0.13 * (1.0 if outer else -1.0)
		var c: Color = p.rear if outer else p.main
		c = c.lightened(k) if k > 0.0 else c.darkened(-k)
		_quad(ci, [pt.call(s[0], outer, false), pt.call(s[1], outer, false), pt.call(s[1], outer, true), pt.call(s[0], outer, true)], c)
	for f in ([0.5] if not lounge else [0.2, 0.4, 0.6, 0.8]):   # the stool's middle post; the lounge's stitching
		var a: float = th - hs + 2.0 * hs * f
		var outer := sin(a) > 0.0
		var b: Vector2 = pt.call(a, outer, false)
		var t: Vector2 = pt.call(a, outer, true)
		ci.draw_line(b - Vector2(0, 0.6), t + Vector2(0, 1.2),
			p.m[1] if not lounge else Color((p.main as Color).darkened(0.55), 0.55), 0.45 if lounge else 0.9, true)
	for a in [th - hs, th + hs]:
		_quad(ci, [pt.call(a, false, false), pt.call(a, true, false), pt.call(a, true, true), pt.call(a, false, true)], p.side)
	for s in segs:
		_quad(ci, [pt.call(s[0], false, true), pt.call(s[1], false, true), pt.call(s[1], true, true), pt.call(s[0], true, true)],
			p.cap if lounge else p.m[1])
	var top := PackedVector2Array()
	for i in n + 1:
		top.append(pt.call(th - hs + 2.0 * hs * i / n, false, true))
	if glow:
		ci.draw_polyline(top, Color(GOLD, 0.55 + 0.45 * pulse), 1.0 + 0.5 * pulse, true)
	else:
		ci.draw_polyline(top, p.m[3] if lounge else p.m[0], 0.6 if lounge else 0.55, true)


static func _quad(ci, q: Array, c: Color) -> void:
	ci.draw_primitive(PackedVector2Array(q), PackedColorArray([c, c, c, c]), PackedVector2Array())


# ------------------------------------------------------------------ craps standing spots
## A standing spot at the craps rail, at `at` on the floor: glowing while it's free and you're
## walking, wearing its player's `colour` (or null) once someone's there. `turn` is how the
## screen is turned from the table (-screen_turn()): the spot lies flat in perspective as the
## screen sees it, still pointing at the table.
static func draw_spot(ci: CanvasItem, at: Vector2, kind: String, glow: bool, pulse: float, colour: Variant, turn := 0.0) -> void:
	var brass: Array = METALS.brass
	var taken := colour != null
	var rim: Color = colour if taken else (Color(GOLD, 0.7 + 0.3 * pulse) if glow else brass[1])
	if kind == "ring":   # (the first standing spots: a ring on the floor)
		ci.draw_set_transform_matrix(_on_floor(at, turn, 0.45))
		if glow:
			ci.draw_circle(Vector2.ZERO, 12.0 + pulse * 1.5, Color(1, 0.84, 0.3, 0.14 + 0.16 * pulse))
			ci.draw_arc(Vector2.ZERO, 11.0, 0, TAU, 40, Color(1, 0.84, 0.3, 0.55 + 0.35 * pulse), 1.4, true)
		elif taken:
			ci.draw_arc(Vector2.ZERO, 11.0, 0, TAU, 40, colour, 1.6, true)
		ci.draw_set_transform(Vector2.ZERO)
		return
	if glow:
		ci.draw_set_transform(at, turn)
		_halo(ci, 22.0, pulse)
	match kind:
		"footprints":   # a brass-rimmed plate with two shoe prints, toes to the table
			ci.draw_set_transform_matrix(_on_floor(at, turn, 0.5))
			var plate := TableFelt._rounded(Rect2(-12, -11, 24, 22), 7)
			ci.draw_colored_polygon(plate, Color(0.05, 0.03, 0.015, 0.82))
			plate.append(plate[0])
			ci.draw_polyline(plate, rim, 2.2 if taken else 1.4, true)
			if not taken:
				var ink := Color(GOLD, 0.75 + 0.25 * pulse) if glow else Color(brass[1], 0.8)
				for fx in [-4.2, 4.2]:
					ci.draw_colored_polygon(_ell(Vector2(fx, -2.5), 2.3, 4.4, 14), ink)
					ci.draw_colored_polygon(_ell(Vector2(fx, 5.3), 1.9, 2.1, 12), ink)
		"spotlight":   # a pool of light with a little standing figure in it (upright on screen: `turn`)
			ci.draw_set_transform(at, turn)
			for i in 4:
				var k := 1.0 - i / 4.0
				ci.draw_colored_polygon(_ell(Vector2.ZERO, 19.0 * k, 8.0 * k), Color(1, 0.89, 0.63, (0.12 if glow else 0.055)))
			ci.draw_polyline(_arc(Vector2.ZERO, 12, 5, 0, TAU, 32), colour if taken else (Color(GOLD, 0.6 + 0.4 * pulse) if glow else Color(1, 0.89, 0.63, 0.35)),
				2.2 if taken else 1.2, true)
			if not taken:
				var ink := Color(GOLD, 0.85 + 0.15 * pulse) if glow else Color(1, 0.89, 0.63, 0.55)
				ci.draw_circle(Vector2(0, -8.3), 1.6, ink)
				ci.draw_colored_polygon(TableFelt._rounded(Rect2(-2.1, -6.3, 4.2, 4.6), 1.2), ink)
				ci.draw_rect(Rect2(-1.7, -2.2, 1.4, 3.2), ink)
				ci.draw_rect(Rect2(0.3, -2.2, 1.4, 3.2), ink)
		_:   # "medallion": a brass disc set in the floor, a chevron pointing at the table
			ci.draw_set_transform_matrix(_on_floor(at, turn, 0.42))
			ci.draw_circle(Vector2(0.5, 1.6), 11.5, Color(0, 0, 0, 0.4))
			ci.draw_circle(Vector2.ZERO, 11.0, brass[2])
			ci.draw_circle(Vector2(-0.6, -0.6), 9.6, brass[1])
			ci.draw_circle(Vector2(-3.5, -3.5), 4.5, Color(brass[0], 0.55))
			ci.draw_arc(Vector2.ZERO, 11.0, 0, TAU, 40, rim if taken or glow else brass[2], 2.4 if taken else 1.2, true)
			ci.draw_arc(Vector2.ZERO, 7.6, 0, TAU, 32, Color(brass[2], 0.8), 0.8, true)
			if not taken:
				ci.draw_colored_polygon(PackedVector2Array([Vector2(0, -5.5), Vector2(5, 1.5), Vector2(2.6, 1.5), Vector2(0, -1.8),
					Vector2(-2.6, 1.5), Vector2(-5, 1.5)]), (brass[2] as Color).darkened(0.3))
	ci.draw_set_transform(Vector2.ZERO)


# ------------------------------------------------------------------ sitting down and getting up
## Where to walk to before sitting on `game`'s `seat`, coming from `from` (the game's
## coordinates): beside the chair (it turns or pulls out towards you), or in front of it.
static func approach(game: FloorGame, seat: int, from: Vector2) -> Vector2:
	var st := style(game.table_id)
	var c := game.chair_pos(seat)
	var bv := Vector2.from_angle(game.rest_theta(seat))
	if game.seat_pose() != "sit" or st.sit == "glide":
		return c + bv * 14.0
	var sv := bv.orthogonal()
	var s := 1.0 if (from - c).dot(sv) >= 0.0 else -1.0
	return c + sv * s * 20.0 * float(st.size) + bv * 3.0


## The way someone in a chair faces, given where its back points (the game's frame).
static func facing_of(theta: float) -> String:
	return Looks.dir_from(-Vector2.from_angle(theta))


## Seat `who` (the node that moves: you, or an EntityAvatar) on `game`'s `seat`, `av` being
## how they look. Plays the style's sit-down from wherever they are (or, not `animate` or from
## afar, puts them straight there). Returns the running tween: its `finished` is when they're sat.
static func sit_down(who: Node2D, av: Avatar, game: FloorGame, seat: int, animate := true) -> Tween:
	stop(who, game)
	var st := style(game.table_id)
	var k := 1.0 / float(st.sit_speed)
	var frame := who.get_parent() as Node2D
	var on_floor := func(p: Vector2) -> Vector2: return frame.to_local(game.to_global(p))
	var c := game.chair_pos(seat)
	var pose := game.seat_pose()
	var face := game.world_dir(game.sit_facing(seat))
	var tw := who.create_tween()
	who.set_meta("seat_tween", tw)
	who.set_meta("seat_chair", seat)
	if not animate or who.position.distance_to(on_floor.call(c)) > 60.0:
		who.position = on_floor.call(c)
		av.dip = 0.0
		av.set_action(pose, face)
		tw.tween_interval(0.0)
		return tw
	if pose != "sit" or st.sit == "glide":   # step in and stand (the craps rail), or glide on (no chair animation)
		_step(tw, who, av, on_floor.call(c), clampf(who.position.distance_to(on_floor.call(c)) / WALK_SPEED, 0.15, 0.35))
		tw.tween_callback(func(): av.set_action(pose, face))
		return tw
	var rest := game.rest_theta(seat)
	var bv := Vector2.from_angle(rest)
	var sv := bv.orthogonal()
	var here := game.to_local(who.global_position)
	var s := 1.0 if (here - c).dot(sv) >= 0.0 else -1.0
	game.chair_side[seat] = s
	var beside: Vector2 = on_floor.call(c + sv * s * 20.0 * float(st.size) + bv * 3.0)
	_step(tw, who, av, beside, who.position.distance_to(beside) / WALK_SPEED)
	var inward := Looks.dir_from(on_floor.call(c) - beside)
	tw.tween_callback(func(): av.set_action("idle", inward))
	if st.sit == "pull":   # pulled back, stepped into, pushed in
		var off := bv * 6.0
		tw.tween_method(func(v: float): game.set_chair(seat, "offset", off * v), 0.0, 1.0, 0.2 * k).set_trans(Tween.TRANS_SINE)
		_step(tw, who, av, on_floor.call(c + off), 0.28 * k)
		tw.tween_callback(func(): av.set_action("idle", face))
		tw.tween_interval(0.09 * k)
		_lower(tw, av, game, seat, face, k)
		tw.tween_method(func(v: float):
			game.set_chair(seat, "offset", off * (1.0 - v))
			who.position = on_floor.call(c + off * (1.0 - v)), 0.0, 1.0, 0.26 * k).set_trans(Tween.TRANS_SINE)
	else:   # swivel: the seat turns to them, they sit side-on, it turns them to the game
		var side_theta := rest + wrapf((-sv * s).angle() - rest, -PI, PI)
		tw.tween_method(func(th: float): game.set_chair(seat, "theta", th), rest, side_theta, 0.24 * k).set_trans(Tween.TRANS_SINE)
		_step(tw, who, av, on_floor.call(c), 0.26 * k)
		var outward := game.world_dir(facing_of(side_theta))
		tw.tween_callback(func(): av.set_action("idle", outward))
		tw.tween_interval(0.09 * k)
		_lower(tw, av, game, seat, outward, k)
		tw.tween_interval(0.11 * k)
		tw.tween_method(func(th: float):
			game.set_chair(seat, "theta", th)
			av.set_action("sit", game.world_dir(facing_of(th))), side_theta, rest, 0.3 * k).set_trans(Tween.TRANS_SINE)
	tw.tween_callback(func():
		game.rest_chair(seat)
		av.set_action("sit", face))
	return tw


## Get `who` up from `game`'s `seat` and over to its stand_pos(), then call `done`.
static func stand_up(who: Node2D, av: Avatar, game: FloorGame, seat: int, done: Callable) -> Tween:
	stop(who, game)
	var st := style(game.table_id)
	var k := 1.0 / float(st.sit_speed)
	var frame := who.get_parent() as Node2D
	var on_floor := func(p: Vector2) -> Vector2: return frame.to_local(game.to_global(p))
	var c := game.chair_pos(seat)
	var stand: Vector2 = on_floor.call(game.stand_pos(seat))
	var tw := who.create_tween()
	who.set_meta("seat_tween", tw)
	who.set_meta("seat_chair", seat)
	if game.seat_pose() == "sit" and st.sit != "glide" and who.position.distance_to(on_floor.call(c)) < 3.0:
		var rest := game.rest_theta(seat)
		var bv := Vector2.from_angle(rest)
		var sv := bv.orthogonal()
		var s: float = game.chair_side.get(seat, 1.0)
		var beside: Vector2 = on_floor.call(c + sv * s * 20.0 * float(st.size) + bv * 3.0)
		var out := Looks.dir_from(beside - on_floor.call(c))
		if st.sit == "pull":
			var off := bv * 6.0
			tw.tween_method(func(v: float):
				game.set_chair(seat, "offset", off * v)
				who.position = on_floor.call(c + off * v), 0.0, 1.0, 0.2 * k).set_trans(Tween.TRANS_SINE)
			_rise(tw, av, out, k)
			_step(tw, who, av, beside, 0.26 * k)
			tw.tween_callback(func():
				var back := game.create_tween()
				back.tween_method(func(v: float): game.set_chair(seat, "offset", off * (1.0 - v)), 0.0, 1.0, 0.24 * k)
				back.tween_callback(game.rest_chair.bind(seat)))
		else:
			var side_theta := rest + wrapf((-sv * s).angle() - rest, -PI, PI)
			tw.tween_method(func(th: float):
				game.set_chair(seat, "theta", th)
				av.set_action("sit", game.world_dir(facing_of(th))), rest, side_theta, 0.24 * k).set_trans(Tween.TRANS_SINE)
			_rise(tw, av, out, k)
			tw.tween_callback(func():
				var back := game.create_tween()
				back.tween_method(func(th: float): game.set_chair(seat, "theta", th), side_theta, rest, 0.32 * k).set_trans(Tween.TRANS_SINE)
				back.tween_callback(game.rest_chair.bind(seat)))
			_step(tw, who, av, beside, 0.26 * k)
	_step(tw, who, av, stand, clampf(who.position.distance_to(stand) / WALK_SPEED, 0.2, 0.4))
	tw.tween_callback(done)
	return tw


## Stop a sit-down or getting-up that's still playing (the chair goes back as it was).
static func stop(who: Node2D, game: FloorGame) -> void:
	var tw: Tween = _tween_of(who)
	if tw and tw.is_valid():
		tw.kill()
		var seat: int = who.get_meta("seat_chair", -1)
		if seat >= 0:
			game.rest_chair(seat)
		av_of(who).dip = 0.0
	who.remove_meta("seat_tween")


static func av_of(who: Node2D) -> Avatar:
	return who if who is Avatar else who.get_node("Avatar")


static func busy(who: Node2D) -> bool:
	var tw := _tween_of(who)
	return tw != null and tw.is_valid() and tw.is_running()


static func _tween_of(who: Node2D) -> Tween:
	return who.get_meta("seat_tween") if who.has_meta("seat_tween") else null


static func _step(tw: Tween, who: Node2D, av: Avatar, to: Vector2, secs: float) -> void:
	if secs <= 0.01:
		return
	tw.tween_callback(func(): av.set_action("walk", Looks.dir_from(to - who.position, av.facing)))
	tw.tween_property(who, "position", to, secs)
	tw.tween_callback(func(): av.set_action("idle"))


static func _lower(tw: Tween, av: Avatar, game: FloorGame, seat: int, facing: String, k: float) -> void:
	tw.tween_property(av, "dip", 1.8, 0.09 * k)
	tw.tween_callback(func():
		av.set_action("sit", facing)
		game.set_chair(seat, "press", 1.0))
	tw.tween_method(func(v: float):
		av.dip = 1.1 * (1.0 - v)
		game.set_chair(seat, "press", 1.0 - v), 0.0, 1.0, 0.17 * k)


static func _rise(tw: Tween, av: Avatar, facing: String, k: float) -> void:
	tw.tween_callback(func():
		av.dip = 1.4
		av.set_action("idle", facing))
	tw.tween_property(av, "dip", 0.0, 0.11 * k)
