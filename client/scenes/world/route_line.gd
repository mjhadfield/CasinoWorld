class_name RouteLine
extends Node2D
## Find's way to a table, drawn on the floor: a dashed brass line along the navigation path, over the carpet and
## under everyone, with a ring pulsing out from where you'd stand. In World's frame, so it turns with the floor.

const COLOUR := Color("ecd396")

var path := PackedVector2Array():
	set(v):
		path = v
		visible = path.size() >= 2
		queue_redraw()
var _t := 0.0


func _ready() -> void:
	z_index = -3   # over the floor, rugs and walls (-10, -6, -5), under the people and tables
	visible = false


func _process(delta: float) -> void:
	if visible:
		_t = fmod(_t + delta, 1.0)
		queue_redraw()


func _draw() -> void:
	if path.size() < 2:
		return
	draw_polyline(path, Color(COLOUR, 0.16), 9.0, true)
	for i in range(1, path.size()):
		draw_dashed_line(path[i - 1], path[i], COLOUR, 3.0, 10.0, true, true)
	var end := path[path.size() - 1]
	draw_arc(end, 10.0 + _t * 16.0, 0, TAU, 32, Color(COLOUR, 1.0 - _t), 2.5, true)
	draw_circle(end, 3.5, COLOUR)
