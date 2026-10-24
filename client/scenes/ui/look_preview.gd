class_name LookPreview
extends Control
## A character's look, drawn big and crisp for the character select and designer: walking round (down, right, up,
## left, as the admin page's preview does), or standing idle. A designed look ("x_...") shows the stock one until
## LookLoader has it (Looks.frames is asked again every frame, so it swaps in as soon as it's here).

const TURN := 1.6   # seconds facing each way while walking round

var look := "player_default"
var walking := true
var fill_height := false   # the frame as tall as the box even when that's wider than it (the frame's sides are empty)
var _t := 0.0


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST   # pixel art, scaled up by whole steps
	mouse_filter = MOUSE_FILTER_IGNORE


func _process(delta: float) -> void:
	if is_visible_in_tree():
		_t += delta
		queue_redraw()


func _draw() -> void:
	var sf := Looks.frames(look)
	var dir: String = ["down", "right", "up", "left"][int(_t / TURN) % 4] if walking else "down"
	var anim := ("walk_" if walking else "idle_") + dir
	if sf == null or not sf.has_animation(anim):
		return
	var n := sf.get_frame_count(anim)
	var frame: Texture2D = sf.get_frame_texture(anim, int(_t * sf.get_animation_speed(anim)) % n)
	var fit := size.y if fill_height else minf(size.x, size.y)
	var side := floorf(fit / Looks.FRAME) * Looks.FRAME   # a whole multiple of 64, so pixels stay square
	if side <= 0.0:
		side = fit
	draw_texture_rect(frame, Rect2((size - Vector2(side, side)) / 2.0, Vector2(side, side)), false)
