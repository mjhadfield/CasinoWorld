class_name FeltCache
extends Node2D
## A table's felt (its rail, felt, chip tray and printed layout: TableFelt), painted once into
## a texture and shown as that one picture. Drawn straight, a felt is three or four hundred
## draw calls every frame (each shape, ring and line of lettering is its own), and three or
## four tables are on screen at once; as a picture it's one. (docs/performance.md)
##
## A copy of the felt's script, the painter, paints it in a SubViewport whenever the felt
## would have redrawn (a snapshot, a hovered spot) -- the felt's own _draw() asks for that
## instead of drawing -- and again when the camera's zoom (or the window) changes how big
## the felt is on screen, so it's always painted at about the screen's own resolution and
## stays as sharp as drawing it straight.

const MARGIN := 10.0      # past the table's Body (the felt's shadow and rail stick out ~6px)
const OVER := 1.25        # painted a little finer than the screen shows it
const RESIZE := 1.2       # painted again once the screen's scale is this far off
const MAX_SIDE := 4096
const AWAY_SCALE := 0.5   # out of sight for a while, it keeps only a small copy (coming back, it's painted again)
const AWAY_AFTER := 3.0

var felt: TableFelt
var _table: CasinoTable
var _vp: SubViewport
var _painter: TableFelt
var _bounds: Rect2        # what's painted, in table coordinates
var _scale := 0.0         # texture pixels per table unit (0: not painted yet)
var _away := 0.0          # seconds out of sight


static func attach(to: TableFelt) -> FeltCache:
	var c := FeltCache.new()
	c.felt = to
	to.add_child(c)
	to.move_child(c, 0)   # under the felt's own children (chips, cards, lights, the wheel)
	return c


func _ready() -> void:
	_table = felt._table()
	position = -felt.position   # table coordinates, like everything else on the felt
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	var mat := CanvasItemMaterial.new()
	mat.blend_mode = CanvasItemMaterial.BLEND_MODE_PREMULT_ALPHA   # (a transparent viewport's colours are premultiplied)
	material = mat
	_bounds = _body_rect().grow(MARGIN)
	_vp = SubViewport.new()
	_vp.transparent_bg = true
	_vp.disable_3d = true
	_vp.canvas_item_default_texture_filter = get_viewport().canvas_item_default_texture_filter
	_vp.render_target_update_mode = SubViewport.UPDATE_DISABLED
	add_child(_vp)
	_painter = felt.get_script().new()
	_painter.painting = true
	_painter.table_ref = _table
	_painter.position = felt.position
	_painter.texture_filter = felt.texture_filter
	_painter.texture_repeat = felt.texture_repeat
	_vp.add_child(_painter)


## The felt changed: paint it again (this frame, before it's shown).
func repaint() -> void:
	if _scale > 0.0:
		_painter.queue_redraw()
		_vp.render_target_update_mode = SubViewport.UPDATE_ONCE


func _process(delta: float) -> void:
	var want: float
	if _scale > 0.0 and not _table.on_screen_now:
		_away += delta
		if _away < AWAY_AFTER or _scale <= AWAY_SCALE:
			return
		want = AWAY_SCALE
	else:
		_away = 0.0
		var screen := get_viewport().get_final_transform().get_scale().x * get_global_transform_with_canvas().get_scale().x
		want = minf(screen * OVER, MAX_SIDE / maxf(_bounds.size.x, _bounds.size.y))
		if _scale > 0.0 and want < _scale * RESIZE and want > _scale / (RESIZE * 1.5):
			return
	_paint_at(want)


func _paint_at(scale: float) -> void:
	_scale = scale
	_vp.size = Vector2i(ceili(_bounds.size.x * _scale), ceili(_bounds.size.y * _scale))
	_vp.canvas_transform = Transform2D(0.0, Vector2(_scale, _scale), 0.0, -_bounds.position * _scale)
	repaint()
	queue_redraw()


func _draw() -> void:
	if _scale > 0.0:
		draw_texture_rect(_vp.get_texture(), Rect2(_bounds.position, Vector2(_vp.size) / _scale), false)


## The table's Body (its collision), which the felt covers, in table coordinates.
func _body_rect() -> Rect2:
	var into := _table.global_transform.affine_inverse()
	var r := Rect2()
	var first := true
	for n in _table.get_node("Body").get_children():
		var pts := PackedVector2Array()
		if n is CollisionPolygon2D:
			pts = n.polygon
		elif n.shape is RectangleShape2D:
			pts = [-n.shape.size / 2.0, n.shape.size / 2.0]
		elif n.shape is CircleShape2D:
			pts = [-Vector2.ONE * n.shape.radius, Vector2.ONE * n.shape.radius]
		for q in pts:
			var at: Vector2 = into * (n.global_transform * q)
			r = Rect2(at, Vector2.ZERO) if first else r.expand(at)
			first = false
	return r
