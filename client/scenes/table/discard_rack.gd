@tool
class_name DiscardRack
extends Node2D
## A clear acrylic discard holder set on the felt: used cards are dropped in
## face down, turned sideways, and stay there until they go back through the
## shuffler -- every hand at Three Card Poker, a whole shoe's worth at Blackjack.
##
## Reusable by any table. It draws the holder and its own stack of cards (so a
## few hundred discards cost nothing), deeper the more it holds, with the top
## few lying a little untidily; the table moves the cards in (put it in a layer
## drawn BELOW the cards):
##   slot(n) -> [position, rotation]  where the nth discard lands, in the parent's coordinates
##   count                            how many cards it holds (add one as each lands)
##   take_all() -> int                empties it (for the shuffler), returning how many
## Drawn in code, centred on its origin, so it stays sharp at any zoom.

const SIZE := Vector2(24, 18)   # takes a card lying sideways, with room to spare
const LAYER := 0.06             # how much each card raises the stack...
const MAX_LIFT := 5.0           # ...up to this

var count := 0:
	set(v):
		count = maxi(v, 0)
		queue_redraw()


func slot(n: int) -> Array:
	var jitter := Vector2(sin(n * 1.7) * 0.8, cos(n * 2.3) * 0.6)
	return [position + Vector2(0, 0.6 - _lift(n + 1)) + jitter, PI / 2 + sin(n * 3.1) * 0.07]


func take_all() -> int:
	var n := count
	count = 0
	return n


func _lift(n: int) -> float:
	return minf(n * LAYER, MAX_LIFT)


## Its table's design (House in the editor, or anywhere without a table).
func _look() -> Dictionary:
	var n := get_parent()
	while n != null and not n is CasinoTable:
		n = n.get_parent()
	return (n as CasinoTable).style() if n else TableStyle.fill({})


func _draw() -> void:
	var r := Rect2(-SIZE / 2, SIZE)
	var look := _look()
	var kind: String = look.rack   # clear (the original), smoked (tinted) or wood-backed
	var tint := TableStyle.colour(look, "rackTint")
	draw_rect(Rect2(r.position + Vector2(0.6, 1.0), r.size), Color(0, 0, 0, 0.3))      # its shadow
	match kind:
		"wood":
			var pts := PackedVector2Array([r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)])
			var uv := PackedVector2Array()
			for p in pts:
				uv.append(p / 30.0 + Vector2(0.5, 0.5))
			draw_colored_polygon(pts, Color.WHITE, uv, TableStyle.WOODS[TableStyle.wood_of(look, str(look.rackWood))])
			draw_rect(Rect2(r.position + Vector2(1.4, 1.4), r.size - Vector2(2.8, 1.4)), TableStyle.colour(look, "felt.colour").darkened(0.35))
		"smoked":
			draw_rect(r, Color(tint, 0.45))
		_:
			draw_rect(r, Color(0.8, 0.9, 0.95, 0.16))                                    # clear acrylic base
	if count > 0:
		# The stack: card edges showing under the top cards, as deep as it is full.
		var lift := _lift(count)
		var card := Rect2(Vector2(-10, -7) + Vector2(0, 0.6), Vector2(20, 14))
		draw_rect(Rect2(card.position + Vector2(0, -lift), Vector2(card.size.x, card.size.y + lift)), Color("e8e4da"))
		for i in int(lift / 0.6):
			var y := card.end.y - i * 0.6
			draw_line(Vector2(card.position.x, y), Vector2(card.end.x, y), Color(0, 0, 0, 0.12), 0.2)
		for k in range(maxi(0, count - 3), count):  # the top few, a little untidy
			var place := slot(k)
			draw_set_transform(place[0] - position, place[1] - PI / 2)
			Card2D.draw_back(self, Rect2(Vector2(-10, -7), Vector2(20, 14)), str(look.back))
		draw_set_transform(Vector2.ZERO)
	# Walls on three sides, open at the front for the dealer's hand.
	var wall := Color(0.9, 0.96, 1.0, 0.55)
	var thick := 1.2
	if kind == "wood":
		wall = Color("2a160b")
		thick = 1.6
	elif kind == "smoked":
		wall = Color(tint.lightened(0.12), 0.85)
	draw_line(r.position, Vector2(r.end.x, r.position.y), wall, thick)
	draw_line(r.position, Vector2(r.position.x, r.end.y), wall, thick)
	draw_line(Vector2(r.end.x, r.position.y), r.end, wall, thick)
	if kind == "wood":   # a brass edge on the inside of its walls
		draw_polyline(PackedVector2Array([Vector2(r.position.x + 0.8, r.end.y), r.position + Vector2(0.8, 0.8), Vector2(r.end.x - 0.8, r.position.y + 0.8), Vector2(r.end.x - 0.8, r.end.y)]), Color("c9a24a"), 0.3)
	draw_line(Vector2(r.position.x, r.end.y), r.end, Color(1, 1, 1, 0.25), 0.4)       # the low front edge
	draw_line(r.position + Vector2(1.2, 1.4), Vector2(r.position.x + 6, r.position.y + 1.4), Color(1, 1, 1, 0.45), 0.35)  # shine
