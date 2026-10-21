@tool
class_name TableFelt
extends Node2D
## The table itself in Mahogany & Brass (picked by Mike on the Table Looks
## mockups), shared by every game: a polished wood rail with a brass bead where
## it meets the felt, deep crimson felt with a woven grain, the chip tray set
## into the bay's rail, and the printed pieces every layout uses (the clear
## Jackpot disc, ringed circle spots, Cinzel lettering). A game's felt
## (tcp_felt.gd, bj_felt.gd) extends this and draws its own layout in
## _draw_layout(). Geometry comes from the parent table, so moving a Seat
## marker in the editor moves that seat's spots too.
##
## Everything is drawn in code, so it stays sharp at any zoom, and in the game it's shown as a
## picture painted at the screen's resolution (FeltCache): paint() is the drawing. This node sits
## just in front of the dealer's feet, so Y-sorting draws the table over the
## dealer's legs (they stand in the bay, behind the chip tray) and under
## everyone standing beside or in front of it. Everything is drawn in table
## coordinates.

const FONT := preload("res://assets/fonts/DejaVuSans-Bold.ttf")
## Cinzel SemiBold, a static instance of the variable font with its overlapping
## outlines merged (made with fonttools' varLib.instancer --remove-overlaps):
## MSDF text renders overlapping outlines with specks and stray marks.
const CINZEL := preload("res://assets/fonts/Cinzel-SemiBold.ttf")
const GRAIN := preload("res://assets/tiles/felt_grain.png")
const FELT := Color("93141f")
const FELT_DEEP := Color("5c0a12")    # towards the rail
const WOOD := Color("6e3a1e")
const WOOD_DARK := Color("4a2412")
const WOOD_PAD := Color("2a140a")     # the dealer's side of the rail
const WOOD_SHINE := Color(1.0, 0.84, 0.67, 0.35)
const BRASS := Color("c9a24a")
const CREAM := Color("f1e4c4")
const SPOT_FILL := Color(0, 0, 0, 0.15)
const RECESS := Color("1a0b05")       # the chip tray's channels
# The chip tray: ten channels, highest chips on the left, never all full.
const TRAY_DENOMS := [50000, 10000, 10000, 2500, 2500, 2500, 500, 500, 100, 100]
const TRAY_FILL := [0.45, 1.0, 0.6, 0.0, 0.85, 1.0, 0.7, 0.0, 0.9, 0.35]
const CHIP_EDGE := 1.05               # one chip lying in a channel, seen from above

var _vignette: GradientTexture2D
var painting := false        # this is FeltCache's copy, which paints the picture
var table_ref: CasinoTable   # (the copy's table: it isn't the copy's parent)
var _cache: FeltCache


func _ready() -> void:
	if not Engine.is_editor_hint() and not painting:
		_attach_cache.call_deferred()   # once the table has its Body


func _attach_cache() -> void:
	_cache = FeltCache.attach(self)
	queue_redraw()


func _table() -> CasinoTable:
	return table_ref if table_ref else get_parent() as CasinoTable


func _draw() -> void:
	if _cache:   # shown as FeltCache's picture: have it painted again instead
		_cache.repaint()
		return
	paint()


## The felt gets lighter towards the middle of the table.
func _felt_gradient() -> GradientTexture2D:
	if _vignette == null:
		var g := Gradient.new()
		g.set_color(0, FELT)
		g.set_offset(0, 0.35)
		g.set_color(1, FELT_DEEP)
		_vignette = GradientTexture2D.new()
		_vignette.gradient = g
		_vignette.fill = GradientTexture2D.FILL_RADIAL
		_vignette.fill_from = Vector2(0.5, 0.5)
		_vignette.fill_to = Vector2(1.0, 0.5)
		_vignette.width = 256
		_vignette.height = 256
	return _vignette


func paint() -> void:
	var t := _table()
	if t == null:
		return
	draw_set_transform(-position)  # draw in table coordinates
	var r := CasinoTable.RAIL

	# Its shadow on the carpet.
	draw_colored_polygon(_shifted(CasinoTable.grown(r + 4.0), Vector2(0, 3)), Color(0, 0, 0, 0.16))
	draw_colored_polygon(_shifted(CasinoTable.grown(r + 1.5), Vector2(0, 2)), Color(0, 0, 0, 0.3))
	# The wood rail: a dark edge, polished wood whose grain follows the curve,
	# dark leather padding on the dealer's side, and a highlight along its top.
	var rail := CasinoTable.grown(r + 0.5)
	draw_colored_polygon(rail, WOOD_DARK)
	draw_colored_polygon(CasinoTable.grown(r - 1.1), WOOD)
	for grain in [[1.6, 0.45], [2.9, 0.3], [4.3, 0.4], [5.4, 0.25]]:
		_loop(CasinoTable.grown(grain[0]), Color(WOOD_DARK, grain[1]), 0.35)
	var dealer_side := PackedVector2Array([Vector2(-400, -400), Vector2(400, -400),
		Vector2(400, t.tray_rect().position.y + 3), Vector2(-400, t.tray_rect().position.y + 3)])
	for part in Geometry2D.intersect_polygons(rail, dealer_side):
		draw_colored_polygon(part, WOOD_PAD)
	_loop(_shifted(CasinoTable.grown(r * 0.68), Vector2(0, -1.2)), WOOD_SHINE, 1.1)

	# The felt: crimson, darker towards the rail, with a woven grain.
	var felt := CasinoTable.outline()
	var centre := Vector2(0, -70)
	var uv := PackedVector2Array()
	var grain_uv := PackedVector2Array()
	for p in felt:
		uv.append((p - centre) / 380.0 + Vector2(0.5, 0.5))
		grain_uv.append(p / 40.0)
	draw_colored_polygon(felt, Color.WHITE, uv, _felt_gradient())
	draw_colored_polygon(felt, Color(1, 1, 1, 0.25), grain_uv, GRAIN)
	# A cream pinstripe just inside the edge, the felt's shadow under the rail,
	# and the brass bead where the felt meets the wood.
	_loop(CasinoTable.grown(-5.0), Color(CREAM, 0.7), 0.5)
	_loop(CasinoTable.grown(-0.9), Color(0, 0, 0, 0.3), 1.4)
	_loop(CasinoTable.grown(-0.3), BRASS, 0.6)

	_chip_tray(t)

	_draw_layout(t)
	draw_set_transform(-position)


## A game's printed layout: its title, rules and every seat's spots.
func _draw_layout(_t: CasinoTable) -> void:
	pass


## The Jackpot spot isn't felt: it's a clear plastic disc with a light under it
## (the house can see who has a Jackpot bet down). The light itself is drawn by
## the Lights node, which flashes and glows the whole disc.
func _jackpot_disc(pos: Vector2) -> void:
	var r := CasinoTable.SPOT_R
	draw_circle(pos + Vector2(0, 0.7), r + 0.5, Color(0, 0, 0, 0.3))   # its shadow on the felt
	draw_circle(pos, r, Color(0.84, 0.92, 0.96, 0.28))                 # clear plastic
	draw_arc(pos, r - 0.4, 0, TAU, 32, Color(1, 1, 1, 0.75), 0.8, true)
	draw_arc(pos, r - 2.0, PI * 1.05, PI * 1.55, 10, Color(1, 1, 1, 0.6), 0.7, true)  # shine
	_text("JACKPOT", pos, 2, Color(1, 1, 1, 0.85), CINZEL)              # centred, like the other spots


## A circle spot fractionally bigger than a chip: shaded felt, a printed ring.
func _circle_spot(pos: Vector2, ring: Color, lines: Array) -> void:
	var cinzel := CINZEL
	draw_circle(pos, CasinoTable.SPOT_R, SPOT_FILL)
	draw_arc(pos, CasinoTable.SPOT_R - 0.4, 0, TAU, 32, ring, 0.8, true)
	if lines.size() == 1:
		_text(lines[0], pos, 2, ring, cinzel)
	else:  # two lines, the pair centred on the spot
		_text(lines[0], pos - Vector2(0, 1.3), 2, ring, cinzel)
		_text(lines[1], pos + Vector2(0, 1.3), 2, ring, cinzel)


## The chip tray, set into the rail at the back of the bay: a mahogany frame
## with a brass rim around ten felt-lined channels, the chips lying in them on
## their edges. Some channels are full, some part-full, some empty.
func _chip_tray(t: CasinoTable) -> void:
	var tray := t.tray_rect()
	draw_colored_polygon(_shifted(_rounded(tray.grow(0.8), 2.8), Vector2(0, 1.2)), Color(0, 0, 0, 0.4))
	draw_colored_polygon(_rounded(tray, 2.5), WOOD_DARK)
	draw_colored_polygon(_rounded(tray.grow(-0.8), 2.0), WOOD)
	_loop(_rounded(tray, 2.5), BRASS, 0.5)
	var inner := tray.grow(-2.0)
	var w := inner.size.x / TRAY_DENOMS.size()
	for i in TRAY_DENOMS.size():
		var channel := Rect2(inner.position.x + i * w + 0.3, inner.position.y, w - 0.6, inner.size.y)
		draw_colored_polygon(_rounded(channel, 1.2), RECESS)
		draw_line(channel.position + Vector2(0.6, 0.4), Vector2(channel.end.x - 0.6, channel.position.y + 0.4), Color(0, 0, 0, 0.6), 0.6)
		var colours: Array = ChipButton.COLOURS[TRAY_DENOMS[i]]
		var count := int(round(TRAY_FILL[i] * floorf((channel.size.y - 0.6) / CHIP_EDGE)))
		for k in count:  # stacked from the front of the channel back towards the dealer
			var chip := Rect2(channel.position.x + 0.35, channel.end.y - 0.3 - (k + 1) * CHIP_EDGE, channel.size.x - 0.7, CHIP_EDGE - 0.12)
			draw_rect(chip, colours[0])
			var stripe := 0.18 + 0.32 * (k % 2)  # the edge spots, staggered chip to chip
			for f in [stripe, stripe + 0.5]:
				draw_rect(Rect2(chip.position.x + chip.size.x * f, chip.position.y, chip.size.x * 0.12, chip.size.y), Color(1, 1, 1, 0.8))
			draw_line(Vector2(chip.position.x, chip.end.y), chip.end, colours[1], 0.15)
		if count > 0:  # light catching the front chip's rim
			draw_line(Vector2(channel.position.x + 0.5, channel.end.y - 0.5), Vector2(channel.end.x - 0.5, channel.end.y - 0.5), Color(1, 1, 1, 0.25), 0.3)


func _text(s: String, centre: Vector2, size: int, colour: Color, font: Font) -> void:
	var width := font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	draw_string(font, centre + Vector2(-width / 2, size * 0.35), s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, colour)


## A closed outline.
func _loop(pts: PackedVector2Array, colour: Color, width: float) -> void:
	if pts.is_empty():
		return
	var closed := pts.duplicate()
	closed.append(pts[0])
	draw_polyline(closed, colour, width, true)


static func _shifted(pts: PackedVector2Array, by: Vector2) -> PackedVector2Array:
	var out := PackedVector2Array()
	for p in pts:
		out.append(p + by)
	return out


## A rectangle with rounded corners, as a polygon.
static func _rounded(rect: Rect2, radius: float) -> PackedVector2Array:
	var pts := PackedVector2Array()
	var r := minf(radius, minf(rect.size.x, rect.size.y) / 2)
	var corners := [[rect.end - Vector2(r, r), 0.0], [Vector2(rect.position.x + r, rect.end.y - r), PI / 2],
		[rect.position + Vector2(r, r), PI], [Vector2(rect.end.x - r, rect.position.y + r), PI * 1.5]]
	for c in corners:
		for i in 5:
			var a: float = c[1] + PI / 2 * i / 4.0
			pts.append(c[0] + Vector2(cos(a), sin(a)) * r)
	return pts
