class_name Furniture
extends Node2D
## A piece of furniture or decor from the asset library (the floor plan's "a:<id>" items): its picture for the way
## it faces (PlanArt), standing on its base point so it Y-sorts with the people, and a body where it blocks walking.
## Rugs lie flat under everyone; wall pieces hang on the back wall. It shows (and blocks) once its picture has
## downloaded, and changes whenever the library does. A piece with a screen (the jackpot board) gets a PlanScreen.

var asset_id := ""
var facing := "down"
var _pic: Sprite2D
var _body: StaticBody2D
var _screen: PlanScreen


func setup(item: Dictionary) -> bool:
	asset_id = str(item.asset).substr(2)
	facing = str(item.get("facing", "down"))
	name = "Furniture_" + str(item.get("id", asset_id))
	_pic = Sprite2D.new()
	_pic.centered = false
	add_child(_pic)
	_apply()
	PlanArt.art_changed.connect(_apply)
	return true


func _apply() -> void:
	var a := PlanArt.asset(asset_id)
	var pic := PlanArt.picture(asset_id, facing)
	_pic.texture = pic.get("texture")
	if not pic.is_empty():
		var size: Vector2 = pic.texture.get_size()
		_pic.flip_h = pic.mirror
		_pic.offset = -pic.anchor if not pic.mirror else Vector2(-(size.x - pic.anchor.x), -pic.anchor.y)
	match str(a.get("mount", "floor")):
		"flat":
			z_index = -6   # (on the floor, under everyone)
		"wall":
			z_index = -4   # (over the wall it hangs on)
		_:
			z_index = 0
	_apply_screen(a, pic)
	var body = a.get("by_facing", {}).get(facing, {}).get("body", a.get("body"))
	if _body:
		_body.queue_free()
		_body = null
	if body is Array and a.get("mount") == "floor" and not pic.is_empty():
		_body = StaticBody2D.new()
		_body.add_to_group("navigation_obstacles")
		var shape := CollisionShape2D.new()
		var r := RectangleShape2D.new()
		r.size = Vector2(float(body[2]), float(body[3]))
		shape.shape = r
		shape.position = Vector2(float(body[0]), float(body[1])) + r.size / 2.0
		_body.add_child(shape)
		add_child(_body)


func _apply_screen(a: Dictionary, pic: Dictionary) -> void:
	var s = a.get("screen")
	if not s is Dictionary or pic.is_empty():
		if _screen:
			_screen.queue_free()
			_screen = null
		return
	if _screen == null:
		_screen = PlanScreen.new()
		add_child(_screen)
	var r: Array = s.get("rect", [0, 0, 0, 0])
	var size: Vector2 = pic.texture.get_size()
	var x := float(r[0]) if not pic.mirror else size.x - float(r[0]) - float(r[2])
	_screen.kind = str(s.get("show", "jackpot"))
	_screen.rect = Rect2(x, float(r[1]), float(r[2]), float(r[3]))
	_screen.position = _pic.offset
	_screen.queue_redraw()
