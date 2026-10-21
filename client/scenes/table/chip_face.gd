class_name ChipFace
## Chips in a table style's design (TableStyle `chips`): the top of a chip seen from above, a chip under it in
## a stack, and a chip on its edge in the dealer's tray. "classic" is the game's own chip (ChipButton.draw_chip),
## which Roulette, Craps and the HUD always use. The rest match the admin page's table designer:
##   clay      four edge inserts, a cream inlay with the value
##   ceramic   fine printed ticks round the edge, a white centre, a gloss
##   stripes   eight edge spots of three thin stripes, a darker centre
##   metal     a metal ring set in the face, in the rail's bead metal
##   house     the felt in the centre, the style's accent on the edge, its ink for the value
##   vintage   cream suit inserts round the edge, a cream centre

const CREAM := Color("f1e4c4")


## The top chip of a stack worth `pence` (its colour), showing `label`, in `design`'s chips ({}: the game's own).
static func draw(ci: CanvasItem, centre: Vector2, r: float, pence: int, label: String, design: Dictionary) -> void:
	var skin: String = design.get("chips", "classic")
	if skin == "classic":
		ChipButton.draw_chip(ci, centre, r, pence, label)
		return
	var c: Array = ChipButton.colours_for(pence)
	var c0: Color = c[0]
	var c1: Color = c[1]
	var dark := c1 == Color("000000")
	var deep := Color("1c1c1c") if dark else c1    # the value's colour on a pale centre
	var edge := Color("d8c9a0") if dark else Color.WHITE
	ci.draw_circle(centre + Vector2(0, 3), r, Color(0, 0, 0, 0.3))   # (as ChipButton.draw_chip)
	ci.draw_circle(centre, r, c0)
	match skin:
		"clay":
			for i in 4:
				var a := i * PI / 2 + 0.3
				ci.draw_arc(centre, r * 0.84, a, a + 0.5, 6, edge, r * 0.28)
				ci.draw_arc(centre, r * 0.84, a + 0.12, a + 0.38, 4, c1, r * 0.1)
			ci.draw_circle(centre, r * 0.6, Color("efe7d4"))
			ci.draw_arc(centre, r * 0.6, 0, TAU, 32, c1, r * 0.07, true)
			_label(ci, centre, r, label, deep)
		"ceramic":
			for i in 24:
				var a := i * PI / 12
				ci.draw_arc(centre, r * 0.88, a, a + 0.11, 3, Color(1, 1, 1, 0.9) if i % 2 else Color(c1, 0.9), r * 0.16)
			ci.draw_arc(centre, r * 0.72, 0, TAU, 32, Color(1, 1, 1, 0.55), r * 0.04, true)
			ci.draw_circle(centre, r * 0.58, Color("f6f4ee"))
			_label(ci, centre, r, label, Color("1c1c1c") if dark else c0)
			ci.draw_arc(centre, r * 0.8, PI * 1.05, PI * 1.6, 10, Color(1, 1, 1, 0.22), r * 0.35)   # the gloss
		"stripes":
			for i in 8:
				for j in 3:
					var a := i * PI / 4 + j * 0.09 - 0.09
					ci.draw_arc(centre, r * 0.85, a - 0.03, a + 0.03, 2, c1 if j == 1 else edge, r * 0.26)
			ci.draw_arc(centre, r * 0.66, 0, TAU, 32, Color(1, 1, 1, 0.8), r * 0.04, true)
			ci.draw_circle(centre, r * 0.6, Color("2a2a2a") if dark else c1)
			_label(ci, centre, r, label, Color.WHITE)
		"metal":
			var m: Array = TableStyle.BEADS.get(str(design.get("rail", {}).get("bead", "brass")), TableStyle.BEADS.brass)
			for i in 6:
				var a := i * PI / 3 + 0.25
				ci.draw_arc(centre, r * 0.86, a, a + 0.3, 4, edge, r * 0.22)
			ci.draw_arc(centre, r * 0.62, 0, TAU, 32, (m[0] as Color).darkened(0.2), r * 0.14, true)
			ci.draw_arc(centre, r * 0.62, PI * 1.1, PI * 1.9, 12, m[1], r * 0.07, true)   # lit along the top
			ci.draw_circle(centre, r * 0.54, c0.darkened(0.15))
			_label(ci, centre, r, label, Color.WHITE)
		"house":
			var accent := TableStyle.colour(design, "print.accent")
			for i in 6:
				var a := i * PI / 3 + 0.25
				ci.draw_arc(centre, r * 0.85, a, a + 0.38, 5, accent, r * 0.24)
			ci.draw_circle(centre, r * 0.62, TableStyle.colour(design, "felt.colour"))
			ci.draw_arc(centre, r * 0.62, 0, TAU, 32, accent, r * 0.06, true)
			ci.draw_arc(centre, r * 0.5, 0, TAU, 32, Color(TableStyle.colour(design, "print.ink"), 0.45), r * 0.02, true)
			_label(ci, centre, r, label, TableStyle.colour(design, "print.ink"))
		"vintage":
			var suits := ["s", "h", "c", "d"]
			for i in 4:
				var a := i * PI / 2 - PI / 2
				Card2D.draw_suit(ci, suits[i], centre + Vector2.from_angle(a) * r * 0.8, r * 0.3, CREAM)
				var b := a + PI / 4
				ci.draw_arc(centre, r * 0.82, b - 0.12, b + 0.12, 3, CREAM, r * 0.1)
			ci.draw_circle(centre, r * 0.56, Color("efe4c8"))
			ci.draw_arc(centre, r * 0.5, 0, TAU, 32, Color(deep, 0.6), r * 0.03, true)
			_label(ci, centre, r, label, deep)
		_:
			ChipButton.draw_chip(ci, centre, r, pence, label)


## A chip lower in a stack, seen from above: its body and a few of its edge marks.
static func layer(ci: CanvasItem, centre: Vector2, r: float, denom: int, design: Dictionary) -> void:
	var c: Array = ChipButton.COLOURS[denom]
	ci.draw_circle(centre, r, c[0])
	ci.draw_arc(centre, r, 0.2, PI - 0.2, 12, Color(0, 0, 0, 0.35), 0.35)
	var mark := CREAM if design.get("chips") == "vintage" else Color(1, 1, 1, 0.75)
	if design.get("chips") == "house":
		mark = TableStyle.colour(design, "print.accent")
	for k in 4:
		var a := 0.35 + k * 0.7
		ci.draw_arc(centre, r - 0.2, a, a + 0.22, 3, mark, 0.6)


## A chip standing on its edge in a tray channel, seen from above, filling `chip`: the k-th in its row.
static func edge(ci: CanvasItem, chip: Rect2, denom: int, k: int, skin: String) -> void:
	var c: Array = ChipButton.COLOURS[denom]
	ci.draw_rect(chip, c[0])
	var stripe := 0.18 + 0.32 * (k % 2)
	var mark := Color(0.94, 0.9, 0.82, 0.85) if skin in ["clay", "vintage"] else Color(1, 1, 1, 0.8)
	var w := 0.07 if skin in ["ceramic", "stripes"] else 0.12
	for f in [stripe, stripe + 0.5]:
		ci.draw_rect(Rect2(chip.position.x + chip.size.x * f, chip.position.y, chip.size.x * w, chip.size.y), mark)
	ci.draw_rect(Rect2(chip.position.x, chip.end.y - 0.12, chip.size.x, 0.12), Color(c[1], 0.8))


## The value, laid out at a large size and scaled down (as ChipButton.draw_chip, for the same reason).
static func _label(ci: CanvasItem, centre: Vector2, r: float, label: String, colour: Color) -> void:
	var font_size := int(r * (0.62 if label.length() <= 3 else 0.46))
	var shrink := font_size / float(ChipButton.LABEL_SIZE)
	var width := ChipButton.FONT.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, ChipButton.LABEL_SIZE).x
	ci.draw_set_transform(centre, 0.0, Vector2(shrink, shrink))
	ci.draw_string(ChipButton.FONT, Vector2(-width / 2, ChipButton.LABEL_SIZE * ChipButton.DIGIT_HEIGHT / 2), label,
		HORIZONTAL_ALIGNMENT_LEFT, -1, ChipButton.LABEL_SIZE, colour)
	ci.draw_set_transform(Vector2.ZERO)
