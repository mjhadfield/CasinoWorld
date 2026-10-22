@tool
class_name CardShuffler
extends Node2D
## An in-table card shuffler, like the automatic shufflers set into casino
## tables: a gunmetal housing sunk into the felt, a smoked-glass lid with the
## deck visible inside, a small display, a status light, an intake slot at the
## back (the dealer's side) and a delivery slot at the front, where hands come
## out ready to be dealt.
##
## Reusable by any table. It only animates itself; the table moves the cards,
## using the points below (all in the parent's coordinates). Put it in a layer
## drawn ABOVE the cards, so cards really slide out from under it and vanish
## into it:
##   slot_point()     inside the machine, behind the delivery slot (start dealt cards here)
##   delivery_point() on the felt just in front of it, where a delivered hand rests
##   intake_point()   inside, behind the intake slot (send used cards here)
##   deliver()        call as each hand comes out: the display and light react
##   take_in()        call as used cards go in
##   shuffle(seconds) the machine shuffles: it hums, the light blinks amber, the display shows progress
##   show_number(n)   its random number (Pai Gow: which position gets the first hand)
## Drawn in code, centred on its origin, so it stays sharp at any zoom, in its table's style (TableStyle
## `shuffler`): brushed metal (the original), gloss with an LED strip in the style's LED colour, or wood and brass.

const FONT := preload("res://assets/fonts/DejaVuSans-Bold.ttf")
const BODY := Vector2(24, 18)
const HOUSING := Color("3a3e44")
const HOUSING_DARK := Color("1f2226")
const GLASS := Color("12161b")
const LCD := Color("0b1a10")
const LCD_TEXT := Color("7dff9a")
const READY_LIGHT := Color("38e06a")
const BUSY_LIGHT := Color("ffb02e")
const DEAL_LIGHT := Color("4aa8ff")

var _state := "ready"           # ready | dealing | shuffling
var _shuffle_until := 0.0
var _shuffle_total := 1.0
var _flash_until := 0.0         # the light flashes as a hand comes out or cards go in
var _flash_colour := DEAL_LIGHT
var _dealing_until := 0.0       # shows DEALING while hands are coming out
var _number := 0                # a random number on the display...
var _number_until := 0.0        # ...until then


func slot_point() -> Vector2:
	return position + Vector2(0, BODY.y / 2 - 5)


func delivery_point() -> Vector2:
	return position + Vector2(0, BODY.y / 2 + 11)


func intake_point() -> Vector2:
	return position + Vector2(0, -BODY.y / 2 + 4)


func deliver() -> void:
	if _state != "shuffling":
		_state = "dealing"
	_dealing_until = _now() + 1.0
	_flash(DEAL_LIGHT, 0.18)


func show_number(n: int, seconds := 3.0) -> void:
	_number = n
	_number_until = _now() + seconds
	_flash(DEAL_LIGHT, 0.4)


func take_in() -> void:
	_flash(BUSY_LIGHT, 0.12)


func shuffle(seconds: float) -> void:
	_state = "shuffling"
	_shuffle_total = maxf(seconds, 0.1)
	_shuffle_until = _now() + _shuffle_total
	set_process(true)


func _ready() -> void:
	set_process(false)


func _flash(colour: Color, seconds: float) -> void:
	_flash_colour = colour
	_flash_until = _now() + seconds
	set_process(true)
	queue_redraw()


## Its table's design (House in the editor, or anywhere without a table).
func _look() -> Dictionary:
	var n := get_parent()
	while n != null and not n is CasinoTable:
		n = n.get_parent()
	return (n as CasinoTable).style() if n else TableStyle.fill({})


func _now() -> float:
	return Time.get_ticks_msec() / 1000.0


func _process(_delta: float) -> void:
	var now := _now()
	if (_state == "shuffling" and now >= _shuffle_until) or (_state == "dealing" and now >= _dealing_until):
		_state = "ready"
	if _state == "ready" and now >= _flash_until and now >= _number_until:
		set_process(false)
	queue_redraw()


func _draw() -> void:
	var now := _now()
	var shuffling := _state == "shuffling"
	# A faint hum while it shuffles: the lid and deck shiver, the housing doesn't.
	var hum := Vector2(sin(now * 90.0) * 0.18, cos(now * 70.0) * 0.12) if shuffling else Vector2.ZERO
	var body := Rect2(-BODY / 2, BODY)
	var look := _look()
	var kind: String = look.shuffler
	var tint := TableStyle.colour(look, "shufflerTint")
	var led := TableStyle.colour(look, "led")

	# Sunk into the table: a shadowed recess, then the housing.
	draw_colored_polygon(_rounded(body.grow(1.4), 3.2), Color(0, 0, 0, 0.55))
	match kind:
		"brass":   # a wooden case in a brass frame
			draw_colored_polygon(_rounded(body, 2.6), Color("24130a"))
			var case := _rounded(body.grow(-0.7), 2.1)
			var uv := PackedVector2Array()
			for p in case:
				uv.append(p / 30.0 + Vector2(0.5, 0.5))
			draw_colored_polygon(case, Color(1, 1, 1, 0.9), uv, TableStyle.WOODS[TableStyle.wood_of(look, str(look.shufflerWood))])
			_outline(_rounded(body.grow(-0.5), 2.2), Color("c9a24a"), 0.6)
		"black":   # gloss, lit from the top left
			draw_colored_polygon(_rounded(body, 2.6), tint.darkened(0.6))
			draw_colored_polygon(_rounded(body.grow(-0.7), 2.1), tint)
			draw_colored_polygon(PackedVector2Array([body.position + Vector2(1, 1), Vector2(body.position.x + 13, body.position.y + 1),
				Vector2(body.position.x + 1, body.position.y + 10)]), Color(1, 1, 1, 0.1))
		_:
			draw_colored_polygon(_rounded(body, 2.6), tint.darkened(0.45))
			draw_colored_polygon(_rounded(body.grow(-0.7), 2.1), tint)
			for i in 7:  # brushed metal
				var y := body.position.y + 1.5 + i * 2.4
				draw_line(Vector2(body.position.x + 1.2, y), Vector2(body.end.x - 1.2, y), Color(1, 1, 1, 0.035 + 0.02 * (i % 2)), 0.5)
	draw_line(body.position + Vector2(2.2, 0.8), Vector2(body.end.x - 2.2, body.position.y + 0.8), Color(1, 1, 1, 0.22), 0.4)

	# The intake slot along the back, where used cards go in.
	var intake := Rect2(-8.5, body.position.y + 1.6, 17, 1.6)
	draw_rect(intake, Color("050607"))
	draw_line(Vector2(intake.position.x, intake.end.y + 0.3), Vector2(intake.end.x, intake.end.y + 0.3), Color(1, 1, 1, 0.18), 0.3)

	# The smoked-glass lid, with the deck inside it.
	var lid := Rect2(-9.5, body.position.y + 4.2, 19, 7.6)
	draw_colored_polygon(_rounded(lid, 1.2), GLASS)
	var deck := Rect2(-5.5, lid.position.y + 1.4, 11, 4.8)
	draw_rect(Rect2(deck.position + hum, deck.size), Card2D.back_colour(look).darkened(0.35))
	for k in 5:  # card edges seen through the glass
		var x := deck.position.x + 1.0 + k * 2.2
		draw_line(Vector2(x, deck.position.y + 0.4) + hum, Vector2(x, deck.end.y - 0.4) + hum, Color(1, 1, 1, 0.08), 0.3)
	draw_rect(Rect2(deck.position + hum, deck.size), Color(Card2D.BACK_FRAME, 0.35), false, 0.3)
	draw_colored_polygon(PackedVector2Array([lid.position + Vector2(1.5, 0), lid.position + Vector2(6.5, 0),
		lid.position + Vector2(3.5, lid.size.y), lid.position + Vector2(-1.0, lid.size.y)]), Color(1, 1, 1, 0.07))  # reflection
	_outline(_rounded(lid, 1.2), Color(1, 1, 1, 0.16), 0.3)

	# The display and the status light, along the front.
	var lcd := Rect2(body.position.x + 2.2, lid.end.y + 1.0, 12.5, 3.2)
	var lcd_text := LCD_TEXT
	match kind:
		"black":
			lcd_text = Color("e9f6ff")
			draw_rect(lcd, Color("06080a"))
		"brass":
			lcd_text = Color("ffcf6e")
			draw_rect(lcd, Color("1b1206"))
		_:
			draw_rect(lcd, LCD)
	draw_rect(lcd, Color(0, 0, 0, 0.6), false, 0.3)
	var text := "READY"
	if shuffling:
		text = "SHUFFLE"  # what fits on its little display
		var done := clampf(1.0 - (_shuffle_until - now) / _shuffle_total, 0.0, 1.0)
		draw_rect(Rect2(lcd.position + Vector2(0.6, lcd.size.y - 0.8), Vector2((lcd.size.x - 1.2) * done, 0.35)), lcd_text)
	elif now < _number_until:
		text = "No. %d" % _number
	elif _state == "dealing":
		text = "DEALING"
	draw_string(FONT, Vector2(lcd.position.x, lcd.position.y + 2.0), text, HORIZONTAL_ALIGNMENT_CENTER, lcd.size.x, 2, lcd_text)

	var light_pos := Vector2(body.end.x - 4.0, lcd.position.y + lcd.size.y / 2)
	var light := led if kind == "black" else READY_LIGHT
	if now < _flash_until:
		light = _flash_colour
	elif shuffling:
		light = BUSY_LIGHT if fmod(now, 0.5) < 0.3 else BUSY_LIGHT.darkened(0.6)
	draw_circle(light_pos, 2.0, Color(light, 0.25))
	draw_circle(light_pos, 1.1, light)
	draw_circle(light_pos + Vector2(-0.35, -0.35), 0.35, Color(1, 1, 1, 0.7))
	if kind == "brass":
		draw_arc(light_pos, 1.5, 0, TAU, 16, Color("c9a24a"), 0.4, true)

	# The delivery slot across the front edge, with its steel lip.
	var slot := Rect2(-8.0, body.end.y - 1.9, 16, 1.2)
	draw_rect(slot, Color("050607"))
	draw_line(Vector2(slot.position.x - 0.5, body.end.y - 0.3), Vector2(slot.end.x + 0.5, body.end.y - 0.3), Color("c9a24a") if kind == "brass" else Color("9aa1aa"), 0.6)
	if kind == "black":   # the LED strip along its front
		draw_line(Vector2(-8, body.end.y - 0.7), Vector2(8, body.end.y - 0.7), Color(led, 0.15), 2.2)
		draw_line(Vector2(-8, body.end.y - 0.7), Vector2(8, body.end.y - 0.7), Color(led, 0.9), 0.9)


func _outline(pts: PackedVector2Array, colour: Color, width: float) -> void:
	var closed := pts.duplicate()
	closed.append(pts[0])
	draw_polyline(closed, colour, width, true)


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
