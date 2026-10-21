extends SceneTree
# The floor map the admin page's Floor tab draws and the server checks slot banks against (slot_banks.py):
# the room, each table's footprint (its collision outline and its chairs, with someone sitting in each) and
# the named floor points NPCs walk to. Writes server/casino_server/floor_map.json; run it again whenever a table
# moves or changes shape (a server test checks the tables against casino_floor.tscn).
#   cd client && godot --headless --path . -s ../tools/floor_map.gd
const OUT := "res://../server/casino_server/floor_map.json"
const SITTER := Rect2(-12, -36, 24, 44)   # a chair and the player sitting on it, from the chair
const DEALER_HEAD := 24.0                 # the dealer stands at the felt's top edge: their head clears it by this

func bounds(points: PackedVector2Array, xf: Transform2D) -> Rect2:
	var r := Rect2(xf * points[0], Vector2.ZERO)
	for p in points:
		r = r.expand(xf * p)
	return r

func shape_rect(n: Node) -> Rect2:
	if n is CollisionPolygon2D:
		return bounds(n.polygon, n.global_transform)
	var s := (n as CollisionShape2D).shape
	var half := Vector2(s.radius, s.radius) if s is CircleShape2D else (s as RectangleShape2D).size / 2
	return bounds(PackedVector2Array([-half, half]), n.global_transform)

func shapes(n: Node, out: Array) -> void:
	for c in n.get_children():
		if c.name == "SitZone":
			continue
		if c is CollisionPolygon2D or c is CollisionShape2D:
			out.append(shape_rect(c))
		shapes(c, out)

func rect_json(r: Rect2) -> Array:
	return [snappedf(r.position.x, 0.5), snappedf(r.position.y, 0.5), snappedf(r.size.x, 0.5), snappedf(r.size.y, 0.5)]

func _initialize() -> void:
	var floor_scene: Node = load("res://scenes/world/casino_floor.tscn").instantiate()
	var tables := []
	var points := {}
	for n in floor_scene.get_children():
		if n.get("table_id") != null and n.scene_file_path.begins_with("res://scenes/table/"):
			floor_scene.remove_child(n)
			n.owner = null
			root.add_child(n)
			await process_frame
			var rects := []
			shapes(n, rects)
			for seat in n.seat_count():
				rects.append(Rect2(n.global_position + n.chair_pos(seat) + SITTER.position, SITTER.size))
			var r: Rect2 = rects[0]
			for x in rects:
				r = r.merge(x)
			r = r.grow_side(SIDE_TOP, DEALER_HEAD)
			tables.append({"id": n.table_id, "name": n.get("game_label") if n.get("game_label") else n.table_id,
				"x": n.position.x, "y": n.position.y, "rect": rect_json(r)})
	for m in floor_scene.get_node("Points").get_children():
		points[str(m.name)] = [m.position.x, m.position.y]
	var room: Vector2 = floor_scene.get_node("Room").SIZE
	var out := {"room": [room.x, room.y], "walkable": [14, 74, room.x - 28, room.y - 88], "tables": tables, "points": points}
	var f := FileAccess.open(OUT, FileAccess.WRITE)
	f.store_string(JSON.stringify(out, " ") + "\n")
	f.close()
	print("floor_map.json: %d tables, %d points" % [tables.size(), points.size()])
	quit(0)
