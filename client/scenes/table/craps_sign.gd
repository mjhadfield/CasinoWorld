@tool
class_name CrapsSign
extends Node2D
## The last-rolls sign that stands beside the craps table, built like the
## roulette sign: a dark housing in a bevelled brass frame, the point (or
## "Coming out") along the top, the latest roll as two dice and its total (it
## pulses as a new one arrives), the ten before it on a glass LED screen -- sevens
## in red, craps in amber, hardways marked H -- and under it the countdown and
## which roll of the shooter's hand this is. The node sits where the pole meets
## the floor, so Y-sorting puts people in front of or behind it.

const FONT := preload("res://assets/fonts/DejaVuSans-Bold.ttf")
const CINZEL := preload("res://assets/fonts/Cinzel-SemiBold.ttf")
const BRASS := Color("c9a24a")
const BRASS_HI := Color("ecd08a")
const W := 32.0
const H := 134.0
const TOP := -168.0          # the housing's top edge, above the base

var history: Array = [[5, 3], [6, 1], [4, 4], [2, 3], [6, 5], [3, 1], [5, 2], [6, 6], [2, 2], [4, 1], [5, 5], [3, 3]]:
	set(v):
		history = v.map(func(r): return [int(r[0]), int(r[1])])   # (JSON numbers arrive as floats)
		queue_redraw()
var point := -1:
	set(v):
		point = v
		queue_redraw()
var footer := "":
	set(v):
		if v != footer:
			footer = v
			queue_redraw()
var rolls := 0:
	set(v):
		rolls = v
		queue_redraw()
var _arrived_at := -10.0


## A new roll: it goes to the top and pulses.
func show_roll(rolls_so_far: Array) -> void:
	history = rolls_so_far.slice(0, 12)
	_arrived_at = Time.get_ticks_msec() / 1000.0


func _process(_delta: float) -> void:
	if Time.get_ticks_msec() / 1000.0 - _arrived_at < 2.2:
		queue_redraw()


func _text(s: String, centre: Vector2, size: float, colour: Color, font: Font = FONT) -> void:
	var px := maxi(1, roundi(size))
	var k := size / px
	var w := font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x
	draw_set_transform(centre, 0, Vector2(k, k))
	draw_string(font, Vector2(-w / 2, px * 0.36), s, HORIZONTAL_ALIGNMENT_LEFT, -1, px, colour)
	draw_set_transform(Vector2.ZERO)


static func _colour(total: int) -> Color:
	return Color("ff5148") if total == 7 else Color("ffb347") if total in [2, 3, 12] else Color("f1ece0")


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
	_text("CRAPS", Vector2(0, y + 5), 3.4, BRASS_HI, CINZEL)
	_text("POINT %d" % point if point > 0 else "COMING OUT", Vector2(0, y + 9.2), 2.3,
		Color.WHITE if point > 0 else Color(BRASS_HI, 0.75), CINZEL)
	# the latest roll: both dice and the total
	if not history.is_empty():
		var latest: Array = history[0]
		var age := Time.get_ticks_msec() / 1000.0 - _arrived_at
		var pulse := 0.5 + 0.5 * cos(age * PI * 3.0) if age < 2.0 else 0.0
		if pulse > 0:
			draw_colored_polygon(TableFelt._rounded(Rect2(x + 3, y + 12, W - 6, 18), 3.0), Color(1, 0.93, 0.67, 0.3 * pulse))
		CrapsDice.draw_die(self, Vector2(-5, y + 18), 0.0, latest[0], 0.0)
		CrapsDice.draw_die(self, Vector2(5, y + 18), 0.0, latest[1], 0.0)
		var total: int = latest[0] + latest[1]
		_text(str(total), Vector2(0, y + 27), 5.0, Color("ff5148") if total == 7 else Color.WHITE)
	# the ten before it, on the LED screen
	var screen := Rect2(x + 2.5, y + 32, W - 5, 84)
	draw_colored_polygon(TableFelt._rounded(screen, 1.5), Color("030303"))
	var earlier := history.slice(1, 11)
	for i in earlier.size():
		var r: Array = earlier[i]
		var total: int = r[0] + r[1]
		var hard: bool = r[0] == r[1] and total in [4, 6, 8, 10]
		var at := Vector2(screen.position.x + 8, screen.position.y + 5 + i * 8)
		var size := 5.2 - i * 0.1
		var led := _colour(total)
		for o in [Vector2(0.45, 0), Vector2(-0.45, 0), Vector2(0, 0.45), Vector2(0, -0.45)]:   # the glow
			_text(str(total), at + o, size, Color(led, 0.22))
		_text(str(total), at, size, led)
		_text("%d·%d%s" % [r[0], r[1], " H" if hard else ""], Vector2(screen.end.x - 7, at.y), 2.6, Color(0.95, 0.92, 0.88, 0.55))
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
	_text(footer, Vector2(0, screen.end.y + 4.5), 2.2, BRASS_HI)
	_text("ROLL %d OF THIS HAND" % maxi(1, rolls), Vector2(0, screen.end.y + 8.5), 1.9, Color(BRASS_HI, 0.6))
