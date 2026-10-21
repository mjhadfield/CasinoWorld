extends Avatar
## Someone else on the floor: another player (their reported moves are
## smoothed) or an NPC (the server says where to walk and how long to take;
## we path there on the floor's navigation map at the speed that arrives on time).
## Positions are in the floor's frame (World), which is what the server and the
## navigation map use however the view is turned.

const MIN_SPEED := 40.0
const MAX_SPEED := 140.0

var entity_id := ""
var kind := "player"
var seated := false
var _target_pos: Variant = null   # Vector2: smoothing towards a reported position
var _walk_speed := 0.0
var _walking := false
var _path := PackedVector2Array()
var _next := 0   # the path point being walked to


## A reported position from another player.
func apply_move(pos: Vector2, dir: String, anim: String) -> void:
	if seated:
		return
	_walking = false
	_target_pos = pos
	set_action("walk" if anim == "walk" else "idle", dir)


func place(pos: Vector2) -> void:
	position = pos
	_target_pos = null


## An NPC walk: get to `pos` in about `duration` seconds.
func walk_to(pos: Vector2, duration: float) -> void:
	if seated:
		return
	_target_pos = null
	_path = NavigationServer2D.map_get_path(get_world_2d().navigation_map, position, pos, true)
	if _path.size() < 2:  # (no map yet): straight there
		_path = PackedVector2Array([position, pos])
	var length := 0.0
	for i in range(1, _path.size()):
		length += _path[i - 1].distance_to(_path[i])
	_next = 1
	_walk_speed = clampf(length / maxf(duration, 0.1), MIN_SPEED, MAX_SPEED)
	_walking = true


func _physics_process(delta: float) -> void:
	if seated:
		return
	if _walking:
		if _next >= _path.size():
			_walking = false
			set_action("idle")
			return
		var step := _path[_next] - position
		var move := minf(_walk_speed * delta, step.length())
		if step.length() > 0.01:
			position += step.normalized() * move
			set_action("walk", Looks.dir_from(step, facing))
		if move >= step.length() - 0.01:
			_next += 1
	elif _target_pos != null:
		var to: Vector2 = _target_pos - position
		if to.length() > 80.0:  # far behind (lag, tab was hidden): just jump
			position = _target_pos
		else:
			position = position.lerp(_target_pos, minf(1.0, delta * 12.0))
		if to.length() < 0.5 and action == "walk":
			pass  # the next report will say idle


## Sit in a chair at `pos` facing `dir` (snaps if they weren't quite there). `pose` "idle"
## stands them there instead (at the craps rail).
func sit_at(pos: Vector2, dir: String, pose := "sit", z := 1) -> void:
	seated = true
	name_below = true
	_walking = false
	_target_pos = null
	z_index = z
	var tween := create_tween()
	tween.tween_property(self, "position", pos, 0.3 if position.distance_to(pos) < 60 else 0.0)
	tween.tween_callback(func(): set_action(pose, dir))


func stand_at(pos: Vector2) -> void:
	seated = false
	name_below = false
	z_index = 0
	set_action("idle", "down")
	var tween := create_tween()
	tween.tween_property(self, "position", pos, 0.3)
