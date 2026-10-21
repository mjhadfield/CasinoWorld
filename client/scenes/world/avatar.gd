@tool
class_name Avatar
extends Node2D
## A person on the floor -- the local player, someone else, an NPC or a dealer.
## Origin is at their feet (for Y-sorting). Drivers (local_player.gd,
## entity_avatar.gd) move it; this just shows the look, the name and speech.
##
## They always stand upright on screen, however the world or their table is turned
## (a turned table, or the view turned to it while you sit there). `facing` is the
## way they face in their parent's frame -- a dealer faces "down" across their own
## table -- and the sprite shows that direction as the screen sees it.

const FONT := preload("res://assets/fonts/DejaVuSans-Bold.ttf")

@export var look := "player_default":
	set(v):
		look = v
		if is_node_ready():
			_apply_look()
@export var display_name := "":
	set(v):
		display_name = v
		if is_node_ready():
			_name_tag.text = v
			_name_tag.visible = v != ""
@export_enum("up", "left", "down", "right") var facing := "down":
	set(v):
		facing = v
		if is_node_ready():
			_refresh_anim()

## Where speech bubbles appear. "right" suits the dealer, whose head is at the
## top of the screen when you're seated at their table.
@export_enum("above", "right") var bubble_side := "above"
## A "right" bubble's height (its middle, above their feet): level with their shoulders,
## or higher to sit clear of whoever's beside them (the craps stickman's).
@export var bubble_y := -33.0
## The name goes under their feet (at a table: sitting, or standing at the craps rail).
var name_below := false:
	set(v):
		name_below = v
		if is_node_ready():
			_refresh_anim()

var action := "idle"  # idle | walk | sit
const DIRS := ["up", "right", "down", "left"]   # clockwise, as Godot turns on screen
var _turn := 0        # quarter turns their parent's frame is at on screen
@onready var _sprite: AnimatedSprite2D = $Sprite
@onready var _name_tag: Label = $NameTag
@onready var _bubble: Label = $Bubble
var _bubble_tween: Tween


func _ready() -> void:
	_apply_look()
	if not Engine.is_editor_hint():
		var loader := get_node_or_null("/root/LookLoader")
		if loader:   # a designed look arriving from the server: put it on
			loader.look_ready.connect(func(l: String):
				if l == look:
					_apply_look())
	_name_tag.text = display_name
	_name_tag.visible = display_name != ""
	if not Engine.is_editor_hint():
		_keep_upright()
	_bubble.hide()
	_bubble.z_index = 4   # over chips on the felt (z 1) and the dice (z 2)
	if bubble_side == "right":
		_bubble.position = Vector2(14, -40)
		_bubble.size = Vector2(110, 14)
		_bubble.grow_vertical = Control.GROW_DIRECTION_BOTH
		_bubble.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
		_bubble.autowrap_mode = TextServer.AUTOWRAP_OFF
		_bubble.custom_minimum_size = Vector2.ZERO
		_bubble.size = _bubble.get_minimum_size()
		_bubble.draw.connect(_draw_bubble_tail)


func _process(_delta: float) -> void:
	if not Engine.is_editor_hint():
		_keep_upright()


func _keep_upright() -> void:
	var parent := get_parent() as Node2D
	var turn := posmod(roundi(parent.global_rotation / (PI / 2)), 4) if parent else 0
	if not is_zero_approx(global_rotation):
		global_rotation = 0.0
	if turn != _turn:
		_turn = turn
		_refresh_anim()


## A direction's unit vector ("up" is (0, -1)).
static func dir_vector(dir: String) -> Vector2:
	return {"up": Vector2.UP, "right": Vector2.RIGHT, "down": Vector2.DOWN, "left": Vector2.LEFT}.get(dir, Vector2.DOWN)


## The way they face as the screen shows it.
func screen_facing() -> String:
	var i := DIRS.find(facing)
	return facing if i < 0 else DIRS[(i + _turn) % 4]


func _draw_bubble_tail() -> void:
	# A little tail pointing back at the speaker (down at them, from a raised bubble).
	var h := _bubble.size.y
	var drop := clampf(-33.0 - bubble_y, 0.0, 30.0) * 0.45
	_bubble.draw_colored_polygon(PackedVector2Array([Vector2(0, h * 0.35 + drop * 0.4), Vector2(-5, h * 0.55 + drop),
		Vector2(0, h * 0.75 + drop * 0.2)]), Color(1, 1, 1, 0.95))


func _apply_look() -> void:
	_sprite.sprite_frames = Looks.frames(look)
	_refresh_anim()


## Set what they're doing ("idle", "walk", "sit") and optionally which way they face.
func set_action(new_action: String, new_facing := "") -> void:
	action = new_action
	if new_facing != "":
		facing = new_facing
	_refresh_anim()


func _refresh_anim() -> void:
	# Seated at a table, the name goes under the chair so it doesn't cover their cards.
	_name_tag.position.y = 2.0 if action == "sit" or name_below else -64.0
	var anim := "%s_%s" % [action, screen_facing()]
	if _sprite.sprite_frames and _sprite.sprite_frames.has_animation(anim) and _sprite.animation != anim:
		_sprite.play(anim)
	queue_redraw()


## A speech bubble over their head for `seconds`.
func say(text: String, seconds := 2.6) -> void:
	_bubble.text = text
	if bubble_side == "right":
		_bubble.size = Vector2.ZERO  # shrink to fit the new line
		_bubble.size = _bubble.get_minimum_size()
		_bubble.position = Vector2(14, bubble_y - _bubble.size.y / 2)
	_bubble.show()
	_bubble.modulate.a = 1.0
	if _bubble_tween:
		_bubble_tween.kill()
	_bubble_tween = create_tween()
	_bubble_tween.tween_interval(seconds)
	_bubble_tween.tween_property(_bubble, "modulate:a", 0.0, 0.4)
	_bubble_tween.tween_callback(_bubble.hide)


func _draw() -> void:
	if action != "sit":
		draw_set_transform(Vector2(0, -1), 0, Vector2(1, 0.45))
		draw_circle(Vector2.ZERO, 11.0, Color(0, 0, 0, 0.28))
