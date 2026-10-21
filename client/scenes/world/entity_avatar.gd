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
var _pending_walk := []   # [pos, duration]: a walk that came while they were still getting up


## A reported position from another player.
func apply_move(pos: Vector2, dir: String, anim: String) -> void:
	if seated or Seating.busy(self):
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
	if Seating.busy(self):
		_pending_walk = [pos, duration]
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
	if seated or Seating.busy(self):
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


## Sit on `game`'s `seat` (or stand at the craps rail), as Seating plays it -- or, not
## `animate` (a snapshot: they were already sitting when we looked), straight there.
func sit_at(game: FloorGame, seat: int, animate := true) -> void:
	_walking = false
	_target_pos = null
	_pending_walk = []
	z_index = game.sit_z(seat)
	name_below = true
	if seated and position.distance_to(get_parent().to_local(game.to_global(game.chair_pos(seat)))) < 1.0:
		if not Seating.busy(self):   # (a fresh snapshot of someone already sat there)
			set_action(game.seat_pose(), game.world_dir(game.sit_facing(seat)))
		return
	if seated:
		Seating.stop(self, game)
		animate = false   # (moved seats while we weren't looking)
	seated = true
	Seating.sit_down(self, self, game, seat, animate)


func stand_at(game: FloorGame, seat: int) -> void:
	seated = false
	name_below = false
	Seating.stand_up(self, self, game, seat, func():
		z_index = 0
		set_action("idle", "down")
		if not _pending_walk.is_empty():
			walk_to(_pending_walk[0], _pending_walk[1])
			_pending_walk = [])
