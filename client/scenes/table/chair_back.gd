class_name ChairBack
extends Node2D
## The back of one of a FloorGame's chairs, drawn over whoever sits in it when it's between
## them and us (see FloorGame._notification). While someone
## sits there it's at their z (1); empty, it's on the floor's (0), so passers-by in front of it
## draw over it.

var game: FloorGame
var seat := 0
var _seen := []   # what it was last drawn for: [offering, free, turn]


func _process(_delta: float) -> void:
	var seen := [game.offer_seats, not game.occupants.has(seat), game.screen_turn()]
	z_index = 0 if seen[1] else 1
	# (a glowing chair breathes: redrawn a few times a second, not every frame)
	if seen != _seen or (game.offer_seats and seen[1] and Engine.get_process_frames() % 4 == 0):
		_seen = seen
		queue_redraw()


func _draw() -> void:
	game.draw_chair(self, seat, "back", Vector2(0, -0.5).rotated(-game.rotation))
