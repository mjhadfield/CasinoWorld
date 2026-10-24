class_name MasterSwap
extends Node2D
## A Master Table changing game (the floor starts one on `master_change`; server tables/master.py). The new game's
## table (`to_table`) takes the old one's place at once, its felt painted without its printing ("base"), and this
## draws the two printings changing over it, the way the table's options on the Floor plan say:
##   "cloth": a fresh cloth rolls down from the dealer's side, uncovering the new layout as it goes;
##   "sweep": the printing flies into the chip tray seat by seat from third base, a sheen crosses the felt, and the
##            new layout deals back out the same way;
##   "dust":  the printing breaks into gold dust that drifts across and settles into the new layout.
## The old table (`from_table`) stays as a ghost until it's done: only its machines and whatever is still moving on
## its felt (chips going back). Machines that both tables have glide across; the rest slide off or on. When the seat
## count changes (Let It Ride and High Card Flush seat five) the chairs slide with their sitters, and the chair that
## goes fades. Signed off on the mockup (docs/master_table/mockup/).

const PRINT := Rect2(-162, -150, 324, 158)   # what a printing covers, in table coordinates
const PPU := 5.0                              # its pixels per table unit
const TRAY := Vector2(0, -128)
const SECONDS := {"cloth": 2.7, "sweep": 3.0, "dust": 3.3}   # at 1x (the server's tables/master.py MORPH)
## When the chairs slide and the machines go and come, as parts of the whole.
const WINDOWS := {
	"sweep": {"chairs": [0.36, 0.72], "out": [0.1, 0.35], "in": [0.55, 0.78]},
	"cloth": {"chairs": [0.3, 0.75], "out": [0.12, 0.4], "in": [0.5, 0.8]},
	"dust": {"chairs": [0.25, 0.7], "out": [0.05, 0.3], "in": [0.62, 0.88]},
}
const PARTICLES := 2400
const STEP := 0.045      # the sweep: each seat this much after the one before

var from_table: CasinoTable
var to_table: CasinoTable
var anim := "cloth"
var speed := 1.0
var mapping := []        # for each new seat, the old seat it took over (-1: a new one)
var k := 0.0             # how far through, 0..1
var _old: ImageTexture
var _new: ImageTexture
var _old_parts := []     # the old printing in pieces: [{rect, seat, rank}]
var _new_parts := []
var _from_blank := false
var _to_blank := false
var _felt := PackedVector2Array()
var _felt_colour := Color.DARK_RED
var _gold := Color("e0c070")
var _dust: Node2D
var _sparks := []
var _machines := []      # [{node, from, to, kind: "both" | "out" | "in"}]
var _markers := []       # [{node, from, to}]
var _ghost_chair: Node2D
var _ghost_from := Vector2.ZERO
var _ghost_to := Vector2.ZERO
var _done := false


## Start changing `from_t` into `to_t` (already in its place on the floor) as `ev` (master_change) says.
static func start(from_t: CasinoTable, to_t: CasinoTable, ev: Dictionary) -> MasterSwap:
	var s := MasterSwap.new()
	s.from_table = from_t
	s.to_table = to_t
	s.anim = str(ev.get("anim", "cloth")) if SECONDS.has(str(ev.get("anim", ""))) else "cloth"
	s.speed = maxf(0.25, float(ev.get("speed", 1.0)))
	s.mapping = ev.get("map", [])
	s.name = "MasterSwap"
	(to_t._felt as TableFelt).held = true   # (painted bare, it would hide the old printing before this draws it)
	to_t._felt.add_child(s)
	to_t._felt.move_child(s, 0)   # (the felt's picture goes under it when it's attached: then this is just over it)
	s.position = -to_t._felt.position
	s._prepare()
	s.run()
	return s


## Before the first frame: the ghost, the machines and the chairs where they start.
func _prepare() -> void:
	var mat := CanvasItemMaterial.new()
	mat.blend_mode = CanvasItemMaterial.BLEND_MODE_PREMULT_ALPHA   # (the printings come from transparent viewports)
	material = mat
	_from_blank = from_table is MasterTable
	_to_blank = to_table is MasterTable
	var d := to_table.style()
	_felt = StyledFelt.felt_outline(str(d.tray.mode) == "ledge")
	_felt_colour = TableStyle.colour(d, "felt.colour")
	_gold = TableStyle.colour(d, "print.accent").lightened(0.25)
	_ghost(from_table)
	_place_machines()
	_place_chairs()
	visible = false   # (until both printings are painted: a frame or two)


func run() -> void:
	var settled := _settled()
	var images := await _paint([from_table, settled])
	if settled != to_table:
		settled.free()
	if not _alive():
		return _finish()
	_old = ImageTexture.create_from_image(images[0])
	_new = ImageTexture.create_from_image(images[1])
	_old_parts = _parts(from_table)
	for m in _markers:   # (its pieces are cut where its chairs finish, too)
		m.node.position = m.to
	_new_parts = _parts(to_table)
	for m in _markers:
		m.node.position = m.from
	if anim == "dust":
		_make_dust(images[0], images[1])
	# The new felt shows from the frame this does, and the old one's picture stays up under it until the new one's
	# is painted (a frame or two): the tables' geometry is the same, so only the printing is seen to change.
	visible = true
	(to_table._felt as TableFelt).release()
	_bob()
	var tw := create_tween()
	tw.tween_method(_step, 0.0, 1.0, SECONDS[anim] / speed)
	await tw.finished
	_finish()


## The new table as it ends up, to paint its printing from. Its spots line up with its chairs, and when the seat
## count changes those start where the old ones were (_place_chairs): painted from it, the printing would land in
## the old places and jump at the end. So then it's a fresh copy, off the floor, with its chairs where they finish
## (only painted from: it never joins the tree, so it has no @onready nodes, and _paint finds its felt by path).
func _settled() -> CasinoTable:
	if _markers.is_empty():
		return to_table
	var t: CasinoTable = load(to_table.scene_file_path).instantiate()
	t.table_id = to_table.table_id
	t.is_master = true
	t.master_game = to_table.master_game
	t.game_label = to_table.game_label
	if "face_up" in to_table:
		t.set("face_up", to_table.get("face_up"))
	return t


func _alive() -> bool:
	return is_instance_valid(from_table) and is_instance_valid(to_table) and to_table.is_inside_tree()


# ------------------------------------------------------------------ the old table, as a ghost
func _ghost(t: CasinoTable) -> void:
	t.self_modulate.a = 0.0          # its chairs, ticks and countdown
	t.dealer.visible = false
	t.offer_seats = false
	t.mode = ""
	for b in t._backs.values():
		b.visible = false
	var lights := t.get_node_or_null("Felt/Lights") as CanvasItem
	if lights:
		lights.visible = false
	t.remove_from_group("navigation_obstacles")
	t.remove_from_group("tables")
	for n in t.find_children("*", "CollisionPolygon2D", true, false) + t.find_children("*", "CollisionShape2D", true, false):
		n.set_deferred("disabled", true)


# ------------------------------------------------------------------ the printings
## Each table's printing on its own, painted once in a viewport (StyledFelt's "print" layer).
func _paint(tables: Array) -> Array:
	var vps := []
	for t in tables:
		var vp := SubViewport.new()
		vp.transparent_bg = true
		vp.disable_3d = true
		vp.size = Vector2i(ceili(PRINT.size.x * PPU), ceili(PRINT.size.y * PPU))
		vp.canvas_item_default_texture_filter = Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_LINEAR
		vp.render_target_update_mode = SubViewport.UPDATE_ONCE
		var felt: Node2D = t.get_node("Felt")
		var painter: TableFelt = felt.get_script().new()
		painter.painting = true
		painter.table_ref = t
		painter.layer = "print"
		painter.position = felt.position
		vp.add_child(painter)
		add_child(vp)
		vp.canvas_transform = Transform2D(0.0, Vector2(PPU, PPU), 0.0, -PRINT.position * PPU)   # (once it's in the tree)
		vps.append(vp)
	await RenderingServer.frame_post_draw
	var out := []
	for vp in vps:
		out.append(vp.get_texture().get_image())
		vp.queue_free()
	return out


## A printing in pieces: the band along the dealer's side (the title, the rules, the dealer's card boxes; on a blank
## table, the whole crest) and a column for each seat, cut halfway between its chair and the next.
func _parts(t: CasinoTable) -> Array:
	var split := INF
	for seat in t.seat_count():
		for spot in t.bet_spots():
			split = minf(split, t.spot_pos(seat, spot).y - t.spot_radius(spot) - 1.0)
	var top := PRINT.position.y
	var bottom := PRINT.end.y
	if split == INF:
		return [{"rect": PRINT, "seat": -1, "rank": -1}]
	var out := [{"rect": Rect2(PRINT.position.x, top, PRINT.size.x, split - top), "seat": -1, "rank": -1}]
	var n := t.seat_count()
	for seat in n:
		var x := t.seat_pos(seat).x
		var right := PRINT.end.x if seat == 0 else (x + t.seat_pos(seat - 1).x) / 2.0
		var left := PRINT.position.x if seat == n - 1 else (x + t.seat_pos(seat + 1).x) / 2.0
		out.append({"rect": Rect2(left, split, right - left, bottom - split), "seat": seat, "rank": n - 1 - seat})
	return out


func _src(r: Rect2) -> Rect2:
	return Rect2((r.position - PRINT.position) * PPU, r.size * PPU)


# ------------------------------------------------------------------ each frame
func _step(v: float) -> void:
	k = v
	if not _alive():
		return
	var old_cache := (from_table._felt as TableFelt)._cache
	if old_cache and old_cache.visible:
		var cache := (to_table._felt as TableFelt)._cache
		if cache and cache._scale > 0.0:
			old_cache.visible = false
	var w: Dictionary = WINDOWS[anim]
	_move_machines(w)
	_move_chairs(clampf(inverse_lerp(w.chairs[0], w.chairs[1], k), 0.0, 1.0))
	queue_redraw()
	if _dust:
		_dust.queue_redraw()


func _draw() -> void:
	if _old == null:
		return
	match anim:
		"sweep":
			_draw_sweep()
		"cloth":
			_draw_cloth()
		_:
			var fade_out := 1.0 - clampf(k / 0.22, 0.0, 1.0)
			var fade_in := clampf((k - 0.7) / 0.22, 0.0, 1.0)
			if fade_out > 0.0:
				draw_texture_rect(_old, PRINT, false, _alpha(fade_out))
			if fade_in > 0.0:
				draw_texture_rect(_new, PRINT, false, _alpha(fade_in))


static func _alpha(a: float) -> Color:
	return Color(a, a, a, a)   # (premultiplied)


func _draw_piece(tex: Texture2D, part: Dictionary, at: Vector2, rot: float, s: float, a: float) -> void:
	if a <= 0.0 or s <= 0.0:
		return
	var r: Rect2 = part.rect
	var centre := r.get_center()
	draw_set_transform(at, rot, Vector2(s, s))
	draw_texture_rect_region(tex, Rect2(r.position - centre, r.size), _src(r), _alpha(clampf(a, 0.0, 1.0)))
	draw_set_transform(Vector2.ZERO)


func _draw_sweep() -> void:
	for part in _old_parts:   # out: the band shrinks away where it is (the crest turning as it goes); each seat's
		var rank: int = part.rank   # column flies into the tray, third base first
		var kk := clampf((k - 0.05 - (rank + 1) * STEP) / 0.2, 0.0, 1.0)
		var c: Vector2 = part.rect.get_center()
		if kk >= 1.0:
			continue
		var e := kk * kk * kk
		if part.seat < 0:
			_draw_piece(_old, part, c, -0.6 * e if _from_blank else 0.0, 1.0 - 0.45 * e, 1.0 - e)
		else:
			var at := c.lerp(TRAY, e) - Vector2(0, sin(PI * e) * 14.0)
			var s := (1.0 + 0.18 * sin(PI * minf(1.0, kk * 2.5))) * (1.0 - 0.7 * e)
			_draw_piece(_old, part, at, 0.0, s, 1.0 - e * e)
	var g := clampf((k - 0.4) / 0.22, 0.0, 1.0)
	if g > 0.0 and g < 1.0:
		_sheen(lerpf(-200.0, 200.0, _ease_io(g)))
	for part in _new_parts:   # in: each seat's column deals back out of the tray, then the band fades in
		var rank: int = part.rank
		var delay := 0.3 if part.seat < 0 else (rank + 1) * STEP
		var kk := clampf((k - 0.5 - delay) / 0.2, 0.0, 1.0)
		if kk <= 0.0:
			continue
		var c: Vector2 = part.rect.get_center()
		var e := 1.0 - pow(1.0 - kk, 3.0)
		if part.seat < 0:
			_draw_piece(_new, part, c, 0.6 * (1.0 - e) if _to_blank else 0.0, 0.55 + 0.45 * _back_out(kk) if _to_blank else 1.0, e)
		else:
			var at := TRAY.lerp(c, e) - Vector2(0, sin(PI * e) * 14.0)
			_draw_piece(_new, part, at, 0.0, 0.3 + 0.7 * _back_out(kk), minf(1.0, kk * 2.0))


## A band of light across the felt (and only the felt), centred at `x`.
func _sheen(x: float) -> void:
	var band := PackedVector2Array([Vector2(x - 40, -150), Vector2(x + 10, -150), Vector2(x + 40, 10), Vector2(x - 10, 10)])
	for poly in Geometry2D.intersect_polygons(band, _felt):
		var colours := PackedColorArray()
		for p in poly:
			var along := inverse_lerp(-150.0, 10.0, p.y)
			var mid := lerpf(x - 15.0, x + 25.0, along)
			var a := 0.2 * maxf(0.0, 1.0 - absf(p.x - mid) / 28.0)
			colours.append(Color(1.0 * a, 0.925 * a, 0.745 * a, a))
		draw_polygon(poly, colours)


func _draw_cloth() -> void:
	var kk := _ease_io(clampf((k - 0.08) / 0.8, 0.0, 1.0))
	var y := lerpf(PRINT.position.y, PRINT.end.y, kk)
	var below := Rect2(PRINT.position.x, y, PRINT.size.x, PRINT.end.y - y)
	var above := Rect2(PRINT.position, Vector2(PRINT.size.x, y - PRINT.position.y))
	if below.size.y > 0.0:
		draw_texture_rect_region(_old, below, _src(below))
	if above.size.y > 0.0:
		draw_texture_rect_region(_new, above, _src(above))
	if kk <= 0.0 or kk >= 1.0:
		return
	# the roll of new cloth, and its shadow on the old
	_band(Rect2(-200, y + 3, 400, 7), func(t: float): return Color(0, 0, 0, 0.4 * (1.0 - t)))
	var f := _felt_colour
	_band(Rect2(-200, y - 5, 400, 8), func(t: float):
		var c: Color
		if t < 0.25:
			c = Color(f.darkened(0.55), 0.0).lerp(f.darkened(0.35), t / 0.25)
		elif t < 0.55:
			c = f.darkened(0.35).lerp(f.lightened(0.22), (t - 0.25) / 0.3)
		elif t < 0.8:
			c = f.lightened(0.22).lerp(f.darkened(0.2), (t - 0.55) / 0.25)
		else:
			c = f.darkened(0.2).lerp(f.darkened(0.6), (t - 0.8) / 0.2)
		return c)


## `r` cut to the felt, shaded down its height by `shade(0..1)`.
func _band(r: Rect2, shade: Callable) -> void:
	var rect := PackedVector2Array([r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)])
	for poly in Geometry2D.intersect_polygons(rect, _felt):
		var colours := PackedColorArray()
		for p in poly:
			var c: Color = shade.call(clampf((p.y - r.position.y) / r.size.y, 0.0, 1.0))
			colours.append(Color(c.r * c.a, c.g * c.a, c.b * c.a, c.a))
		draw_polygon(poly, colours)


# ------------------------------------------------------------------ gold dust
func _make_dust(old_img: Image, new_img: Image) -> void:
	var src := _ink(old_img)
	var dst := _ink(new_img)
	for i in PARTICLES:
		var a: Vector2 = src[randi() % src.size()]
		var b: Vector2 = dst[randi() % dst.size()]
		_sparks.append({"a": a, "b": b, "c": Vector2((a.x + b.x) / 2.0 + randf_range(-40, 40), minf(a.y, b.y) - randf_range(10, 46)),
			"d": randf_range(0.0, 0.14), "s": randf_range(0.5, 1.15), "tw": randf_range(0.0, 6.0)})
	_dust = Node2D.new()
	var mat := CanvasItemMaterial.new()
	mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	_dust.material = mat
	_dust.draw.connect(_draw_dust)
	add_child(_dust)


## Where a printing has ink (in table coordinates), found by trying random points.
func _ink(img: Image) -> Array:
	var out := []
	var w := img.get_width()
	var h := img.get_height()
	for i in PARTICLES * 30:
		var x := randi() % w
		var y := randi() % h
		if img.get_pixel(x, y).a > 0.4:
			out.append(PRINT.position + Vector2(x, y) / PPU)
			if out.size() >= PARTICLES:
				break
	if out.is_empty():
		out.append(Vector2(0, -64))
	return out


func _draw_dust() -> void:
	var now := Time.get_ticks_msec()
	var fade := minf(clampf(k / 0.12, 0.0, 1.0), 1.0 - clampf((k - 0.82) / 0.16, 0.0, 1.0))
	if fade <= 0.0:
		return
	for p in _sparks:
		var e := _ease_io(clampf((k - 0.06 - p.d) / 0.74, 0.0, 1.0))
		var u := 1.0 - e
		var at: Vector2 = u * u * p.a + 2.0 * u * e * p.c + e * e * p.b
		var a := fade * (0.55 + 0.45 * sin(now / 90.0 + p.tw))
		var s: float = p.s
		_dust.draw_rect(Rect2(at - Vector2(s, s) / 2.0, Vector2(s, s)), Color(_gold, a))
		if s > 1.0:
			_dust.draw_circle(at, s * 1.6, Color(_gold, a * 0.25))


# ------------------------------------------------------------------ the machines
func _equipment(t: CasinoTable) -> Dictionary:
	var out := {}
	for path in ["Felt/Machines", "Felt/Fixtures"]:
		var layer := t.get_node_or_null(path)
		if layer:
			for n in layer.get_children():
				if n is CardShuffler:
					out["shuffler"] = n
				elif n is CardShoe:
					out["shoe"] = n
				elif n is DiscardRack:
					out["rack"] = n
	return out


func _place_machines() -> void:
	var old := _equipment(from_table)
	var new := _equipment(to_table)
	for key in ["shuffler", "shoe", "rack"]:
		var a: Node2D = old.get(key)
		var b: Node2D = new.get(key)
		if a and b:
			_machines.append({"node": b, "from": a.position, "to": b.position, "kind": "both"})
			b.position = a.position
			a.visible = false
		elif a:
			_machines.append({"node": a, "from": a.position, "to": a.position + Vector2(26, 0), "kind": "out"})
		elif b:
			_machines.append({"node": b, "from": b.position + Vector2(26, 0), "to": b.position, "kind": "in"})
			b.position = b.position + Vector2(26, 0)
			b.modulate.a = 0.0


func _move_machines(w: Dictionary) -> void:
	var k_out := clampf(inverse_lerp(w.out[0], w.out[1], k), 0.0, 1.0)
	var k_in := clampf(inverse_lerp(w["in"][0], w["in"][1], k), 0.0, 1.0)
	var k_both := clampf(inverse_lerp(w.out[0], w["in"][1], k), 0.0, 1.0)
	for m in _machines:
		var n: Node2D = m.node
		if not is_instance_valid(n):
			continue
		match m.kind:
			"both":
				n.position = m.from.lerp(m.to, _ease_io(k_both))
			"out":
				n.position = m.from.lerp(m.to, k_out * k_out * k_out)
				n.modulate.a = 1.0 - k_out
			"in":
				n.position = m.from.lerp(m.to, 1.0 - pow(1.0 - k_in, 3.0))
				n.modulate.a = k_in


# ------------------------------------------------------------------ the chairs
## Six seats to five or back: the new table's chairs start where the old ones were and slide into place (the
## sitters, re-seated by the snapshot that follows, move with them); the chair that goes fades away.
func _place_chairs() -> void:
	if from_table.seat_count() == to_table.seat_count() or mapping.size() != to_table.seat_count():
		return
	for seat in to_table.seat_count():
		var marker := to_table.get_node_or_null("Seat%d" % seat) as Node2D
		if marker == null:
			continue
		var was := int(mapping[seat])
		var from := from_table.seat_pos(was) if was >= 0 else marker.position
		_markers.append({"node": marker, "from": from, "to": marker.position})
		marker.position = from
	to_table.place_chair_backs()
	var gone := -1
	var kept := mapping.map(func(x): return int(x))   # (JSON numbers are floats: `in` needs ints)
	for seat in from_table.seat_count():
		if not seat in kept:
			gone = seat
	if gone >= 0:
		_ghost_chair = GhostChair.new()
		_ghost_chair.table = from_table
		_ghost_chair.seat = gone
		_ghost_from = from_table.chair_pos(gone)
		var nearest := to_table.seat_pos(0)
		for m in _markers:
			if absf(m.to.x - _ghost_from.x) < absf(nearest.x - _ghost_from.x):
				nearest = m.to
		_ghost_to = (_ghost_from + nearest) / 2.0
		_ghost_chair.position = _ghost_from
		to_table.add_child(_ghost_chair)


func _move_chairs(v: float) -> void:
	if _markers.is_empty():
		return
	var e := _ease_io(v)
	for m in _markers:
		m.node.position = m.from.lerp(m.to, e)
	to_table.place_chair_backs()
	to_table.move_sitters()
	to_table.redraw_chairs()
	if _ghost_chair:
		_ghost_chair.position = _ghost_from.lerp(_ghost_to, e)
		_ghost_chair.modulate.a = 1.0 - v


## The chair that goes, drawn as the old table drew it.
class GhostChair extends Node2D:
	var table: CasinoTable
	var seat := 0

	func _draw() -> void:
		if is_instance_valid(table):
			table.draw_chair(self, seat, "seat", Vector2.ZERO)
			table.draw_chair(self, seat, "back", Vector2.ZERO)


# ------------------------------------------------------------------ the dealer, and the end
func _bob() -> void:
	var dealer := to_table.dealer
	var tw := dealer.create_tween()
	tw.tween_method(func(v: float): dealer.dip = -2.5 * sin(PI * v), 0.0, 1.0, 0.6 / speed)
	tw.tween_callback(func(): dealer.dip = 0.0)


func _finish() -> void:
	if _done:
		return
	_done = true
	if is_instance_valid(to_table):
		for m in _markers:
			m.node.position = m.to
		for m in _machines:
			if m.kind != "out" and is_instance_valid(m.node):
				m.node.position = m.to
				m.node.modulate.a = 1.0
		if not _markers.is_empty():
			to_table.place_chair_backs()
			to_table.move_sitters()
			to_table.redraw_chairs()
		to_table._felt.layer = "all"
		(to_table._felt as TableFelt).release()
	if _ghost_chair and is_instance_valid(_ghost_chair):
		_ghost_chair.queue_free()
	if is_instance_valid(from_table):
		from_table.queue_free()
	queue_free()


static func _ease_io(v: float) -> float:
	return 2.0 * v * v if v < 0.5 else 1.0 - pow(-2.0 * v + 2.0, 2.0) / 2.0


static func _back_out(v: float) -> float:
	var c := 1.7
	return 1.0 + (c + 1.0) * pow(v - 1.0, 3.0) + c * pow(v - 1.0, 2.0)
