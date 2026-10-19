@tool
class_name RouletteSign
extends Node2D
## The results display that stands beside the roulette table, as in a real
## casino. A dark housing in a bevelled brass frame: the latest number large in
## a roundel of its colour (it pulses as a new one arrives), the eleven before
## it on a glass LED screen -- red to the right, black to the left, zero in the
## middle -- and the red/zero/black split of the last twelve along the foot. It
## stands on a pole with brass collars and a weighted base. The node sits where
## the pole meets the floor, so Y-sorting puts people in front of or behind it.

const FONT := preload("res://assets/fonts/DejaVuSans-Bold.ttf")
const CINZEL := preload("res://assets/fonts/Cinzel-SemiBold.ttf")
const RED := [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
const BRASS := Color("c9a24a")
const BRASS_HI := Color("ecd08a")
const W := 32.0
const H := 130.0
const TOP := -156.0          # the housing's top edge, above the base

var history: Array = [17, 0, 32, 5, 23, 36, 1, 14, 30, 8, 19, 27]:
	set(v):
		history = v.map(func(n): return int(n))  # (JSON numbers arrive as floats)
		queue_redraw()
var _arrived_at := -10.0


## A new result: it goes to the top and the roundel pulses.
func show_result(numbers: Array) -> void:
	history = numbers.slice(0, 12)
	_arrived_at = Time.get_ticks_msec() / 1000.0


func _process(_delta: float) -> void:
	if Time.get_ticks_msec() / 1000.0 - _arrived_at < 2.2:
		queue_redraw()


func _led(n: int) -> Color:
	return Color("3fdc82") if n == 0 else Color("ff5148") if n in RED else Color("f1ece0")


func _roundel(n: int) -> Color:
	return Color("1f8a52") if n == 0 else Color("d33a33") if n in RED else Color("151212")


## Text at any size (fonts take whole sizes, so a fractional one is scaled).
func _text(s: String, centre: Vector2, size: float, colour: Color, font: Font = FONT) -> void:
	var px := maxi(1, roundi(size))
	var k := size / px
	var w := font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x
	draw_set_transform(centre, 0, Vector2(k, k))
	draw_string(font, Vector2(-w / 2, px * 0.36), s, HORIZONTAL_ALIGNMENT_LEFT, -1, px, colour)
	draw_set_transform(Vector2.ZERO)


func _draw() -> void:
	var x := -W / 2
	var y := TOP
	# pole and base
	draw_set_transform(Vector2(1, 2), 0, Vector2(1, 0.32))
	draw_circle(Vector2.ZERO, 13.0, Color(0, 0, 0, 0.35))
	draw_set_transform(Vector2.ZERO)
	draw_rect(Rect2(-2.2, y + H, 4.4, -(y + H)), Color("2a2422"))
	draw_rect(Rect2(-0.6, y + H, 1.0, -(y + H)), Color(1, 1, 1, 0.12))
	draw_set_transform(Vector2.ZERO, 0, Vector2(1, 0.35))
	draw_circle(Vector2.ZERO, 11.0, Color("2b2422"))
	draw_circle(Vector2(0, -1.5), 9.5, Color("40362f"))
	draw_set_transform(Vector2.ZERO)
	draw_rect(Rect2(-3.4, y + H, 6.8, 2.4), BRASS)
	draw_rect(Rect2(-3.0, -3.5, 6.0, 1.6), BRASS)
	# the housing in its bevelled brass frame
	draw_colored_polygon(TableFelt._rounded(Rect2(x + 1.2, y + 2, W, H), 3.5), Color(0, 0, 0, 0.35))
	draw_colored_polygon(TableFelt._rounded(Rect2(x - 1.6, y - 1.6, W + 3.2, H + 3.2), 4.0), Color("b48d3a"))
	draw_colored_polygon(TableFelt._rounded(Rect2(x - 1.6, y - 1.6, W + 3.2, (H + 3.2) * 0.5), 4.0), Color(1, 0.9, 0.6, 0.25))
	draw_colored_polygon(TableFelt._rounded(Rect2(x, y, W, H), 2.6), Color("16120f"))
	draw_colored_polygon(TableFelt._rounded(Rect2(x, y, W, H * 0.4), 2.6), Color(1, 1, 1, 0.03))
	_text("ROULETTE", Vector2(0, y + 5), 3.4, BRASS_HI, CINZEL)
	_text("SINGLE ZERO", Vector2(0, y + 9), 2.2, Color(BRASS_HI, 0.7), CINZEL)
	# the latest number
	var latest: int = history[0] if not history.is_empty() else 0
	var age := Time.get_ticks_msec() / 1000.0 - _arrived_at
	var pulse := 0.5 + 0.5 * cos(age * PI * 3.0) if age < 2.0 else 0.0
	var c := Vector2(0, y + 20)
	if pulse > 0:
		draw_circle(c, 10.5 + 1.5 * pulse, Color(1, 0.93, 0.67, 0.45 * pulse))
	draw_circle(c, 8.4, _roundel(latest))
	draw_circle(c + Vector2(-2.2, -2.6), 4.6, Color(1, 1, 1, 0.14))
	draw_arc(c, 8.4, 0, TAU, 40, BRASS_HI, 0.9, true)
	_text(str(latest), c + Vector2(0, 0.3), 7.4 if latest > 9 else 8.2, Color.WHITE)
	# the LED screen
	var screen := Rect2(x + 2.5, y + 31, W - 5, 86)
	draw_colored_polygon(TableFelt._rounded(screen, 1.5), Color("030303"))
	draw_line(Vector2(0, screen.position.y + 2), Vector2(0, screen.end.y - 2), Color(1, 1, 1, 0.06), 0.25)
	var earlier := history.slice(1, 12)
	for i in earlier.size():
		var n: int = earlier[i]
		var at := Vector2(0.0 if n == 0 else (screen.end.x - 6.5 if n in RED else screen.position.x + 6.5), screen.position.y + 5 + i * 7.4)
		var size := 5.4 - i * 0.12
		var led := _led(n)
		for o in [Vector2(0.45, 0), Vector2(-0.45, 0), Vector2(0, 0.45), Vector2(0, -0.45)]:   # the glow
			_text(str(n), at + o, size, Color(led, 0.22))
		_text(str(n), at, size, led)
	var ly := screen.position.y
	while ly < screen.end.y:   # scanlines
		draw_rect(Rect2(screen.position.x, ly, screen.size.x, 0.35), Color(1, 1, 1, 0.035))
		ly += 1.1
	draw_colored_polygon(PackedVector2Array([screen.position, screen.position + Vector2(screen.size.x, 0),
		screen.position + Vector2(screen.size.x, screen.size.y * 0.18), screen.position + Vector2(0, screen.size.y * 0.42)]),
		Color(1, 1, 1, 0.05))   # the glass's sheen
	var frame := TableFelt._rounded(screen, 1.5)
	frame.append(frame[0])
	draw_polyline(frame, Color(BRASS, 0.55), 0.4, true)
	# red / zero / black over the last twelve
	var reds := history.filter(func(n): return n in RED).size()
	var zeros := history.filter(func(n): return n == 0).size()
	var blacks := history.size() - reds - zeros
	var by := screen.end.y + 3.5
	var unit := screen.size.x / maxf(1.0, history.size())
	draw_rect(Rect2(screen.position.x, by, reds * unit, 2.4), Color("d33a33"))
	draw_rect(Rect2(screen.position.x + reds * unit, by, zeros * unit, 2.4), Color("1f8a52"))
	draw_rect(Rect2(screen.position.x + (reds + zeros) * unit, by, blacks * unit, 2.4), Color("ece6d8"))
	_text(str(reds), Vector2(screen.position.x + 2.5, by + 6), 3.0, Color("ff8a80"))
	_text(str(blacks), Vector2(screen.end.x - 2.5, by + 6), 3.0, Color("ece6d8"))
