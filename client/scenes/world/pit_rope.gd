@tool
extends StaticBody2D
## A run of brass stanchions with a red velvet rope between them, closing off the
## Blackjack pit so only the staff inside it can get between the dealers. `posts` are the
## post feet (local; put the origin at the lowest one, for Y-sorting). It blocks walking
## (and the navigation bake) along its whole length.
##
## The posts stand upright on screen however the floor is turned, like the people.

const POST_H := 13.0
const VELVET := Color("8e1b2c")
const VELVET_HI := Color("c23a4c")
const BRASS := Color("c9a24a")
const BRASS_HI := Color("ffe08a")

@export var posts := PackedVector2Array([Vector2.ZERO, Vector2(40, 0)]):
	set(v):
		posts = v
		queue_redraw()
		if is_node_ready():
			_build_collision()
var _shown_turn := 0.0


func _ready() -> void:
	_build_collision()


func _process(_delta: float) -> void:
	if not is_equal_approx(global_rotation, _shown_turn):
		_shown_turn = global_rotation
		queue_redraw()


func _build_collision() -> void:
	for c in get_children():
		if c is CollisionShape2D:
			remove_child(c)
			c.queue_free()
	for i in range(1, posts.size()):
		var a := posts[i - 1]
		var b := posts[i]
		var shape := RectangleShape2D.new()
		shape.size = Vector2(a.distance_to(b) + 6.0, 6.0)
		var c := CollisionShape2D.new()
		c.shape = shape
		c.position = (a + b) / 2.0
		c.rotation = (b - a).angle()
		add_child(c)


func _draw() -> void:
	var up := Vector2.UP.rotated(-global_rotation)   # screen up, in our frame
	for p in posts:   # shadows first
		draw_set_transform(p, -global_rotation, Vector2(1, 0.5))
		draw_circle(Vector2.ZERO, 4.0, Color(0, 0, 0, 0.3))
	draw_set_transform(Vector2.ZERO)
	for i in range(1, posts.size()):   # the rope, sagging between the post tops
		var a := posts[i - 1] + up * (POST_H - 2.0)
		var b := posts[i] + up * (POST_H - 2.0)
		var sag := -up * minf(5.0, a.distance_to(b) * 0.08)
		var pts := PackedVector2Array()
		for k in 13:
			var t := k / 12.0
			pts.append(a.lerp(b, t) + sag * 4.0 * t * (1.0 - t))
		draw_polyline(pts, VELVET, 2.2, true)
		draw_polyline(pts, VELVET_HI, 0.7, true)
	for p in posts:
		draw_set_transform(p, -global_rotation, Vector2(1, 0.5))
		draw_circle(Vector2.ZERO, 3.0, BRASS)
		draw_set_transform(p, -global_rotation)
		draw_line(Vector2.ZERO, Vector2(0, -POST_H), BRASS, 1.6)
		draw_line(Vector2(-0.4, 0), Vector2(-0.4, -POST_H), BRASS_HI, 0.5)
		draw_circle(Vector2(0, -POST_H), 1.8, BRASS_HI)
	draw_set_transform(Vector2.ZERO)
