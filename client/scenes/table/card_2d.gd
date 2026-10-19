@tool
class_name Card2D
extends Node2D
## A playing card lying on the felt, drawn in code so it stays crisp when the
## camera zooms in. "Qs"/"10h" face up, "Jkr" the Joker, "??" face down.
## Centred on its origin.

const FONT := preload("res://assets/fonts/DejaVuSans-Bold.ttf")
const SIZE := Vector2(14, 20)
const SUITS := {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
const RED := Color("c62828")
const BLACK := Color("1b1b1b")
const JOKER := Color("6a2c91")
## Card backs: charcoal with a brass frame, so they stand out on the crimson felt.
const BACK := Color("34373c")
const BACK_FRAME := Color("c9a24a")

@export var code := "??":
	set(v):
		code = v
		queue_redraw()


const _RANKS := {"Jkr": 15, "A": 14, "K": 13, "Q": 12, "J": 11}


## For sorting high to low: the Joker first (it plays as an Ace or better), then A, K, Q...
static func rank_value(card_code: String) -> int:
	if card_code == "Jkr":
		return 15
	var rank := card_code.substr(0, card_code.length() - 1)
	return _RANKS.get(rank, int(rank))


## Turn over to `new_code` with a flip (scale.x squeeze); returns the tween.
func flip_to(new_code: String, duration := 0.25) -> Tween:
	if code == "??" and new_code != "??" and not Engine.is_editor_hint() and is_inside_tree():
		Sfx.play_at("flip", global_position)  # turned face up (turning face down is silent)
	var tween := create_tween()
	tween.tween_property(self, "scale:x", 0.0, duration / 2)
	tween.tween_callback(func(): code = new_code)
	tween.tween_property(self, "scale:x", 1.0, duration / 2)
	return tween


func _draw() -> void:
	paint(self, code)


## Draws a card (face, back for "??", or the Joker for "Jkr") centred on the
## origin of `xform`, on any canvas item -- the felt's cards at their own size,
## the Pai Gow sorter's scaled up. The suits are drawn as shapes, not font
## glyphs, and every edge is antialiased, so a card stays crisp at any size.
static func paint(ci: CanvasItem, card_code: String, xform := Transform2D.IDENTITY) -> void:
	ci.draw_set_transform_matrix(xform)
	var r := Rect2(-SIZE / 2, SIZE)
	_round_rect(ci, Rect2(r.position + Vector2(0.6, 0.8), r.size), Color(0, 0, 0, 0.25))  # shadow
	if card_code == "??":
		draw_back(ci, r)
	else:
		_round_rect(ci, r, Color("fbfaf5"), Color("b9b4a5"))
		var joker := card_code == "Jkr"
		var rank := "" if joker else card_code.substr(0, card_code.length() - 1)
		var suit := "star" if joker else card_code.right(1)
		var colour := JOKER if joker else (RED if suit in ["h", "d"] else BLACK)
		# The index, small and tucked into the top-left corner (so it still shows
		# when cards are fanned tightly), and again upside down in the bottom-right.
		_corner_index(ci, r, rank, suit, colour)
		ci.draw_set_transform_matrix(xform * Transform2D(PI, Vector2.ZERO))
		_corner_index(ci, r, rank, suit, colour)
		ci.draw_set_transform_matrix(xform)
		# The suit, large, in the middle (the Joker: a big star, and its name).
		if joker:
			draw_suit(ci, "star", Vector2(0, -0.6), 8.0, colour)
			var word := FONT.get_string_size("JOKER", HORIZONTAL_ALIGNMENT_LEFT, -1, 2).x
			ci.draw_string(FONT, Vector2(-word / 2, 6.4), "JOKER", HORIZONTAL_ALIGNMENT_LEFT, -1, 2, colour)
		else:
			draw_suit(ci, suit, Vector2(0, 0.6), 7.0, colour)
	ci.draw_set_transform_matrix(Transform2D.IDENTITY)


## The corner index: the rank with its suit beneath (the Joker: just a star).
static func _corner_index(ci: CanvasItem, r: Rect2, rank: String, suit: String, colour: Color) -> void:
	var column := r.position.x + 2.4  # rank and suit centred on one column
	if rank == "":
		draw_suit(ci, suit, Vector2(column, r.position.y + 3.4), 3.4, colour)
		return
	var size := 4 if rank.length() < 2 else 3
	var width := FONT.get_string_size(rank, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	ci.draw_string(FONT, Vector2(column - width / 2, r.position.y + 4.0), rank, HORIZONTAL_ALIGNMENT_LEFT, -1, size, colour)
	draw_suit(ci, suit, Vector2(column, r.position.y + 6.1), 2.5, colour)


## A suit (or the Joker's star) as shapes, `h` tall, centred on `c`: filled,
## with antialiased edges.
static func draw_suit(ci: CanvasItem, suit: String, c: Vector2, h: float, colour: Color) -> void:
	match suit:
		"d":
			_shape(ci, PackedVector2Array([c + Vector2(0, -h / 2), c + Vector2(h * 0.38, 0), c + Vector2(0, h / 2), c + Vector2(-h * 0.38, 0)]), colour)
		"h":
			var r := h * 0.27
			_circle(ci, c + Vector2(-r * 0.92, -h * 0.2), r, colour)
			_circle(ci, c + Vector2(r * 0.92, -h * 0.2), r, colour)
			_shape(ci, PackedVector2Array([c + Vector2(-h * 0.5, -h * 0.12), c + Vector2(h * 0.5, -h * 0.12), c + Vector2(0, h * 0.48)]), colour)
		"s":
			var r := h * 0.26
			_circle(ci, c + Vector2(-r * 0.92, h * 0.1), r, colour)
			_circle(ci, c + Vector2(r * 0.92, h * 0.1), r, colour)
			_shape(ci, PackedVector2Array([c + Vector2(-h * 0.48, h * 0.04), c + Vector2(h * 0.48, h * 0.04), c + Vector2(0, -h * 0.5)]), colour)
			_shape(ci, PackedVector2Array([c + Vector2(-h * 0.05, h * 0.12), c + Vector2(h * 0.05, h * 0.12), c + Vector2(h * 0.18, h * 0.5), c + Vector2(-h * 0.18, h * 0.5)]), colour)
		"c":
			var r := h * 0.22
			_circle(ci, c + Vector2(0, -h * 0.25), r, colour)
			_circle(ci, c + Vector2(-h * 0.25, h * 0.04), r, colour)
			_circle(ci, c + Vector2(h * 0.25, h * 0.04), r, colour)
			_shape(ci, PackedVector2Array([c + Vector2(-h * 0.05, -h * 0.05), c + Vector2(h * 0.05, -h * 0.05), c + Vector2(h * 0.18, h * 0.5), c + Vector2(-h * 0.18, h * 0.5)]), colour)
		"star":
			var pts := PackedVector2Array()
			for i in 10:
				var a := -PI / 2 + i * PI / 5
				pts.append(c + Vector2(cos(a), sin(a)) * (h / 2 if i % 2 == 0 else h * 0.2))
			_shape(ci, pts, colour)


## A circle as a polygon with a thin antialiased edge (Godot's own antialiased
## circles feather by a fixed amount that blurs when a card is drawn large).
static func _circle(ci: CanvasItem, c: Vector2, r: float, colour: Color) -> void:
	var pts := PackedVector2Array()
	for i in 28:
		pts.append(c + Vector2.from_angle(TAU * i / 28.0) * r)
	_shape(ci, pts, colour)


## A filled polygon with an antialiased outline in the same colour (the fill
## alone has hard, stepped edges when drawn large).
static func _shape(ci: CanvasItem, pts: PackedVector2Array, colour: Color) -> void:
	ci.draw_colored_polygon(pts, colour)
	var closed := pts.duplicate()
	closed.append(pts[0])
	ci.draw_polyline(closed, colour, 0.12, true)


## A card-shaped rectangle with slightly rounded corners and an antialiased edge.
static func _round_rect(ci: CanvasItem, r: Rect2, fill: Color, edge := Color(0, 0, 0, 0)) -> void:
	var rad := 0.9
	var pts := PackedVector2Array()
	var corners := [[r.end - Vector2(rad, rad), 0.0], [Vector2(r.position.x + rad, r.end.y - rad), PI / 2],
		[r.position + Vector2(rad, rad), PI], [Vector2(r.end.x - rad, r.position.y + rad), PI * 1.5]]
	for corner in corners:
		for i in 4:
			var a: float = corner[1] + PI / 2 * i / 3.0
			pts.append(corner[0] + Vector2(cos(a), sin(a)) * rad)
	ci.draw_colored_polygon(pts, fill)
	var closed := pts.duplicate()
	closed.append(pts[0])
	ci.draw_polyline(closed, edge if edge.a > 0 else fill, 0.3 if edge.a > 0 else 0.12, true)


## A card's back in `r` on any canvas item (the discard rack draws its stack
## with this): charcoal with a brass frame and a white border.
static func draw_back(ci: CanvasItem, r: Rect2) -> void:
	_round_rect(ci, r, Color("f4f2ec"), Color(0, 0, 0, 0.35))  # white border
	ci.draw_rect(r.grow(-1.3), BACK)
	ci.draw_rect(r.grow(-2.6), Color(BACK_FRAME, 0.85), false, 0.4)
	var inner := r.grow(-2.6)
	for i in 4:  # a faint diamond lattice
		var f := (i + 1) / 5.0
		ci.draw_line(Vector2(inner.position.x, inner.position.y + inner.size.y * f), Vector2(inner.position.x + inner.size.x * f, inner.position.y), Color(1, 1, 1, 0.1), 0.3)
		ci.draw_line(Vector2(inner.end.x - inner.size.x * f, inner.end.y), Vector2(inner.end.x, inner.end.y - inner.size.y * f), Color(1, 1, 1, 0.1), 0.3)
