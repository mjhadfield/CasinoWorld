@tool
extends StaticBody2D
## The pit boss's podium in the middle of the Blackjack pit: a mahogany desk with
## a brass top and a little screen, drawn in code. Origin is its front foot (for
## Y-sorting); the pit boss stands just behind it.

func _draw() -> void:
	draw_set_transform(Vector2(0, -1), 0, Vector2(1, 0.45))
	draw_circle(Vector2.ZERO, 18.0, Color(0, 0, 0, 0.28))
	draw_set_transform(Vector2.ZERO)
	draw_rect(Rect2(-15, -18, 30, 18), Color("3b1d0e"))       # the desk's front
	draw_rect(Rect2(-15, -18, 30, 2), Color("6e3a1e"))
	draw_rect(Rect2(-17, -24, 34, 7), Color("c9a24a"))        # brass top
	draw_rect(Rect2(-16, -23, 32, 5), Color("e7b84a"))
	draw_rect(Rect2(-8, -31, 16, 8), Color("120406"))         # the screen
	draw_rect(Rect2(-7, -30, 14, 6), Color("2f6f8f"))
