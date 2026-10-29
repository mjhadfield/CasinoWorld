class_name CountOverlay
extends Node2D
## The card count at Blackjack, a training aid (Settings › Cards › Card count at Blackjack, off to start with): the
## Hi-Lo running count (RC) and true count (TC) of the cards seen since the shuffle, with the decks still to come,
## from the server's `count` (BlackjackMachine.count: the hole card only once it's turned over).
##
## It sits on the felt just above the shoe, but it's meant to read as a
## heads-up display over the table, not part of it: a smoked-glass panel hovering on a soft shadow, a hairline edge
## that breathes, the HUD's lettering (not the table style's). The figures roll to each new count as the cards land;
## the edge flashes green as the count rises and red as it falls; the true count is green from +2 (a good count) and
## red from -1. While the shoe's shuffled it reads SHUFFLING with a slow sweep, then starts again at 0.
##
## The table feeds it (bj_table.gd): set_count() from the snapshot and each event that shows cards, shuffling() on
## `shuffle`. Drawn in code, centred on its origin, in table units (drawn at 10x and scaled down so the lettering is
## sharp at any zoom). It redraws a few times a second while it breathes, every frame only while something moves.

const FONT := preload("res://assets/fonts/BarlowCondensed-Bold.ttf")
const SIZE := Vector2(28, 11)
const K := 0.1                                 # its lettering's drawn at 1/K and scaled down
const ROLL := 0.35                             # seconds for the figures to roll to a new count
const FLASH := 0.6                             # ...and for the edge's flash to fade
const BREATH := 2.4                            # the edge's slow breath, as the spot glows (SpotGlow)
const BOB := 4.0                               # its hover, a quarter of a unit up and down
const IDLE_FPS := 12.0                         # how often it redraws when only breathing

const GLASS := Color(0.035, 0.045, 0.055, 0.74)
const EDGE := Color("c9a24a")
const INK := Color("f3ead2")
const MUTED := Color(0.93, 0.88, 0.76, 0.55)
const UP := Color("5fe39a")
const DOWN := Color("ff7a6b")

var _running := 0.0
var _true := 0.0
var _decks := 8.0
var _from := Vector2.ZERO                      # (running, true) the figures are rolling from...
var _to := Vector2.ZERO                        # ...and to
var _roll_start := -100.0
var _flash_start := -100.0
var _flash_colour := UP
var _shuffling := false
var _shuffle_start := 0.0
var _last_draw := 0.0


func _ready() -> void:
	z_index = 2   # (above the cards and the dealer's labels in its layer)
	_apply_setting()
	Settings.changed.connect(func(key, _v):
		if key == "show_card_count":
			_apply_setting())


func _apply_setting() -> void:
	visible = bool(Settings.value("show_card_count"))
	set_process(visible)
	queue_redraw()


## A count from the server: {running, true, decks}. `instant` (a snapshot): no roll, no flash.
func set_count(c: Dictionary, instant := false) -> void:
	if c.is_empty():
		return
	var running := float(c.get("running", 0))
	var tc := float(c.get("true", 0.0))
	_decks = float(c.get("decks", _decks))
	_shuffling = false
	if not instant and running != _to.x:
		_flash_colour = UP if running > _to.x else DOWN
		_flash_start = _now()
	_from = Vector2(_running, _true) if not instant else Vector2(running, tc)
	_to = Vector2(running, tc)
	_roll_start = -100.0 if instant else _now()
	if instant:
		_running = running
		_true = tc
	queue_redraw()


## The shoe's going through the shuffler: SHUFFLING until the new shoe's count comes.
func shuffling() -> void:
	_shuffling = true
	_shuffle_start = _now()
	queue_redraw()


func _now() -> float:
	return Time.get_ticks_msec() / 1000.0


func _process(_delta: float) -> void:
	var now := _now()
	var t := clampf((now - _roll_start) / ROLL, 0.0, 1.0)
	var eased := 1.0 - pow(1.0 - t, 3.0)
	_running = lerpf(_from.x, _to.x, eased)
	_true = lerpf(_from.y, _to.y, eased)
	var busy := t < 1.0 or now - _flash_start < FLASH or _shuffling
	if busy or now - _last_draw >= 1.0 / IDLE_FPS:
		_last_draw = now
		queue_redraw()


# ------------------------------------------------------------------ drawing
func _draw() -> void:
	var now := _now()
	var lift := Vector2(0, sin(now * TAU / BOB) * 0.25)
	draw_set_transform(lift, 0.0, Vector2(K, K))
	var r := Rect2(-SIZE / 2 / K, SIZE / K)
	# The glass, on a shadow that sits down and right of it: it hovers.
	var box := StyleBoxFlat.new()
	box.bg_color = GLASS
	box.set_corner_radius_all(18)
	box.shadow_color = Color(0, 0, 0, 0.42)
	box.shadow_size = 14
	box.shadow_offset = Vector2(6, 10)
	var breath := 0.45 + 0.1 * sin(now * TAU / BREATH)
	var edge := Color(EDGE, breath)
	var flash := 1.0 - clampf((now - _flash_start) / FLASH, 0.0, 1.0)
	if flash > 0.0:
		edge = edge.lerp(Color(_flash_colour, 0.95), flash)
	box.border_color = edge
	box.set_border_width_all(3)
	box.anti_aliasing = true
	draw_style_box(box, r)
	# A sheen across the top of the glass.
	draw_rect(Rect2(r.position + Vector2(18, 6), Vector2(r.size.x - 36, 2)), Color(1, 1, 1, 0.06))
	_text("HI-LO", Vector2(r.position.x + 16, -18), 19, MUTED)
	_text("%.1f DECKS" % _decks, Vector2(r.end.x - 16, -18), 19, MUTED, true)
	if _shuffling:
		var sweep := fmod((now - _shuffle_start) / 1.6, 1.0)
		var x := lerpf(r.position.x + 20, r.end.x - 60, sweep)
		draw_rect(Rect2(Vector2(x, r.position.y + 34), Vector2(40, r.size.y - 44)), Color(EDGE, 0.12))
		_text("SHUFFLING", Vector2(-_width("SHUFFLING", 40) / 2, 34), 40, INK)
	else:
		draw_line(Vector2(0, -2), Vector2(0, 42), Color(EDGE, 0.3), 2.0)
		_text("RC", Vector2(r.position.x + 16, 32), 22, MUTED)
		_text(_signed(roundi(_running)), Vector2(r.position.x + 46, 37), 44, INK)
		_text("TC", Vector2(14, 32), 22, MUTED)
		_text(_signed_tc(_true), Vector2(44, 37), 44, _tc_colour(_to.y))
	draw_set_transform(Vector2.ZERO)


func _text(s: String, at: Vector2, size: int, colour: Color, right := false) -> void:
	var x := at.x - (_width(s, size) if right else 0.0)
	draw_string(FONT, Vector2(x, at.y), s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, colour)


func _width(s: String, size: int) -> float:
	return FONT.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x


static func _signed(n: int) -> String:
	return "+%d" % n if n > 0 else str(n)


static func _signed_tc(v: float) -> String:
	var s := "%.1f" % absf(v)
	if s == "0.0":
		return "0.0"
	return ("+" if v > 0 else "-") + s


static func _tc_colour(tc: float) -> Color:
	if tc >= 2.0:
		return UP
	if tc <= -1.0:
		return DOWN
	return INK
