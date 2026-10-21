@tool
extends Node2D
## The casino's walls and entrance, drawn in code: the main floor (SIZE, the
## compact room holding the game tables until the floor is redesigned) and the
## Blackjack pit room east of it (PIT), through a doorway in the shared wall.
## Collisions live in the floor scene's Walls body.

const FONT := preload("res://assets/fonts/DejaVuSans-Bold.ttf")
const SIZE := Vector2(1900, 1160)
const PIT := Rect2(1900, 0, 1000, 1160)
const DOORWAY := Vector2(780, 880)  # the opening in the shared wall, top to bottom
const DOOR_X := 700.0  # the entrance (the room grew east for the wheel games)
const WALL_H := 70.0
const WALL := Color("1a0508")


func _draw() -> void:
	_back_wall(Rect2(Vector2.ZERO, SIZE), "HADFIELD CASINO", 300)
	_back_wall(PIT, "BLACKJACK", 200)
	# Side and front walls, with the doorway left open between the two rooms.
	draw_rect(Rect2(0, 0, 8, SIZE.y), WALL)
	draw_rect(Rect2(PIT.end.x - 8, 0, 8, PIT.size.y), WALL)
	draw_rect(Rect2(0, SIZE.y - 10, PIT.end.x, 10), WALL)
	for side in [[0.0, DOORWAY.x], [DOORWAY.y, SIZE.y]]:
		draw_rect(Rect2(SIZE.x - 8, side[0], 16, side[1] - side[0]), WALL)
	for y in [DOORWAY.x, DOORWAY.y]:  # brass door jambs
		draw_rect(Rect2(SIZE.x - 10, y - 3, 20, 6), Color("c9a24a"))
	# Entrance doors.
	var door := DOOR_X
	draw_rect(Rect2(door - 44, SIZE.y - 14, 88, 14), Color("c9a24a"))
	draw_rect(Rect2(door - 40, SIZE.y - 12, 39, 10), Color(0.6, 0.8, 0.9, 0.6))
	draw_rect(Rect2(door + 1, SIZE.y - 12, 39, 10), Color(0.6, 0.8, 0.9, 0.6))


## A room's back wall: striped wallpaper, dark wainscot, gold trim, a sign and lamps.
func _back_wall(room: Rect2, title: String, sign_w: float) -> void:
	var x0 := room.position.x
	var w := room.size.x
	draw_rect(Rect2(x0, 0, w, WALL_H), Color("4a0f1d"))
	for x in range(int(x0), int(x0 + w), 24):
		draw_rect(Rect2(x, 0, 10, 42), Color("561526"))
	draw_rect(Rect2(x0, 42, w, 22), Color("2b0a10"))
	draw_rect(Rect2(x0, 62, w, 4), Color("c9a24a"))
	draw_rect(Rect2(x0, 66, w, 4), WALL)
	var sign_rect := Rect2(x0 + w / 2 - sign_w / 2, 6, sign_w, 30)
	draw_rect(sign_rect, Color("120406"))
	draw_rect(sign_rect, Color("f2c14e"), false, 2.0)
	draw_string(FONT, Vector2(sign_rect.position.x, 28), title, HORIZONTAL_ALIGNMENT_CENTER, sign_w, 18, Color("ffd76a"))
	for f in [0.12, 0.32, 0.68, 0.88]:
		draw_circle(Vector2(x0 + w * f, 24), 7, Color(1, 0.85, 0.5, 0.25))
		draw_circle(Vector2(x0 + w * f, 24), 3.5, Color("ffe6a8"))
