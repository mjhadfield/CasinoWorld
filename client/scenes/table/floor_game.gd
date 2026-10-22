@tool
class_name FloorGame
extends Node2D
## Anything on the casino floor you can sit at and play: a table (CasinoTable) or a slot
## cabinet (SlotCabinet). The floor talks to every one of them through this: where its
## seats and stools are, who's sitting in them, the glowing SIT stools while you walk,
## and the snapshot/event feed from the server.
##
## Animation steps go through _after() and _tween(), which belong to an epoch node a fresh
## snapshot frees -- so nothing left over from before a resync runs over the new state.

@export var table_id := "tcp_1"
## How many seats it has (the Seat0.. markers say where).
@export var seats := 6

## "" or "seated" (the local player is sitting here).
var mode := "":
	set(v):
		mode = v
		queue_redraw()
var my_seat := -1
## While the local player is walking the floor (not sitting anywhere), the free
## stools glow with SIT on them: click one to sit there, or stand on it and press E.
var offer_seats := false:
	set(v):
		offer_seats = v
		queue_redraw()
var occupants := {}   # seat -> {entity, name, human}
## Chairs someone's sitting down in or getting out of: seat -> {theta, press, offset} (see Seating).
var chair_state := {}
var chair_side := {}  # seat -> which side of it its sitter got on from (1 or -1), to get off the same way
var _backs := {}      # seat -> its ChairBack (the back drawn over its sitter)
var sitters := {}     # seat -> who's sitting there (the node that moves), so they move with the chairs
## Whether any of it is in the camera's view (a VisibleOnScreenNotifier2D round it says): off
## screen, nothing that's only for show is redrawn every frame (see breathes_now()).
var on_screen_now := false
var phase := ""
var _queue: Array[Callable] = []
var _busy_until := 0.0
var _epoch: Node          # owns the pending animation timers and tweens (see _after/_tween)

const STOOL_R := 10.0
const STOOL_SQUASH := 0.6


# ------------------------------------------------------------------ the server's feed
## A sound at a spot at this table, from its game's sound set, heard nearby only.
func sfx_at(key: String, at: Vector2, trim_db := 0.0) -> void:
	Sfx.play_at(key, at, trim_db, table_id)


## The table or cabinet a node belongs to ("" if it's on none), for its sound set.
static func table_of(node: Node) -> String:
	while node != null and not node is FloorGame:
		node = node.get_parent()
	return (node as FloorGame).table_id if node != null else ""


## A `table_state`: draw it as it is, at once.
func apply_snapshot(_state: Dictionary) -> void:
	pass


## A `table_event`: queue its animation.
func handle_event(_ev: Dictionary) -> void:
	pass


# ------------------------------------------------------------------ geometry
func seat_count() -> int:
	return seats


## Where a seat is on the floor (its Seat marker): where its sitter's feet go while the table
## shows upright, and what stand_pos() and the server's seat points are measured from.
func seat_pos(seat: int) -> Vector2:
	var marker := get_node_or_null("Seat%d" % seat) as Node2D
	return marker.position if marker else Vector2.ZERO


## Where a seat's chair stands and its sitter sits, as the screen shows it: seat_pos(), drawn in
## towards the table by chair_tuck() while it shows upside down or on its side.
func chair_pos(seat: int) -> Vector2:
	return seat_pos(seat) + chair_tuck()


## How far the chairs are drawn in from their seats, in the table's frame (see CasinoTable).
func chair_tuck() -> Vector2:
	return Vector2.ZERO


## A seat's stool: just behind the sitter as the screen sees it (as at a cabinet), so it
## moves to the other side of the chair while a turned table shows upside down.
func stool_pos(seat: int) -> Vector2:
	return chair_pos(seat) + on_screen(Vector2(0, -4))


## How the table shows on screen, in quarter turns as an angle: 0 upright, PI upside down
## (a turned table to someone walking past, or an upright one while you sit at a turned one).
func screen_turn() -> float:
	return snappedf(wrapf(global_rotation, -PI, PI), PI / 2) if is_inside_tree() else rotation


## Whether the table shows on its side (a quarter turn either way), its dealer to our left or right.
func sideways() -> bool:
	return is_equal_approx(absf(screen_turn()), PI / 2)


## An offset as the screen sees it (up is up), in the table's coordinates: for things placed
## about a sitter, who's always upright -- their stool, the ring round them, their Ready tick.
func on_screen(offset: Vector2) -> Vector2:
	return offset.rotated(-screen_turn())


## The free, glowing chair (or standing spot) under `local` (local coordinates), or -1.
func stool_at(local: Vector2) -> int:
	if not offer_seats:
		return -1
	for seat in free_seats():
		if seat_pose() == "sit":
			if Seating.hit_box(Seating.style(table_id)).has_point((local - chair_pos(seat)).rotated(screen_turn())):
				return seat
			continue
		var d := local - stool_pos(seat)
		if Vector2(d.x, d.y / STOOL_SQUASH).length() <= STOOL_R + 3.0:
			return seat
	return -1


## Where someone stands after getting up from a seat.
func stand_pos(seat: int) -> Vector2:
	return seat_pos(seat) + Vector2(0, 22)


## The point the camera centres on when you're here.
func focus_point() -> Vector2:
	return to_global(Vector2(0, -42))


## How players take a seat: "sit" on a stool, or "idle" (standing at the rail, at Craps).
func seat_pose() -> String:
	return "sit"


## Which way someone sitting in a seat faces (everyone faces the dealer, "up", at a table),
## in the table's own frame.
func sit_facing(_seat: int) -> String:
	return "up"


## A direction in the table's frame, as the floor sees it: a table can be turned (a
## blackjack pit's far row is upside down, `rotation` PI, its dealers' backs to the pit).
func world_dir(dir: String) -> String:
	return Looks.dir_from(Avatar.dir_vector(dir).rotated(rotation), dir)


## Whether someone sitting here draws over everything around (1: over a table's rail) or
## takes the floor's Y-sort (0: behind a slot cabinet whose screen faces away).
func sit_z(_seat: int) -> int:
	return 1


# ------------------------------------------------------------------ chairs
## Where a seat's chair back points at rest (behind its sitter), in the table's frame.
func rest_theta(seat: int) -> float:
	return (-Avatar.dir_vector(sit_facing(seat))).angle()


## Move a chair while someone sits down or gets up (Seating's sit_down and stand_up).
func set_chair(seat: int, key: String, value) -> void:
	if not chair_state.has(seat):
		chair_state[seat] = {}
	chair_state[seat][key] = value
	redraw_chairs()


func rest_chair(seat: int) -> void:
	chair_state.erase(seat)
	redraw_chairs()


## The chairs' colours ({frame, upholstery}), where the table's style gives them (the card tables and
## Roulette); empty keeps the seating style's own (slot cabinets).
func chair_colours() -> Dictionary:
	return {}


func redraw_chairs() -> void:
	queue_redraw()
	for b in _backs.values():
		b.queue_redraw()


## A seat's chair in `ci`, from its origin at `at` (ci's coordinates, which are the table's
## turned or not): "seat" is what's under the sitter, "back" what's over them. A free chair
## glows while you're walking.
func draw_chair(ci: CanvasItem, seat: int, layer: String, at: Vector2) -> void:
	var st := Seating.style(table_id, chair_colours())
	var glow := offer_seats and not occupants.has(seat) and not Engine.is_editor_hint()
	var pulse := 0.55 + 0.45 * sin(Time.get_ticks_msec() / 1000.0 * 5.0) if glow and Settings.value("seat_glow") else 0.8
	var cs: Dictionary = chair_state.get(seat, {})
	var turn := screen_turn()
	at += cs.get("offset", Vector2.ZERO)
	var theta := float(cs.get("theta", rest_theta(seat))) + turn
	Seating.draw_chair(ci, at, -turn, theta, float(cs.get("press", 0.0)), st, layer, glow, pulse)


## Whether a free chair's glow takes a breath this frame: a few times a second while it's on
## screen, each table on a frame of its own so they don't all land on the same one (and never,
## with Settings' seat glow off: it glows steadily).
func breathes_now() -> bool:
	return offer_seats and on_screen_now and (Engine.get_process_frames() + get_instance_id()) % 4 == 0 \
		and Settings.value("seat_glow")


## Each chair's back gets a node of its own, just behind its sitter in the floor's Y-sort (and
## at their z while they're there), so a back between them and us draws over them.
func _notification(what: int) -> void:
	if what != NOTIFICATION_READY or Engine.is_editor_hint():
		return
	if seat_pose() == "sit":
		for seat in seat_count():
			var b := ChairBack.new()
			b.game = self
			b.seat = seat
			add_child(b)
			_backs[seat] = b
		place_chair_backs()
	var seen := VisibleOnScreenNotifier2D.new()
	seen.name = "OnScreen"
	seen.rect = footprint().grow(48.0)
	seen.screen_entered.connect(func():
		on_screen_now = true
		redraw_chairs())   # (whatever changed while it was out of sight)
	seen.screen_exited.connect(func(): on_screen_now = false)
	add_child(seen)


## Everything it covers in its own coordinates: its collision shapes and its chairs, with
## room for whoever sits in them (as tools/floor_map.gd measures a table).
func footprint() -> Rect2:
	var into := global_transform.affine_inverse()
	var r := Rect2(-20, -20, 40, 40)
	for n in find_children("*", "CollisionShape2D", true, false) + find_children("*", "CollisionPolygon2D", true, false):
		var pts := PackedVector2Array()
		if n is CollisionPolygon2D:
			pts = n.polygon
		elif n.shape is CircleShape2D:
			pts = [Vector2(-1, -1) * n.shape.radius, Vector2(1, 1) * n.shape.radius]
		elif n.shape is RectangleShape2D:
			pts = [-n.shape.size / 2.0, n.shape.size / 2.0]
		for q in pts:
			r = r.expand(into * (n.global_transform * q))
	for seat in seat_count():
		r = r.merge(Rect2(chair_pos(seat) + Vector2(-16, -44), Vector2(32, 52)))
	return r


func place_chair_backs() -> void:
	for seat in _backs:
		_backs[seat].position = chair_pos(seat) + Vector2(0, 0.5).rotated(-rotation)
		_backs[seat].queue_redraw()


## The chairs moved (the table shows a different way up): everyone sitting in them moves too,
## except whoever's still sitting down or getting up (Seating puts them in the chair at the end).
func move_sitters() -> void:
	for seat in sitters.keys():
		var who = sitters[seat]
		if not is_instance_valid(who):
			sitters.erase(seat)
		elif not Seating.busy(who):
			who.position = (who.get_parent() as Node2D).to_local(to_global(chair_pos(seat)))


func free_seats() -> Array:
	var free := []
	for i in seat_count():
		if not occupants.has(i):
			free.append(i)
	return free


# ------------------------------------------------------------------ animation epochs
## A one-shot timer for a later animation step: `_after(t).timeout.connect(...)`. It (and
## every _tween()) belongs to the current epoch, which a snapshot frees -- so steps left
## over from before a resync never run over the fresh state.
func _after(seconds: float) -> Timer:
	var timer := Timer.new()
	timer.one_shot = true
	timer.wait_time = maxf(seconds, 0.001)
	timer.timeout.connect(timer.queue_free)
	_anim_root().add_child(timer)
	timer.start()
	return timer


func _tween() -> Tween:
	return _anim_root().create_tween()


func _anim_root() -> Node:
	if _epoch == null:
		_epoch = Node.new()
		_epoch.name = "Anim"
		add_child(_epoch)
	return _epoch


## Drops every pending step (a snapshot replaces whatever they were animating).
func _new_epoch() -> void:
	_queue.clear()
	_busy_until = 0.0
	if _epoch:  # out of the tree, its timers and tweens stop at once
		remove_child(_epoch)
		_epoch.queue_free()
		_epoch = null


# ------------------------------------------------------------------ drawing
## A seat's chair, under its sitter (glowing while it's free and you're walking the floor;
## its back is drawn by its ChairBack).
func _draw_stool(seat: int, _glow: bool, _pulse: float) -> void:
	draw_chair(self, seat, "seat", chair_pos(seat))
