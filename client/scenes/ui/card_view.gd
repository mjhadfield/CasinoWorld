@tool
class_name CardView
extends Control
## One playing card, drawn in code: a code like "Qs" / "10h" is face up, "??"
## is face down, and "" is an empty slot. Swap _draw for card sprites later.

const FONT := preload("res://assets/fonts/DejaVuSans-Bold.ttf")
const SUITS := {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
const RED := Color("c62828")
const BLACK := Color("1b1b1b")

@export var code := "":
	set(value):
		code = value
		queue_redraw()

var _target := ""  # where the latest show_card() is heading, even mid-animation
var _tween: Tween
var _face := _box(Color("fbfaf5"), Color("c9c4b5"))
var _back := _box(Color("8e1b2b"), Color("f1e2b8"))
var _slot := _box(Color(1, 1, 1, 0.06), Color(1, 1, 1, 0.25))


func _init() -> void:
	custom_minimum_size = Vector2(84, 118)
	mouse_filter = MOUSE_FILTER_IGNORE


func _ready() -> void:
	_target = code
	resized.connect(func(): pivot_offset = size / 2)
	pivot_offset = size / 2


## Change the card with a little animation: deal in (from empty), or flip (from face down).
func show_card(new_code: String, delay := 0.0) -> void:
	if new_code == _target:
		return
	var from := _target
	_target = new_code
	if _tween:  # a newer update wins: snap the old animation to where it was going
		_tween.kill()
		_tween = null
		scale = Vector2.ONE
		modulate.a = 1.0
		code = from
	if new_code == "" or Engine.is_editor_hint():
		code = new_code
		return
	var tween := create_tween()
	_tween = tween
	tween.tween_interval(delay)
	if code == "??" and new_code != "??":
		tween.tween_property(self, "scale:x", 0.0, 0.12)
		tween.tween_callback(func(): code = new_code)
		tween.tween_property(self, "scale:x", 1.0, 0.12)
	else:
		tween.tween_callback(func():
			code = new_code
			scale = Vector2(0.6, 0.6)
			modulate.a = 0.0)
		tween.set_parallel()
		tween.tween_property(self, "scale", Vector2.ONE, 0.18).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		tween.tween_property(self, "modulate:a", 1.0, 0.12)


func _draw() -> void:
	var rect := Rect2(Vector2.ZERO, size)
	if code == "":
		draw_style_box(_slot, rect)
	elif code == "??":
		draw_style_box(_back, rect)
		draw_rect(rect.grow(-9), Color(1, 1, 1, 0.12), false, 2.0)
	else:
		draw_style_box(_face, rect)
		var rank := code.substr(0, code.length() - 1)
		var suit: String = SUITS.get(code.right(1), "?")
		var colour := RED if code.right(1) in ["h", "d"] else BLACK
		draw_string(FONT, Vector2(7, 24), rank, HORIZONTAL_ALIGNMENT_LEFT, -1, 20, colour)
		draw_string(FONT, Vector2(7, 44), suit, HORIZONTAL_ALIGNMENT_LEFT, -1, 18, colour)
		draw_string(FONT, Vector2(0, size.y * 0.72), suit, HORIZONTAL_ALIGNMENT_CENTER, size.x, 46, colour)


static func _box(bg: Color, border: Color) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = bg
	box.border_color = border
	box.set_border_width_all(2)
	box.set_corner_radius_all(8)
	return box
