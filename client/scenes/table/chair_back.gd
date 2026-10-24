class_name ChairBack
extends Node2D
## The back of one of a FloorGame's chairs, drawn over whoever sits in it when it's between
## them and us (see FloorGame._notification). While someone
## sits there it's at their z (1); empty, it's on the floor's (0), so passers-by in front of it
## draw over it. A second box's chair, nobody in it, carries its RESERVED sign here, over the whole chair.

var game: FloorGame
var seat := 0
# what it was last drawn for
var _drawn := false
var _offering := false
var _free := false
var _reserved := false
var _turn := 0.0


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS   # (the RESERVED sign, drawn far smaller than it's built)


func _process(_delta: float) -> void:
	var free := not game.occupants.has(seat)
	var turn := game.screen_turn()
	var reserved := game.reserved(seat)
	if not _drawn or free != _free or reserved != _reserved or game.offer_seats != _offering or turn != _turn:
		_drawn = true
		_free = free
		_reserved = reserved
		_offering = game.offer_seats
		_turn = turn
		z_index = 0 if free else 1
		queue_redraw()
	elif free and game.breathes_now():   # (a glowing chair breathes: redrawn a few times a second)
		queue_redraw()


func _draw() -> void:
	game.draw_chair(self, seat, "back", Vector2(0, -0.5).rotated(-game.rotation))
