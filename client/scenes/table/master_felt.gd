@tool
extends StyledFelt
## The Master Table before anyone's chosen a game: no spots, just its crest (signed off on the mockup,
## docs/master_table/mockup/): a gold ring with a crown set on top, MASTER TABLE and NINE GAMES · ONE TABLE round
## its band, the four suits in the middle round a gold star, deco tips on the other three points of the ring, and
## ASK THE DEALER FOR ANY GAME under it. The dealer's rules either side say what it is.

const CREST := Vector2(0, -64)
const RING := 24.0          # the gold ring
const BAND := 18.9          # the band's lettering runs round this
const INNER := 15.2


func _draw_layout(_t: CasinoTable) -> void:
	for line in [["ANY CARD GAME", -62, -1.5], ["ON ONE TABLE", -62, 3.5], ["CHANGE GAME", 62, -1.5], ["BETWEEN HANDS", 62, 3.5]]:
		small(line[0], line[1], line[2])
	crest(CREST)
	var y := CREST.y + 31.0
	var gold := role_colour("accent")
	print_text("ASK THE DEALER FOR ANY GAME", Vector2(0, y), 3, Color(ink(), 0.92))
	for s in [-1.0, 1.0]:
		draw_line(Vector2(s * 33, y), Vector2(s * 48, y), Color(gold, 0.8), 0.3, true)
		_diamond(Vector2(s * 31, y), 0.8, 0.9, gold)


func crest(c: Vector2) -> void:
	var gold := role_colour("accent")
	var ink_c := ink()
	draw_circle(c, RING + 0.6, Color(0, 0, 0, 0.15))
	_ring(c, RING, 1.0, gold.lightened(0.45), gold, gold.darkened(0.35))
	draw_arc(c, RING - 1.5, 0, TAU, 64, Color(ink_c, 0.55), 0.22, true)
	draw_arc(c, INNER, 0, TAU, 64, Color(ink_c, 0.75), 0.32, true)
	draw_arc(c, INNER - 1.0, 0, TAU, 64, Color(ink_c, 0.35), 0.18, true)
	arc_text("MASTER TABLE", c, BAND, -PI / 2, 4, ink_c, false)
	arc_text("NINE GAMES · ONE TABLE", c, BAND, PI / 2, 2, Color(ink_c, 0.85), true)
	for s in [-1.0, 1.0]:   # a diamond each side, between the words
		_diamond(c + Vector2(s * BAND, 0), 0.9, 1.4, gold)
	for pair in [[-PI / 2, "s"], [0.0, "h"], [PI / 2, "c"], [PI, "d"]]:
		var at: Vector2 = c + Vector2.from_angle(pair[0]) * 8.0 + Vector2(0, 0.3)
		Card2D.draw_suit(self, pair[1], at, 5.6, gold if pair[1] in ["h", "d"] else ink_c)
	var star := PackedVector2Array()
	for i in 8:
		star.append(c + Vector2.from_angle(-PI / 2 + i * PI / 4) * (2.2 if i % 2 == 0 else 1.0))
	draw_colored_polygon(star, gold)
	# the crown on top, breaking the ring; deco tips on the other three points, as the House spots have
	_ellipse(c + Vector2(0, -RING), Vector2(7.6, 2.4), TableStyle.colour(d, "felt.colour"))
	crown(c + Vector2(0, -RING + 0.8), 11.0)
	for at in [c + Vector2(RING, 0), c + Vector2(0, RING), c + Vector2(-RING, 0)]:
		_diamond(at, 1.2, 1.6, gold.lightened(0.2))


## A crown whose base's middle is `base`, `w` across.
func crown(base: Vector2, w: float) -> void:
	var gold := role_colour("accent")
	var h := w * 0.7
	var pts := PackedVector2Array([Vector2(-w / 2, 0), Vector2(-w / 2, -h * 0.25), Vector2(-w * 0.56, -h * 0.92),
		Vector2(-w * 0.25, -h * 0.48), Vector2(0, -h), Vector2(w * 0.25, -h * 0.48), Vector2(w * 0.56, -h * 0.92),
		Vector2(w / 2, -h * 0.25), Vector2(w / 2, 0)])
	var colours := PackedColorArray()
	for i in pts.size():
		pts[i] += base
		colours.append(gold.lightened(0.45).lerp(gold.darkened(0.35), inverse_lerp(base.y - h, base.y, pts[i].y)))
	draw_polygon(pts, colours)
	_loop(pts, gold.darkened(0.5), 0.25)
	for tip in [Vector2(-w * 0.56, -h * 0.92), Vector2(0, -h), Vector2(w * 0.56, -h * 0.92)]:
		draw_circle(base + tip, w * 0.07, gold.lightened(0.35))
	draw_rect(Rect2(base + Vector2(-w / 2, -h * 0.25), Vector2(w, 0.3)), gold.darkened(0.45))
	var felt := TableStyle.colour(d, "felt.colour")
	for k in [-0.3, 0.0, 0.3]:
		draw_circle(base + Vector2(w * k, -h * 0.12), w * 0.045, felt.lightened(0.25) if k == 0.0 else felt)


## `s` round a circle (centre `c`, radius `r`), centred on the angle `mid`: along the top reading left to right, or
## (`bottom`) along the bottom, still upright.
func arc_text(s: String, c: Vector2, r: float, mid: float, size: int, colour: Color, bottom: bool) -> void:
	var f := TableStyle.font(d)
	var gap := size * 0.16
	var widths := []
	var total := -gap
	for ch in s:
		var w := f.get_string_size(ch, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
		widths.append(w)
		total += w + gap
	var dir := -1.0 if bottom else 1.0
	var a0 := mid - dir * total / (2.0 * r)
	var along := 0.0
	for i in s.length():
		var a: float = a0 + dir * (along + widths[i] / 2.0) / r
		draw_set_transform(-position + c + Vector2.from_angle(a) * r, a + dir * PI / 2)
		draw_char(f, Vector2(-widths[i] / 2.0, size * 0.35), s[i], size, colour)
		along += widths[i] + gap
	draw_set_transform(-position)


func _diamond(at: Vector2, hw: float, hh: float, colour: Color) -> void:
	draw_colored_polygon(PackedVector2Array([at + Vector2(0, -hh), at + Vector2(hw, 0), at + Vector2(0, hh), at + Vector2(-hw, 0)]), colour)


func _ellipse(at: Vector2, radii: Vector2, colour: Color) -> void:
	var pts := PackedVector2Array()
	for i in 32:
		pts.append(at + Vector2(cos(TAU * i / 32), sin(TAU * i / 32)) * radii)
	draw_colored_polygon(pts, colour)
