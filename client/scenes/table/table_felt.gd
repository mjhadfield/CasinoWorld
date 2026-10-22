@tool
class_name TableFelt
extends Node2D
## The base of every table's felt: StyledFelt (the card tables, Roulette and Craps, each in its table style)
## extends it. It sits the drawing in FeltCache and holds what the felts share: the chip tray's contents
## (edge_chip, the denominations and how full each channel is) and the drawing helpers. A game's felt draws in
## paint() and lays out its printing in _draw_layout(). Geometry comes from the parent table, so moving a Seat
## marker in the editor moves that seat's spots too.
##
## Everything is drawn in code, so it stays sharp at any zoom, and in the game it's shown as a
## picture painted at the screen's resolution (FeltCache): paint() is the drawing. This node sits
## just in front of the dealer's feet, so Y-sorting draws the table over the
## dealer's legs (they stand in the bay, behind the chip tray) and under
## everyone standing beside or in front of it. Everything is drawn in table
## coordinates.

const FONT := preload("res://assets/fonts/DejaVuSans-Bold.ttf")
const GRAIN := preload("res://assets/tiles/felt_grain.png")   # the fine felt grain (tools/build_art.py)
const WOOD_DARK := Color("4a2412")
const WOOD_SHINE := Color(1.0, 0.84, 0.67, 0.35)
const SPOT_FILL := Color(0, 0, 0, 0.15)
const RECESS := Color("1a0b05")       # a sunk channel (the craps chip rail)
# The chip tray: ten channels, highest chips on the left, never all full.
const TRAY_DENOMS := [50000, 10000, 10000, 2500, 2500, 2500, 500, 500, 100, 100]
const TRAY_FILL := [0.45, 1.0, 0.6, 0.0, 0.85, 1.0, 0.7, 0.0, 0.9, 0.35]
const CHIP_EDGE := 1.05               # one chip lying in a channel, seen from above

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


## A light's offset `v` as the screen sees it (a shadow falling down the screen, a crown lit from
## above), in the table's coordinates: on a table showing upside down it still falls down the screen.
func _lit(v: Vector2) -> Vector2:
	var t := _table()
	return v.rotated(-t.screen_turn()) if t and t.is_inside_tree() else v


func _draw() -> void:
	if _cache:   # shown as FeltCache's picture: have it painted again instead
		_cache.repaint()
		return
	paint()


## The table's drawing (FeltCache paints it).
func paint() -> void:
	pass


## A game's printed layout: its title, rules and every seat's spots.
func _draw_layout(_t: CasinoTable) -> void:
	pass


## One chip standing on its edge in a channel, seen from above, filling `chip`: the k-th in
## its row (the edge spots are staggered chip to chip). `upright` for a channel running
## left to right, where the chips stand across it.
static func edge_chip(ci: CanvasItem, chip: Rect2, denom: int, k: int, upright := false) -> void:
	var colours: Array = ChipButton.COLOURS[denom]
	ci.draw_rect(chip, colours[0])
	var stripe := 0.18 + 0.32 * (k % 2)
	for f in [stripe, stripe + 0.5]:
		if upright:
			ci.draw_rect(Rect2(chip.position.x, chip.position.y + chip.size.y * f, chip.size.x, chip.size.y * 0.12), Color(1, 1, 1, 0.8))
		else:
			ci.draw_rect(Rect2(chip.position.x + chip.size.x * f, chip.position.y, chip.size.x * 0.12, chip.size.y), Color(1, 1, 1, 0.8))
	if upright:
		ci.draw_line(Vector2(chip.end.x, chip.position.y), chip.end, colours[1], 0.15)
	else:
		ci.draw_line(Vector2(chip.position.x, chip.end.y), chip.end, colours[1], 0.15)


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
