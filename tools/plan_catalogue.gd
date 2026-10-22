extends SceneTree
# The built-in pieces the floor plan places (plan.py, the admin page's Floor plan tab): every table game and the
# slot cabinet, measured from their scenes. For each game, at each way it can turn: its footprint (its collision
# outline, its chairs with someone sitting in each, and its dealers standing), its body (just the collision
# outline: what blocks walking), where each seat's player stands to sit down, and -- for the Floor plan tab to draw
# them the way the game shows them, upright on screen -- where its chairs and dealers are. A table with a results
# sign (Roulette, Craps) also gets the sign's own footprint and base at each end it can stand past, apart from the
# table's: the sign is tall and thin, and merged into the table's footprint it would claim the table's whole width.
# Writes server/casino_server/plan_catalogue.json; run it again whenever a table changes shape or a game is added.
#   cd client && CASINO_SERVER_URL=ws://127.0.0.1:9/ws godot --headless --path . -s ../tools/plan_catalogue.gd
# (the server URL keeps the Net autoload off the live server)
const OUT := "res://../server/casino_server/plan_catalogue.json"
const SITTER := Rect2(-12, -36, 24, 44)   # a chair and the player sitting on it, from the chair
const STANDER := Rect2(-12, -52, 24, 56)  # a dealer standing, from their feet
const CABINET_TOP := 24.0   # a slot cabinet's art rises this far over its collision outline and its sitter
const SIGN := Rect2(-17.6, -157.6, 35.2, 160)   # a results sign (Roulette, Craps), upright from its foot
# game -> [scene, its properties, the turns it may have on the floor (degrees)]. Every table can be turned round
# a quarter turn either way or upside down (the classic pit's far row is).
const GAMES := {
	"three_card_poker": ["res://scenes/table/tcp_table.tscn", {"game_label": "Three Card Poker"}, [0, 90, 180, 270]],
	"blackjack": ["res://scenes/table/bj_table.tscn", {"game_label": "Blackjack"}, [0, 90, 180, 270]],
	"pai_gow_fortune": ["res://scenes/table/pg_table.tscn", {"game_label": "Fortune Pai Gow"}, [0, 90, 180, 270]],
	"pai_gow_face_up": ["res://scenes/table/pg_table.tscn", {"game_label": "Face Up Pai Gow", "face_up": true}, [0, 90, 180, 270]],
	"mississippi_stud": ["res://scenes/table/ms_table.tscn", {"game_label": "Mississippi Stud"}, [0, 90, 180, 270]],
	"ultimate_texas_holdem": ["res://scenes/table/uth_table.tscn", {"game_label": "Ultimate Texas Hold'em"}, [0, 90, 180, 270]],
	"let_it_ride": ["res://scenes/table/lir_table.tscn", {"game_label": "Let It Ride"}, [0, 90, 180, 270]],
	"high_card_flush": ["res://scenes/table/hcf_table.tscn", {"game_label": "High Card Flush"}, [0, 90, 180, 270]],
	"baccarat": ["res://scenes/table/bac_table.tscn", {"game_label": "Baccarat"}, [0, 90, 180, 270]],
	"roulette": ["res://scenes/table/rou_table.tscn", {"game_label": "Roulette"}, [0, 90, 180, 270]],
	"craps": ["res://scenes/table/crp_table.tscn", {"game_label": "Craps"}, [0, 90, 180, 270]],
	# (measured blank; it also gets the five-seat table's stands and chairs: Let It Ride and High Card Flush seat five)
	"master_table": ["res://scenes/table/master_table.tscn", {"game_label": "Master Table"}, [0, 90, 180, 270]],
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
		if c.name == "SitZone" or c.name == "SignBase":   # (the sign's base is measured with the sign)
			continue
		if (c is CollisionPolygon2D and not c.polygon.is_empty()) or c is CollisionShape2D:
			out.append(shape_rect(c))
		shapes(c, out)


func merged(rects: Array) -> Rect2:
	var r: Rect2 = rects[0]
	for x in rects:
		r = r.merge(x)
	return r


## The way someone facing `dir` on a table turned `turn` faces on screen.
func screen_dir(dir: String, turn: float) -> String:
	var dirs := {"down": Vector2.DOWN, "up": Vector2.UP, "left": Vector2.LEFT, "right": Vector2.RIGHT}
	var v: Vector2 = dirs[dir].rotated(turn)
	for d in dirs:
		if v.distance_to(dirs[d]) < 0.5:
			return d
	return dir


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
	await process_frame   # (and a frame for the table to see which way up it shows: its chairs and dealer move)
	await process_frame
	var body := []
	shapes(n, body)
	var all := body.duplicate()
	var stands := []
	var chairs := []
	for seat in n.seat_count():
		var at: Vector2 = n.to_global(n.chair_pos(seat))
		all.append(Rect2(at + SITTER.position, SITTER.size))  # (sitters are upright)
		chairs.append(point_json(at))
		stands.append(point_json(n.to_global(n.stand_pos(seat))))
	var crew := []
	for c in n.get_children():
		if c is Node2D and c.has_method("set_action"):   # the dealer (and Craps' boxman): Avatars
			var at: Vector2 = n.to_global(c.position)
			all.append(Rect2(at + STANDER.position, STANDER.size))
			crew.append({"at": point_json(at), "facing": screen_dir(str(c.facing), n.rotation)})
	var out := {"rect": rect_json(merged(all)), "body": rect_json(merged(body)), "stands": stands,
		"chairs": chairs, "crew": crew}
	var sign := n.get_node_or_null("Sign") as Node2D
	if sign:   # (it stands upright past one end: on a table on its side it rises over whatever's beyond)
		var base := n.get_node("Body/SignBase") as CollisionShape2D
		var r: float = (base.shape as CircleShape2D).radius
		out["sign"] = {}
		for side in ["right", "left"]:
			var sx := 1.0 if side == "right" else -1.0
			var foot: Vector2 = n.to_global(Vector2(sx * absf(sign.position.x), sign.position.y))
			var middle: Vector2 = n.to_global(Vector2(sx * absf(base.position.x), base.position.y))
			out["sign"][side] = {"rect": rect_json(Rect2(foot + SIGN.position, SIGN.size)),
				"body": rect_json(Rect2(middle - Vector2(r, r), Vector2(2 * r, 2 * r))), "foot": point_json(foot)}
		out["sign_default"] = "left" if degrees == 90 else "right"   # (CasinoTable._stand_sign)
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
		if game == "master_table":
			for deg in at:
				at[deg]["stands5"] = games["let_it_ride"].at[deg].stands
				at[deg]["chairs5"] = games["let_it_ride"].at[deg].chairs
	var cab := {}
	for facing in ["down", "up", "left", "right"]:
		var m: Dictionary = await measure(CABINET, {"facing": facing}, 0)
		var r: Array = m.rect
		cab[facing] = {"rect": [r[0], r[1] - CABINET_TOP, r[2], r[3] + CABINET_TOP], "body": m.body, "stands": m.stands}
	var f := FileAccess.open(OUT, FileAccess.WRITE)
	f.store_string(JSON.stringify({"games": games, "cabinet": cab}, " ", false) + "\n")
	f.close()
	print("plan_catalogue.json: %d games and the slot cabinet" % games.size())
	quit(0)
