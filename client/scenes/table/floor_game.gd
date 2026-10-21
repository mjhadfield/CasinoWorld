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


func chair_pos(seat: int) -> Vector2:
	var marker := get_node_or_null("Seat%d" % seat) as Node2D
	return marker.position if marker else Vector2.ZERO


## A seat's stool: just behind the sitter as the screen sees it (as at a cabinet), so it
## moves to the other side of the chair while a turned table shows upside down.
func stool_pos(seat: int) -> Vector2:
	return chair_pos(seat) + on_screen(Vector2(0, -4))


## How the table shows on screen, in quarter turns as an angle: 0 upright, PI upside down
## (a turned table to someone walking past, or an upright one while you sit at a turned one).
func screen_turn() -> float:
	return snappedf(wrapf(global_rotation, -PI, PI), PI / 2) if is_inside_tree() else rotation


## An offset as the screen sees it (up is up), in the table's coordinates: for things placed
## about a sitter, who's always upright -- their stool, the ring round them, their Ready tick.
func on_screen(offset: Vector2) -> Vector2:
	return offset.rotated(-screen_turn())


## The free, glowing stool under `local` (local coordinates), or -1.
func stool_at(local: Vector2) -> int:
	if not offer_seats:
		return -1
	for seat in free_seats():
		var d := local - stool_pos(seat)
		if Vector2(d.x, d.y / STOOL_SQUASH).length() <= STOOL_R + 3.0:
			return seat
	return -1


## Where someone stands after getting up from a seat.
func stand_pos(seat: int) -> Vector2:
	return chair_pos(seat) + Vector2(0, 22)


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
## A seat's stool (glowing with SIT while it's free and you're walking the floor).
func _draw_stool(seat: int, glow: bool, pulse: float) -> void:
	var p := stool_pos(seat)
	draw_set_transform(p, 0, Vector2(1, STOOL_SQUASH))
	if glow:  # a soft halo, breathing
		draw_circle(Vector2.ZERO, STOOL_R + 2.5 + pulse * 1.5, Color(1, 0.84, 0.3, 0.18 + 0.2 * pulse))
	draw_circle(Vector2(0, 1.2), STOOL_R + 0.5, Color(0, 0, 0, 0.3))
	draw_circle(Vector2.ZERO, STOOL_R, Color("8a5a14") if glow else Color("3b1d0e"))  # mahogany stools, to match the rail
	draw_circle(Vector2(0, -0.8), STOOL_R - 2.0, Color("e7b84a").lerp(Color("ffe08a"), pulse) if glow else Color("6e3a1e"))
	draw_set_transform(Vector2.ZERO)
	if glow:  # (upright to someone walking past a turned table)
		draw_set_transform(p, -rotation)
		draw_string(Card2D.FONT, Vector2(-20, 2.0), "SIT", HORIZONTAL_ALIGNMENT_CENTER, 40, 6, Color(0.25, 0.12, 0.0))
		draw_set_transform(Vector2.ZERO)
