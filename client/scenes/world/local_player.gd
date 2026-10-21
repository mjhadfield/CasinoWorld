extends CharacterBody2D
## You. Keyboard (WASD/arrows), click/tap-to-walk, or click and hold to keep
## walking towards the pointer (as the view follows you, the pointer stays ahead,
## so you can cross the whole floor that way). Movement is client-side
## and reported to the server (move) ~10 times a second, so everyone else
## sees you walk around; the server still owns every game result.
##
## Positions are in the floor's frame (World, our parent), which the floor turns to
## show a turned table the right way up -- so the keys still move you across the
## screen, and a tap still walks you to where you tapped.

const SEND_INTERVAL := 0.1

@export var speed := 105.0

@onready var avatar: Avatar = $Avatar
var controls_enabled := true
var _tap_target: Variant = null  # Vector2 while walking to a tap
var _holding := false            # the button's held down: the target follows the pointer
var _send_timer := 0.0
var _last_sent := {}


func _physics_process(delta: float) -> void:
	if not controls_enabled:
		return
	var frame := get_parent() as Node2D
	if _holding:
		if Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
			_tap_target = frame.get_local_mouse_position()
		else:
			_holding = false  # let go: finish the walk to the last point, like a tap
	var dir := Input.get_vector("move_left", "move_right", "move_up", "move_down").rotated(-frame.global_rotation)
	if dir != Vector2.ZERO:
		_tap_target = null
		_holding = false
	elif _tap_target != null:
		var to_target: Vector2 = _tap_target - position
		if to_target.length() < 3.0:
			if not _holding:  # held over yourself: just wait for the pointer to move on
				_tap_target = null
		else:
			dir = to_target.normalized()
	velocity = dir.rotated(frame.global_rotation) * speed   # (velocity is global)
	move_and_slide()
	if _tap_target != null and not _holding and get_slide_collision_count() > 0 \
			and get_real_velocity().length() < speed * 0.25:
		_tap_target = null  # walked into something on the way to a tap (a held walk slides on)
	var moving := get_real_velocity().length() > 5.0
	avatar.set_action("walk" if moving else "idle", Looks.dir_from(dir, avatar.facing))
	_send_timer -= delta
	if _send_timer <= 0.0:
		_send_timer = SEND_INTERVAL
		_report()


func _unhandled_input(event: InputEvent) -> void:
	if not controls_enabled:
		return
	# Touch is emulated as a left click. HUD buttons consume their own clicks first.
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_tap_target = (get_parent() as Node2D).get_local_mouse_position()
		_holding = true


## Walk towards `pos` as if it had been tapped (stops at anything in the way).
func walk_to(pos: Vector2) -> void:
	if controls_enabled:
		_tap_target = pos
		_holding = false


func is_walking_to_target() -> bool:
	return _tap_target != null


## Where you're walking to (null if nowhere).
func target() -> Variant:
	return _tap_target


## Halt and forget any tap target.
func stop() -> void:
	velocity = Vector2.ZERO
	_tap_target = null
	_holding = false
	avatar.set_action("idle")


func set_controls(enabled: bool) -> void:
	controls_enabled = enabled
	if not enabled:
		stop()
		_report()


## Glide to a chair and sit down, facing `facing` (`pose` "idle": stand at the rail instead).
func sit_at(pos: Vector2, facing: String, pose := "sit", z := 1) -> void:
	set_controls(false)
	$Collision.disabled = true
	avatar.z_index = z  # 1: over the table rail, whatever the Y-sort says (0 behind a slot cabinet)
	avatar.name_below = true
	var tween := create_tween()
	avatar.set_action("walk", Looks.dir_from(pos - position, facing))
	tween.tween_property(self, "position", pos, 0.35)
	tween.tween_callback(func(): avatar.set_action(pose, facing))


## Stand up next to the chair, then walk freely again.
func stand_at(pos: Vector2) -> void:
	avatar.z_index = 0
	avatar.name_below = false
	var tween := create_tween()
	avatar.set_action("walk")
	tween.tween_property(self, "position", pos, 0.3)
	tween.tween_callback(func():
		$Collision.disabled = false
		avatar.set_action("idle", "down")
		set_controls(true))


func _report() -> void:
	var msg := {"x": snappedf(position.x, 0.1), "y": snappedf(position.y, 0.1),
		"dir": avatar.facing, "anim": avatar.action if avatar.action != "sit" else "idle"}
	if not (Session.on_floor and Net.is_open()):
		_last_sent = {}  # say where we are once we've joined: a fresh join puts us at the entrance
		return
	if msg != _last_sent:
		_last_sent = msg
		Net.send("move", msg)
