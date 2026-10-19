@tool
extends Node2D
## The casino's walls and entrance, drawn in code. For now the floor is a
## compact test room holding just the game tables; it gets redesigned once
## the tables are built. The room is SIZE wide/tall; collisions live in the
## floor scene's Walls body.

const FONT := preload("res://assets/fonts/DejaVuSans-Bold.ttf")
const SIZE := Vector2(1900, 1160)
const DOOR_X := 700.0  # the entrance (the room grew east for the wheel games)
const WALL_H := 70.0


func _draw() -> void:
	# Back wall: striped wallpaper, dark wainscot, gold trim.
	draw_rect(Rect2(0, 0, SIZE.x, WALL_H), Color("4a0f1d"))
	for x in range(0, int(SIZE.x), 24):
		draw_rect(Rect2(x, 0, 10, 42), Color("561526"))
	draw_rect(Rect2(0, 42, SIZE.x, 22), Color("2b0a10"))
	draw_rect(Rect2(0, 62, SIZE.x, 4), Color("c9a24a"))
	draw_rect(Rect2(0, 66, SIZE.x, 4), Color("1a0508"))
	# Sign over the floor.
	var sign_rect := Rect2(SIZE.x / 2 - 150, 6, 300, 30)
	draw_rect(sign_rect, Color("120406"))
	draw_rect(sign_rect, Color("f2c14e"), false, 2.0)
	draw_string(FONT, Vector2(sign_rect.position.x, 28), "HADFIELD CASINO", HORIZONTAL_ALIGNMENT_CENTER, 300, 18, Color("ffd76a"))
	# Wall lamps.
	for f in [0.12, 0.32, 0.68, 0.88]:
		draw_circle(Vector2(SIZE.x * f, 24), 7, Color(1, 0.85, 0.5, 0.25))
		draw_circle(Vector2(SIZE.x * f, 24), 3.5, Color("ffe6a8"))
	# Side and front walls.
	draw_rect(Rect2(0, 0, 8, SIZE.y), Color("1a0508"))
	draw_rect(Rect2(SIZE.x - 8, 0, 8, SIZE.y), Color("1a0508"))
	draw_rect(Rect2(0, SIZE.y - 10, SIZE.x, 10), Color("1a0508"))
	# Entrance doors.
	var door := DOOR_X
	draw_rect(Rect2(door - 44, SIZE.y - 14, 88, 14), Color("c9a24a"))
	draw_rect(Rect2(door - 40, SIZE.y - 12, 39, 10), Color(0.6, 0.8, 0.9, 0.6))
	draw_rect(Rect2(door + 1, SIZE.y - 12, 39, 10), Color(0.6, 0.8, 0.9, 0.6))
