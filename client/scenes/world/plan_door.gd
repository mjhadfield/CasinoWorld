class_name PlanDoor
extends Node2D
## A door in a room's wall (PlanRoom): drawn shut, it swings open while anyone's near (the local player and
## everyone in group "door_openers") and closes behind them. A door with no room beyond (`locked`) never opens; its
## wall stays solid. Doors never block walking -- the gap in the wall bodies is what lets people through.

const NEAR := 46.0    # px from the doorway's middle that opens it
const BRASS := Color("c9a24a")
const GLASS := Color(0.6, 0.8, 0.9, 0.6)

var side := "top"
var gap := Rect2()
var wood := Color("3a1a12")
var locked := false
var _open := 0.0       # 0 shut .. 1 open
var _want := 0.0
var _check := 0.0


func setup(o: Dictionary, g: Rect2, colour: Color, is_locked: bool) -> void:
	side = str(o.side)
	gap = g
	wood = colour
	locked = is_locked
	z_index = -4


func _process(delta: float) -> void:
	if locked:
		return
	_check -= delta
	if _check <= 0.0:
		_check = 0.15
		var mid := to_global(gap.get_center())
		_want = 0.0
		for n in get_tree().get_nodes_in_group("door_openers"):
			if n.is_visible_in_tree() and (n as Node2D).global_position.distance_to(mid) < NEAR + gap.size.length() / 2.0:
				_want = 1.0
				break
	if not is_equal_approx(_open, _want):
		_open = move_toward(_open, _want, delta * 4.0)
		queue_redraw()


func _draw() -> void:
	var g := gap
	match side:
		"top":   # two panelled leaves in the back wall, swinging in
			var leaf := g.size.x / 2.0 * (1.0 - _open * 0.85)
			for left in [true, false]:
				var r := Rect2(g.position.x if left else g.end.x - leaf, 8, leaf, g.size.y - 12)
				draw_rect(r, wood)
				draw_rect(r.grow(-3), wood.lightened(0.08), false, 1.5)
				if leaf > 8:
					draw_circle(Vector2(r.end.x - 4 if left else r.position.x + 4, r.get_center().y + 4), 1.8, BRASS)
		"bottom":   # glass doors in the front wall, sliding apart
			var leaf := g.size.x / 2.0 * (1.0 - _open * 0.9)
			draw_rect(Rect2(g.position.x, g.position.y - 2, leaf, g.size.y), GLASS)
			draw_rect(Rect2(g.end.x - leaf, g.position.y - 2, leaf, g.size.y), GLASS)
			draw_rect(Rect2(g.position.x, g.position.y - 2, leaf, g.size.y), BRASS, false, 1.0)
			draw_rect(Rect2(g.end.x - leaf, g.position.y - 2, leaf, g.size.y), BRASS, false, 1.0)
		_:   # a side door: seen edge-on, a leaf across the gap that folds back against the wall
			var len := g.size.y * (1.0 - _open * 0.85)
			draw_rect(Rect2(g.position.x, g.position.y, g.size.x, len), wood)
			draw_rect(Rect2(g.position.x, g.position.y, g.size.x, len), wood.lightened(0.1), false, 1.0)
