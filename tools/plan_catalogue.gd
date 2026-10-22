extends SceneTree
# The built-in pieces the floor plan places (plan.py, the admin page's Floor plan tab): every table game and the
# slot cabinet, measured from their scenes. For each game, at each way it can turn: its footprint (its collision
# outline and its chairs with someone sitting in each, and the dealer's head over the top edge when upright), its
# body (just the collision outline: what blocks walking) and where each seat's player stands to sit down. Writes
# server/casino_server/plan_catalogue.json; run it again whenever a table changes shape or a game is added.
#   cd client && CASINO_SERVER_URL=ws://127.0.0.1:9/ws godot --headless --path . -s ../tools/plan_catalogue.gd
# (the server URL keeps the Net autoload off the live server)
const OUT := "res://../server/casino_server/plan_catalogue.json"
const SITTER := Rect2(-12, -36, 24, 44)   # a chair and the player sitting on it, from the chair
const DEALER_HEAD := 24.0                 # the dealer stands at the felt's top edge: their head clears it by this
# game -> [scene, its properties, the turns it may have on the floor (degrees)]. Every card table can be turned
# round (the classic pit's far row is); Roulette and Craps have their own shapes and stay upright for now.
const GAMES := {
	"three_card_poker": ["res://scenes/table/tcp_table.tscn", {"game_label": "Three Card Poker"}, [0, 180]],
	"blackjack": ["res://scenes/table/bj_table.tscn", {"game_label": "Blackjack"}, [0, 180]],
	"pai_gow_fortune": ["res://scenes/table/pg_table.tscn", {"game_label": "Fortune Pai Gow"}, [0, 180]],
	"pai_gow_face_up": ["res://scenes/table/pg_table.tscn", {"game_label": "Face Up Pai Gow", "face_up": true}, [0, 180]],
	"mississippi_stud": ["res://scenes/table/ms_table.tscn", {"game_label": "Mississippi Stud"}, [0, 180]],
	"ultimate_texas_holdem": ["res://scenes/table/uth_table.tscn", {"game_label": "Ultimate Texas Hold'em"}, [0, 180]],
	"let_it_ride": ["res://scenes/table/lir_table.tscn", {"game_label": "Let It Ride"}, [0, 180]],
	"high_card_flush": ["res://scenes/table/hcf_table.tscn", {"game_label": "High Card Flush"}, [0, 180]],
	"baccarat": ["res://scenes/table/bac_table.tscn", {"game_label": "Baccarat"}, [0, 180]],
	"roulette": ["res://scenes/table/rou_table.tscn", {"game_label": "Roulette"}, [0]],
	"craps": ["res://scenes/table/crp_table.tscn", {"game_label": "Craps"}, [0]],
}
const CABINET := "res://scenes/slots/slot_cabinet.tscn"


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
		if (c is CollisionPolygon2D and not c.polygon.is_empty()) or c is CollisionShape2D:
			out.append(shape_rect(c))
		shapes(c, out)


func merged(rects: Array) -> Rect2:
	var r: Rect2 = rects[0]
	for x in rects:
		r = r.merge(x)
	return r


func rect_json(r: Rect2) -> Array:
	return [snappedf(r.position.x, 0.5), snappedf(r.position.y, 0.5), snappedf(r.size.x, 0.5), snappedf(r.size.y, 0.5)]


func point_json(p: Vector2) -> Array:
	return [snappedf(p.x, 0.5), snappedf(p.y, 0.5)]


## A table placed at the origin, turned `degrees`: its shapes measured in the floor's frame.
func measure(path: String, props: Dictionary, degrees: int) -> Dictionary:
	var n: Node2D = load(path).instantiate()
	for k in props:
		n.set(k, props[k])
	n.rotation = deg_to_rad(degrees)
	root.add_child(n)
	await process_frame
	var body := []
	shapes(n, body)
	var all := body.duplicate()
	var stands := []
	for seat in n.seat_count():
		all.append(Rect2(n.to_global(n.chair_pos(seat)) + SITTER.position, SITTER.size))  # (sitters are upright)
		stands.append(point_json(n.to_global(n.stand_pos(seat))))
	var r := merged(all)
	if degrees == 0:
		r = r.grow_side(SIDE_TOP, DEALER_HEAD)
	var out := {"rect": rect_json(r), "body": rect_json(merged(body)), "stands": stands}
	n.queue_free()
	await process_frame
	return out


func _initialize() -> void:
	var games := {}
	for game in GAMES:
		var spec: Array = GAMES[game]
		var at := {}
		for deg in spec[2]:
			at[str(deg)] = await measure(spec[0], spec[1], deg)
		var probe: Node = load(spec[0]).instantiate()
		games[game] = {"name": spec[1]["game_label"], "seats": probe.seats, "rotations": spec[2], "at": at}
		probe.free()
	var cab := {}
	for facing in ["down", "up", "left", "right"]:
		cab[facing] = await measure(CABINET, {"facing": facing}, 0)
	var f := FileAccess.open(OUT, FileAccess.WRITE)
	f.store_string(JSON.stringify({"games": games, "cabinet": cab}, " ", false) + "\n")
	f.close()
	print("plan_catalogue.json: %d games and the slot cabinet" % games.size())
	quit(0)
