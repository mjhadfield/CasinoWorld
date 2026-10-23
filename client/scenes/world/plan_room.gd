class_name PlanRoom
extends Node2D
## One room of the floor plan (the server's plan.py; the welcome's `world`), built here from its data: the floor
## (a tiled texture, tinted, with patches), the walls drawn in code (the back wall a 70px band in 3/4 view with its
## wallpaper, wainscot, brass trim, sign and lamps; the sides and front a dark edge), its doorways cut through them,
## the wall bodies with those gaps left open, and everything placed in it: tables, slot cabinets, pieces and
## standing figures. NPCs' points and no-go zones come too. It sits on the plan at (x, y); everything in it is
## placed from that corner, and it Y-sorts along with the rest of World.
##
## A doorway joins it to the room beyond (`to`). An archway is just open; a door is drawn shut until someone comes
## near, then swings open (PlanDoor). A door with no room beyond stays shut, and its wall stays solid.
##
## An NPCs-only room (a lift: NPCs appear in it and leave by it) has a bar across each of its doorways that only
## you bump into -- it's no navigation obstacle, so NPCs path straight through -- and its doors don't open for you.

const FONT := preload("res://assets/fonts/DejaVuSans-Bold.ttf")
const CARPET := preload("res://assets/tiles/carpet.png")
const SLOT_CABINET := preload("res://scenes/slots/slot_cabinet.tscn")
const AVATAR := preload("res://scenes/world/avatar.tscn")
const PODIUM := preload("res://scenes/world/pit_podium.gd")
const TABLE_SCENES := {
	"three_card_poker": preload("res://scenes/table/tcp_table.tscn"),
	"blackjack": preload("res://scenes/table/bj_table.tscn"),
	"pai_gow_fortune": preload("res://scenes/table/pg_table.tscn"),
	"pai_gow_face_up": preload("res://scenes/table/pg_table.tscn"),
	"mississippi_stud": preload("res://scenes/table/ms_table.tscn"),
	"ultimate_texas_holdem": preload("res://scenes/table/uth_table.tscn"),
	"let_it_ride": preload("res://scenes/table/lir_table.tscn"),
	"high_card_flush": preload("res://scenes/table/hcf_table.tscn"),
	"baccarat": preload("res://scenes/table/bac_table.tscn"),
	"roulette": preload("res://scenes/table/rou_table.tscn"),
	"craps": preload("res://scenes/table/crp_table.tscn"),
	"master_table": preload("res://scenes/table/master_table.tscn"),   # (blank: the floor swaps in its game's table)
}
const SIGN := {"back": Color("120406"), "rim": Color("f2c14e"), "text": Color("ffd76a")}
const BRASS := Color("c9a24a")
const GLASS := Color(0.6, 0.8, 0.9, 0.6)

var id := ""
var data := {}
var rect := Rect2()         # on the plan (walls included)
var wall := {"top": 70.0, "side": 8.0, "bottom": 10.0}
var style := {}
var points := {}            # "room/name" -> {"at": Vector2 on the plan, "kind"}
var games: Array[FloorGame] = []   # its tables and cabinets (the floor registers them)
var openings: Array = []
var npc_only := false


## Make the room from its data (`world`: the rest of the welcome's world, for the wall sizes and styles).
func build(room: Dictionary, world: Dictionary) -> void:
	data = room
	id = str(room.id)
	name = "Room_" + id
	position = Vector2(float(room.x), float(room.y))
	rect = Rect2(position, Vector2(float(room.w), float(room.h)))
	y_sort_enabled = true
	var w: Dictionary = world.get("walls", {})
	wall = {"top": float(w.get("top", 70)), "side": float(w.get("side", 8)), "bottom": float(w.get("bottom", 10))}
	style = world.get("styles", {}).get(str(room.get("walls", {}).get("style", "crimson")), {})
	openings = room.get("openings", [])
	npc_only = bool(room.get("npc_only", false))
	var npc_rooms := {}   # (this one and those beyond its doorways that are NPCs only)
	for r in world.get("rooms", []):
		if r.get("npc_only", false):
			npc_rooms[str(r.id)] = true
	var floor_layer := Node2D.new()
	floor_layer.name = "Floor"
	floor_layer.z_index = -10
	floor_layer.texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED
	floor_layer.draw.connect(_draw_floor.bind(floor_layer))
	PlanArt.art_changed.connect(floor_layer.queue_redraw)   # (a floor texture from the library came in)
	add_child(floor_layer)
	var walls := Node2D.new()
	PlanArt.art_changed.connect(walls.queue_redraw)
	walls.name = "Walls"
	walls.z_index = -5
	walls.texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED
	walls.draw.connect(_draw_walls.bind(walls))
	add_child(walls)
	_build_wall_bodies()
	for o in openings:
		if o.kind == "door" or o.get("to") == null:
			var d := PlanDoor.new()
			d.setup(o, _gap(o), _door_colour(), o.get("to") == null)
			d.npcs_only = npc_rooms.has(id) or npc_rooms.has(str(o.get("to")))
			add_child(d)
		if npc_only and o.get("to") != null:
			_bar_players(_gap(o))
	for item in room.get("items", []):
		_place(item)
	_build_zones(room.get("zones", []))
	for p in room.get("points", []):
		points["%s/%s" % [id, p.name]] = {"at": position + Vector2(float(p.x), float(p.y)), "kind": str(p.kind)}


## Where a point inside this room is, on the plan.
func contains(at: Vector2) -> bool:
	return rect.has_point(at)


# ------------------------------------------------------------------ what's placed in it
func _place(item: Dictionary) -> void:
	var at := Vector2(float(item.x), float(item.y))
	var asset := str(item.asset)
	if asset.begins_with("table:"):
		var game := str(item.get("game", asset.substr(6)))
		if not TABLE_SCENES.has(game):
			return
		var t: CasinoTable = TABLE_SCENES[game].instantiate()
		t.table_id = str(item.id)            # (set before it's in the tree: several scenes default to tcp_1)
		t.game_label = str(item.get("name", t.game_label))
		t.game = game
		if game == "pai_gow_face_up":
			t.face_up = true
		t.sign_side = str(item.get("props", {}).get("sign", ""))
		t.is_master = game == "master_table"
		t.position = at
		t.rotation = deg_to_rad(float(item.get("rot", 0)))
		t.add_to_group("navigation_obstacles")
		add_child(t)
		games.append(t)
	elif asset == "slot":
		var c: SlotCabinet = SLOT_CABINET.instantiate()
		c.table_id = str(item.id)
		c.variant = str(item.get("props", {}).get("variant", "armadillo"))
		c.look = item.get("cabinet", {})
		c.position = at
		c.add_to_group("navigation_obstacles")
		add_child(c)
		c.facing = str(item.get("facing", "down"))
		games.append(c)
	elif asset == "podium":
		var p := StaticBody2D.new()
		p.set_script(PODIUM)
		p.name = "Podium_" + str(item.id)
		p.position = at
		p.add_to_group("navigation_obstacles")
		var shape := CollisionShape2D.new()
		var r := RectangleShape2D.new()
		r.size = Vector2(30, 10)
		shape.shape = r
		shape.position = Vector2(0, -4)
		p.add_child(shape)
		add_child(p)
	elif asset == "npc":
		var a: Avatar = AVATAR.instantiate()
		var props: Dictionary = item.get("props", {})
		a.look = str(props.get("look", "dealer"))
		a.display_name = str(props.get("name", ""))
		a.facing = str(item.get("facing", "down"))
		a.position = at
		add_child(a)
		a.add_body().get_parent().add_to_group("navigation_obstacles")   # (they stay put: taps walk round them)
	elif asset.begins_with("a:"):
		var f := Furniture.new()
		if f.setup(item):
			f.position = at
			add_child(f)


## No-go zones: NPC-only ones on collision layer 2 (only the navigation bake sees them; players walk through, as
## the classic pit's fence), the rest on layer 1 (nobody walks there).
func _build_zones(zones: Array) -> void:
	for z in zones:
		var body := StaticBody2D.new()
		body.add_to_group("navigation_obstacles")
		if z.kind == "npc_block":
			body.collision_layer = 2
			body.collision_mask = 0
		var shape := CollisionShape2D.new()
		var r := RectangleShape2D.new()
		r.size = Vector2(float(z.w), float(z.h))
		shape.shape = r
		shape.position = Vector2(float(z.x), float(z.y)) + r.size / 2.0
		body.add_child(shape)
		add_child(body)


## A body across a doorway on layer 1, which you collide with; left out of the navigation bake, so NPCs walk through.
func _bar_players(g: Rect2) -> void:
	var body := StaticBody2D.new()
	body.name = "PlayerBar"
	var shape := CollisionShape2D.new()
	var r := RectangleShape2D.new()
	r.size = g.size
	shape.shape = r
	shape.position = g.get_center()
	body.add_child(shape)
	add_child(body)


# ------------------------------------------------------------------ the walls
## A doorway's gap through this room's wall, in the room's coordinates.
func _gap(o: Dictionary) -> Rect2:
	var lo := float(o.at) - float(o.width) / 2.0
	var w := float(o.width)
	match str(o.side):
		"top":
			return Rect2(lo, 0, w, wall.top)
		"bottom":
			return Rect2(lo, rect.size.y - wall.bottom, w, wall.bottom)
		"left":
			return Rect2(0, lo, wall.side, w)
		_:
			return Rect2(rect.size.x - wall.side, lo, wall.side, w)


## The wall bodies: each wall in pieces, with the doorways that lead somewhere left open.
func _build_wall_bodies() -> void:
	var body := StaticBody2D.new()
	body.name = "WallBodies"
	body.add_to_group("navigation_obstacles")
	add_child(body)
	var size := rect.size
	var sides := {
		"top": Rect2(0, 0, size.x, wall.top), "bottom": Rect2(0, size.y - wall.bottom, size.x, wall.bottom),
		"left": Rect2(0, 0, wall.side, size.y), "right": Rect2(size.x - wall.side, 0, wall.side, size.y)}
	for side in sides:
		var r: Rect2 = sides[side]
		var along: bool = side in ["top", "bottom"]
		var cuts := []
		for o in openings:
			if o.side == side and o.get("to") != null:
				var g := _gap(o)
				cuts.append([g.position.x, g.end.x] if along else [g.position.y, g.end.y])
		cuts.sort_custom(func(a, b): return a[0] < b[0])
		var start: float = r.position.x if along else r.position.y
		var stop: float = r.end.x if along else r.end.y
		var pieces := []
		for c in cuts:
			if c[0] > start:
				pieces.append([start, c[0]])
			start = maxf(start, c[1])
		if stop > start:
			pieces.append([start, stop])
		for p in pieces:
			var shape := CollisionShape2D.new()
			var box := RectangleShape2D.new()
			var piece := Rect2(p[0], r.position.y, p[1] - p[0], r.size.y) if along else Rect2(r.position.x, p[0], r.size.x, p[1] - p[0])
			box.size = piece.size
			shape.shape = box
			shape.position = piece.get_center()
			body.add_child(shape)


func _c(key: String, fallback: String) -> Color:
	return Color(str(style.get(key, fallback)))


func _door_colour() -> Color:
	return _c("wainscot", "2b0a10").lightened(0.15)


func _draw_floor(ci: CanvasItem) -> void:
	var fl: Dictionary = data.get("floor", {})
	_paint(ci, Rect2(Vector2.ZERO, rect.size), str(fl.get("texture", "carpet")), Color(str(fl.get("tint", "#ffffff"))))
	for p in data.get("patches", []):
		_draw_patch(ci, p)


func _paint(ci: CanvasItem, r: Rect2, texture: String, tint: Color) -> void:
	var tex: Texture2D = CARPET if texture == "carpet" else PlanArt.floor_texture(texture)
	if tex == null:
		ci.draw_rect(r, tint)
	else:
		ci.draw_texture_rect(tex, r, true, tint)


## A floor patch: its floor inside its outline, the pattern over that, the border inside the edge. The admin's
## plan/draw.js draws the same shapes.
func _draw_patch(ci: CanvasItem, p: Dictionary) -> void:
	var r := Rect2(float(p.x), float(p.y), float(p.w), float(p.h))
	var texture := str(p.get("texture", "plain"))
	var tint := Color(str(p.get("tint", "#ffffff")))
	var shape := _patch_outline(r, p, 0.0)
	if str(p.get("shape", "rect")) == "rect":
		_paint(ci, r, texture, tint)
	else:
		var tex: Texture2D = CARPET if texture == "carpet" else PlanArt.floor_texture(texture)
		var pts := _solid(shape)
		if pts.size() < 3:
			pass
		elif tex == null:
			ci.draw_colored_polygon(pts, tint)
		else:   # (the floor layer repeats textures, so the UVs tile from the patch's corner)
			var uvs := PackedVector2Array()
			for q in pts:
				uvs.append((q - r.position) / tex.get_size())
			ci.draw_colored_polygon(pts, tint, uvs, tex)
	var pat: Dictionary = p.get("pattern", {})
	if str(pat.get("kind", "none")) != "none":
		var colour := Color(str(pat.get("colour", "#000000")), float(pat.get("opacity", 30)) / 100.0)
		for poly in _pattern_shapes(r.size, pat):
			for i in poly.size():
				poly[i] += r.position
			if Array(poly).all(func(q: Vector2): return Geometry2D.is_point_in_polygon(q, shape)):
				ci.draw_colored_polygon(poly, colour)
			else:
				for piece in Geometry2D.intersect_polygons(poly, shape):
					ci.draw_colored_polygon(piece, colour)
	var bor: Dictionary = p.get("border", {})
	var width := float(bor.get("width", 6))
	var colour := Color(str(bor.get("colour", "#c9a24a")))
	var rings := []
	match str(bor.get("style", "none")):
		"line":
			rings = [[0.0, width, colour]]
		"double":
			var t := maxf(1.0, width / 4.0)
			rings = [[0.0, t, colour], [width - t, width, colour]]
		"inlay":
			rings = [[0.0, width, colour]]
			if width >= 3.0:
				rings += [[0.0, 1.0, colour.darkened(0.5)], [width - 1.0, width, colour.darkened(0.5)]]
	for ring in rings:
		var outer := _patch_outline(r, p, ring[0])
		var inner := _patch_outline(r, p, ring[1])
		for i in outer.size():
			var j := (i + 1) % outer.size()
			var quad := _solid(PackedVector2Array([outer[i], outer[j], inner[j], inner[i]]))
			if quad.size() >= 3:
				ci.draw_colored_polygon(quad, ring[2])


## `pts` without repeats (a rounded corner of no radius is one point many times), so it triangulates; fewer than
## three points left, or no area, is nothing to draw.
func _solid(pts: PackedVector2Array) -> PackedVector2Array:
	var out := PackedVector2Array()
	for q in pts:
		if out.is_empty() or out[-1].distance_squared_to(q) > 0.0001:
			out.append(q)
	if out.size() > 1 and out[0].distance_squared_to(out[-1]) <= 0.0001:
		out.remove_at(out.size() - 1)
	var area := 0.0
	for i in out.size():
		area += out[i].cross(out[(i + 1) % out.size()])
	return out if out.size() >= 3 and absf(area) > 0.01 else PackedVector2Array()


## A patch's outline, `inset` in from its edge; the same number of points at any inset (so a border is quads).
func _patch_outline(r: Rect2, p: Dictionary, inset: float) -> PackedVector2Array:
	var x := r.position.x + inset
	var y := r.position.y + inset
	var w := maxf(0.0, r.size.x - 2.0 * inset)
	var h := maxf(0.0, r.size.y - 2.0 * inset)
	var out := PackedVector2Array()
	match str(p.get("shape", "rect")):
		"oval":
			for i in 64:
				var a := PI * i / 32.0
				out.append(Vector2(x + w / 2.0 + w / 2.0 * cos(a), y + h / 2.0 + h / 2.0 * sin(a)))
		"rounded":
			var rad := maxf(0.0, minf(float(p.get("radius", 24)) - inset, minf(w / 2.0, h / 2.0)))
			for c in [[x + w - rad, y + rad, -90.0], [x + w - rad, y + h - rad, 0.0], [x + rad, y + h - rad, 90.0], [x + rad, y + rad, 180.0]]:
				for k in 7:
					var a := deg_to_rad(c[2] + 15.0 * k)
					out.append(Vector2(c[0] + rad * cos(a), c[1] + rad * sin(a)))
		_:
			out = PackedVector2Array([Vector2(x, y), Vector2(x + w, y), Vector2(x + w, y + h), Vector2(x, y + h)])
	return out


## The pattern's shapes over a patch of `size`, from its corner (they run past the edge; the outline clips them).
func _pattern_shapes(size: Vector2, pat: Dictionary) -> Array[PackedVector2Array]:
	var s := float(pat.get("size", 32))
	var nx := ceili(size.x / s)
	var ny := ceili(size.y / s)
	var out: Array[PackedVector2Array] = []
	match str(pat.kind):
		"stripes":
			for i in nx:
				out.append(_box(i * s, 0, s / 2.0, size.y))
		"diagonal":
			var k := -size.y
			while k < size.x:
				out.append(PackedVector2Array([Vector2(k, 0), Vector2(k + s / 2.0, 0), Vector2(k + s / 2.0 + size.y, size.y), Vector2(k + size.y, size.y)]))
				k += s
		"checks":
			for i in nx:
				for j in range(i % 2, ny, 2):
					out.append(_box(i * s, j * s, s, s))
		"diamonds":
			for i in nx + 1:
				for j in ny + 1:
					var c := Vector2(i * s, j * s)
					out.append(PackedVector2Array([c + Vector2(0, -s / 2.0), c + Vector2(s / 2.0, 0), c + Vector2(0, s / 2.0), c + Vector2(-s / 2.0, 0)]))
		"dots":
			for i in nx:
				for j in ny:
					var dot := PackedVector2Array()
					for k in 16:
						dot.append(Vector2(i * s + s / 2.0, j * s + s / 2.0) + Vector2(cos(PI * k / 8.0), sin(PI * k / 8.0)) * s / 4.0)
					out.append(dot)
		"grid":   # (the uprights stop at the rails, so nothing's drawn twice)
			var lw := maxf(1.0, roundf(s / 16.0))
			for j in ny + 1:
				out.append(_box(0, j * s - lw / 2.0, size.x, lw))
			for i in nx + 1:
				for j in ny:
					out.append(_box(i * s - lw / 2.0, j * s + lw / 2.0, lw, s - lw))
	return out


func _box(x: float, y: float, w: float, h: float) -> PackedVector2Array:
	return PackedVector2Array([Vector2(x, y), Vector2(x + w, y), Vector2(x + w, y + h), Vector2(x, y + h)])


func _draw_walls(ci: CanvasItem) -> void:
	var size := rect.size
	var top: float = wall.top
	var edge := _c("edge", "1a0508")
	var trim := _c("trim", "c9a24a")
	# The back wall: wallpaper with its stripe, the wainscot, brass trim, a dark rail.
	ci.draw_rect(Rect2(0, 0, size.x, top), _c("paper", "4a0f1d"))
	for x in range(0, int(size.x), 24):
		ci.draw_rect(Rect2(x, 0, 10, top * 0.6), _c("stripe", "561526"))
	ci.draw_rect(Rect2(0, top * 0.6, size.x, top * 0.31), _c("wainscot", "2b0a10"))
	ci.draw_rect(Rect2(0, top - 8, size.x, 4), trim)
	ci.draw_rect(Rect2(0, top - 4, size.x, 4), edge)
	# Side and front walls.
	ci.draw_rect(Rect2(0, 0, wall.side, size.y), edge)
	ci.draw_rect(Rect2(size.x - wall.side, 0, wall.side, size.y), edge)
	ci.draw_rect(Rect2(0, size.y - wall.bottom, size.x, wall.bottom), edge)
	var gaps: Array[Rect2] = []
	for o in openings:
		gaps.append(_gap(o))
	# Lamps along the back wall, clear of the doorways and the sign.
	var sign_text := str(data.get("walls", {}).get("sign", ""))
	var sign_w := clampf(sign_text.length() * 12.0 + 40.0, 120.0, 420.0)
	var sign_rect := Rect2(float(data.get("walls", {}).get("sign_at", size.x / 2)) - sign_w / 2, 6, sign_w, 30)
	var lamps := maxi(2, int(size.x / 240.0))
	for i in lamps:
		var at := Vector2(size.x * (i + 0.5) / lamps, 24)
		if (sign_text != "" and sign_rect.grow(14).has_point(at)) or gaps.any(func(g: Rect2): return g.grow(10).has_point(at)):
			continue
		ci.draw_circle(at, 7, Color(1, 0.85, 0.5, 0.25))
		ci.draw_circle(at, 3.5, Color("ffe6a8"))
	if sign_text != "":
		ci.draw_rect(sign_rect, SIGN.back)
		ci.draw_rect(sign_rect, SIGN.rim, false, 2.0)
		ci.draw_string(FONT, Vector2(sign_rect.position.x, 28), sign_text, HORIZONTAL_ALIGNMENT_CENTER, sign_w, 18, SIGN.text)
	# The doorways: the floor carries on through the gap, framed in brass.
	for o in openings:
		var g := _gap(o)
		_paint(ci, g, str(data.get("floor", {}).get("texture", "carpet")), Color(str(data.get("floor", {}).get("tint", "#ffffff"))))
		match str(o.side):
			"top":
				ci.draw_rect(Rect2(g.position.x - 5, 0, 5, g.size.y), trim)
				ci.draw_rect(Rect2(g.end.x, 0, 5, g.size.y), trim)
				ci.draw_rect(Rect2(g.position.x - 5, 0, g.size.x + 10, 6), trim.darkened(0.25))
			"bottom":
				ci.draw_rect(Rect2(g.position.x - 4, g.position.y - 2, 4, g.size.y + 2), trim)
				ci.draw_rect(Rect2(g.end.x, g.position.y - 2, 4, g.size.y + 2), trim)
			_:
				ci.draw_rect(Rect2(g.position.x - 2, g.position.y - 3, g.size.x + 4, 6), BRASS)
				ci.draw_rect(Rect2(g.position.x - 2, g.end.y - 3, g.size.x + 4, 6), BRASS)
