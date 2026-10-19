@tool
class_name ChipStack2D
extends Node2D
## A stack of chips on the felt worth `amount` pence, broken into Casino v2's
## denominations (biggest at the bottom), with the total on the top chip.
## With a `tint`, it's a stack of roulette colour chips instead: every chip the
## seat's colour (the stack as tall as the cash chips would be), the total on top.

const RADIUS := 6.0
const LAYER := 1.5
const MAX_LAYERS := 8

@export var amount := 0:
	set(v):
		amount = v
		queue_redraw()
@export var tint := Color(0, 0, 0, 0):
	set(v):
		tint = v
		queue_redraw()

const TINT_RADIUS := 5.4
const TINT_LAYER := 1.1
const FONT := preload("res://assets/fonts/DejaVuSans-Bold.ttf")


func _init() -> void:
	z_index = 1  # chips always sit on top of cards (a Play bet rests on the face-down hand)


static func breakdown(pence: int) -> Array:
	var chips := []
	var left := pence
	var denoms := ChipButton.COLOURS.keys()
	denoms.sort()
	denoms.reverse()
	for d in denoms:
		while left >= d and chips.size() < MAX_LAYERS:
			chips.append(d)
			left -= d
	if chips.is_empty() and pence > 0:
		chips.append(denoms[-1])
	return chips


func _draw() -> void:
	if amount <= 0:
		return
	if tint.a > 0:
		_draw_colour_chips()
		return
	var chips := breakdown(amount)
	draw_set_transform(Vector2(0.5, 1.2), 0, Vector2(1, 0.55))
	draw_circle(Vector2.ZERO, RADIUS + 0.5, Color(0, 0, 0, 0.3))
	draw_set_transform(Vector2.ZERO)
	for i in chips.size() - 1:
		var c: Array = ChipButton.COLOURS[chips[i]]
		var y := -i * LAYER
		draw_circle(Vector2(0, y), RADIUS, c[1])
		draw_arc(Vector2(0, y), RADIUS * 0.85, 0, TAU, 16, Color(1, 1, 1, 0.5), 0.6)
	var top_y := -(chips.size() - 1) * LAYER
	ChipButton.draw_chip(self, Vector2(0, top_y), RADIUS, chips[-1], _label(amount))


func _draw_colour_chips() -> void:
	var n := mini(6, breakdown(amount).size())
	var r := TINT_RADIUS
	draw_set_transform(Vector2(0.5, 0.8), 0, Vector2(1, 0.62))
	draw_circle(Vector2.ZERO, r + 0.3, Color(0, 0, 0, 0.35))
	draw_set_transform(Vector2.ZERO)
	for i in n:
		var y := -i * TINT_LAYER
		draw_circle(Vector2(0, y), r, tint)
		draw_arc(Vector2(0, y), r, 0, TAU, 24, Color(0, 0, 0, 0.35), 0.35, true)
	var top := Vector2(0, -(n - 1) * TINT_LAYER)
	for k in 6:  # the edge inserts
		var a := k * TAU / 6.0
		draw_arc(top, r - 0.6, a, a + 0.32, 4, Color(1, 1, 1, 0.85), 1.1)
	draw_circle(top, r - 2.0, Color(1, 1, 1, 0.28))
	var label := _label(amount)
	var size := 3 if label.length() > 3 else 4
	var w := FONT.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	draw_string(FONT, top + Vector2(-w / 2, size * 0.36), label, HORIZONTAL_ALIGNMENT_LEFT, -1, size, Color("1a0b05"))


static func _label(pence: int) -> String:
	var pounds := pence / 100
	if pounds >= 1000:
		return "%dk" % (pounds / 1000)
	return str(pounds) if pence % 100 == 0 else "%d.%02d" % [pounds, pence % 100]  # 0.95, 1.50 -- never rounded
