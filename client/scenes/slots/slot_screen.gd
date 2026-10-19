class_name SlotScreen
extends Control
## The full-screen slot game you get sitting at a cabinet (signed off on the slots mockup,
## docs/slots/mockup/game.js): the jackpot meters and the logo across the top, the reels in
## a wooden frame, the random-feature panel, Buy Bonus, the button deck, and the three
## feature scenes -- the Trail Bonus, Combo Free Spins and the Jackpot Pick.
##
## The server decides everything; this plays its events in order. It's drawn on a virtual
## 1280x720 canvas scaled to fit the window, in three layers: the chrome underneath, the
## reels (clipped to their window) and everything over them. Sitting down, it grows out of
## the cabinet's little screen; standing up, it shrinks back into it.

signal stand_requested
signal settings_requested

## The shared progressives, latest from the server (any cabinet's spin carries them), and
## how much each grows by a second on its own -- the meters count up between updates.
static var meters := {}
static var meter_rates := {}
static var _meters_at := 0.0


static func set_meters(amounts: Dictionary, rates = null) -> void:
	meters = amounts
	if rates is Dictionary:
		meter_rates = rates
	_meters_at = Time.get_ticks_msec() / 1000.0


## A meter as it stands now (pence).
static func meter_now(id: String) -> float:
	var grown := float(meter_rates.get(id, 0.0)) * (Time.get_ticks_msec() / 1000.0 - _meters_at)
	return float(meters.get(id, 0)) + maxf(0.0, grown)

const W := 1280.0
const H := 720.0
const CELL_W := 150.0
const CELL_H := 112.0
const REEL_X := 265.0
const REEL_Y := 128.0
const REEL_W := CELL_W * 5
const REEL_H := CELL_H * 4
# Where things go on the 1280x720 screen. Everything drawn or clickable stays inside
# SAFE (debug builds warn when a button doesn't), so nothing clips on any window shape.
const SAFE := Rect2(4, 4, W - 8, H - 8)
const LOGO_RECT := Rect2(494, 4, 292, 99)    # between the Major and Minor meters
const DECK_TOP := 592.0                      # the button deck's band
const DECK_ROW := Rect2(0, 626, W, 80)       # the deck's boxes and buttons
const SPIN_CENTRE := Vector2(1112, 664)
const SPIN_R := 46.0                         # (its dark ring is 4 wider: 614..714)
const SIDE_INFO := Rect2(1052, 0, 196, 104)  # each "3+ WAGONS" box (y set per box)
const RYE := preload("res://assets/fonts/Rye-Regular.ttf")
const COND := preload("res://assets/fonts/BarlowCondensed-Bold.ttf")
const CREAM := Color("f6ead0")
const GOLD := Color("f4c94f")
const GOLD_HI := Color("fff1b0")
const INK := Color("2b1004")
const MUTED := Color("b89b74")
const TIERS := {"mini": Color("4fb3ff"), "minor": Color("55d07a"), "major": Color("c768ff"), "grand": Color("ff5a48")}
const TIER_NAMES := {"mini": "MINI", "minor": "MINOR", "major": "MAJOR", "grand": "GRAND"}
const LINE_COLOURS := ["ffd54a", "ff7a59", "5fd4ff", "9cff6b", "ff6bd5", "ffb347", "6b9dff", "d0ff4a", "ff4a6e",
	"4affc3", "ffe0a3", "b38bff", "ff9e4a", "4ad2ff", "e3ff7a", "ff7ab8", "7affd9", "ffcf4a", "a6b8ff",
	"ff6a4a", "4aff8f", "ffa6e1", "c6ff4a", "4a9eff", "ffd1a6"]
const FEATURE_ROWS := [["wilds", "RANDOM WILDS"], ["wildReels", "WILD REELS"], ["colossal", "COLOSSAL REELS"],
	["multiplier", "MULTIPLIER"], ["upgrade", "SYMBOL UPGRADE"], ["repeat", "REPEAT WIN"], ["instant", "INSTANT WIN"]]
const TILE := 86.0
const TRAIL_ICONS := {"coin": "t_coin", "snake": "t_snake", "heart": "t_heart", "forward": "t_forward", "back": "t_forward",
	"lightning": "t_lightning", "crate": "t_crate", "upgrade": "t_upgrade", "double": "t_double", "prizepot": "t_gold"}


## One drawing layer: it asks the screen to draw its part.
class Layer extends Control:
	var host: SlotScreen
	var which := ""

	func _draw() -> void:
		host._draw_layer(self, which)


var cab: SlotCabinet
var rules := {}
var variant := "armadillo"
var _strips: Array = []
var _free_strips: Array = []
var _big: Array = []
var _lines: Array = []
var _ladder: Array = [25, 50, 75, 100, 150, 250, 500, 1000, 2500]
var _bet_idx := 3
var _under: Layer
var _reels_layer: Layer
var _over: Layer
var _box := StyleBoxFlat.new()

# where the virtual canvas sits (grows out of the cabinet's screen)
var _grow := 1.0
var _from_rect := Rect2()
var _closing := false

# the clock, animation and the event queue
var _now := 0.0
var _epoch := 0
var _hurry := false
var _tweens: Array = []
var _queue: Array = []
var _running := false
var _hits: Array = []
var _hover := ""
var _last_spin_sent := -10.0
var _credit_adj := 0      # what the credit meter shows on top of the held balance: -stakes, +wins shown so far

# what's on screen
var grid: Array = []
var landed := true
var wins: Array = []
var cycle := 0
var cycle_at := 0.0
var win_shown := 0.0
var win_target := 0.0
var roller := 1.0
var message := ""
var feature_lit := {}
var multiplier := 1
var cell_fx := {}
var banner := {}
var overlay := {}
var particles: Array = []
var flyers: Array = []
var shake := 0.0
var reels: Array = []
var colossal := {}
var free := {}
var trail := {}
var pick := {}
var auto := 0
var auto_menu := false
var turbo := false
var _spinning_shown := false


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	focus_mode = Control.FOCUS_NONE
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	for which in ["under", "reels", "over"]:
		var layer := Layer.new()
		layer.host = self
		layer.which = which
		layer.mouse_filter = Control.MOUSE_FILTER_IGNORE
		layer.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
		add_child(layer)
		match which:
			"under": _under = layer
			"reels": _reels_layer = layer
			"over": _over = layer
	_reels_layer.clip_contents = true
	_box.anti_aliasing = true
	hide()
	for r in 5:
		reels.append({"r": r, "pos": 0.0, "spinning": false, "stopping": false, "v": 0.0, "strip": [], "glow": 0.0})


# ------------------------------------------------------------------ opening and closing
func open(c: SlotCabinet, r: Dictionary, from_rect: Rect2) -> void:
	cab = c
	rules = r
	variant = str(r.get("variant", "armadillo"))
	_strips = r.get("strips", [])
	_free_strips = r.get("free_strips", [])
	_big = r.get("big_strip", [])
	_lines = r.get("lines", [])
	_ladder = r.get("ladder", _ladder)
	_bet_idx = clampi(_bet_idx, 0, _ladder.size() - 1)
	_reset_state()
	for x in reels:
		x.strip = _strips[x.r] if _strips.size() == 5 else []
		x.pos = float(randi() % maxi(1, x.strip.size()))
	grid = _grid_from_reels()
	message = "25 LINES  ·  GOOD LUCK, PARTNER"
	_from_rect = from_rect
	_closing = false
	_grow = 0.0
	show()
	var tw := create_tween()
	tw.tween_property(self, "_grow", 1.0, 0.45).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)


func close(to_rect: Rect2) -> void:
	auto = 0
	overlay = {}
	_from_rect = to_rect
	_closing = true
	_epoch += 1
	_queue.clear()
	_running = false
	_credit_adj = 0
	var tw := create_tween()
	tw.tween_property(self, "_grow", 0.0, 0.35).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN)
	tw.tween_callback(func():
		if _closing:
			hide())


func _reset_state() -> void:
	_epoch += 1
	_queue.clear()
	_running = false
	_tweens.clear()
	_hurry = false
	wins = []
	cell_fx = {}
	feature_lit = {}
	multiplier = 1
	banner = {}
	overlay = {}
	particles = []
	flyers = []
	colossal = {}
	free = {}
	trail = {}
	pick = {}
	landed = true
	win_shown = 0.0
	win_target = 0.0
	_credit_adj = 0
	Session.hold_balance(false)


## A `table_state` for this cabinet (sitting down, or after a resync): show it as it is.
func apply_snapshot(state: Dictionary) -> void:
	_reset_state()
	var bet := int(state.get("bet", 100))
	if bet in _ladder:
		_bet_idx = _ladder.find(bet)
	var last = state.get("last")
	if last != null:
		grid = last.grid
	match str(state.get("phase", "idle")):
		"trail":
			if state.get("trail") != null:
				_begin_trail(state.trail)
				trail.waiting = float(state.get("trail_ready_in", 0.0)) <= 0.0
				trail.auto_at = _now + float(state.get("timer", 6.0) if state.get("timer") != null else 6.0)
		"free_games":
			if state.get("free") != null:
				free = {"n": int(state.free.n), "of": int(state.free.of), "total": int(state.free.total)}
		"jackpot_pick":
			if state.get("pick") != null:
				_begin_pick()
				var coins: Array = state.pick.coins
				for i in coins.size():
					if coins[i] != null:
						pick.coins[i].tier = str(coins[i])
						pick.coins[i].flip = 1.0
						pick.tally[str(coins[i])] = int(pick.tally.get(str(coins[i]), 0)) + 1


func on_resynced() -> void:
	pass   # the table_state that follows redraws it


## Escape: shut whatever's open, else stand up.
func cancel_pressed() -> void:
	if auto_menu:
		auto_menu = false
	elif not overlay.is_empty() and overlay.kind in ["info", "buy", "notice", "cashout"]:
		overlay = {}
	else:
		_cash_out()


# ------------------------------------------------------------------ the server's events
func on_event(ev: Dictionary) -> void:
	match ev.kind:
		"spin":
			Session.hold_balance(true)   # the credit shows the win when the reels stop
			_credit_adj -= int(ev.outcome.bet)
			if _running:
				_hurry = true   # a new spin cuts the last one's show short
		"bonus_bought":
			Session.hold_balance(true)
			_credit_adj -= int(ev.cost)
	_queue.append(ev)
	if not _running:
		_run_queue()


func _run_queue() -> void:
	_running = true
	var ep := _epoch
	while not _queue.is_empty():
		var ev: Dictionary = _queue.pop_front()
		await _handle(ev)
		if ep != _epoch:
			return
	_running = false


func _handle(ev: Dictionary) -> void:
	match ev.kind:
		"spin":
			await _on_spin(ev)
		"bonus_bought":
			message = "BONUS BOUGHT: %s" % Money.format(int(ev.cost))
		"jackpot_start":
			_begin_pick()
			Sfx.play("bonus_trigger")
			await _banner("JACKPOT PICK", "pick coins until three match", 1.8)
		"jackpot_reveal":
			await _reveal_coin(int(ev.index), str(ev.tier))
		"slot_jackpot_won":
			await _jackpot_won(ev)
		"trail_start":
			_begin_trail(ev.trail)
			Sfx.play("bonus_trigger")
			await _banner("TRAIL BONUS", "bought for %s" % Money.format(int(ev.trail.bet) * int(rules.get("buy_cost", 45)))
				if ev.get("bought", false) else "fire the pistol to move the armadillo", 2.2)
			trail.waiting = true
			trail.auto_at = _now + 6.0
			message = "FIRE THE PISTOL  ·  SPACE OR CLICK FIRE"
		"trail_roll":
			if not trail.is_empty():
				trail.waiting = false
				await _animate_roll(ev.roll)
				trail.total = int(ev.total)
				if not ev.roll.done:
					trail.waiting = true
					trail.auto_at = _now + 6.0
		"trail_end":
			await _wait(0.6)
			_credit_adj += int(ev.total)
			await _summary("PRIZEPOT!" if ev.get("prizepot", false) else "TRAIL BONUS",
				"%d shots at %s" % [int(ev.rolls), Money.format(int(trail.get("bet", 100)))], int(ev.total))
			if int(ev.total) >= 10 * int(trail.get("bet", 100)):
				await _big_win(int(ev.total), int(trail.get("bet", 100)))
			trail = {}
			_clear_wins()
			win_shown = float(ev.total)
			win_target = win_shown
			message = "TRAIL BONUS PAID %s" % Money.format(int(ev.total))
		"free_start":
			free = {"n": 0, "of": int(ev.of), "total": 0, "bet": int(ev.bet)}
			Sfx.play("bonus_trigger")
			await _banner("COMBO FREE GAMES", "%d games  ·  a random feature every spin" % int(ev.of), 2.2)
		"free_game":
			free.n = int(ev.n)
			message = "FREE GAME %d OF %d" % [int(ev.n), int(ev.of)]
			await _play_spin(ev.outcome, float(free.total))
			free.total = int(ev.total)
			await _wait(0.6)
		"free_end":
			_credit_adj += int(ev.total)
			await _summary("FREE GAMES", "%d combo free games at %s" % [int(free.get("of", 3)), Money.format(int(free.get("bet", 100)))], int(ev.total))
			if int(ev.total) >= 10 * int(free.get("bet", 100)):
				await _big_win(int(ev.total), int(free.get("bet", 100)))
			free = {}
			message = "FREE GAMES PAID %s" % Money.format(int(ev.total))
		"features_done":
			_round_over()


func _on_spin(ev: Dictionary) -> void:
	var o: Dictionary = ev.outcome
	_hurry = false
	message = "GOOD LUCK!"
	await _play_spin(o)
	if int(o.total) >= 10 * int(o.bet):
		await _big_win(int(o.total), int(o.bet))
	message = "YOU WON %s" % Money.format(int(o.total)) if int(o.total) > 0 else "25 LINES  ·  GOOD LUCK, PARTNER"
	_credit_adj += int(o.total)
	var next: Array = ev.get("features_next", [])
	if not next.is_empty():
		auto = 0
		return
	_round_over()
	if auto > 0:
		if int(o.total) >= 25 * int(o.bet):
			auto = 0
		else:
			auto -= 1
			if auto > 0:
				await _wait(0.45)
				if auto > 0 and visible and not _closing:
					_send_spin()


## Everything this spin started has been shown: the credit catches up.
func _round_over() -> void:
	if _queue.is_empty():
		_credit_adj = 0
		Session.hold_balance(false)


# ------------------------------------------------------------------ clock and tweens
func _process(delta: float) -> void:
	if not visible:
		return
	var dt := minf(delta, 0.05) * (1.8 if turbo else 1.0)
	_now += dt
	for tw in _tweens.duplicate():
		tw.t += dt / tw.dur
		var k := _ease(tw.ease, minf(1.0, tw.t))
		for key in tw.to:
			tw.obj[key] = lerpf(tw.from[key], tw.to[key], k)
		if tw.t >= 1.0:
			_tweens.erase(tw)
	for x in reels:
		if x.spinning:
			x.pos -= x.v * dt
	if win_shown < win_target:
		win_shown = minf(win_target, win_shown + maxf(1.0, roller) * dt)
	for p in particles:
		p.vy += p.g * dt
		p.x += p.vx * dt
		p.y += p.vy * dt
		p.spin += p.vs * dt
		p.life -= dt
	particles = particles.filter(func(p): return p.life > 0 and p.y < H + 60)
	flyers = flyers.filter(func(f): return not f.get("dead", false))
	shake = maxf(0.0, shake - dt * 2.5)
	if not _running and wins.size() > 0 and _now > cycle_at:
		cycle = (cycle + 1) % (wins.size() + 1)
		cycle_at = _now + 1.4
	if not trail.is_empty() and trail.get("waiting", false) and _now >= float(trail.get("auto_at", 1e9)) + 1.0:
		trail.waiting = false   # the server fires it itself; its roll is on the way
	_place_layers()
	_under.queue_redraw()
	_reels_layer.queue_redraw()
	_over.queue_redraw()
	queue_redraw()


func _wait(sec: float) -> void:
	var until := _now + sec
	var ep := _epoch
	while _now < until and not _hurry and ep == _epoch and visible:
		await get_tree().process_frame


## Tweens keys of a Dictionary; await it to wait for the end.
func _tw(obj: Dictionary, to: Dictionary, dur: float, ease := "out") -> void:
	var from := {}
	for key in to:
		from[key] = float(obj.get(key, 0.0))
	var entry := {"obj": obj, "from": from, "to": to, "t": 0.0, "dur": maxf(dur, 0.001), "ease": ease}
	_tweens.append(entry)
	var ep := _epoch
	while entry.t < 1.0 and ep == _epoch and visible:
		await get_tree().process_frame


static func _ease(kind: String, t: float) -> float:
	match kind:
		"out": return 1.0 - pow(1.0 - t, 3)
		"inout": return 4.0 * t * t * t if t < 0.5 else 1.0 - pow(-2.0 * t + 2.0, 3) / 2.0
		"back":
			var c := 1.9
			return 1.0 + (c + 1.0) * pow(t - 1.0, 3) + c * pow(t - 1.0, 2)
	return t


# ------------------------------------------------------------------ layout
func _canvas_rect() -> Rect2:
	var vp := get_viewport_rect().size
	var s := minf(vp.x / W, vp.y / H)
	var full := Rect2((vp - Vector2(W, H) * s) / 2.0, Vector2(W, H) * s)
	if _grow >= 1.0 or _from_rect.size == Vector2.ZERO:
		return full
	var g := _ease("out", _grow)
	return Rect2(_from_rect.position.lerp(full.position, g), _from_rect.size.lerp(full.size, g))


func _place_layers() -> void:
	var r := _canvas_rect()
	var sc := Vector2(r.size.x / W, r.size.y / H)
	var jitter := Vector2(randf_range(-7, 7), randf_range(-5, 5)) * shake * sc.x if shake > 0 else Vector2.ZERO
	for layer in [_under, _over]:
		layer.position = r.position + jitter
		layer.size = Vector2(W, H)
		layer.scale = sc
	_reels_layer.position = r.position + jitter + Vector2(REEL_X, REEL_Y) * sc
	_reels_layer.size = Vector2(REEL_W, REEL_H)
	_reels_layer.scale = sc
	modulate.a = clampf(_grow * 1.6, 0.0, 1.0)


func _draw() -> void:
	# the letterbox: the floor shows dimly round the edges while it grows
	draw_rect(Rect2(Vector2.ZERO, get_viewport_rect().size), Color(0.04, 0.02, 0.01, 0.92 * _grow))


func _draw_layer(ci: CanvasItem, which: String) -> void:
	match which:
		"under":
			_hits = []
			_draw_background(ci)
			_draw_top(ci)
			if not trail.is_empty():
				_draw_trail(ci)
			else:
				_draw_sides(ci)
				_draw_frame(ci)
		"reels":
			if trail.is_empty():
				_draw_reels(ci)
		"over":
			if trail.is_empty():
				_draw_reel_overlay(ci)
				_draw_wins(ci)
				if not pick.is_empty():
					_draw_pick(ci)
			else:
				_draw_trail_hud(ci)
			if not free.is_empty():
				_rr(ci, Rect2(440, REEL_Y - 16, 400, 34), 10, Color("7d130c"), 2, GOLD)
				_text(ci, "COMBO FREE GAME %d OF %d" % [int(free.n), int(free.of)], Vector2(640, REEL_Y + 1), 22, COND, GOLD_HI, "center", 0, 380)
			_draw_deck(ci)
			_draw_flyers(ci)
			_draw_banner(ci)
			_draw_particles(ci)
			_draw_overlay(ci)


# ------------------------------------------------------------------ drawing helpers
## A line of text centred (or left/right aligned) on `at`. With `max_w`, it shrinks to fit
## that width -- so a theme's longer names never spill out of their boxes.
func _text(ci: CanvasItem, s: String, at: Vector2, size: int, font: Font = COND, col := CREAM, align := "center", outline := 0, max_w := 0.0) -> void:
	size = _fit(s, font, size, max_w)
	var w := font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	var x := at.x - w / 2.0 if align == "center" else (at.x - w if align == "right" else at.x)
	var y := at.y + (font.get_ascent(size) - font.get_descent(size)) / 2.0
	if outline > 0:
		ci.draw_string_outline(font, Vector2(x, y), s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, outline, Color(0.12, 0.05, 0.02, 0.95))
	ci.draw_string(font, Vector2(x, y), s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, col)


## The largest size (down to 10) at which `s` fits `max_w` (0: no limit).
static func _fit(s: String, font: Font, size: int, max_w: float) -> int:
	if max_w <= 0.0:
		return size
	var w := font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	if w <= max_w:
		return size
	return maxi(10, int(size * max_w / w))


## Banner and big-win lettering: Rye in gold on a dark outline, with a drop shadow. (Every
## layer sits exactly on the text, so it stays sharp at any window size.)
func _gold_text(ci: CanvasItem, s: String, at: Vector2, size: int, max_w := 0.0) -> void:
	size = _fit(s, RYE, size, max_w)
	var w := RYE.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	var p := Vector2(at.x - w / 2.0, at.y + (RYE.get_ascent(size) - RYE.get_descent(size)) / 2.0)
	var edge := maxi(2, int(size * 0.14))
	ci.draw_string_outline(RYE, p + Vector2(0, size * 0.06), s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, edge + 2, Color(0.1, 0.03, 0.01, 0.85))
	ci.draw_string_outline(RYE, p, s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, edge, Color("2b1004"))
	ci.draw_string(RYE, p, s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, Color("f6c14a"))


func _rr(ci: CanvasItem, r: Rect2, radius: float, fill: Color, border := 0.0, border_col := Color.TRANSPARENT) -> void:
	_box.bg_color = fill
	_box.set_corner_radius_all(int(radius))
	_box.set_border_width_all(int(border))
	_box.border_color = border_col
	_box.draw_center = fill.a > 0.0
	ci.draw_style_box(_box, r)


func _vgrad(ci: CanvasItem, r: Rect2, top: Color, bottom: Color) -> void:
	ci.draw_polygon(PackedVector2Array([r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)]),
		PackedColorArray([top, top, bottom, bottom]))


func _wood(ci: CanvasItem, r: Rect2, radius := 14.0) -> void:
	_rr(ci, r, radius, Color("5c341a"), 2, Color("1a0b03"))
	_vgrad(ci, Rect2(r.position + Vector2(4, 4), Vector2(r.size.x - 8, r.size.y * 0.45)), Color(0.55, 0.33, 0.19, 0.55), Color(0.36, 0.2, 0.1, 0.0))
	var i := 10.0
	while i < r.size.y - 8:
		var y := r.position.y + i
		ci.draw_line(Vector2(r.position.x + 6, y + sin(i) * 2.0), Vector2(r.end.x - 6, y + cos(i) * 1.5), Color(0.12, 0.05, 0.02, 0.12), 1.2)
		i += 7.0
	_rr(ci, r.grow(-3), radius - 3, Color.TRANSPARENT, 3, Color("d9a54a"))


func _button(ci: CanvasItem, id: String, r: Rect2, label: String, on := false, disabled := false, size := 22, colour: Array = []) -> void:
	var hover := _hover == id and not disabled
	var cols: Array = colour if not colour.is_empty() else ([Color("ffe08a"), Color("8a5410")] if on else [Color("6e4426"), Color("2c1609")])
	var a := 0.4 if disabled else 1.0
	_rr(ci, r, r.size.y * 0.28, Color(cols[1], a), 3 if hover else 2, Color(GOLD_HI if hover else Color("d9a54a"), a))
	_vgrad(ci, Rect2(r.position + Vector2(3, 3), Vector2(r.size.x - 6, r.size.y * 0.5 - 3)), Color(cols[0], 0.75 * a), Color(cols[0], 0.0))
	_text(ci, label, r.get_center() + Vector2(0, 1), size, COND, Color(INK if (on or not colour.is_empty()) else CREAM, a), "center", 0, r.size.x - 14)
	if not disabled:
		_add_hit(id, r)


## Something clickable. Debug builds warn (once each) if it's off the safe area of the screen.
var _warned := {}
func _add_hit(id: String, r: Rect2) -> void:
	_hits.append([id, r])
	if OS.is_debug_build() and not SAFE.encloses(r) and not _warned.has(id):
		_warned[id] = true
		push_warning("SlotScreen: '%s' at %s isn't inside the safe area %s" % [id, r, SAFE])


func _tex(id: String) -> Texture2D:
	return SlotArt.tex(variant, id)


func _sym(ci: CanvasItem, sym: String, r: Rect2, fx: Dictionary = {}, alpha := 1.0) -> void:
	var tex := _tex(sym)
	if tex == null:
		return
	var s := 0.92 * float(fx.get("scale", 1.0))
	var flip := absf(cos(float(fx.flip) * PI)) if fx.has("flip") else 1.0
	var size := minf(r.size.x, r.size.y) * s
	var c := r.get_center()
	ci.draw_set_transform(c, 0, Vector2(maxf(0.02, flip), 1))
	var glow := float(fx.get("glow", 0.0))
	if glow > 0.0:
		var gc: Color = fx.get("glow_colour", Color("ffe27a"))
		ci.draw_circle(Vector2.ZERO, size * 0.5, Color(gc, 0.35 * glow))
	ci.draw_texture_rect(tex, Rect2(-size / 2.0, -size / 2.0, size, size), false, Color(1, 1, 1, alpha))
	if sym in ["W", "BS", "FS"]:
		var label: String = {"W": "WILD", "BS": "BONUS", "FS": "FREE SPINS"}[sym]
		var lw := r.size.x * 0.72
		_rr(ci, Rect2(-lw / 2.0, r.size.y / 2.0 - 30, lw, 24), 6, Color(Color("7d130c") if sym == "W" else Color("2b1004"), alpha), 2, Color(GOLD, alpha))
		_text(ci, label, Vector2(0, r.size.y / 2.0 - 17), 17 if sym == "FS" else 21, RYE, Color(GOLD_HI, alpha))
	ci.draw_set_transform(Vector2.ZERO)


# ------------------------------------------------------------------ the chrome
func _draw_background(ci: CanvasItem) -> void:
	_vgrad(ci, Rect2(0, 0, W, 300), Color("1b1440"), Color("6a2c5c"))
	_vgrad(ci, Rect2(0, 300, W, 150), Color("6a2c5c"), Color("e0663a"))
	_vgrad(ci, Rect2(0, 450, W, 120), Color("e0663a"), Color("f7b25a"))
	_vgrad(ci, Rect2(0, 570, W, 150), Color("f7b25a"), Color("5a2a16"))
	var rng := RandomNumberGenerator.new()
	rng.seed = 42
	for i in 90:
		ci.draw_rect(Rect2(rng.randf() * W, rng.randf() * H * 0.35, 1.6, 1.6), Color(1, 0.94, 0.82, 0.2 + rng.randf() * 0.6))
	ci.draw_circle(Vector2(640, 470), 200, Color(1, 0.67, 0.31, 0.18))
	ci.draw_circle(Vector2(640, 470), 90, Color(1, 0.86, 0.55, 0.28))
	ci.draw_colored_polygon(PackedVector2Array([Vector2(0, 520), Vector2(60, 520), Vector2(80, 430), Vector2(260, 420), Vector2(290, 520),
		Vector2(420, 540), Vector2(460, 470), Vector2(600, 466), Vector2(630, 540), Vector2(1280, 560), Vector2(1280, 720), Vector2(0, 720)]), Color("6e2c22"))
	ci.draw_colored_polygon(PackedVector2Array([Vector2(700, 560), Vector2(760, 450), Vector2(900, 440), Vector2(930, 500), Vector2(1050, 498),
		Vector2(1080, 420), Vector2(1230, 410), Vector2(1280, 470), Vector2(1280, 720), Vector2(700, 720)]), Color("57211c"))
	ci.draw_colored_polygon(PackedVector2Array([Vector2(0, 600), Vector2(300, 580), Vector2(640, 610), Vector2(980, 590), Vector2(1280, 610),
		Vector2(1280, 720), Vector2(0, 720)]), Color("3a160f"))
	ci.draw_rect(Rect2(0, 0, W, H), Color(0.04, 0.02, 0.01, 0.25))


func _draw_top(ci: CanvasItem) -> void:
	for spec in [["grand", 18.0, 250.0], ["major", 278.0, 210.0], ["minor", 792.0, 210.0], ["mini", 1012.0, 250.0]]:
		var id: String = spec[0]
		var r := Rect2(spec[1], 14, spec[2], 70)
		_rr(ci, r, 18, Color("1a0d06"))
		_rr(ci, r.grow(-4), 15, Color(TIERS[id], 0.9))
		_vgrad(ci, Rect2(r.position + Vector2(6, 6), Vector2(r.size.x - 12, 24)), Color(1, 1, 1, 0.22), Color(1, 1, 1, 0.0))
		var lit: bool = pick.get("lit", "") == id and int(_now * 6) % 2 == 1
		_rr(ci, r.grow(4) if lit else r, 22 if lit else 18, Color.TRANSPARENT, 5 if lit else 3, GOLD_HI if lit else GOLD)
		_text(ci, TIER_NAMES[id], Vector2(r.get_center().x, r.position.y + 18), 18, COND, Color.WHITE, "center", 4, r.size.x - 24)
		_text(ci, Money.format(int(meter_now(id))), Vector2(r.get_center().x, r.position.y + 46), 32, COND, Color.WHITE, "center", 6, r.size.x - 24)
	_draw_logo(ci)


## The variant's logo (art, so each theme brings its own lettering), fitted into LOGO_RECT.
func _draw_logo(ci: CanvasItem) -> void:
	var tex := _tex("logo")
	if tex == null:
		var name := str(rules.get("name", "")).to_upper()
		_gold_text(ci, name, LOGO_RECT.get_center(), 40, LOGO_RECT.size.x)
		return
	var ts := Vector2(tex.get_width(), tex.get_height())
	var k := minf(LOGO_RECT.size.x / ts.x, LOGO_RECT.size.y / ts.y)
	var size := ts * k
	ci.draw_texture_rect(tex, Rect2(LOGO_RECT.get_center() - size / 2.0, size), false)


func _draw_frame(ci: CanvasItem) -> void:
	_wood(ci, Rect2(REEL_X - 22, REEL_Y - 18, REEL_W + 44, REEL_H + 36), 18)
	for r in 5:
		var x := REEL_X + r * CELL_W
		ci.draw_rect(Rect2(x, REEL_Y, CELL_W, REEL_H), Color("1c0e07"))
		ci.draw_rect(Rect2(x + CELL_W * 0.2, REEL_Y, CELL_W * 0.6, REEL_H), Color("2a160b"))
	for p in [Vector2(REEL_X - 10, REEL_Y - 6), Vector2(REEL_X + REEL_W + 10, REEL_Y - 6), Vector2(REEL_X - 10, REEL_Y + REEL_H + 6), Vector2(REEL_X + REEL_W + 10, REEL_Y + REEL_H + 6)]:
		ci.draw_circle(p, 4.5, Color("e3b45a"))


func _draw_sides(ci: CanvasItem) -> void:
	_wood(ci, Rect2(18, REEL_Y - 18, 224, REEL_H + 36), 16)
	_text(ci, "RANDOM FEATURES", Vector2(130, REEL_Y + 8), 19, COND, GOLD_HI, "center", 0, 196)
	for i in FEATURE_ROWS.size():
		var id: String = FEATURE_ROWS[i][0]
		var y := REEL_Y + 32 + i * 52
		var lit: bool = feature_lit.get(id, false)
		var label: String = "MULTIPLIER ×%d" % multiplier if id == "multiplier" and multiplier > 1 else FEATURE_ROWS[i][1]
		_rr(ci, Rect2(34, y, 192, 42), 10, Color(1, 0.8 + 0.1 * sin(_now * 8.0), 0.35, 0.95) if lit else Color(0.08, 0.035, 0.015, 0.65), 2, GOLD_HI if lit else Color("7a5a36"))
		_text(ci, label, Vector2(130, y + 22), 20, COND, INK if lit else MUTED, "center", 0, 176)
	_button(ci, "settings", Rect2(34, REEL_Y + 32 + 7 * 52 + 4, 192, 36), "SETTINGS", false, false, 18)
	_wood(ci, Rect2(1038, REEL_Y - 18, 224, REEL_H + 36), 16)
	var busy := _running or not pick.is_empty() or not free.is_empty()
	var by := REEL_Y + 6
	var buy := Rect2(1052, by, 196, 178)
	var hov := _hover == "buy" and not busy
	_rr(ci, buy, 14, Color(0.35, 0.16, 0.04, 0.95) if hov else Color(0.16, 0.07, 0.02, 0.85), 4 if hov else 3, GOLD)
	var a := 0.45 if busy else 1.0
	_text(ci, "BUY BONUS", Vector2(1150, by + 24), 26, COND, Color(GOLD_HI, a), "center", 0, 180)
	var bs := _tex("BS")
	if bs:
		ci.draw_texture_rect(bs, Rect2(1098, by + 38, 104, 104), false, Color(1, 1, 1, a))
	_text(ci, Money.format(_bet() * int(rules.get("buy_cost", 45))), Vector2(1150, by + 156), 26, COND, Color(1, 1, 1, a), "center", 0, 180)
	if not busy and int(rules.get("buy_cost", 0)) > 0:
		_add_hit("buy", buy)
	var info := [["BS", "3+ WAGONS", "TRAIL BONUS"], ["FS", "3+ PISTOLS", "3 COMBO FREE GAMES"]]
	for i in info.size():
		# Each box: the symbol on the left, its two lines centred in the space to its right.
		var box := Rect2(SIDE_INFO.position + Vector2(0, by + 196 + i * 116), SIDE_INFO.size)
		_rr(ci, box, 12, Color(0.08, 0.035, 0.015, 0.65))
		var icon := Rect2(box.position + Vector2(6, 14), Vector2(76, 76))
		var t := _tex(info[i][0])
		if t:
			ci.draw_texture_rect(t, icon, false)
		var text_x := icon.end.x + 4.0
		var text_w := box.end.x - 8.0 - text_x
		var mid := text_x + text_w / 2.0
		_text(ci, info[i][1], Vector2(mid, box.position.y + 40), 22, COND, GOLD_HI, "center", 0, text_w)
		_text(ci, info[i][2], Vector2(mid, box.position.y + 66), 16, COND, CREAM, "center", 0, text_w)


func _draw_deck(ci: CanvasItem) -> void:
	ci.draw_rect(Rect2(0, DECK_TOP, W, H - DECK_TOP), Color(0.05, 0.02, 0.01, 0.86))
	ci.draw_rect(Rect2(0, DECK_TOP, W, 2), Color("d9a54a"))
	_text(ci, message, Vector2(560, DECK_TOP + 15), 19, COND, GOLD_HI, "center", 0, 1000)
	var top := DECK_ROW.position.y
	var h := DECK_ROW.size.y
	var credit := Session.shown_balance + _credit_adj
	_deck_box(ci, Rect2(20, top, 210, h), "CREDIT", Money.format(credit), Color.WHITE)
	_deck_box(ci, Rect2(242, top, 230, h), "BET", Money.format(_bet()), Color.WHITE, 112)
	var idle := not _running and pick.is_empty() and trail.is_empty() and free.is_empty()
	_button(ci, "bet-", Rect2(252, top + 36, 40, 38), "−", false, not idle or _bet_idx == 0, 30)
	_button(ci, "bet+", Rect2(422, top + 36, 40, 38), "+", false, not idle or _bet_idx == _ladder.size() - 1, 30)
	_deck_box(ci, Rect2(484, top, 230, h), "FREE GAMES WIN" if not free.is_empty() else "WIN",
		Money.format(int(win_shown)) if win_shown > 0 else "", Color("ffe27a"))
	var by := top + (h - 56.0) / 2.0
	_button(ci, "info", Rect2(728, by, 92, 56), "INFO", false, not idle)
	_button(ci, "turbo", Rect2(828, by, 92, 56), "TURBO", turbo)
	_button(ci, "auto", Rect2(928, by, 92, 56), "STOP %d" % auto if auto > 0 else "AUTO", auto > 0 or auto_menu, not idle and auto == 0)
	var c := SPIN_CENTRE
	var spinning := reels.any(func(x): return x.spinning or x.stopping)
	var hov := _hover == "spin"
	ci.draw_circle(c, SPIN_R + 4.0, Color("1a0b03"))
	ci.draw_circle(c, SPIN_R, Color("c9871c") if spinning else Color("f0b43a"))
	ci.draw_circle(c + Vector2(-10, -14), SPIN_R * 0.45, Color(1, 0.95, 0.7, 0.45))
	ci.draw_arc(c, SPIN_R, 0, TAU, 64, GOLD_HI, 5 if hov else 3, true)
	var label := "STOP" if spinning else ("FIRE" if not trail.is_empty() else "SPIN")
	_text(ci, label, c + Vector2(0, 2), 28, COND, INK, "center", 0, SPIN_R * 1.6)
	_add_hit("spin", Rect2(c - Vector2(SPIN_R, SPIN_R), Vector2(SPIN_R, SPIN_R) * 2.0))
	_button(ci, "cashout", Rect2(1172, by, 96, 56), "CASH OUT", false, false, 18)
	if auto_menu:
		var n := 0
		for count in [10, 25, 50, 100]:
			_button(ci, "auto%d" % count, Rect2(924, top - 50 - n * 46, 100, 40), "%d SPINS" % count, false, false, 20, [GOLD_HI, Color("9a5a10")])
			n += 1


## A deck readout. `value_w` narrows the value (the bet sits between its − and + buttons).
func _deck_box(ci: CanvasItem, r: Rect2, label: String, value: String, col: Color, value_w := 0.0) -> void:
	_rr(ci, r, 12, Color("1a0c05"), 2, Color("7a5a36"))
	_text(ci, label, Vector2(r.get_center().x, r.position.y + 16), 16, COND, MUTED, "center", 0, r.size.x - 16)
	_text(ci, value, Vector2(r.get_center().x, r.position.y + r.size.y - 26), 34, COND, col, "center", 0,
		value_w if value_w > 0.0 else r.size.x - 20)


# ------------------------------------------------------------------ the reels
func _grid_from_reels() -> Array:
	var g := []
	for x in reels:
		var strip: Array = x.strip
		for row in 4:
			g.append(strip[(int(x.pos) + row) % strip.size()] if not strip.is_empty() else "L1")
	return g


## Draws in the clipped reel window's coordinates (0,0 is the window's top-left).
func _draw_reels(ci: CanvasItem) -> void:
	var col := colossal
	for x in reels:
		var in_group: bool = not col.is_empty() and x.r >= int(col.start) and x.r < int(col.start) + int(col.k)
		if in_group and x.r != int(col.start):
			continue
		if x.spinning or x.stopping or not landed:
			if in_group:
				_draw_big_reel(ci, x)
			else:
				_draw_spinning_reel(ci, x)
	if landed:
		_draw_grid(ci)
	for x in reels:
		if x.glow > 0.0:
			ci.draw_rect(Rect2(x.r * CELL_W + 4, 4, CELL_W - 8, REEL_H - 8), Color(1, 0.89, 0.48, x.glow * (0.6 + 0.4 * sin(_now * 12.0))), false, 8)


func _draw_spinning_reel(ci: CanvasItem, x: Dictionary) -> void:
	var strip: Array = x.strip
	if strip.is_empty():
		return
	var n := strip.size()
	var base := floori(x.pos)
	var frac: float = x.pos - base
	var blur := minf(1.0, absf(x.v) / 18.0)
	for i in range(-1, 5):
		var sym: String = strip[posmod(base + i, n)]
		var r := Rect2(x.r * CELL_W, (i - frac) * CELL_H, CELL_W, CELL_H)
		if blur > 0.05:
			_sym(ci, sym, Rect2(r.position + Vector2(0, -22 * blur), r.size), {}, 0.28 * blur)
			_sym(ci, sym, Rect2(r.position + Vector2(0, 22 * blur), r.size), {}, 0.28 * blur)
			_sym(ci, sym, r, {}, 1.0 - 0.45 * blur)
		else:
			_sym(ci, sym, r)


func _draw_big_reel(ci: CanvasItem, x: Dictionary) -> void:
	var col := colossal
	var k := int(col.k)
	var size := CELL_H * k
	var wpx := CELL_W * k
	ci.draw_rect(Rect2(int(col.start) * CELL_W, 0, wpx, REEL_H), Color(0.24, 0.11, 0.04, 0.6))
	if _big.is_empty():
		return
	var base := floori(x.pos)
	var frac: float = x.pos - base
	for i in range(-1, ceili(4.0 / k) + 1):
		var sym: String = _big[posmod(base + i, _big.size())]
		_sym(ci, sym, Rect2(int(col.start) * CELL_W + (wpx - size * 1.05) / 2.0, (i - frac) * size, size * 1.05, size))


func _block_cells(b: int) -> Array:
	var col := colossal
	var cells := []
	for row in 4:
		if floori(float(row + int(col.offset)) / int(col.k)) == b:
			for r in range(int(col.start), int(col.start) + int(col.k)):
				cells.append(r * 4 + row)
	return cells


func _draw_grid(ci: CanvasItem) -> void:
	var col := colossal
	if not col.is_empty():
		var k := int(col.k)
		var size := CELL_H * k
		var wpx := CELL_W * k
		ci.draw_rect(Rect2(int(col.start) * CELL_W, 0, wpx, REEL_H), Color(0.24, 0.11, 0.04, 0.6))
		for b in range(0, ceili(4.0 / k) + 1):
			var cells := _block_cells(b)
			if cells.is_empty():
				continue
			var now_sym: String = grid[cells[0]]
			if cells.all(func(c): return grid[c] == now_sym):
				var fx: Dictionary = cell_fx.get(cells[0], {}) if cell_fx.get(cells[0], {}).get("big", false) else {}
				_sym(ci, now_sym, Rect2(int(col.start) * CELL_W + (wpx - size * 1.05) / 2.0, (b * k - int(col.offset)) * CELL_H, size * 1.05, size), fx)
	for c in 20:
		var r := floori(c / 4.0)
		if not col.is_empty() and r >= int(col.start) and r < int(col.start) + int(col.k):
			var cells := _block_cells(floori(float(c % 4 + int(col.offset)) / int(col.k)))
			if cells.all(func(q): return grid[q] == grid[cells[0]]):
				continue
		_sym(ci, str(grid[c]), Rect2(r * CELL_W, (c % 4) * CELL_H, CELL_W, CELL_H), cell_fx.get(c, {}))


## Over the reels (unclipped): dividers and the glass.
func _draw_reel_overlay(ci: CanvasItem) -> void:
	for r in range(1, 5):
		if not colossal.is_empty() and r > int(colossal.start) and r < int(colossal.start) + int(colossal.k):
			continue
		ci.draw_rect(Rect2(REEL_X + r * CELL_W - 1, REEL_Y, 2, REEL_H), Color(0.85, 0.65, 0.29, 0.55))
	_vgrad(ci, Rect2(REEL_X, REEL_Y, REEL_W, 80), Color(1, 1, 1, 0.1), Color(1, 1, 1, 0.0))
	_vgrad(ci, Rect2(REEL_X, REEL_Y + REEL_H - 70, REEL_W, 70), Color(0, 0, 0, 0.0), Color(0, 0, 0, 0.35))


func _cell_rect(c: int) -> Rect2:
	return Rect2(REEL_X + floori(c / 4.0) * CELL_W, REEL_Y + (c % 4) * CELL_H, CELL_W, CELL_H)


func _draw_wins(ci: CanvasItem) -> void:
	if not landed or wins.is_empty():
		return
	var lines: Array = wins if (_running or cycle == 0) else [wins[cycle - 1]]
	for w in lines:
		var colr := Color(LINE_COLOURS[(int(w.line) - 1) % 25])
		var rows: Array = _lines[int(w.line) - 1] if _lines.size() >= int(w.line) else [1, 1, 1, 1, 1]
		var pts := PackedVector2Array([Vector2(REEL_X - 8, REEL_Y + int(rows[0]) * CELL_H + CELL_H / 2.0)])
		for reel in 5:
			pts.append(Vector2(REEL_X + reel * CELL_W + CELL_W / 2.0, REEL_Y + int(rows[reel]) * CELL_H + CELL_H / 2.0))
		pts.append(Vector2(REEL_X + REEL_W + 8, pts[5].y))
		ci.draw_polyline(pts, Color(colr, 0.25), 18, true)
		ci.draw_polyline(pts, Color(0.08, 0.03, 0.01, 0.7), 9, true)
		ci.draw_polyline(pts, colr, 5, true)
		for c in w.cells:
			var r := _cell_rect(int(c)).grow(-6)
			_rr(ci, r, 10, Color(colr, 0.12), 4, colr)
		if lines.size() == 1:
			var last := _cell_rect(int(w.cells[w.cells.size() - 1]))
			_rr(ci, Rect2(last.end.x - 92, last.position.y + 6, 86, 30), 8, Color(0.08, 0.03, 0.01, 0.85))
			_text(ci, Money.format(int(w.pence)), Vector2(last.end.x - 49, last.position.y + 21), 22, COND, colr)
	if not _running and cycle > 0:
		var w: Dictionary = wins[cycle - 1]
		var name: String = rules.get("symbols", {}).get(str(w.sym), str(w.sym))
		message = "LINE %d  ·  %d × %s  ·  %s" % [int(w.line), int(w.count), name.to_upper(), Money.format(int(w.pence))]


# ------------------------------------------------------------------ playing a spin
func _clear_wins() -> void:
	wins = []
	cycle = 0
	win_shown = 0.0
	win_target = 0.0
	cell_fx = {}
	feature_lit = {}
	multiplier = 1


## `base`: what the win meter starts from (a free game adds to the games before it).
func _play_spin(o: Dictionary, base := 0.0) -> void:
	var ep := _epoch
	_clear_wins()
	win_shown = base
	win_target = base
	landed = false
	colossal = {}
	var strips: Array = _free_strips if o.free else _strips
	for x in reels:
		x.strip = strips[x.r] if strips.size() == 5 else []
		x.glow = 0.0
	var pre := []
	if o.colossal != null:
		colossal = o.colossal.duplicate()
		pre.append(["colossal", "COLOSSAL REELS", "%d×%d symbols" % [int(o.colossal.k), int(o.colossal.k)]])
	if int(o.multiplier) > 1:
		multiplier = int(o.multiplier)
		pre.append(["multiplier", "%d× MULTIPLIER" % multiplier, "on every line win this spin"])
	if not o.wild_reels.is_empty():
		pre.append(["wildReels", "WILD REELS", "%d reel%s going wild" % [o.wild_reels.size(), "s" if o.wild_reels.size() > 1 else ""]])
	if not o.wilds.is_empty():
		pre.append(["wilds", "RANDOM WILDS", "%d shot%s fired" % [o.wilds.size(), "s" if o.wilds.size() > 1 else ""]])
	Sfx.play("reel_spin")
	var i := 0
	for x in reels:
		if not colossal.is_empty() and x.r >= int(colossal.start) and x.r < int(colossal.start) + int(colossal.k):
			if x.r == int(colossal.start):
				x.pos = randf() * maxf(1.0, _big.size())
				_start_reel(x, 10.0 / int(colossal.k), i)
		else:
			_start_reel(x, 20.0, i)
		i += 1
	for p in pre:
		feature_lit[p[0]] = true
		Sfx.play("feature_multiplier" if p[0] == "multiplier" else ("feature_reels" if p[0] in ["colossal", "wildReels"] else "bonus_trigger"))
		await _banner(p[1], p[2], 1.25)
		if ep != _epoch:
			return
	await _wait(0.15 if not pre.is_empty() else 0.55)
	var seen := {"BS": 0, "FS": 0}
	var r := 0
	while r < 5:
		var x: Dictionary = reels[r]
		if not colossal.is_empty() and r > int(colossal.start) and r < int(colossal.start) + int(colossal.k):
			r += 1
			continue
		if not _hurry and (int(seen.BS) >= 2 or int(seen.FS) >= 2):
			x.glow = 1.0
			x.v = 34.0
			message = "ONE MORE…"
			Sfx.play("reel_tease")
			await _wait(1.0)
		if not colossal.is_empty() and r == int(colossal.start):
			await _stop_reel(x, float(colossal.stop) + float(colossal.offset) / int(colossal.k), _big.size())
			r = int(colossal.start) + int(colossal.k) - 1
		else:
			await _stop_reel(x, float(o.stops[r]), (x.strip as Array).size())
			for row in 4:
				var s: String = o.landed[r * 4 + row]
				if seen.has(s):
					seen[s] = int(seen[s]) + 1
		if ep != _epoch:
			return
		Sfx.play("reel_stop")
		x.glow = 0.0
		if not _hurry:
			await _wait(0.12)
		r += 1
	grid = (o.after_colossal as Array).duplicate()
	landed = true
	_hurry = false
	# Wild Reels: the armadillo rolls down each one.
	for wr in o.wild_reels:
		var f := _flyer({"img": "armadillo", "x": REEL_X + int(wr) * CELL_W + CELL_W / 2.0, "y": REEL_Y - 40, "size": 130, "rot": 0.0})
		_tw(f, {"y": REEL_Y + REEL_H + 40, "rot": PI * 6}, 0.9, "inout")
		for row in 4:
			await _wait(0.2)
			var c: int = int(wr) * 4 + row
			if not grid[c] in ["BS", "FS"]:
				grid[c] = "W"
				cell_fx[c] = {"scale": 1.25, "glow": 1.0}
				_tw(cell_fx[c], {"scale": 1.0, "glow": 0.0}, 0.4)
		await _wait(0.15)
		f.dead = true
	# Random Wilds: shots ring out and stars land.
	for c in o.wilds:
		var rect := _cell_rect(int(c))
		var f := _flyer({"x": rect.get_center().x, "y": rect.get_center().y, "flash": true, "s": 1.4})
		_tw(f, {"s": 0.2, "a": 0.0}, 0.3)
		shake = 0.35
		Sfx.play("feature_wilds")
		grid[int(c)] = "W"
		cell_fx[int(c)] = {"scale": 1.7, "glow": 1.0}
		_tw(cell_fx[int(c)], {"scale": 1.0, "glow": 0.0}, 0.35, "back")
		await _wait(0.32)
	# Symbol Upgrade.
	if o.upgrade != null:
		feature_lit.upgrade = true
		var names: Dictionary = rules.get("symbols", {})
		for c in o.upgrade.cells:
			cell_fx[int(c)] = {"glow": 1.0, "glow_colour": Color("7affd9")}
		Sfx.play("feature_upgrade")
		await _banner("SYMBOL UPGRADE", "%s → %s" % [names.get(str(o.upgrade.from), o.upgrade.from), names.get(str(o.upgrade.to), o.upgrade.to)], 1.2)
		for c in o.upgrade.cells:
			cell_fx[int(c)]["flip"] = 0.0
			_tw(cell_fx[int(c)], {"flip": 0.5}, 0.22, "lin")
		await _wait(0.22)
		for c in o.upgrade.cells:
			grid[int(c)] = str(o.upgrade.to)
			cell_fx[int(c)]["big"] = true
			_tw(cell_fx[int(c)], {"flip": 1.0}, 0.22, "lin")
		await _wait(0.3)
		for c in o.upgrade.cells:
			cell_fx[int(c)] = {}
	grid = (o.grid as Array).duplicate()
	if ep != _epoch:
		return
	# The line wins.
	if not o.wins.is_empty():
		wins = o.wins
		cycle = 0
		for w in wins:
			for c in w.cells:
				var fx: Dictionary = cell_fx.get(int(c), {})
				fx.scale = 1.1
				cell_fx[int(c)] = fx
				_tw(fx, {"scale": 1.0}, 0.5, "back")
		roller = maxf(float(o.line_win) / 0.9, float(o.bet))
		win_target += float(o.line_win)
		Sfx.play("win_small")
		message = ("LINE WINS %s (×%d)" % [Money.format(int(o.line_win)), multiplier]) if multiplier > 1 else "LINE WINS %s" % Money.format(int(o.line_win))
		await _wait(1.1)
		if int(o.repeat) > 0:
			feature_lit.repeat = true
			for k in range(2, int(o.repeat) + 1):
				await _banner("REPEAT WIN", "pays again: %d of %d" % [k, int(o.repeat)], 1.0)
				win_target += float(o.line_win)
				Sfx.play("win_bangup")
				for w in wins:
					for c in w.cells:
						cell_fx[int(c)] = {"scale": 1.15, "glow": 1.0}
						_tw(cell_fx[int(c)], {"scale": 1.0, "glow": 0.0}, 0.6)
				await _wait(0.5)
	if int(o.instant) > 0:
		feature_lit.instant = true
		var f := _flyer({"img": "barrel", "x": 640, "y": REEL_Y + REEL_H / 2.0, "size": 220, "s": 0.2})
		await _tw(f, {"s": 1.0}, 0.45, "back")
		Sfx.play("instant_win")
		_coin_burst(640, REEL_Y + REEL_H / 2.0 - 40, 40)
		var t := _flyer({"text": "INSTANT WIN %s" % Money.format(int(o.instant)), "x": 640, "y": REEL_Y + REEL_H / 2.0 + 120, "text_size": 48, "s": 0.4})
		_tw(t, {"s": 1.0}, 0.3, "back")
		roller = maxf(float(o.instant), float(o.bet))
		win_target += float(o.instant)
		await _wait(1.3)
		_tw(f, {"a": 0.0}, 0.3)
		await _tw(t, {"a": 0.0}, 0.3)
		f.dead = true
		t.dead = true
	win_shown = win_target


func _start_reel(x: Dictionary, v: float, i: int) -> void:
	x.stopping = false
	await get_tree().create_timer(i * 0.04).timeout
	x.spinning = true
	x.v = 0.0
	_tw(x, {"v": v}, 0.25, "lin")


func _stop_reel(x: Dictionary, stop: float, n: int) -> void:
	if n <= 0:
		x.spinning = false
		return
	x.spinning = false
	x.stopping = true
	var target := stop + floorf(x.pos / n) * n
	while target > x.pos - 3.0:
		target -= n
	x.v = 0.0
	await _tw(x, {"pos": target - 0.18}, 0.12 if _hurry else 0.34)
	await _tw(x, {"pos": target}, 0.14)
	x.pos = fposmod(target, n)
	x.stopping = false


# ------------------------------------------------------------------ banners, flyers, particles, overlays
func _banner(title: String, sub: String, dur: float) -> void:
	banner = {"text": title, "sub": sub, "t0": _now, "dur": dur}
	await _wait(dur * 0.8)


func _draw_banner(ci: CanvasItem) -> void:
	if banner.is_empty():
		return
	var t := (_now - float(banner.t0)) / float(banner.dur)
	if t > 1.0:
		banner = {}
		return
	var a := t / 0.15 if t < 0.15 else ((1.0 - t) / 0.2 if t > 0.8 else 1.0)
	var s := 0.6 + 0.4 * _ease("back", t / 0.15) if t < 0.15 else 1.0
	var c := Vector2(640, REEL_Y + REEL_H / 2.0)
	ci.draw_set_transform(c, 0, Vector2(s, s))
	var h := 132.0 if banner.sub != "" else 100.0
	_rr(ci, Rect2(-420, -66, 840, h), 22, Color(0.09, 0.04, 0.01, 0.88 * a), 4, Color(GOLD, a))
	_gold_text(ci, banner.text, Vector2(0, -16), 58, 800)
	if banner.sub != "":
		_text(ci, banner.sub, Vector2(0, 40), 26, COND, Color(CREAM, a), "center", 0, 800)
	ci.draw_set_transform(Vector2.ZERO)


func _flyer(props: Dictionary) -> Dictionary:
	var f := {"x": 640.0, "y": 360.0, "s": 1.0, "a": 1.0, "size": 120.0, "rot": 0.0}
	f.merge(props, true)
	flyers.append(f)
	return f


func _draw_flyers(ci: CanvasItem) -> void:
	for f in flyers:
		if float(f.a) <= 0.0:
			continue
		ci.draw_set_transform(Vector2(f.x, f.y), float(f.rot), Vector2(f.s, f.s))
		if f.has("img"):
			var tex := _tex(str(f.img))
			if tex:
				var sz := float(f.size)
				ci.draw_texture_rect(tex, Rect2(-sz / 2.0, -sz / 2.0, sz, sz), false, Color(1, 1, 1, f.a))
		if f.has("text"):
			_text(ci, str(f.text), Vector2.ZERO, int(f.get("text_size", 40)), COND, Color(f.get("colour", GOLD_HI), f.a), "center", 6)
		if f.get("flash", false):
			ci.draw_circle(Vector2.ZERO, 60, Color(1, 0.75, 0.25, 0.35 * float(f.a)))
			ci.draw_circle(Vector2.ZERO, 30, Color(1, 0.95, 0.75, 0.8 * float(f.a)))
		ci.draw_set_transform(Vector2.ZERO)


func _coin_burst(x: float, y: float, n: int, spread := 1.0) -> void:
	for i in n:
		var ang := -PI / 2.0 + (randf() - 0.5) * 2.2 * spread
		var v := 300.0 + randf() * 520.0
		particles.append({"x": x, "y": y, "vx": cos(ang) * v, "vy": sin(ang) * v, "g": 1100.0, "life": 2.4,
			"spin": randf() * 6.0, "vs": 6.0 + randf() * 10.0, "r": 10.0 + randf() * 9.0})


func _coin_rain(n: int) -> void:
	for i in n:
		particles.append({"x": randf() * W, "y": -40.0 - randf() * 400.0, "vx": (randf() - 0.5) * 80.0, "vy": 100.0 + randf() * 200.0,
			"g": 500.0, "life": 4.0, "spin": randf() * 6.0, "vs": 5.0 + randf() * 9.0, "r": 11.0 + randf() * 10.0})


func _draw_particles(ci: CanvasItem) -> void:
	for p in particles:
		var sx := cos(float(p.spin))
		ci.draw_set_transform(Vector2(p.x, p.y), 0, Vector2(maxf(0.12, absf(sx)), 1))
		ci.draw_circle(Vector2.ZERO, float(p.r), Color("8a5410"))
		ci.draw_circle(Vector2.ZERO, float(p.r) - 2.0, GOLD if sx > 0 else Color("d9a030"))
		ci.draw_circle(Vector2(-float(p.r) * 0.3, -float(p.r) * 0.3), float(p.r) * 0.35, Color(1, 0.96, 0.76, 0.8))
		ci.draw_set_transform(Vector2.ZERO)


func _big_win(total: int, bet: int) -> void:
	var x := float(total) / float(bet)
	var title := "EPIC WIN" if x >= 50 else ("MEGA WIN" if x >= 25 else "BIG WIN")
	overlay = {"kind": "bigwin", "title": title, "shown": 0.0, "t0": _now, "done": false}
	Sfx.play("big_win")
	_coin_rain(70)
	var ov := overlay
	var count := 5.0 if x >= 50 else (4.0 if x >= 25 else 3.0)
	_tw(ov, {"shown": float(total)}, count)
	var until := _now + count + 1.5
	var next_rain := _now + 0.6
	var ep := _epoch
	while _now < until and not ov.done and ep == _epoch and visible:
		if _now > next_rain:
			_coin_rain(18)
			next_rain = _now + 0.6
		await get_tree().process_frame
	if overlay == ov:
		overlay = {}


func _summary(title: String, sub: String, amount: int) -> void:
	overlay = {"kind": "summary", "title": title, "sub": sub, "amount": amount, "t0": _now, "done": false}
	_coin_burst(640, 380, 50, 1.4)
	var ov := overlay
	var ep := _epoch
	while not ov.done and _now - float(ov.t0) < 5.0 and ep == _epoch and visible:
		await get_tree().process_frame
	if overlay == ov:
		overlay = {}


func _draw_overlay(ci: CanvasItem) -> void:
	if overlay.is_empty():
		return
	ci.draw_rect(Rect2(0, 0, W, H), Color(0.03, 0.01, 0.0, 0.72))
	_hits = []
	match overlay.kind:
		"bigwin":
			var t := minf(1.0, (_now - float(overlay.t0)) * 2.2)
			var s := (0.5 + 0.5 * _ease("back", t)) * (1.0 + 0.03 * sin(_now * 6.0))
			ci.draw_set_transform(Vector2(640, 300), 0, Vector2(s, s))
			_gold_text(ci, overlay.title, Vector2(0, -40), 120, 1100)
			_text(ci, Money.format(int(overlay.shown)), Vector2(0, 70), 84, COND, Color.WHITE, "center", 10)
			ci.draw_set_transform(Vector2.ZERO)
			_text(ci, "Click to continue", Vector2(640, 520), 20, COND, MUTED)
			_hits.append(["overlay", Rect2(0, 0, W, H)])
		"summary":
			_wood(ci, Rect2(340, 170, 600, 330), 22)
			_gold_text(ci, overlay.title, Vector2(640, 240), 54, 560)
			_text(ci, overlay.sub, Vector2(640, 300), 24, COND, CREAM, "center", 0, 560)
			_text(ci, Money.format(int(overlay.amount)), Vector2(640, 372), 76, COND, Color("ffe27a"), "center", 8, 560)
			_button(ci, "overlay", Rect2(560, 430, 160, 50), "COLLECT", false, false, 22, [GOLD_HI, Color("9a5a10")])
			_text(ci, "collects itself in %d" % maxi(1, ceili(5.0 - (_now - float(overlay.t0)))), Vector2(640, 496), 16, COND, MUTED)
		"buy":
			_wood(ci, Rect2(360, 170, 560, 340), 22)
			_gold_text(ci, "BUY BONUS", Vector2(640, 228), 50, 520)
			var bs := _tex("BS")
			if bs:
				ci.draw_texture_rect(bs, Rect2(580, 256, 120, 120), false)
			var cost := _bet() * int(rules.get("buy_cost", 45))
			_text(ci, "Go straight to the Trail Bonus for %s" % Money.format(cost), Vector2(640, 400), 26, COND, CREAM, "center", 0, 520)
			_text(ci, "%d × your %s bet. Trail wins pay at %s." % [int(rules.get("buy_cost", 45)), Money.format(_bet()), Money.format(_bet())], Vector2(640, 430), 19, COND, MUTED, "center", 0, 520)
			_button(ci, "buy-yes", Rect2(470, 450, 160, 48), "BUY", false, Session.shown_balance + _credit_adj < cost, 22, [GOLD_HI, Color("9a5a10")])
			_button(ci, "buy-no", Rect2(650, 450, 160, 48), "CANCEL")
		"cashout":
			_wood(ci, Rect2(390, 220, 500, 250), 20)
			_gold_text(ci, "CASH OUT?", Vector2(640, 270), 44, 460)
			_text(ci, "Your bonus is played out for you and paid.", Vector2(640, 330), 24, COND, CREAM, "center", 0, 460)
			_button(ci, "cash-yes", Rect2(470, 380, 160, 48), "STAND UP", false, false, 22, [GOLD_HI, Color("9a5a10")])
			_button(ci, "cash-no", Rect2(650, 380, 160, 48), "KEEP PLAYING")
		"notice":
			_wood(ci, Rect2(390, 250, 500, 200), 20)
			_text(ci, overlay.text, Vector2(640, 320), 28, COND, CREAM, "center", 0, 460)
			_button(ci, "overlay", Rect2(560, 372, 160, 48), "OK")
		"info":
			_draw_info(ci)


func _draw_info(ci: CanvasItem) -> void:
	_wood(ci, Rect2(40, 40, 1200, 640), 22)
	_gold_text(ci, "PAYS AT " + Money.format(_bet()), Vector2(640, 82), 34, 800)
	var lb := _bet() / 25.0
	var pays: Dictionary = rules.get("pays", {})
	var order := ["W", "H1", "H2", "M1", "M2", "M3", "M4", "L1", "L2", "L3", "L4"]
	for i in order.size():
		var sym: String = order[i]
		var colx := i if i < 3 else (i - 3 if i < 7 else i - 7)
		var row := 0 if i < 3 else (1 if i < 7 else 2)
		var n := 3 if row == 0 else 4
		var x0 := 640.0 - (n * 280.0) / 2.0 + colx * 280.0
		var y := 118.0 + row * 128.0
		var tex := _tex(sym)
		if tex:
			ci.draw_texture_rect(tex, Rect2(x0 + 10, y + 4, 104, 104), false)
		var p: Array = pays.get(sym, [0, 0, 0])
		for j in 3:
			var k := 5 - j
			_text(ci, "%d" % k, Vector2(x0 + 136, y + 30 + j * 26), 20, COND, Color("ffb347"), "left")
			_text(ci, Money.format(int(float(p[k - 3]) * lb)), Vector2(x0 + 160, y + 30 + j * 26), 22, COND, CREAM, "left")
	var tips := ["Wild stands in for everything except the Wagon and the Pistols. Pays left to right on 25 lines; the longest match on each line pays.",
		"Random features can hit any spin. Wilds, Wild Reels, Colossal Reels and the Multiplier land before the reels stop;",
		"Symbol Upgrade, Repeat Win and Instant Win come after. 3+ Wagons: Trail Bonus. 3+ Pistols: 3 Combo Free Games.",
		"Upgrades: Spade, Club → Whiskey  ·  Diamond, Heart → Boots  ·  Whiskey → Hat  ·  Boots → Horseshoe  ·  Hat, Horseshoe → Snake  ·  Snake → Armadillo"]
	for i in tips.size():
		_text(ci, tips[i], Vector2(640, 528 + i * 28), 19, COND, GOLD_HI if i == 3 else CREAM, "center", 0, 1140)
	_button(ci, "overlay", Rect2(1100, 56, 120, 44), "CLOSE")


# ------------------------------------------------------------------ the Jackpot Pick
func _begin_pick() -> void:
	var coins := []
	for i in 12:
		coins.append({"tier": "", "flip": 0.0, "s": 1.0, "dim": false, "asked": false})
	pick = {"coins": coins, "tally": {}, "lit": "", "done": false}


func _reveal_coin(index: int, tier: String) -> void:
	if pick.is_empty():
		return
	var coin: Dictionary = pick.coins[index]
	Sfx.play("pick_reveal")
	await _tw(coin, {"flip": 0.5}, 0.16, "lin")
	coin.tier = tier
	await _tw(coin, {"flip": 1.0}, 0.16, "lin")
	pick.tally[tier] = int(pick.tally.get(tier, 0)) + 1


func _jackpot_won(ev: Dictionary) -> void:
	if pick.is_empty():
		_begin_pick()
	var tier := str(ev.tier)
	pick.done = true
	pick.lit = tier
	for c in pick.coins:
		if c.tier == tier:
			_tw(c, {"s": 1.2}, 0.4, "back")
	Sfx.play("jackpot_win")
	await _wait(1.0)
	var all: Array = ev.get("coins", [])
	for i in pick.coins.size():
		var c: Dictionary = pick.coins[i]
		if c.tier == "" and i < all.size():
			c.tier = str(all[i])
			c.dim = true
			c.flip = 1.0
	await _wait(0.8)
	_coin_rain(90)
	_credit_adj += int(ev.amount)
	await _summary("%s JACKPOT" % TIER_NAMES.get(tier, tier.to_upper()), "shared by every slot on the floor", int(ev.amount))
	pick = {}


func _draw_pick(ci: CanvasItem) -> void:
	_wood(ci, Rect2(REEL_X - 22, REEL_Y - 18, REEL_W + 44, REEL_H + 36), 18)
	_gold_text(ci, "PICK A COIN", Vector2(640, REEL_Y + 22), 40, 600)
	var coins: Array = pick.coins
	for i in coins.size():
		var c: Dictionary = coins[i]
		var cx := REEL_X + 105.0 + (i % 4) * 180.0
		var cy := REEL_Y + 125.0 + floori(i / 4.0) * 128.0
		var r := 52.0 * float(c.s)
		var hover: bool = _hover == "coin%d" % i and c.tier == "" and not pick.done
		if not pick.done and c.tier == "" and not c.asked:
			_add_hit("coin%d" % i, Rect2(cx - r, cy - r, r * 2, r * 2))
		ci.draw_set_transform(Vector2(cx, cy), 0, Vector2(maxf(0.05, absf(cos(float(c.flip) * PI))), 1))
		var a := 0.45 if c.dim else 1.0
		var face: bool = c.tier != "" and float(c.flip) >= 0.5
		if face:
			ci.draw_circle(Vector2.ZERO, r, Color(0.1, 0.04, 0.01, a))
			ci.draw_circle(Vector2.ZERO, r - 4, Color(TIERS.get(c.tier, GOLD), a))
			ci.draw_circle(Vector2(-r * 0.3, -r * 0.3), r * 0.35, Color(1, 1, 1, 0.35 * a))
			_text(ci, TIER_NAMES.get(c.tier, c.tier), Vector2(0, 2), 26, COND, Color(1, 1, 1, a), "center", 5)
		else:
			ci.draw_circle(Vector2.ZERO, r, Color("5a3505"))
			ci.draw_circle(Vector2.ZERO, r - 4, Color("ffd970") if hover else GOLD)
			var t := _tex("t_coin")
			if t:
				ci.draw_texture_rect(t, Rect2(-r * 0.7, -r * 0.7, r * 1.4, r * 1.4), false)
		if pick.done and c.tier == pick.lit and not c.dim:
			ci.draw_arc(Vector2.ZERO, r, 0, TAU, 48, Color.WHITE, 4, true)
		ci.draw_set_transform(Vector2.ZERO)
	var j := 0
	for id in ["mini", "minor", "major", "grand"]:
		var x := REEL_X + 60.0 + j * 180.0
		var y := REEL_Y + REEL_H - 22.0
		_text(ci, TIER_NAMES[id], Vector2(x, y), 20, COND, TIERS[id], "left", 4)
		for k in 3:
			ci.draw_circle(Vector2(x + 76 + k * 22, y), 8, TIERS[id] if int(pick.tally.get(id, 0)) > k else Color(1, 1, 1, 0.15))
		j += 1


# ------------------------------------------------------------------ the Trail Bonus
func _trail_pos(i: int) -> Vector2:
	return Vector2(120.0 + i * TILE, 400.0 + sin(i * 0.55) * 64.0 + sin(i * 0.17) * 30.0)


func _begin_trail(t: Dictionary) -> void:
	var board: Array = []
	for sp in t.board:
		board.append((sp as Dictionary).duplicate())
	var p := _trail_pos(int(t.pos))
	trail = {"board": board, "bet": int(t.bet), "pos": int(t.pos), "hearts": int(t.hearts), "upgraded": t.upgraded,
		"doubled": t.doubled, "total": int(t.total), "token": {"i": int(t.pos), "x": p.x, "y": p.y, "hop": 0.0, "sq": 1.0},
		"cam": p.x - 380.0, "bullets": 0, "cyl": 0.0, "waiting": false, "auto_at": 1e9, "snake": {}, "crate": {},
		"double_at": -10.0, "lightning_at": -10.0}
	_clear_wins()


func _animate_roll(roll: Dictionary) -> void:
	var tr := trail
	tr.bullets = 0
	Sfx.play("trail_fire")
	for i in int(roll.bullets):
		tr.bullets = i + 1
		await _wait(0.09)
	await _tw(tr, {"cyl": float(tr.cyl) + TAU * (2.0 + int(roll.bullets) / 6.0)}, 0.6)
	var label := "%d" % int(roll.bullets)
	if int(roll.move) != int(roll.bullets):
		label = "%d × 2 = %d" % [int(roll.bullets), int(roll.move)]
	var f := _flyer({"text": label, "x": 1150, "y": 250, "text_size": 64, "s": 0.3})
	_tw(f, {"s": 1.0}, 0.25, "back")
	var evs: Array = (roll.events as Array).duplicate()
	while not evs.is_empty() and int(evs[0].pos) == int(roll.from):
		await _trail_event(evs.pop_front())
	var at := int(roll.from)
	for p in roll.path:
		await _move_token(int(p), "slide" if absi(int(p) - at) > 1 else "hop")
		at = int(p)
		while not evs.is_empty() and int(evs[0].pos) == at:
			await _trail_event(evs.pop_front())
	while not evs.is_empty():
		await _trail_event(evs.pop_front())
	f.dead = true
	tr.bullets = 0


func _move_token(i: int, how: String) -> void:
	var tk: Dictionary = trail.token
	var p := _trail_pos(i)
	if how == "hop":
		tk.hop = 0.0
		Sfx.play("trail_hop")
		_tw(tk, {"hop": 1.0}, 0.2, "lin")
		await _tw(tk, {"x": p.x, "y": p.y}, 0.2, "lin")
		tk.sq = 0.7
		_tw(tk, {"sq": 1.0}, 0.15, "back")
	else:
		await _tw(tk, {"x": p.x, "y": p.y}, 0.5, "inout")
	tk.i = i
	tk.hop = 0.0
	trail.pos = i


func _trail_event(e: Dictionary) -> void:
	var tr := trail
	var p := _trail_pos(int(e.pos))
	var sx := p.x - float(tr.cam)
	var sy := p.y
	var board: Array = tr.board
	match str(e.kind):
		"coin", "prizepot":
			_pop("%s" % Money.format(int(e.pence)), Color("ffe27a"), sx, sy)
			if e.kind == "coin" and int(e.pos) < board.size():
				board[int(e.pos)].taken = true
			Sfx.play("trail_coin")
			_coin_burst(sx, sy - 30, 80 if e.kind == "prizepot" else 12, 0.6)
			tr.total = int(tr.total) + int(e.pence)
			win_target = float(tr.total)
			roller = maxf(float(e.pence) * 1.4, float(_bet()))
			await _wait(1.6 if e.kind == "prizepot" else 0.55)
		"heart":
			_pop("+1 HEART", Color("ff8a80"), sx, sy)
			board[int(e.pos)].taken = true
			tr.hearts = int(tr.hearts) + 1
			await _wait(0.6)
		"heart_used":
			_pop("SAVED BY A HEART", Color("ff8a80"), sx, sy)
			tr.snake = {"pos": int(e.pos), "t0": _now}
			shake = 0.6
			tr.hearts = int(tr.hearts) - 1
			Sfx.play("trail_snake")
			await _wait(0.9)
		"snake":
			_pop("SNAKE BITE!", Color("ff5a48"), sx, sy)
			tr.snake = {"pos": int(e.pos), "t0": _now}
			shake = 1.0
			Sfx.play("trail_snake")
			await _wait(1.2)
		"double":
			_pop("DOUBLE! ALL COINS ×2", Color("ffb347"), sx, sy)
			tr.doubled = true
			tr.double_at = _now
			for sp in board:
				if (sp.type == "coin" and not sp.get("taken", false)) or sp.type == "prizepot":
					sp.x = int(sp.x) * 2
			await _wait(1.1)
		"upgrade":
			_pop("SPIN UPGRADE: MOVES ×2", Color("7affd9"), sx, sy)
			tr.upgraded = true
			await _wait(1.0)
		"lightning":
			_pop("LIGHTNING ROLL NEXT", Color("ffe14a"), sx, sy)
			await _wait(0.9)
		"lightning_roll":
			_pop("LIGHTNING ROLL!", Color("ffe14a"), sx, sy)
			tr.lightning_at = _now
			await _wait(0.6)
		"crate":
			_pop("CRATE: COINS WITHIN %d" % int(e.r), Color("ffb347"), sx, sy)
			tr.crate = {"pos": int(e.pos), "r": int(e.r), "t0": _now}
			for j in range(maxi(1, int(e.pos) - int(e.r)), mini(board.size() - 1, int(e.pos) + int(e.r) + 1)):
				if board[j].type == "coin":
					board[j].taken = true
			if int(e.pence) > 0:
				tr.total = int(tr.total) + int(e.pence)
				win_target = float(tr.total)
				roller = maxf(float(e.pence), float(_bet()))
				_coin_burst(sx, sy - 30, 24, 0.8)
				Sfx.play("trail_coin")
			await _wait(1.0)
		"forward":
			_pop("FORWARD %d" % int(e.n), Color("9cff6b"), sx, sy)
			await _wait(0.6)
		"back":
			_pop("BACK %d" % int(e.n), Color("ff9e4a"), sx, sy)
			await _wait(0.6)


func _pop(txt: String, colour: Color, x: float, y: float) -> void:
	var f := _flyer({"text": txt, "x": x, "y": y - 90, "text_size": 40, "colour": colour, "s": 0.4})
	await _tw(f, {"s": 1.0, "y": y - 130}, 0.35, "back")
	await get_tree().create_timer(0.6).timeout
	await _tw(f, {"a": 0.0}, 0.3)
	f.dead = true


func _draw_trail(ci: CanvasItem) -> void:
	var tr := trail
	var board: Array = tr.board
	var tk: Dictionary = tr.token
	tr.cam = float(tr.cam) + (float(tk.x) - 380.0 - float(tr.cam)) * 0.08
	var cam := float(tr.cam)
	_rr(ci, Rect2(18, REEL_Y - 18, 1010, REEL_H + 36), 18, Color(0.16, 0.06, 0.02, 0.35))
	# the dusty road
	var pts := PackedVector2Array()
	var lo := maxi(0, floori((cam - 100.0) / TILE))
	var hi := mini(board.size() - 1, ceili((cam + 1100.0) / TILE))
	for i in range(maxi(0, lo - 1), mini(board.size(), hi + 2)):
		var p := _trail_pos(i)
		pts.append(Vector2(p.x - cam, p.y))
	if pts.size() > 1:
		ci.draw_polyline(pts, Color(0.24, 0.11, 0.04, 0.55), 64, true)
		ci.draw_polyline(pts, Color("c89a62"), 50, true)
		ci.draw_polyline(pts, Color("d8ae74"), 44, true)
	var dbl := _now - float(tr.double_at) < 0.8
	for i in range(lo, hi + 1):
		var p := _trail_pos(i)
		var x := p.x - cam
		if x < 40 or x > 1006:
			continue
		var sp: Dictionary = board[i]
		var end: bool = sp.type == "prizepot"
		var sz := 120.0 if end else 64.0
		var a := 0.35 if sp.get("taken", false) else 1.0
		var crate: bool = not (tr.crate as Dictionary).is_empty() and _now - float(tr.crate.t0) < 1.0 and absi(i - int(tr.crate.pos)) <= int(tr.crate.r)
		var light := _now - float(tr.lightning_at) < 1.2 and i > int(tk.i) - 7 and i <= int(tk.i)
		var fill := Color("5e1d12") if sp.type == "snake" else (Color("5a3a08") if end else Color("4a2a14"))
		_rr(ci, Rect2(x - sz / 2.0, p.y - sz / 2.0, sz, sz), 12, Color(fill, a), 4 if (crate or light) else 2,
			Color("ffb347") if crate else (Color("ffe14a") if light else Color(Color("d9a54a"), a)))
		if TRAIL_ICONS.has(sp.type):
			var tex := _tex(TRAIL_ICONS[sp.type])
			if tex:
				var isz := sz * 0.82
				var c := Vector2(x, p.y - (6.0 if sp.type == "coin" or end else 0.0))
				ci.draw_set_transform(c, 0, Vector2(-1 if sp.type == "back" else 1, 1))
				ci.draw_texture_rect(tex, Rect2(-isz / 2.0, -isz / 2.0, isz, isz), false, Color(1, 1, 1, a))
				ci.draw_set_transform(Vector2.ZERO)
		if sp.type == "coin" or end:
			_text(ci, "%d×" % int(sp.x), Vector2(x, p.y + sz / 2.0 - 10), int((26 if end else 19) * (1.25 if dbl else 1.0)), COND, Color(1, 1, 1, a), "center", 4)
		if sp.type == "double":
			_text(ci, "×2", Vector2(x, p.y + 2), 26, COND, Color.WHITE, "center", 5)
		if sp.type == "start":
			_text(ci, "START", Vector2(x, p.y), 20, COND, GOLD_HI, "center", 4)
	# the armadillo
	var tx := float(tk.x) - cam
	var ty := float(tk.y) - 46.0 - sin(float(tk.hop) * PI) * 46.0
	var tex := _tex("armadillo")
	if tex and tx > 0 and tx < 1030:
		ci.draw_set_transform(Vector2(tx, ty + 30), 0, Vector2(1.0 / pow(float(tk.sq), 0.3), float(tk.sq)))
		ci.draw_texture_rect(tex, Rect2(-55, -82, 110, 110), false)
		ci.draw_set_transform(Vector2.ZERO)
	var sn: Dictionary = tr.snake
	if not sn.is_empty() and _now - float(sn.t0) < 1.1:
		var sp := _trail_pos(int(sn.pos))
		var k := minf(1.0, (_now - float(sn.t0)) * 4.0)
		var st := _tex("t_snake")
		if st:
			ci.draw_texture_rect(st, Rect2(sp.x - cam + 10, sp.y - 60 - 50 * k, 110, 110), false)


func _draw_trail_hud(ci: CanvasItem) -> void:
	var tr := trail
	var board: Array = tr.board
	var tk: Dictionary = tr.token
	var prog := float(tk.i) / maxf(1.0, board.size() - 1)
	_rr(ci, Rect2(40, REEL_Y - 8, 900, 18), 9, Color(0.08, 0.03, 0.01, 0.8))
	if prog > 0.0:
		_rr(ci, Rect2(40, REEL_Y - 8, maxf(18.0, 900 * prog), 18), 9, Color("d8ae74"))
	var gold := _tex("t_gold")
	if gold:
		ci.draw_texture_rect(gold, Rect2(930, REEL_Y - 28, 50, 50), false)
	var arm := _tex("armadillo")
	if arm:
		ci.draw_texture_rect(arm, Rect2(40 + 900 * prog - 20, REEL_Y - 34, 44, 44), false)
	_text(ci, "TRAIL WIN %s" % Money.format(int(tr.total)), Vector2(520, REEL_Y + 34), 34, COND, Color("ffe27a"), "center", 6, 400)
	var heart := _tex("t_heart")
	for h in int(tr.hearts):
		if heart:
			ci.draw_texture_rect(heart, Rect2(40 + h * 46, REEL_Y + 18, 44, 44), false)
	var cx := 40.0 + maxi(1, int(tr.hearts)) * 46.0 + 10.0
	if tr.upgraded:
		_rr(ci, Rect2(cx, REEL_Y + 24, 150, 32), 8, Color("1d6b62"))
		_text(ci, "MOVES ×2", Vector2(cx + 75, REEL_Y + 41), 20, COND, Color.WHITE)
		cx += 160
	if tr.doubled:
		_rr(ci, Rect2(cx, REEL_Y + 24, 150, 32), 8, Color("8a2a12"))
		_text(ci, "COINS DOUBLED", Vector2(cx + 75, REEL_Y + 41), 20, COND, Color.WHITE)
	_wood(ci, Rect2(1038, REEL_Y - 18, 224, REEL_H + 36), 16)
	_text(ci, "THE PISTOL", Vector2(1150, REEL_Y + 10), 22, COND, GOLD_HI, "center", 0, 196)
	_text(ci, "moves 2 spaces per bullet" if tr.upgraded else "1 to 6 bullets a shot", Vector2(1150, REEL_Y + 34), 16, COND, CREAM, "center", 0, 196)
	var cyc := Vector2(1150, REEL_Y + 150)
	var cyl := _tex("cylinder")
	ci.draw_set_transform(cyc, float(tr.cyl), Vector2.ONE)
	if cyl:
		ci.draw_texture_rect(cyl, Rect2(-78, -78, 156, 156), false)
	for k in int(tr.bullets):
		var ang := -PI / 2.0 + k * PI / 3.0
		ci.draw_circle(Vector2(cos(ang), sin(ang)) * 35.0, 13, Color("b07a1c"))
		ci.draw_circle(Vector2(cos(ang), sin(ang)) * 35.0 + Vector2(-3, -3), 6, GOLD_HI)
	ci.draw_set_transform(Vector2.ZERO)
	if tr.waiting:
		_button(ci, "fire", Rect2(cyc.x - 80, cyc.y + 100, 160, 58), "FIRE", false, false, 32, [Color("ffb4a6"), Color("7d130c")])
		var left := maxf(0.0, float(tr.auto_at) - _now)
		_text(ci, "fires itself in %d" % ceili(left), Vector2(cyc.x, cyc.y + 176), 16, COND, MUTED)


# ------------------------------------------------------------------ input
func _virtual(p: Vector2) -> Vector2:
	var r := _canvas_rect()
	return (p - r.position) / (r.size / Vector2(W, H))


func _hit(p: Vector2) -> String:
	var v := _virtual(p)
	for i in range(_hits.size() - 1, -1, -1):
		if (_hits[i][1] as Rect2).has_point(v):
			return _hits[i][0]
	return ""


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		_hover = _hit(event.position)
	elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_act(_hit(event.position))
		accept_event()


func _unhandled_input(event: InputEvent) -> void:
	if not visible or _closing:
		return
	if event is InputEventKey and event.pressed and not event.echo and event.physical_keycode == KEY_SPACE:
		if not overlay.is_empty() and overlay.kind in ["bigwin", "summary"]:
			_act("overlay")
		elif overlay.is_empty():
			_spin_or_stop()
		get_viewport().set_input_as_handled()


func _act(id: String) -> void:
	if not overlay.is_empty():
		match id:
			"overlay":
				overlay.done = true
				if overlay.kind in ["info", "notice"]:
					overlay = {}
			"buy-yes":
				overlay = {}
				Net.send("buy_bonus", {"bet": _bet()})
			"buy-no", "cash-no":
				overlay = {}
			"cash-yes":
				overlay = {}
				stand_requested.emit()
		return
	if id.begins_with("coin"):
		var i := int(id.substr(4))
		if not pick.is_empty() and not pick.done and pick.coins[i].tier == "" and not pick.coins[i].asked:
			pick.coins[i].asked = true
			Net.send("jackpot_pick", {"index": i})
		return
	if id != "auto" and not id.begins_with("auto"):
		auto_menu = false
	var idle := not _running and pick.is_empty() and trail.is_empty() and free.is_empty()
	match id:
		"spin":
			_spin_or_stop()
		"fire":
			_fire()
		"bet-":
			if idle:
				_bet_idx = maxi(0, _bet_idx - 1)
				_bet_changed()
		"bet+":
			if idle:
				_bet_idx = mini(_ladder.size() - 1, _bet_idx + 1)
				_bet_changed()
		"turbo":
			turbo = not turbo
		"settings":
			settings_requested.emit()
		"auto":
			if auto > 0:
				auto = 0
			else:
				auto_menu = not auto_menu
		"info":
			overlay = {"kind": "info"}
		"buy":
			if idle:
				overlay = {"kind": "buy"}
		"cashout":
			_cash_out()
		"":
			if idle or _running:
				_spin_or_stop()
		_:
			if id.begins_with("auto"):
				auto_menu = false
				auto = int(id.substr(4))
				_send_spin()


func _bet_changed() -> void:
	wins = []
	message = "BET %s  ·  25 LINES" % Money.format(_bet())


func _cash_out() -> void:
	auto = 0
	if not pick.is_empty() or not trail.is_empty() or not free.is_empty():
		overlay = {"kind": "cashout"}
	else:
		stand_requested.emit()


func _bet() -> int:
	return int(_ladder[_bet_idx]) if not _ladder.is_empty() else 100


func _spin_or_stop() -> void:
	if not trail.is_empty():
		return _fire()
	if reels.any(func(x): return x.spinning or x.stopping):
		_hurry = true
		return
	if not pick.is_empty() or not free.is_empty():
		return
	_send_spin()


func _send_spin() -> void:
	var t := Time.get_ticks_msec() / 1000.0
	if t - _last_spin_sent < 1.0:
		return
	if Session.shown_balance + _credit_adj < _bet():
		auto = 0
		overlay = {"kind": "notice", "text": "Not enough credit for that bet."}
		return
	_last_spin_sent = t
	if _running:
		_hurry = true
	Net.send("spin", {"bet": _bet()})


func _fire() -> void:
	if not trail.is_empty() and trail.get("waiting", false):
		trail.waiting = false
		Net.send("trail_fire")
