@tool
class_name CardShoe
extends Node2D
## A dealing shoe on the felt: a smoked-red acrylic box holding the decks, the
## cards slid down to the mouth on the dealer's side, the yellow cut card
## standing among them at its depth. As cards are dealt the stack shortens;
## when the cut card comes out it's set aside on the felt beside the shoe.
##
## Reusable by any shoe game (Blackjack now; Baccarat and the like later). It
## only draws itself; the table moves the cards, using (parent's coordinates):
##   mouth_point()             where a dealt card leaves the shoe
##   set_state(remaining, total, cut, cut_out)   from the server's `shoe` state
##   take_one()                one card has just been dealt
##   cut_out()                 the cut card has come out
##   load_full()               a freshly shuffled shoe is put in
## Drawn in code, centred on its origin, so it stays sharp at any zoom.

const BODY := Vector2(28, 16)
const ACRYLIC := Color(0.42, 0.06, 0.1, 0.92)
const ACRYLIC_EDGE := Color("2a0508")
const CUT_CARD := Color("ffd23c")

var remaining := 416
var total := 416
var cut := 100           # the cut card sits this many cards from the back
var is_cut_out := false
var _shown := 416.0      # what's drawn, eased towards `remaining` when a shoe is loaded


func mouth_point() -> Vector2:
	return position + Vector2(-BODY.x / 2 - 2, 2)


func set_state(new_remaining: int, new_total: int, new_cut: int, new_cut_out: bool) -> void:
	remaining = new_remaining
	total = maxi(new_total, 1)
	cut = new_cut
	is_cut_out = new_cut_out
	_shown = remaining
	queue_redraw()


func take_one() -> void:
	remaining = maxi(remaining - 1, 0)
	_shown = remaining
	queue_redraw()


func cut_out() -> void:
	is_cut_out = true
	queue_redraw()


func load_full(seconds := 0.8) -> void:
	is_cut_out = false
	var from := float(remaining)
	remaining = total
	var tw := create_tween()
	tw.tween_method(func(v: float):
		_shown = v
		queue_redraw(), from, float(total), seconds).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)


## Its table's design (House in the editor, or anywhere without a table).
func _look() -> Dictionary:
	var n := get_parent()
	while n != null and not n is CasinoTable:
		n = n.get_parent()
	return (n as CasinoTable).style() if n else TableStyle.fill({})


func _draw() -> void:
	var body := Rect2(-BODY / 2, BODY)
	var look := _look()
	var wooden: bool = look.shoe == "wood"
	var tint := TableStyle.colour(look, "shoeTint")   # its acrylic (the original: red)
	var back := Card2D.back_colour(look)
	draw_rect(Rect2(body.position + Vector2(0.8, 1.2), body.size), Color(0, 0, 0, 0.35))  # its shadow
	draw_rect(body, Color("1e0e06") if wooden else tint.darkened(0.6))
	if wooden:
		var inside := body.grow(-0.8)
		var pts := PackedVector2Array([inside.position, Vector2(inside.end.x, inside.position.y), inside.end, Vector2(inside.position.x, inside.end.y)])
		var uv := PackedVector2Array()
		for p in pts:
			uv.append(p / 34.0 + Vector2(0.5, 0.5))
		draw_colored_polygon(pts, Color.WHITE, uv, TableStyle.WOODS[TableStyle.wood_of(look, str(look.shoeWood))])
	else:
		draw_rect(body.grow(-0.8), Color(tint, 0.92))
	# The decks inside, standing on edge, slid down to the mouth (left).
	var inner := Rect2(body.position + Vector2(3.5, 2.2), Vector2(body.size.x - 5.5, body.size.y - 4.4))
	var fill := clampf(_shown / float(total), 0.0, 1.0)
	var stack := Rect2(inner.position, Vector2(inner.size.x * fill, inner.size.y))
	if stack.size.x > 0.2:
		draw_rect(stack, Color("ece8de"))
		var edges := int(stack.size.x / 0.7)
		for i in edges:
			var x := stack.position.x + i * 0.7
			draw_line(Vector2(x, stack.position.y), Vector2(x, stack.end.y), Color(0, 0, 0, 0.1), 0.2)
		draw_rect(Rect2(stack.end.x - 1.4, stack.position.y, 1.4, stack.size.y), back)  # the back card
		# The cut card, standing in the stack at its depth.
		if not is_cut_out and _shown > cut and total > 0:
			var x := inner.position.x + inner.size.x * (_shown - cut) / float(total)
			draw_rect(Rect2(x - 0.4, inner.position.y - 1.2, 0.8, inner.size.y + 2.4), CUT_CARD)
	# Smoked lid over the cards: tint and a highlight along the top.
	draw_rect(inner, Color(0.12, 0.06, 0.02, 0.25) if wooden else Color(tint.darkened(0.15), 0.3))
	draw_line(body.position + Vector2(1.5, 1.0), Vector2(body.end.x - 1.5, body.position.y + 1.0), Color(1, 0.8, 0.8, 0.3), 0.5)
	# The mouth: a sloped opening with the face of the front card showing, and a finger notch.
	var mouth := PackedVector2Array([body.position + Vector2(0, 2), body.position + Vector2(3.5, 2.2),
		Vector2(body.position.x + 3.5, body.end.y - 2.2), Vector2(body.position.x, body.end.y - 2)])
	draw_colored_polygon(mouth, Color("c9a24a") if wooden else tint.darkened(0.75))
	if fill > 0.0:
		draw_rect(Rect2(body.position.x + 0.6, body.position.y + 3.0, 2.6, body.size.y - 6.0), back.lightened(0.15))
	draw_arc(Vector2(body.position.x + 1.2, 0), 2.6, -PI / 2, PI / 2, 10, Color(0, 0, 0, 0.6), 0.6, true)
	draw_rect(body, Color(0.78, 0.82, 0.86, 0.5) if not wooden and tint.get_luminance() < 0.1 else Color(1, 1, 1, 0.12), false, 0.4)
	# Once it's out, the cut card lies flat on the felt beside the shoe.
	if is_cut_out:
		var card := Rect2(Vector2(-6, body.end.y + 2.5), Vector2(20, 13))
		draw_rect(Rect2(card.position + Vector2(0.5, 0.7), card.size), Color(0, 0, 0, 0.3))
		draw_rect(card, CUT_CARD)
		draw_rect(card.grow(-1.2), Color(1, 1, 1, 0.25), false, 0.4)
