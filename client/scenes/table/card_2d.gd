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
## A four-colour deck's diamonds and clubs (the table style's `suits`).
const BLUE := Color("1f5fbf")
const GREEN := Color("1e7d3a")
## Card backs: charcoal with a brass frame, so they stand out on the crimson felt.
const BACK := Color("34373c")
const BACK_FRAME := Color("c9a24a")
const STOCK := Color("f4f2ec")    # the card's white border round the back
const IVORY := Color("f3ead2")    # the Vintage front's stock

@export var code := "??":
	set(v):
		code = v
		queue_redraw()
## How it's drawn: its table's style (TableStyle; `back`, `backColour`, `cardColour`, `front`, `suits` and
## `print.font`). Empty draws the game's own: Classic faces, the charcoal back.
var look := {}:
	set(v):
		look = v
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
		Sfx.play_at("flip", global_position, 0.0, FloorGame.table_of(self))  # turned face up (turning face down is silent)
	var tween := create_tween()
	tween.tween_property(self, "scale:x", 0.0, duration / 2)
	tween.tween_callback(func(): code = new_code)
	tween.tween_property(self, "scale:x", 1.0, duration / 2)
	return tween


func _draw() -> void:
	paint(self, code, Transform2D.IDENTITY, look)


## Draws a card (face, back for "??", or the Joker for "Jkr") centred on the
## origin of `xform`, on any canvas item -- the felt's cards at their own size,
## the Pai Gow sorter's scaled up -- in a table style's front and back (`look`).
## The suits are drawn as shapes, not font glyphs, and every edge is
## antialiased, so a card stays crisp at any size.
##
## The fronts: "classic" (a small index tucked into the top-left corner, so it
## still shows when cards are fanned tightly, again upside down bottom-right, a
## big suit in the middle), "jumbo" (a big index in both corners, no centre
## suit), "vintage" (ivory, the index in the table's lettering, the suit in a
## double-ruled panel) and "minimal" (a big rank over a small suit, a tiny index
## top-left). `suits` "four" makes diamonds blue and clubs green.
static func paint(ci: CanvasItem, card_code: String, xform := Transform2D.IDENTITY, look := {}) -> void:
	ci.draw_set_transform_matrix(xform)
	var r := Rect2(-SIZE / 2, SIZE)
	_round_rect(ci, Rect2(r.position + Vector2(0.6, 0.8), r.size), Color(0, 0, 0, 0.25))  # shadow
	if card_code == "??":
		draw_back(ci, r, look)
		ci.draw_set_transform_matrix(Transform2D.IDENTITY)
		return
	var front := str(look.get("front", "classic"))
	var vintage := front == "vintage"
	_round_rect(ci, r, IVORY if vintage else Color("fbfaf5"), Color("b9a77f") if vintage else Color("b9b4a5"))
	var joker := card_code == "Jkr"
	var rank := "" if joker else card_code.substr(0, card_code.length() - 1)
	var suit := "star" if joker else card_code.right(1)
	var colour := JOKER if joker else suit_colour(suit, look)
	if joker:   # the Joker's the same on every front: a big star, and its name
		_corner_index(ci, r, rank, suit, colour)
		ci.draw_set_transform_matrix(xform * Transform2D(PI, Vector2.ZERO))
		_corner_index(ci, r, rank, suit, colour)
		ci.draw_set_transform_matrix(xform)
		draw_suit(ci, "star", Vector2(0, -0.6), 8.0, colour)
		var word := FONT.get_string_size("JOKER", HORIZONTAL_ALIGNMENT_LEFT, -1, 2).x
		ci.draw_string(FONT, Vector2(-word / 2, 6.4), "JOKER", HORIZONTAL_ALIGNMENT_LEFT, -1, 2, colour)
		ci.draw_set_transform_matrix(Transform2D.IDENTITY)
		return
	match front:
		"jumbo":
			for flip in [false, true]:
				if flip:
					ci.draw_set_transform_matrix(xform * Transform2D(PI, Vector2.ZERO))
				var size := 7 if rank.length() < 2 else 5
				_rank(ci, FONT, rank, Vector2(r.position.x + 3.6, r.position.y + 6.4), size, colour)
				draw_suit(ci, suit, Vector2(r.position.x + 3.6, r.position.y + 9.3), 3.6, colour)
			ci.draw_set_transform_matrix(xform)
		"vintage":
			var panel := Rect2(r.position + Vector2(4.2, 2.2), r.size - Vector2(8.4, 4.4))
			ci.draw_rect(panel, Color(colour, 0.6), false, 0.3)
			ci.draw_rect(panel.grow(-0.6), Color(colour, 0.35), false, 0.15)
			var font := _font(look)
			for flip in [false, true]:
				if flip:
					ci.draw_set_transform_matrix(xform * Transform2D(PI, Vector2.ZERO))
				_rank(ci, font, rank, Vector2(r.position.x + 2.2, r.position.y + 4.0), 4 if rank.length() < 2 else 3, colour)
				draw_suit(ci, suit, Vector2(r.position.x + 2.2, r.position.y + 6.1), 2.2, colour)
			ci.draw_set_transform_matrix(xform)
			draw_suit(ci, suit, Vector2(0, 0.4), 5.0, colour)
		"minimal":
			_rank(ci, FONT, rank, Vector2(0, 2.0), 9 if rank.length() < 2 else 7, colour)
			draw_suit(ci, suit, Vector2(0, 5.4), 3.0, colour)
			_rank(ci, FONT, rank, Vector2(r.position.x + 1.9, r.position.y + 3.0), 2, colour)   # (for cascaded cards)
		_:
			_corner_index(ci, r, rank, suit, colour)
			ci.draw_set_transform_matrix(xform * Transform2D(PI, Vector2.ZERO))
			_corner_index(ci, r, rank, suit, colour)
			ci.draw_set_transform_matrix(xform)
			draw_suit(ci, suit, Vector2(0, 0.6), 7.0, colour)
	ci.draw_set_transform_matrix(Transform2D.IDENTITY)


## A suit's colour: red and black, or a four-colour deck's.
static func suit_colour(suit: String, look := {}) -> Color:
	if str(look.get("suits", "two")) == "four":
		return {"h": RED, "d": BLUE, "c": GREEN}.get(suit, BLACK)
	return RED if suit in ["h", "d"] else BLACK


## The table's lettering, for the Vintage front.
static func _font(look: Dictionary) -> Font:
	var p: Variant = look.get("print")
	return TableStyle.FONTS.get(p.get("font", ""), FONT) if p is Dictionary else FONT


## A rank centred on `column.x`, its baseline at `column.y`.
static func _rank(ci: CanvasItem, font: Font, rank: String, at: Vector2, size: int, colour: Color) -> void:
	var width := font.get_string_size(rank, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	ci.draw_string(font, Vector2(at.x - width / 2, at.y), rank, HORIZONTAL_ALIGNMENT_LEFT, -1, size, colour)


## The corner index: the rank with its suit beneath (the Joker: just a star).
static func _corner_index(ci: CanvasItem, r: Rect2, rank: String, suit: String, colour: Color) -> void:
	var column := r.position.x + 2.4  # rank and suit centred on one column
	if rank == "":
		draw_suit(ci, suit, Vector2(column, r.position.y + 3.4), 3.4, colour)
		return
	_rank(ci, FONT, rank, Vector2(column, r.position.y + 4.0), 4 if rank.length() < 2 else 3, colour)
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


## The card backs' designs (TableStyle `back`), by the main colour each had before the colour was its own
## choice (`backColour`; table_styles.BACK_MAIN).
const BACKS := {"charcoal": BACK, "lattice": Color("8e1a22"), "sunburst": Color("4d1616"), "monogram": Color("5a1322"),
	"stripe": Color("141414"), "emerald": Color("145238")}


## A back's main colour in a table style.
static func back_colour(look: Dictionary) -> Color:
	if look.has("backColour"):
		return Color(str(look.backColour))
	return BACKS.get(str(look.get("back", "charcoal")), BACK)


## A card's back in `r` on any canvas item (the discard rack draws its stack
## with this), in a table style's design over its back colour, inside a border
## in its card colour: "charcoal" (framed: a faint lattice in a brass frame, the
## game's own), "lattice", "sunburst", "monogram" or "stripe".
static func draw_back(ci: CanvasItem, r: Rect2, look := {}) -> void:
	_round_rect(ci, r, Color(str(look.get("cardColour", STOCK.to_html(false)))), Color(0, 0, 0, 0.35))
	var design := str(look.get("back", "charcoal"))
	var main := back_colour(look)
	var inner := r.grow(-1.3)
	ci.draw_rect(inner, main)
	var c := inner.get_center()
	match design:
		"lattice", "emerald":
			var line := Color(1.0, 0.92, 0.85, 0.52)
			var ix := inner.position.x
			var iy := inner.position.y
			var iw := inner.size.x
			var ih := inner.size.y
			var t := -ih
			while t < iw + ih:   # 45-degree lines both ways, cut to the inner rectangle
				var u0 := maxf(0.0, t - iw)
				var u1 := minf(ih, t)
				if u1 > u0:
					ci.draw_line(Vector2(ix + t - u0, iy + u0), Vector2(ix + t - u1, iy + u1), line, 0.18)
				u0 = maxf(0.0, ih - t)
				u1 = minf(ih, ih - t + iw)
				if u1 > u0:
					ci.draw_line(Vector2(ix + t - ih + u0, iy + u0), Vector2(ix + t - ih + u1, iy + u1), line, 0.18)
				t += 1.6
			ci.draw_rect(inner.grow(-1.3), Color(1, 1, 1, 0.7), false, 0.4)
		"sunburst":
			var gold := Color("e0b84e")
			var half := inner.size / 2
			for i in 24:
				var dir := Vector2.from_angle(i * PI / 12)
				var reach := minf(half.x / maxf(absf(dir.x), 0.001), half.y / maxf(absf(dir.y), 0.001))
				ci.draw_line(c, c + dir * reach, Color(gold, 0.45), 0.2)
			ci.draw_colored_polygon(PackedVector2Array([c + Vector2(0, -4), c + Vector2(3, 0), c + Vector2(0, 4), c + Vector2(-3, 0)]), gold)
			ci.draw_rect(inner.grow(-0.9), gold, false, 0.35)
			ci.draw_rect(inner.grow(-1.7), gold, false, 0.18)
		"monogram":
			var gold := Color("d9b453")
			ci.draw_rect(inner.grow(-1.0), gold, false, 0.35)
			ci.draw_rect(inner.grow(-1.8), gold, false, 0.18)
			ci.draw_arc(c, 3.3, 0, TAU, 32, gold, 0.3, true)
			var font: Font = TableStyle.FONTS.cormorant
			var w := font.get_string_size("CW", HORIZONTAL_ALIGNMENT_LEFT, -1, 3).x
			ci.draw_string(font, c + Vector2(-w / 2, 1.05), "CW", HORIZONTAL_ALIGNMENT_LEFT, -1, 3, Color("e8cf86"))
		"stripe":
			var x := inner.position.x
			var y := inner.position.y
			var red := Color("c8202b")
			var band := red if main.r - maxf(main.g, main.b) < 0.25 else Color("f1e4c4")   # (cream on a red back)
			ci.draw_colored_polygon(PackedVector2Array([Vector2(x, y + inner.size.y * 0.62), Vector2(inner.end.x, y + inner.size.y * 0.22),
				Vector2(inner.end.x, y + inner.size.y * 0.38), Vector2(x, y + inner.size.y * 0.78)]), band)
			ci.draw_rect(inner.grow(-0.9), Color("c9d0d6"), false, 0.3)
		_:   # framed: a faint lattice in a brass frame
			ci.draw_rect(r.grow(-2.6), Color(BACK_FRAME, 0.85), false, 0.4)
			var frame := r.grow(-2.6)
			for i in 4:
				var f := (i + 1) / 5.0
				ci.draw_line(Vector2(frame.position.x, frame.position.y + frame.size.y * f), Vector2(frame.position.x + frame.size.x * f, frame.position.y), Color(1, 1, 1, 0.1), 0.3)
				ci.draw_line(Vector2(frame.end.x - frame.size.x * f, frame.end.y), Vector2(frame.end.x, frame.end.y - frame.size.y * f), Color(1, 1, 1, 0.1), 0.3)
