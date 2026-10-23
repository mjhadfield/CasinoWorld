@tool
class_name ChipButton
extends Button
## A casino chip in the chip tray. Colours follow Casino v2's fixed convention
## (ui/chips.py): £1 blue, £5 red, £25 green, £100 black, £500 pink.

const FONT := preload("res://assets/fonts/DejaVuSans-Bold.ttf")
const LABEL_SIZE := 48          # chip labels are laid out at this size, then scaled
const DIGIT_HEIGHT := 0.729     # DejaVu Sans Bold's figures, as a fraction of the font size
const COLOURS := {
	100: [Color("1f6fd6"), Color("0d3c85")],
	500: [Color("d1362f"), Color("8f211d")],
	2500: [Color("1f8a4c"), Color("125c32")],
	10000: [Color("1c1c1c"), Color("000000")],
	50000: [Color("d6389f"), Color("8f1f68")],
}

## Pence.
@export var value := 100:
	set(v):
		value = v
		queue_redraw()
@export var selected := false:
	set(v):
		selected = v
		queue_redraw()


func _init() -> void:
	custom_minimum_size = Vector2(62, 62)
	flat = true
	focus_mode = FOCUS_NONE


## Chip colours for an amount: the biggest denomination that fits in it.
static func colours_for(pence: int) -> Array:
	var best := 100
	for denom in COLOURS:
		if pence >= denom:
			best = maxi(best, denom)
	return COLOURS[best]


static func draw_chip(canvas: CanvasItem, centre: Vector2, radius: float, pence: int, label: String) -> void:
	var c := colours_for(pence)
	canvas.draw_circle(centre + Vector2(0, 3), radius, Color(0, 0, 0, 0.3))
	canvas.draw_circle(centre, radius, c[1])
	for i in 6:
		var a := i * TAU / 6.0
		canvas.draw_arc(centre, radius * 0.86, a, a + 0.4, 6, Color(1, 1, 1, 0.85), radius * 0.2)
	canvas.draw_circle(centre, radius * 0.66, c[0])
	draw_label(canvas, centre, radius, radius * 0.66, label, Color.WHITE)


## A chip's value, centred in its inlay (`inner`: the inlay's radius): as big as the chip allows, but never wider
## than the inlay, so "100" or "500" stays off the edge pattern. Measured and drawn at a large size, then scaled
## down: at the tiny sizes a felt chip uses, Godot's own centring rounds to whole pixels and leaves it off-centre.
static func draw_label(canvas: CanvasItem, centre: Vector2, radius: float, inner: float, label: String, colour: Color) -> void:
	var width := FONT.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, LABEL_SIZE).x
	# The text's corners just inside the inlay: (w/2)^2 + (h/2)^2 <= (0.9 inner)^2, w and h in proportion to the size.
	var fit := 1.8 * inner / Vector2(width / LABEL_SIZE, DIGIT_HEIGHT).length()
	var font_size := minf(int(radius * (0.62 if label.length() <= 3 else 0.46)), fit)
	var shrink := font_size / float(LABEL_SIZE)
	canvas.draw_set_transform(centre, 0.0, Vector2(shrink, shrink))
	canvas.draw_string(FONT, Vector2(-width / 2, LABEL_SIZE * DIGIT_HEIGHT / 2), label,
		HORIZONTAL_ALIGNMENT_LEFT, -1, LABEL_SIZE, colour)
	canvas.draw_set_transform(Vector2.ZERO)


func _draw() -> void:
	var centre := size / 2
	var radius := minf(size.x, size.y) / 2 - 5
	if selected:
		draw_circle(centre, radius + 5, Color("ffd54a"))
	draw_chip(self, centre, radius, value, str(value / 100))
