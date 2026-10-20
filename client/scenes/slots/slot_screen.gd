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
const ARMADILLO_DISPLAY := preload("res://assets/fonts/Rye-Regular.ttf")
const ARMADILLO_UI := preload("res://assets/fonts/BarlowCondensed-Bold.ttf")
# The look: Armadillo's, unless the variant's rules bring a theme (a slot built with the admin page's Slot design
# wizard: its colours, fonts, frame, words and win animations). _apply_theme sets these when the screen opens.
var RYE: Font = ARMADILLO_DISPLAY
var COND: Font = ARMADILLO_UI
var CREAM := Color("f6ead0")
var GOLD := Color("f4c94f")
var GOLD_HI := Color("fff1b0")
var INK := Color("2b1004")
var MUTED := Color("b89b74")
var EDGE := Color("d9a54a")
var ALERT := Color("7d130c")
var WIN_COL := Color("ffe27a")
var SPIN_COL := Color("f0b43a")
var GOLD_TEXT := Color("f6c14a")
var GOLD_LO := Color("9a6614")      # the dark end of gold: coins, pressed buttons
var SHADE := Color("1a0b03")        # the backing of banners and pop-ups, and every dimming
const ARMADILLO_TEXTS := {
	"tagline": "GOOD LUCK, PARTNER", "trail": "TRAIL BONUS", "trail_hint": "fire the pistol to move the armadillo",
	"trail_message": "FIRE THE PISTOL  ·  SPACE OR CLICK FIRE", "launcher": "THE PISTOL", "launcher_hint": "1 to 6 bullets a shot",
	"launcher_up": "moves 2 spaces per bullet", "free": "COMBO FREE GAMES", "free_banner": "COMBO FREE GAME %d OF %d",
	"free_summary": "FREE GAMES", "free_sub": "%d combo free games at %s", "bonus_line": "3+ WAGONS", "free_line": "3+ PISTOLS",
	"buy_text": "Go straight to the Trail Bonus for %s", "buy_sub": "%d × your %s bet. Trail wins pay at %s.",
	"battle": "RED ALERT", "battle_hint": "tap a ship to fire", "enemy": "ENEMY SHIP", "boss": "FLAGSHIP",
	"voyage_name": "DEAD MAN'S MAP", "voyage_hint": "choose your next island", "voyage_start": "TORTUGA", "voyage_final": "ISLA DE MUERTA",
	"voyage_treasure": "TREASURE ISLAND", "voyage_wreck": "SHIPWRECK", "voyage_skull": "SKULL ISLAND", "voyage_port": "PORT ROYAL",
	"voyage_cove": "HIDDEN COVE", "voyage_relic": "RELIC", "voyage_chest": "LEGENDARY TREASURE", "voyage_legend": "THE LEGEND",
	"voyage_artefacts": ["COMPASS", "MEDALLION", "SPYGLASS", "CUTLASS"]}
const ARMADILLO_TIPS := ["Wild stands in for everything except the Wagon and the Pistols. Pays left to right on 25 lines; the longest match on each line pays.",
	"Random features can hit any spin. Wilds, Wild Reels, Colossal Reels and the Multiplier land before the reels stop;",
	"Symbol Upgrade, Repeat Win and Instant Win come after. 3+ Wagons: Trail Bonus. 3+ Pistols: 3 Combo Free Games.",
	"Upgrades: Spade, Club → Whiskey  ·  Diamond, Heart → Boots  ·  Whiskey → Hat  ·  Boots → Horseshoe  ·  Hat, Horseshoe → Snake  ·  Snake → Armadillo"]
var texts: Dictionary = ARMADILLO_TEXTS
var tips: Array = ARMADILLO_TIPS
var labels := true                  # WILD / BONUS / FREE SPINS lettered on those symbols (a built slot's art has its own)
var frame_style := "wood"
var frame_colour := Color("d9a54a")
## The deck's look (the wizard's Scene step): the bottom bar, readout boxes and buttons. See _deck_look.
var deck := {}
var win_anims := {}                 # tier group -> {preset, strength, colour}: what a symbol does while its line win shows
## The skin (the wizard's Scene step): "classic" is the frame styles above; "lcars" draws every part from its own
## shapes, palette, glass and decor (the "skin" section below; docs/slots/scenes.md).
var skin := {}
var feature_rows: Array = []
var background := false
const TIERS := {"mini": Color("4fb3ff"), "minor": Color("55d07a"), "major": Color("c768ff"), "grand": Color("ff5a48")}
const TIER_NAMES := {"mini": "MINI", "minor": "MINOR", "major": "MAJOR", "grand": "GRAND"}
const LINE_COLOURS := ["ffd54a", "ff7a59", "5fd4ff", "9cff6b", "ff6bd5", "ffb347", "6b9dff", "d0ff4a", "ff4a6e",
	"4affc3", "ffe0a3", "b38bff", "ff9e4a", "4ad2ff", "e3ff7a", "ff7ab8", "7affd9", "ffcf4a", "a6b8ff",
	"ff6a4a", "4aff8f", "ffa6e1", "c6ff4a", "4a9eff", "ffd1a6"]
const FEATURE_ROWS := [["wilds", "RANDOM WILDS"], ["wildReels", "WILD REELS"], ["colossal", "COLOSSAL REELS"],
	["multiplier", "MULTIPLIER"], ["upgrade", "SYMBOL UPGRADE"], ["repeat", "REPEAT WIN"], ["instant", "INSTANT WIN"]]
const TILE := 86.0
## Buttons that click (Spin has its own sound, and the Jackpot Pick coins theirs).
const CLICKS := ["bet-", "bet+", "turbo", "settings", "auto", "info", "buy", "cashout", "buy-yes", "buy-no", "cash-no", "overlay"]
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
const ROUTES := {"BS": ["trail"], "FS": ["free"], "buy": ["trail"]}   # Armadillo's ways in (rules.routes)
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
var _loops := {}          # name -> Sfx loop handle: the loops this screen has running ("spin", "meter", ...)

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
var battle := {}
var voyage := {}
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
	SlotArt.art_changed.connect(func():   # a built slot's fonts may arrive after it opened
		if visible and not rules.is_empty():
			_apply_theme())


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
	_apply_theme()
	_reset_state()
	for x in reels:
		x.strip = _strips[x.r] if _strips.size() == 5 else []
		x.pos = float(randi() % maxi(1, x.strip.size()))
	grid = _grid_from_reels()
	message = "25 LINES  ·  " + texts.tagline
	_from_rect = from_rect
	_closing = false
	_grow = 0.0
	show()
	var tw := create_tween()
	tw.tween_property(self, "_grow", 1.0, 0.45).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)


## The variant's look and words (rules.theme), or Armadillo's. Called again when its fonts finish downloading.
func _apply_theme() -> void:
	var theme: Dictionary = rules.get("theme", {})
	var c: Dictionary = theme.get("colours", {})
	var col := func(key: String, armadillo: String) -> Color: return Color(str(c.get(key, armadillo)))
	CREAM = col.call("cream", "f6ead0")
	GOLD = col.call("gold", "f4c94f")
	GOLD_HI = col.call("goldHi", "fff1b0")
	INK = col.call("ink", "2b1004")
	MUTED = col.call("muted", "b89b74")
	EDGE = col.call("edge", "d9a54a")
	ALERT = col.call("alert", "7d130c")
	WIN_COL = col.call("win", "ffe27a")
	SPIN_COL = col.call("spin", "f0b43a")
	GOLD_LO = col.call("goldLo", "9a6614")
	SHADE = col.call("shade", "1a0b03")
	GOLD_TEXT = GOLD if theme.has("colours") else Color("f6c14a")
	var fonts: Dictionary = theme.get("fonts", {})
	RYE = SlotArt.font(variant, "display") if fonts.has("display") and SlotArt.font(variant, "display") else ARMADILLO_DISPLAY
	COND = SlotArt.font(variant, "ui") if fonts.has("ui") and SlotArt.font(variant, "ui") else ARMADILLO_UI
	texts = ARMADILLO_TEXTS.duplicate()
	var t: Dictionary = theme.get("texts", {})
	if not t.is_empty():
		var trail_name := str(t.get("trail", "TRAIL BONUS"))
		var launcher := str(t.get("launcher", "THE LAUNCHER"))
		var free_name := str(t.get("free", "FREE GAMES"))
		texts.merge({"tagline": str(t.get("tagline", "GOOD LUCK")), "trail": trail_name, "trail_hint": str(t.get("hint", "fire to move along the trail")),
			"trail_message": "%s  ·  SPACE OR CLICK FIRE" % launcher, "launcher": launcher, "launcher_hint": "1 to 6 spaces a shot",
			"launcher_up": "moves doubled", "free": free_name, "free_banner": free_name + " %d OF %d", "free_summary": free_name,
			"free_sub": "%d games at %s", "bonus_line": str(t.get("bonus_line", "3+ BONUS")), "free_line": str(t.get("free_line", "3+ FREE SPINS")),
			"buy_text": "Go straight to the " + trail_name.capitalize() + " for %s", "buy_sub": "%d × your %s bet. Bonus wins pay at %s.",
			"battle": str(t.get("battle", "RED ALERT")), "battle_hint": str(t.get("battle_hint", "tap a ship to fire")),
			"enemy": str(t.get("enemy", "ENEMY SHIP")), "boss": str(t.get("boss", "FLAGSHIP"))}, true)
		# the voyage's words (Build writes voyage_<word>; the islands, chest and legend as voyage_<word>_name)
		for k in ["name", "hint", "start", "final", "relic"]:
			texts["voyage_" + k] = str(t.get("voyage_" + k, ARMADILLO_TEXTS["voyage_" + k]))
		for k in ["treasure", "wreck", "skull", "port", "cove", "chest", "legend"]:
			texts["voyage_" + k] = str(t.get("voyage_%s_name" % k, ARMADILLO_TEXTS["voyage_" + k]))
		texts["voyage_artefacts"] = t.get("voyage_artefacts", ARMADILLO_TEXTS.voyage_artefacts)
	tips = theme.get("rules", ARMADILLO_TIPS)
	labels = bool(theme.get("labels", true))
	var fr: Dictionary = theme.get("frame", {})
	frame_style = str(fr.get("style", "wood"))
	frame_colour = Color(str(fr.get("colour", "d9a54a")))
	var dk: Dictionary = theme.get("deck", {})
	deck = _deck_look(str(dk.get("style", frame_style)), dk.get("colour"))
	win_anims = theme.get("win", {})
	background = bool(theme.get("background", false))
	skin = theme.get("skin", {})
	if skin.get("texts", {}).has("tagline"):
		texts["tagline"] = str(skin.texts.tagline)
	var on: Array = rules.get("features", [])
	var names: Dictionary = theme.get("texts", {}).get("feature_names", {})
	feature_rows = FEATURE_ROWS.filter(func(f): return on.is_empty() or on.has(f[0])).map(func(f): return [f[0], str(names.get(f[0], f[1]))])


func close(to_rect: Rect2) -> void:
	auto = 0
	overlay = {}
	_from_rect = to_rect
	_closing = true
	_epoch += 1
	_stop_loops()
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
	_stop_loops()
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
	battle = {}
	voyage = {}
	pick = {}
	landed = true
	win_shown = 0.0
	win_target = 0.0
	_credit_adj = 0
	for x in reels:
		x.spinning = false
		x.stopping = false
		x.v = 0.0
		x.glow = 0.0
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
		"battle":
			if state.get("battle") != null:
				_begin_battle(state.battle)
				battle.waiting = float(state.get("battle_ready_in", 0.0)) <= 0.0
				battle.auto_at = _now + float(state.get("timer", 8.0) if state.get("timer") != null else 8.0)
		"voyage":
			if state.get("voyage") != null:
				_begin_voyage(_voyage_view(state.voyage))
				if float(state.get("voyage_ready_in", 0.0)) <= 0.0 and not bool(state.voyage.done):
					_voyage_ready()
					voyage.auto_at = _now + float(state.get("timer", 12.0) if state.get("timer") != null else 12.0)
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


## Every await below can come back to a reset screen (a resync's snapshot, or closing it):
## then stop, rather than write this event's leftovers into the new state.
func _handle(ev: Dictionary) -> void:
	var ep := _epoch
	match ev.kind:
		"spin":
			await _on_spin(ev)
		"bonus_bought":
			message = "BONUS BOUGHT: %s" % Money.format(int(ev.cost))
		"jackpot_start":
			_begin_pick()
			_sfx("bonus_trigger")
			await _banner("JACKPOT PICK", "pick coins until three match", 1.8)
		"jackpot_reveal":
			await _reveal_coin(int(ev.index), str(ev.tier))
		"slot_jackpot_won":
			await _jackpot_won(ev)
		"trail_start":
			_begin_trail(ev.trail)
			_sfx("bonus_trigger")
			await _banner(texts.trail, "bought for %s" % Money.format(int(ev.trail.bet) * int(rules.get("buy_cost", 45)))
				if ev.get("bought", false) else texts.trail_hint, 2.2)
			if ep != _epoch:
				return
			trail.waiting = true
			trail.auto_at = _now + 6.0
			message = texts.trail_message
		"trail_roll":
			if not trail.is_empty():
				trail.waiting = false
				await _animate_roll(ev.roll)
				if ep != _epoch:
					return
				trail.total = int(ev.total)
				if not ev.roll.done:
					trail.waiting = true
					trail.auto_at = _now + 6.0
		"trail_end":
			await _wait(0.6)
			if ep != _epoch:
				return
			_credit_adj += int(ev.total)
			await _summary("PRIZEPOT!" if ev.get("prizepot", false) else texts.trail,
				"%d shots at %s" % [int(ev.rolls), Money.format(int(trail.get("bet", 100)))], int(ev.total))
			if ep != _epoch:
				return
			if int(ev.total) >= 10 * int(trail.get("bet", 100)):
				await _big_win(int(ev.total), int(trail.get("bet", 100)))
			if ep != _epoch:
				return
			trail = {}
			_clear_wins()
			win_shown = float(ev.total)
			win_target = win_shown
			message = "%s PAID %s" % [texts.trail, Money.format(int(ev.total))]
		"battle_start":
			_begin_battle(ev.battle)
			_sfx("battle_alert")
			await _banner(texts.battle, "bought for %s" % Money.format(int(ev.battle.bet) * int(rules.get("buy_cost", 45)))
				if ev.get("bought", false) else texts.battle_hint, 2.6)
			if ep != _epoch:
				return
			_battle_ready()
		"battle_shot":
			if not battle.is_empty():
				battle.waiting = false
				await _animate_shot(ev.shot)
				if ep != _epoch:
					return
				battle.total = int(ev.total)
				if not ev.shot.done:
					_battle_ready()
		"battle_end":
			await _wait(0.6)
			if ep != _epoch:
				return
			_credit_adj += int(ev.total)
			var b_bet := int(battle.get("bet", 100))
			var games := " · %d free game%s to come" % [int(ev.spins), "" if int(ev.spins) == 1 else "s"] if int(ev.spins) > 0 else ""
			await _summary("%s DESTROYED!" % texts.boss if ev.get("won", false) else texts.battle,
				"%d of %d waves cleared%s" % [int(ev.cleared), int(battle.get("waves", 5)), games], int(ev.total))
			if ep != _epoch:
				return
			if int(ev.total) >= 10 * b_bet:
				await _big_win(int(ev.total), b_bet)
			if ep != _epoch:
				return
			battle = {}
			_clear_wins()
			win_shown = float(ev.total)
			win_target = win_shown
			message = "%s PAID %s" % [texts.battle, Money.format(int(ev.total))]
		"voyage_start":
			_begin_voyage(_voyage_view(ev.voyage))
			_sfx("voyage_start")
			await _banner(texts.voyage_name, "bought for %s" % Money.format(int(ev.voyage.bet) * int(rules.get("buy_cost", 45)))
				if ev.get("bought", false) else texts.voyage_hint, 2.6)
			if ep != _epoch:
				return
			_voyage_ready()
		"voyage_step":
			if not voyage.is_empty():
				voyage.waiting = false
				await _animate_voyage(ev.step)
				if ep != _epoch:
					return
				voyage.st = _voyage_view(ev.voyage)
				if not ev.step.done:
					_voyage_ready()
		"voyage_end":
			await _wait(0.8)
			if ep != _epoch:
				return
			_credit_adj += int(ev.total)
			var v_bet := int(voyage.get("bet", 100))
			var v_games := " · %d free game%s to come" % [int(ev.spins), "" if int(ev.spins) == 1 else "s"] if int(ev.spins) > 0 else ""
			var sunk := bool(ev.get("sunk", false))
			var found := 0 if sunk else (ev.treasure.parts as Array).filter(func(p): return int(p) > 0).size()
			await _summary(texts.voyage_name if sunk else "%s!" % texts.voyage_chest,
				("sunk on the way" if sunk else "%d of 4 artefacts" % found) + v_games, int(ev.total))
			if ep != _epoch:
				return
			if int(ev.total) >= 10 * v_bet:
				await _big_win(int(ev.total), v_bet)
			if ep != _epoch:
				return
			voyage = {}
			_clear_wins()
			win_shown = float(ev.total)
			win_target = win_shown
			message = "%s PAID %s" % [texts.voyage_name, Money.format(int(ev.total))]
		"free_start":
			free = {"n": 0, "of": int(ev.of), "total": 0, "bet": int(ev.bet)}
			_sfx("bonus_trigger")
			var sub := "%d games  ·  a random feature every spin" % int(ev.of)
			if ev.get("bought", false):
				sub = "bought for %s" % Money.format(int(ev.bet) * int(rules.get("buy_cost", 45)))
			elif str(ev.get("source", "")) == "battle":
				sub = "%d won in %s  ·  a random feature every spin" % [int(ev.of), texts.battle.to_lower()]
			elif str(ev.get("source", "")) == "voyage":
				sub = "%d bought on %s  ·  a random feature every spin" % [int(ev.of), texts.voyage_name.to_lower()]
			await _banner(texts.free, sub, 2.2)
		"free_game":
			free.n = int(ev.n)
			_sfx("free_spin")
			message = "FREE GAME %d OF %d" % [int(ev.n), int(ev.of)]
			await _play_spin(ev.outcome, float(free.total))
			if ep != _epoch:
				return
			free.total = int(ev.total)
			await _wait(0.6)
		"free_end":
			_credit_adj += int(ev.total)
			await _summary(texts.free_summary, texts.free_sub % [int(free.get("of", 3)), Money.format(int(free.get("bet", 100)))], int(ev.total))
			if ep != _epoch:
				return
			if int(ev.total) >= 10 * int(free.get("bet", 100)):
				await _big_win(int(ev.total), int(free.get("bet", 100)))
			if ep != _epoch:
				return
			free = {}
			message = "FREE GAMES PAID %s" % Money.format(int(ev.total))
		"features_done":
			_round_over()


func _on_spin(ev: Dictionary) -> void:
	var o: Dictionary = ev.outcome
	var ep := _epoch
	_hurry = false
	message = "GOOD LUCK!"
	await _play_spin(o)
	if ep != _epoch:
		return
	if int(o.total) >= 10 * int(o.bet):
		await _big_win(int(o.total), int(o.bet))
		if ep != _epoch:
			return
	message = "YOU WON %s" % Money.format(int(o.total)) if int(o.total) > 0 else "25 LINES  ·  " + texts.tagline
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
				if auto > 0 and visible and not _closing and ep == _epoch:
					_send_spin()


## Everything this spin started has been shown: the credit catches up.
func _round_over() -> void:
	if _queue.is_empty():
		_credit_adj = 0
		Session.hold_balance(false)


# ------------------------------------------------------------------ sounds
## A moment from this machine's sound set (Sfx.focus is the same cabinet, but say so).
func _sfx(key: String, pitch := 1.0) -> void:
	Sfx.play(key, pitch, cab.table_id if cab else "")


func _after_sfx(sec: float, key: String) -> void:
	var ep := _epoch
	await get_tree().create_timer(sec).timeout
	if ep == _epoch and visible:
		_sfx(key)


## Start a looping moment under a name, unless that name is already playing.
func _loop(name: String, key: String) -> void:
	if not _loops.has(name):
		_loops[name] = Sfx.start_loop(key, cab.table_id if cab else "")


func _unloop(name: String, fade := 0.15) -> void:
	if _loops.has(name):
		Sfx.stop_loop(int(_loops[name]), fade)
		_loops.erase(name)


func _stop_loops() -> void:
	for name in _loops.keys():
		_unloop(name)


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
		if win_shown < win_target:
			_loop("meter", "win_bangup")
	if win_shown >= win_target and _loops.has("meter"):
		_unloop("meter")
		_sfx("win_end")
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
	if not battle.is_empty() and battle.get("waiting", false) and _now >= float(battle.get("auto_at", 1e9)) + 1.0:
		battle.waiting = false   # ...and the same for the battle's shot
	if not voyage.is_empty() and voyage.get("waiting", false) and _now >= float(voyage.get("auto_at", 1e9)) + 1.0:
		voyage.waiting = false   # ...and the voyage's choice
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
	draw_rect(Rect2(Vector2.ZERO, get_viewport_rect().size), Color(SHADE.darkened(0.6), 0.92 * _grow))


func _draw_layer(ci: CanvasItem, which: String) -> void:
	match which:
		"under":
			_hits = []
			_draw_background(ci)
			_draw_decor(ci, "under")
			_draw_top(ci)
			if not trail.is_empty():
				_draw_trail(ci)
			elif not battle.is_empty():
				_draw_battle(ci)
			elif not voyage.is_empty():
				_draw_voyage(ci)
			else:
				_draw_sides(ci)
				_draw_frame(ci)
		"reels":
			if trail.is_empty() and battle.is_empty() and voyage.is_empty():
				_draw_reels(ci)
		"over":
			if not trail.is_empty():
				_draw_trail_hud(ci)
			elif not battle.is_empty():
				_draw_battle_hud(ci)
			elif not voyage.is_empty():
				_draw_voyage_hud(ci)
			else:
				_draw_reel_overlay(ci)
				_draw_wins(ci)
				if not pick.is_empty():
					_draw_pick(ci)
			if not free.is_empty():
				_rr(ci, Rect2(440, REEL_Y - 16, 400, 34), 10, ALERT, 2, GOLD)
				_text(ci, texts.free_banner % [int(free.n), int(free.of)], Vector2(640, REEL_Y + 1), 22, COND, GOLD_HI, "center", 0, 380)
			_draw_deck(ci)
			_draw_decor(ci, "over")
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
		ci.draw_string_outline(font, Vector2(x, y), s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, outline, Color(SHADE, 0.95))
	ci.draw_string(font, Vector2(x, y), s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, col)


## The largest size (down to 8: a wide font can need it) at which `s` fits `max_w` (0: no limit).
static func _fit(s: String, font: Font, size: int, max_w: float) -> int:
	if max_w <= 0.0:
		return size
	var w := font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	if w <= max_w:
		return size
	size = maxi(8, int(size * max_w / w))
	while size > 8 and font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x > max_w:
		size -= 1
	return size


## Banner and big-win lettering: Rye in gold on a dark outline, with a drop shadow. (Every
## layer sits exactly on the text, so it stays sharp at any window size.)
func _gold_text(ci: CanvasItem, s: String, at: Vector2, size: int, max_w := 0.0) -> void:
	size = _fit(s, RYE, size, max_w)
	var w := RYE.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	var p := Vector2(at.x - w / 2.0, at.y + (RYE.get_ascent(size) - RYE.get_descent(size)) / 2.0)
	var edge := maxi(2, int(size * 0.14))
	ci.draw_string_outline(RYE, p + Vector2(0, size * 0.06), s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, edge + 2, Color(SHADE, 0.85))
	ci.draw_string_outline(RYE, p, s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, edge, INK)
	ci.draw_string(RYE, p, s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, GOLD_TEXT)


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


func _hgrad(ci: CanvasItem, r: Rect2, left: Color, right: Color) -> void:
	ci.draw_polygon(PackedVector2Array([r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)]),
		PackedColorArray([left, right, right, left]))


## Wood untinted is Armadillo's browns; any other style or a tint derives the set from one base colour (the wizard's
## mockup, game.js deckLook, matches).
func _deck_look(style: String, tint: Variant) -> Dictionary:
	if style == "wood" and tint == null:
		return {"band": Color(0.05, 0.02, 0.01, 0.86), "box": Color("1a0c05"), "box_edge": Color("7a5a36"),
			"inset": Color(0.08, 0.035, 0.015, 0.65), "buy": Color(0.16, 0.07, 0.02, 0.85), "buy_hover": Color(0.35, 0.16, 0.04, 0.95),
			"btn": [Color("6e4426"), Color("2c1609")], "ring": Color("1a0b03")}
	var b := Color(str(tint)) if tint != null else Color({"wood": "6e4426", "neon": "2b2470", "glass": "5a6f96"}.get(style, "5d6470"))
	var glass := style == "glass"
	return {"band": Color(b.darkened(0.75), 0.62) if glass else Color(b.darkened(0.9), 0.88), "box": Color(b.darkened(0.82), 0.6 if glass else 1.0),
		"box_edge": frame_colour if style == "neon" else b.lerp(Color.WHITE, 0.12), "inset": Color(b.darkened(0.8), 0.65),
		"buy": Color(b.darkened(0.7), 0.85), "buy_hover": Color(b.darkened(0.45), 0.95), "btn": [b, b.darkened(0.6)], "ring": b.darkened(0.85)}


## A panel in the slot's frame style: wood (Armadillo's), metal, neon or glass, edged in its colour.
func _wood(ci: CanvasItem, r: Rect2, radius := 14.0) -> void:
	if _lc():
		_lcars_panel(ci, r)
		return
	if frame_style != "wood":
		var top := Color("5d6470")
		var bottom := Color("15181d")
		if frame_style == "neon":
			top = Color(0.04, 0.03, 0.12, 0.94)
			bottom = Color(0.02, 0.01, 0.06, 0.94)
		elif frame_style == "glass":
			top = Color(1, 1, 1, 0.16)
			bottom = Color(0.04, 0.05, 0.12, 0.6)
		_rr(ci, r, radius, bottom, 2, Color(1, 1, 1, 0.35) if frame_style == "glass" else Color("0b0c10"))
		_vgrad(ci, Rect2(r.position + Vector2(4, 4), Vector2(r.size.x - 8, r.size.y * 0.5)), top, Color(top, 0.0))
		if frame_style == "neon":
			_rr(ci, r.grow(2), radius + 2, Color.TRANSPARENT, 5, Color(frame_colour, 0.3))
		_rr(ci, r.grow(-3), radius - 3, Color.TRANSPARENT, 3, frame_colour)
		return
	_rr(ci, r, radius, Color("5c341a"), 2, Color("1a0b03"))
	_vgrad(ci, Rect2(r.position + Vector2(4, 4), Vector2(r.size.x - 8, r.size.y * 0.45)), Color(0.55, 0.33, 0.19, 0.55), Color(0.36, 0.2, 0.1, 0.0))
	var i := 10.0
	while i < r.size.y - 8:
		var y := r.position.y + i
		ci.draw_line(Vector2(r.position.x + 6, y + sin(i) * 2.0), Vector2(r.end.x - 6, y + cos(i) * 1.5), Color(0.12, 0.05, 0.02, 0.12), 1.2)
		i += 7.0
	_rr(ci, r.grow(-3), radius - 3, Color.TRANSPARENT, 3, EDGE)


func _button(ci: CanvasItem, id: String, r: Rect2, label: String, on := false, disabled := false, size := 22, colour: Array = []) -> void:
	var hover := _hover == id and not disabled
	var cols: Array = colour if not colour.is_empty() else ([GOLD.lerp(GOLD_HI, 0.5), GOLD_LO] if on else deck.btn)
	var a := 0.4 if disabled else 1.0
	if _lc():   # LCARS: a flat pill, its label on the right
		var bp: Dictionary = _part("button")
		var f: Color = cols[1] if not colour.is_empty() else (_sc(bp.get("on", "warn")) if on else _sc(bp.get("fill", "b")))
		SkinDraw.fill(ci, SkinDraw.pill(r, "right" if bp.get("shape") == "half" else "both"), Color(f.lerp(Color.WHITE, 0.3) if hover else f, a))
		var wide := r.size.x > 80 and label.length() > 1
		_text(ci, label, Vector2(r.end.x - 12 if wide else r.get_center().x, r.get_center().y + 1), mini(size, int(r.size.y * 0.5)),
			RYE if wide else COND, Color(_sc(bp.get("text", "ink")), a), "right" if wide else "center", 0, r.size.x - 20)
		if not disabled:
			_add_hit(id, r)
		return
	_rr(ci, r, r.size.y * 0.28, Color(cols[1], a), 3 if hover else 2, Color(GOLD_HI if hover else EDGE, a))
	_vgrad(ci, Rect2(r.position + Vector2(3, 3), Vector2(r.size.x - 6, r.size.y * 0.5 - 3)), Color(cols[0], 0.75 * a), Color(cols[0], 0.0))
	_text(ci, label, r.get_center() + Vector2(0, 1), size, COND, Color(INK if (on or not colour.is_empty()) else CREAM, a), "center", 0, r.size.x - 14)
	if not disabled:
		_add_hit(id, r)


## FIRE: the alert colour brightened on top, itself underneath.
func _fire_colours() -> Array:
	var hot := Color(minf(ALERT.r * 1.8, 1.0), minf(ALERT.g * 1.8, 1.0), minf(ALERT.b * 1.8, 1.0))
	return [hot.lerp(Color.WHITE, 0.6), ALERT]


## Something clickable. Debug builds warn (once each) if it's off the safe area of the screen.
var _warned := {}
func _add_hit(id: String, r: Rect2) -> void:
	_hits.append([id, r])
	if OS.is_debug_build() and not SAFE.encloses(r) and not _warned.has(id):
		_warned[id] = true
		push_warning("SlotScreen: '%s' at %s isn't inside the safe area %s" % [id, r, SAFE])


func _tex(id: String) -> Texture2D:
	return SlotArt.tex(variant, id)


## Which bonuses a way in plays ("BS", "FS" or "buy"); several means one of them at random.
func _routes(way: String) -> Array:
	return rules.get("routes", ROUTES).get(way, [])


func _can_buy() -> bool:
	return int(rules.get("buy_cost", 0)) > 0 and not _routes("buy").is_empty()


## What a way in plays, for the side panel: the bonus's name, or each of them "or" (it's one at random).
func _plays(kinds: Array) -> String:
	var names := []
	for k in kinds:
		match str(k):
			"trail": names.append(texts.trail)
			"battle": names.append(texts.battle)
			"voyage": names.append(texts.voyage_name)
			_: names.append("%d %s" % [int(rules.get("free_games", 3)), texts.free])
	return " OR ".join(names)


## The Buy Bonus picture: the scatter of what it buys (the bonus scatter's when that's the trail's).
func _buy_icon() -> Texture2D:
	for s in ["BS", "FS"]:
		for k in _routes("buy"):
			if k in _routes(s):
				return _tex(s)
	return _tex("BS") if _tex("BS") else _tex("FS")


func _sym(ci: CanvasItem, sym: String, r: Rect2, fx: Dictionary = {}, alpha := 1.0) -> void:
	var tex := _tex(sym)
	if tex == null:
		return
	var s := 0.92 * float(fx.get("scale", 1.0))
	var flip := absf(cos(float(fx.flip) * PI)) if fx.has("flip") else 1.0
	# a win animation (Sprites step), while this symbol's line win shows
	var anim: Dictionary = fx.get("anim", {})
	var k := float(anim.get("strength", 1.0))
	var preset := str(anim.get("preset", "none"))
	var dy := 0.0
	if preset == "pulse":
		s *= 1.0 + 0.08 * k * (0.5 + 0.5 * sin(_now * 7.0))
	elif preset == "bounce":
		dy = -10.0 * k * absf(sin(_now * 6.0))
	elif preset == "spin":
		flip = maxf(0.08, absf(cos(_now * 3.0 * k)))
	var size := minf(r.size.x, r.size.y) * s
	var c := r.get_center() + Vector2(0, dy)
	ci.draw_set_transform(c, 0, Vector2(maxf(0.02, flip), 1))
	var glow := float(fx.get("glow", 0.0))
	if glow > 0.0:
		var gc: Color = fx.get("glow_colour", WIN_COL)
		ci.draw_circle(Vector2.ZERO, size * 0.5, Color(gc, 0.35 * glow))
	if preset == "glow":
		ci.draw_circle(Vector2.ZERO, size * 0.52, Color(Color(str(anim.get("colour", "ffe27a"))), 0.3 * minf(1.0, k) * (0.6 + 0.4 * sin(_now * 6.0))))
	ci.draw_texture_rect(tex, Rect2(-size / 2.0, -size / 2.0, size, size), false, Color(1, 1, 1, alpha))
	if preset == "shine":   # a light band sweeping across the symbol
		var p := fmod(_now * 0.9, 1.4) - 0.2
		var x0 := -size / 2.0 + p * size * 1.6 - size * 0.3
		var band := PackedVector2Array([Vector2(x0, -size / 2.0), Vector2(x0 + size * 0.22, -size / 2.0), Vector2(x0 - size * 0.38, size / 2.0), Vector2(x0 - size * 0.6, size / 2.0)])
		var square := PackedVector2Array([Vector2(-size / 2.0, -size / 2.0), Vector2(size / 2.0, -size / 2.0), Vector2(size / 2.0, size / 2.0), Vector2(-size / 2.0, size / 2.0)])
		for part in Geometry2D.intersect_polygons(band, square):
			ci.draw_colored_polygon(part, Color(1, 1, 1, 0.3 * minf(1.0, k) * alpha))
	if labels and sym in ["W", "BS", "FS"]:
		var label: String = {"W": "WILD", "BS": "BONUS", "FS": "FREE SPINS"}[sym]
		var lw := r.size.x * 0.72
		_rr(ci, Rect2(-lw / 2.0, r.size.y / 2.0 - 30, lw, 24), 6, Color(ALERT if sym == "W" else INK, alpha), 2, Color(GOLD, alpha))
		_text(ci, label, Vector2(0, r.size.y / 2.0 - 17), 17 if sym == "FS" else 21, RYE, Color(GOLD_HI, alpha))
	ci.draw_set_transform(Vector2.ZERO)


# ------------------------------------------------------------------ the skin (the wizard mockup's game.js matches)
func _lc() -> bool:
	return str(skin.get("base", "classic")) == "lcars"


## A skin's colour: one of its names (its palette, then the screen's colours) or a colour like #8fd3ff.
func _sc(ref: String) -> Color:
	if ref.begins_with("#"):
		return Color(ref)
	var pal: Dictionary = skin.get("palette", {})
	if pal.has(ref):
		return Color(str(pal[ref]))
	var named := {"gold": GOLD, "goldHi": GOLD_HI, "goldLo": GOLD_LO, "edge": EDGE, "cream": CREAM, "muted": MUTED, "ink": INK,
		"shade": SHADE, "win": WIN_COL, "spin": SPIN_COL, "alert": ALERT}
	return named.get(ref, EDGE)


func _part(p: String) -> Dictionary:
	return skin.get("parts", {}).get(p, {})


## One of the screen's words, as the skin relabels it.
func _t(key: String, fallback: String) -> String:
	return str(skin.get("texts", {}).get(key, fallback))


func _glass(ci: CanvasItem, pts: PackedVector2Array, tint: String, edge: Color, edge_w := -1.0) -> void:
	var g: Dictionary = skin.get("glass", {})
	SkinDraw.glass(ci, pts, _tex("bg_glass") if background else null, _sc(tint), float(g.get("opacity", 0.55)), float(g.get("sheen", 0.0)),
		edge, float(g.get("edge", 1.5)) if edge_w < 0.0 else edge_w)


## An LCARS panel: elbows top and bottom on its spine side, the spine between in blocks, a glass body. The side panels'
## spines run in the screen's margin, on its edge; a pop-up's on its left.
func _lcars_panel(ci: CanvasItem, r: Rect2) -> void:
	var p := _part("panel")
	if p.get("shape") == "glass":
		_glass(ci, SkinDraw.rounded(r, 16), str(p.get("fill", "glass")), _sc(p.get("edge", "hl")))
		return
	var right := r.end.x >= 1250.0
	var left := r.position.x <= 20.0
	var arm := 16.0 if left or right else 14.0
	var bar := 14.0
	var gap := 4.0
	var ox := 4.0 if left else r.position.x
	var ow := r.end.x - 4.0 if left else (1276.0 - r.position.x if right else r.size.x)
	var bx := 4.0 + arm + gap if left else (r.position.x if right else r.position.x + arm + gap)
	var bw := r.end.x - 4.0 - bx if left else (1276.0 - arm - gap - r.position.x - 4.0 if right else r.size.x - arm - gap)
	var eh := minf(110.0, r.size.y * 0.3)
	var y := r.position.y
	var h := r.size.y
	_glass(ci, SkinDraw.rounded(Rect2(bx, y + bar + gap, bw, h - 2.0 * (bar + gap)), 10), str(p.get("fill", "glass")), _sc(p.get("edge", "hl")), 1.0)
	SkinDraw.fill(ci, SkinDraw.elbow(Rect2(ox, y, ow, eh), "tr" if right else "tl", arm, bar, 44), _sc(p.get("top", "a")))
	SkinDraw.fill(ci, SkinDraw.elbow(Rect2(ox, y + h - eh, ow, eh), "br" if right else "bl", arm, bar, 44), _sc(p.get("bottom", "c")))
	var spine: Array = p.get("spine", ["b"])
	var top := y + eh + gap
	var seg := (h - 2.0 * (eh + gap) - gap * (spine.size() - 1)) / spine.size()
	for i in spine.size():
		ci.draw_rect(Rect2(ox + ow - arm if right else ox, top + i * (seg + gap), arm, seg), _sc(str(spine[i])))


func _lcars_frame(ci: CanvasItem) -> void:
	var p := _part("frame")
	var r := Rect2(REEL_X - 22, REEL_Y - 18, REEL_W + 44, REEL_H + 36)
	ci.draw_rect(Rect2(REEL_X, REEL_Y, REEL_W, REEL_H), _sc(p.get("fill", "glass")))
	for i in 5:
		var x := REEL_X + i * CELL_W
		_hgrad(ci, Rect2(x, REEL_Y, CELL_W / 2.0, REEL_H), Color(0, 0, 0, 0.45), Color(1, 1, 1, 0.03))
		_hgrad(ci, Rect2(x + CELL_W / 2.0, REEL_Y, CELL_W / 2.0, REEL_H), Color(1, 1, 1, 0.03), Color(0, 0, 0, 0.45))
	var edge := _sc(p.get("edge", "hl"))
	if p.get("shape") == "glass":
		_glass(ci, SkinDraw.rounded(Rect2(r.position.x, r.position.y, r.size.x, 14), 7), str(p.get("fill", "glass")), edge, 1.0)
		_glass(ci, SkinDraw.rounded(Rect2(r.position.x, r.end.y - 14, r.size.x, 14), 7), str(p.get("fill", "glass")), edge, 1.0)
		SkinDraw.outline(ci, SkinDraw.rounded(r, 18), edge, 1.5)
		return
	var arm := 10.0
	var bar := 10.0
	var gap := 4.0
	var top := _sc(p.get("top", "a"))
	var bottom := _sc(p.get("bottom", "c"))
	SkinDraw.fill(ci, SkinDraw.elbow(Rect2(r.position.x, r.position.y, 260, 120), "tl", arm, bar, 28), top)
	SkinDraw.fill(ci, SkinDraw.elbow(Rect2(r.end.x - 260, r.end.y - 120, 260, 120), "br", arm, bar, 28), bottom)
	# the bars running on from each elbow, in blocks; the last one's end rounded
	var run := r.size.x - 260.0 - gap
	var seg := [0.62, 0.24, 0.14]
	var x := r.position.x + 260.0 + gap
	var cols := [top, edge, bottom]
	for i in 3:
		var sw: float = run * seg[i] - (gap if i < 2 else 0.0)
		SkinDraw.fill(ci, SkinDraw.pill(Rect2(x, r.position.y, sw, bar), "right" if i == 2 else "none"), cols[i])
		x += sw + gap
	x = r.end.x - 260.0 - gap
	cols = [bottom, edge, top]
	for i in 3:
		var sw: float = run * seg[i] - (gap if i < 2 else 0.0)
		SkinDraw.fill(ci, SkinDraw.pill(Rect2(x - sw, r.end.y - bar, sw, bar), "left" if i == 2 else "none"), cols[i])
		x -= sw + gap
	ci.draw_rect(Rect2(r.position.x + 2, r.position.y + 120 + gap, 2, r.size.y - 120 - 2 * gap - bar), Color(edge, 0.7))
	ci.draw_rect(Rect2(r.end.x - 4, r.position.y + bar + gap, 2, r.size.y - 120 - 2 * gap - bar), Color(edge, 0.7))


## A jackpot meter: a tier-coloured cap on its outer end and a glass body (tab); a coloured pill; or glass.
func _lcars_meter(ci: CanvasItem, id: String, r: Rect2, lit: bool) -> void:
	var p := _part("meter")
	var pal: Dictionary = skin.get("palette", {})
	var tier: Color = Color(str(pal[id])) if pal.has(id) else TIERS[id]
	var fill: Color = tier if p.get("fill", "tier") == "tier" else _sc(str(p.fill))
	var value := Money.format(int(meter_now(id)))
	if p.get("shape") == "pill":
		SkinDraw.fill(ci, SkinDraw.pill(r), fill.lerp(Color.WHITE, 0.35) if lit else fill)
		_text(ci, TIER_NAMES[id], Vector2(r.get_center().x, r.position.y + 18), 16, RYE, _sc("ink"), "center", 0, r.size.x - 40)
		_text(ci, value, Vector2(r.get_center().x, r.position.y + 46), 32, COND, _sc("ink"), "center", 0, r.size.x - 40)
		return
	var body := r
	if p.get("shape") == "glass":
		_glass(ci, SkinDraw.rounded(r, 18), "glass", fill, 4.0 if lit else 2.0)
	else:
		var cap := 44.0
		var gap := 5.0
		var outer_left := r.position.x < 640.0
		var cap_r := Rect2(r.position.x if outer_left else r.end.x - cap, r.position.y, cap, r.size.y)
		body = Rect2(r.position.x + cap + gap if outer_left else r.position.x, r.position.y, r.size.x - cap - gap, r.size.y)
		SkinDraw.fill(ci, SkinDraw.pill(cap_r, "left" if outer_left else "right"), fill.lerp(Color.WHITE, 0.45) if lit else fill)
		var pts := PackedVector2Array([body.position, Vector2(body.end.x, body.position.y), body.end, Vector2(body.position.x, body.end.y)])
		_glass(ci, pts, "glass", _sc("hl") if lit else fill, 3.0 if lit else 1.5)
	_text(ci, TIER_NAMES[id], Vector2(body.get_center().x, body.position.y + 17), 16, RYE, fill, "center", 0, body.size.x - 16)
	_text(ci, value, Vector2(body.get_center().x, body.position.y + 46), 32, COND, _sc(p.get("text", "goldHi")), "center", 0, body.size.x - 16)


## A box (credit, bet, win; the feature list; the info boxes): a glass pill (rounded when tall), or glass. A lit
## colour fills it instead.
func _lcars_box(ci: CanvasItem, r: Rect2, lit := Color.TRANSPARENT, edge_w := -1.0) -> void:
	var p := _part("box")
	var pts := SkinDraw.rounded(r, minf(14.0 if p.get("shape") == "glass" else 22.0, r.size.y / 2.0)) if p.get("shape") == "glass" or r.size.y > 60.0 else SkinDraw.pill(r)
	if lit.a > 0.0:
		SkinDraw.fill(ci, pts, lit)
		return
	_glass(ci, pts, str(p.get("fill", "glass")), _sc(p.get("edge", "b")), edge_w)


## The deck: dark glass under an LCARS rail, an elbow at its left end.
func _lcars_deck(ci: CanvasItem) -> void:
	var p := _part("deck")
	var fill := _sc(p.get("fill", "d"))
	var accent := _sc(p.get("accent", "a"))
	var edge := _sc(p.get("edge", "hl"))
	ci.draw_rect(Rect2(0, DECK_TOP, W, H - DECK_TOP), Color(_sc("shade"), 0.9))
	var bar := 6.0
	if p.get("shape") == "bar":
		SkinDraw.fill(ci, SkinDraw.pill(Rect2(4, DECK_TOP, 600, bar), "left"), accent)
		ci.draw_rect(Rect2(608, DECK_TOP, 200, bar), edge)
		SkinDraw.fill(ci, SkinDraw.pill(Rect2(812, DECK_TOP, W - 816, bar), "right"), fill)
		return
	SkinDraw.fill(ci, SkinDraw.elbow(Rect2(4, DECK_TOP, 140, H - DECK_TOP - 4), "tl", 12, bar, 26), accent)
	ci.draw_rect(Rect2(148, DECK_TOP, 460, bar), fill)
	ci.draw_rect(Rect2(612, DECK_TOP, 180, bar), edge)
	SkinDraw.fill(ci, SkinDraw.pill(Rect2(796, DECK_TOP, W - 800, bar), "right"), fill)


## The spin button: a pill across the gap between AUTO and CASH OUT, or a glass disc. Returns where it clicks.
func _lcars_spin(ci: CanvasItem, label: String, spinning: bool, hov: bool) -> Rect2:
	var p := _part("spin")
	var f := _sc(p.get("fill", "hl"))
	var tc := _sc(p.get("text", "ink"))
	if p.get("shape") == "disc":
		var c := SPIN_CENTRE
		var disc := SkinDraw.rounded(Rect2(c - Vector2(46, 46), Vector2(92, 92)), 46)
		_glass(ci, disc, "glass", f, 5.0 if hov else 3.0)
		ci.draw_circle(c, 34, f.darkened(0.25) if spinning else f)
		_text(ci, label, c + Vector2(0, 2), 22, RYE, tc, "center", 0, 62)
		return Rect2(c - Vector2(46, 46), Vector2(92, 92))
	var b := Rect2(1036, 628, 128, 72)
	SkinDraw.fill(ci, SkinDraw.pill(b), f.darkened(0.25) if spinning else (f.lerp(Color.WHITE, 0.3) if hov else f))
	_text(ci, label, b.get_center() + Vector2(0, 2), 28, RYE, tc, "center", 0, b.size.x - 28)
	return b


## Decor: the skin's free shapes, under the parts or over them.
func _draw_decor(ci: CanvasItem, layer: String) -> void:
	for d in skin.get("decor", []):
		if str(d.get("layer", "under")) != layer or d.get("show", true) == false:
			continue
		var r := Rect2(float(d.x), float(d.y), float(d.w), float(d.h))
		var col := Color(_sc(str(d.get("colour", "hl"))), float(d.get("alpha", 1.0)))
		var font := COND if d.get("font") == "ui" else RYE
		match str(d.kind):
			"elbow":
				SkinDraw.fill(ci, SkinDraw.elbow(r, str(d.corner), float(d.arm), float(d.bar), float(d.r)), col)
			"bar", "pill":
				SkinDraw.fill(ci, SkinDraw.pill(r, str(d.get("round", "both"))), col)
				if d.kind == "pill" and str(d.get("text", "")) != "":
					var al := str(d.get("align", "right"))
					var tx := r.position.x + r.size.y / 2.0 + 4.0 if al == "left" else (r.end.x - r.size.y / 2.0 - 4.0 if al == "right" else r.get_center().x)
					_text(ci, SkinDraw.tokens(str(d.text), str(rules.get("name", ""))), Vector2(tx, r.get_center().y + 1), int(d.size), font,
						Color(_sc(str(d.get("text_colour", "ink"))), col.a), al, 0, r.size.x - r.size.y)
			"text":
				var al := str(d.get("align", "left"))
				var tx := r.position.x if al == "left" else (r.end.x if al == "right" else r.get_center().x)
				_text(ci, SkinDraw.tokens(str(d.text), str(rules.get("name", ""))), Vector2(tx, r.get_center().y), int(d.size), font, col, al, 0, r.size.x)
			"readout":
				var cells: Array = d.get("cells", [2, 5, 2])
				var cols: Array = d.get("colours", ["hl"])
				var total := 0.0
				for n in cells:
					total += float(n) + 1.2
				var gap := 3.0
				var unit := (r.size.x - gap * (cells.size() - 1)) / total
				var x := r.position.x
				var tick := float(d.get("tick", 2.0))
				for i in cells.size():
					var cw := unit * (float(cells[i]) + 1.2)
					var epoch := int(floor(_now / tick + i * 0.37)) if tick > 0.0 else 0
					var round := "left" if i == 0 else ("right" if i == cells.size() - 1 else "none")
					SkinDraw.fill(ci, SkinDraw.pill(Rect2(x, r.position.y, cw, r.size.y), round), Color(_sc(str(cols[i % cols.size()])), col.a))
					_text(ci, SkinDraw.readout_value(int(d.get("seed", 1)), i, epoch, int(cells[i])),
						Vector2(x + cw - 4.0 - (r.size.y / 3.0 if i == cells.size() - 1 else 0.0), r.get_center().y + 1), int(r.size.y * 0.78), COND,
						Color(_sc(str(d.get("text_colour", "ink"))), col.a), "right", 0, cw - 6.0)
					x += cw + gap


# ------------------------------------------------------------------ the chrome
func _draw_background(ci: CanvasItem) -> void:
	var bg := _tex("bg") if background else null
	if bg:
		ci.draw_texture_rect(bg, Rect2(0, 0, W, H), false)
		ci.draw_rect(Rect2(0, 0, W, H), Color(SHADE.darkened(0.6), 0.2))
		return
	if _lc():   # no picture: deep space, not Armadillo's dusk
		ci.draw_rect(Rect2(0, 0, W, H), Color.BLACK)
		for i in 6:
			ci.draw_circle(Vector2(640, 324), 900.0 - i * 140.0, Color(_sc("glass").lerp(Color.WHITE, 0.05), 0.22))
		return
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
		if _lc():
			_lcars_meter(ci, id, r, pick.get("lit", "") == id and int(_now * 6) % 2 == 1)
			continue
		_rr(ci, r, 18, SHADE)
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
	if _lc():
		_lcars_frame(ci)
		return
	_wood(ci, Rect2(REEL_X - 22, REEL_Y - 18, REEL_W + 44, REEL_H + 36), 18)
	# Each reel shades dark at its edges to light down the middle, as the mockup's canvas gradient does.
	var reel_bg: Array = {"wood": [Color("1c0e07"), Color("2e190d")], "metal": [Color("0d0f13"), Color("1d2128")]}.get(frame_style, [Color("05040f"), Color("100c26")])
	for r in 5:
		var x := REEL_X + r * CELL_W
		_hgrad(ci, Rect2(x, REEL_Y, CELL_W / 2.0, REEL_H), reel_bg[0], reel_bg[1])
		_hgrad(ci, Rect2(x + CELL_W / 2.0, REEL_Y, CELL_W / 2.0, REEL_H), reel_bg[1], reel_bg[0])
	for p in [Vector2(REEL_X - 10, REEL_Y - 6), Vector2(REEL_X + REEL_W + 10, REEL_Y - 6), Vector2(REEL_X - 10, REEL_Y + REEL_H + 6), Vector2(REEL_X + REEL_W + 10, REEL_Y + REEL_H + 6)]:
		ci.draw_circle(p, 4.5, Color("e3b45a") if frame_style == "wood" else frame_colour)


func _draw_sides(ci: CanvasItem) -> void:
	_wood(ci, Rect2(18, REEL_Y - 18, 224, REEL_H + 36), 16)
	var lc := _lc()
	var cx := 134.0 if lc else 130.0
	_text(ci, _t("features", "RANDOM FEATURES"), Vector2(cx, REEL_Y + 8), 19, RYE if lc else COND, _sc(_part("panel").get("title", "hl")) if lc else GOLD_HI, "center", 0, 196)
	for i in feature_rows.size():
		var id: String = feature_rows[i][0]
		var y := REEL_Y + 32 + i * 52
		var lit: bool = feature_lit.get(id, false)
		var label: String = "%s ×%d" % [feature_rows[i][1], multiplier] if id == "multiplier" and multiplier > 1 else feature_rows[i][1]
		if lc:
			_lcars_box(ci, Rect2(36, y, 196, 42), _sc("hl") if lit else Color.TRANSPARENT, 1.0)
		else:
			_rr(ci, Rect2(34, y, 192, 42), 10, Color(WIN_COL.lerp(GOLD_HI, 0.5 + 0.5 * sin(_now * 8.0)), 0.95) if lit else deck.inset, 2, GOLD_HI if lit else deck.box_edge)
		_text(ci, label, Vector2(cx, y + 22), 20, COND, INK if lit else (_sc(_part("box").get("label", "c")) if lc else MUTED), "center", 0, 180 if lc else 176)
	_button(ci, "settings", Rect2(36 if lc else 34, REEL_Y + 32 + 7 * 52 + 4, 196 if lc else 192, 36), _t("settings", "SETTINGS"), false, false, 18)
	_wood(ci, Rect2(1038, REEL_Y - 18, 224, REEL_H + 36), 16)
	var busy := _running or not pick.is_empty() or not free.is_empty()
	var by := REEL_Y + 6
	var buy := Rect2(1048, by, 200, 178) if lc else Rect2(1052, by, 196, 178)
	var hov := _hover == "buy" and not busy
	if lc:
		_glass(ci, SkinDraw.rounded(buy, 18), "glass", _sc("hl" if hov else "warn"), 3.0 if hov else 2.0)
	else:
		_rr(ci, buy, 14, deck.buy_hover if hov else deck.buy, 4 if hov else 3, GOLD)
	var a := 0.45 if busy or not _can_buy() else 1.0
	_text(ci, _t("buy", "BUY BONUS"), Vector2(1150, by + 24), 26, RYE if lc else COND, Color(_sc("warn") if lc else GOLD_HI, a), "center", 0, 180)
	var bs := _buy_icon()
	if bs:
		ci.draw_texture_rect(bs, Rect2(1098, by + 38, 104, 104), false, Color(1, 1, 1, a))
	_text(ci, Money.format(_bet() * int(rules.get("buy_cost", 45))), Vector2(1150, by + 156), 26, COND, Color(1, 1, 1, a), "center", 0, 180)
	if not busy and _can_buy():
		_add_hit("buy", buy)
	var info := []
	for s in ["BS", "FS"]:
		if not _routes(s).is_empty():
			info.append([s, texts.bonus_line if s == "BS" else texts.free_line, "A RANDOM BONUS" if _routes(s).size() > 1 else _plays(_routes(s))])
	for i in info.size():
		# Each box: the symbol on the left, its two lines centred in the space to its right.
		var box := Rect2(SIDE_INFO.position + Vector2(0, by + 196 + i * 116), SIDE_INFO.size)
		if lc:
			_lcars_box(ci, Rect2(1048, box.position.y, 200, box.size.y), Color.TRANSPARENT, 1.0)
		else:
			_rr(ci, box, 12, deck.inset)
		var icon := Rect2(box.position + Vector2(4, 24), Vector2(56, 56)) if lc else Rect2(box.position + Vector2(6, 14), Vector2(76, 76))   # (LCARS: room for a wide font)
		var t := _tex(info[i][0])
		if t:
			ci.draw_texture_rect(t, icon, false)
		var text_x := icon.end.x + 4.0
		var text_w := box.end.x - 8.0 - text_x
		var mid := text_x + text_w / 2.0
		_text(ci, info[i][1], Vector2(mid, box.position.y + 40), 17 if lc else 22, RYE if lc else COND, _sc("hl") if lc else GOLD_HI, "center", 0, text_w)
		_text(ci, info[i][2], Vector2(mid, box.position.y + 66), 14 if lc else 16, COND, CREAM, "center", 0, text_w)


func _draw_deck(ci: CanvasItem) -> void:
	var lc := _lc()
	if lc:
		_lcars_deck(ci)
	else:
		ci.draw_rect(Rect2(0, DECK_TOP, W, H - DECK_TOP), deck.band)
		ci.draw_rect(Rect2(0, DECK_TOP, W, 2), EDGE)
	_text(ci, message, Vector2(560, DECK_TOP + 15), 19, COND, GOLD_HI, "center", 0, 1000)
	var top := DECK_ROW.position.y
	var h := DECK_ROW.size.y
	var credit := Session.shown_balance + _credit_adj
	_deck_box(ci, Rect2(20, top, 210, h), _t("credit", "CREDIT"), Money.format(credit), Color.WHITE)
	_deck_box(ci, Rect2(242, top, 230, h), _t("bet", "BET"), Money.format(_bet()), Color.WHITE, 112)
	var idle := not _running and pick.is_empty() and trail.is_empty() and battle.is_empty() and voyage.is_empty() and free.is_empty()
	_button(ci, "bet-", Rect2(252, top + 36, 40, 38), "−", false, not idle or _bet_idx == 0, 30)
	_button(ci, "bet+", Rect2(422, top + 36, 40, 38), "+", false, not idle or _bet_idx == _ladder.size() - 1, 30)
	_deck_box(ci, Rect2(484, top, 230, h), "FREE GAMES WIN" if not free.is_empty() else _t("win", "WIN"),
		Money.format(int(win_shown)) if win_shown > 0 else "", WIN_COL)
	var by := top + (h - 56.0) / 2.0
	_button(ci, "info", Rect2(728, by, 92, 56), _t("info", "INFO"), false, not idle)
	_button(ci, "turbo", Rect2(828, by, 92, 56), _t("turbo", "TURBO"), turbo)
	_button(ci, "auto", Rect2(928, by, 92, 56), "STOP %d" % auto if auto > 0 else _t("auto", "AUTO"), auto > 0 or auto_menu, not idle and auto == 0)
	var c := SPIN_CENTRE
	var spinning := reels.any(func(x): return x.spinning or x.stopping)
	var hov := _hover == "spin"
	var label := _t("stop", "STOP") if spinning else (_t("fire", "FIRE") if not trail.is_empty() or not battle.is_empty() else (_t("sail", "SAIL") if not voyage.is_empty() else _t("spin", "SPIN")))
	if lc:
		_add_hit("spin", _lcars_spin(ci, label, spinning, hov))
		_button(ci, "cashout", Rect2(1172, by, 96, 56), _t("cashout", "CASH OUT"), false, false, 18)
		if auto_menu:
			for n in 4:
				_button(ci, "auto%d" % [10, 25, 50, 100][n], Rect2(924, top - 50 - n * 46, 100, 40), "%d SPINS" % [10, 25, 50, 100][n], false, false, 20, [GOLD_HI, SPIN_COL.darkened(0.4)])
		return
	ci.draw_circle(c, SPIN_R + 4.0, deck.ring)
	ci.draw_circle(c, SPIN_R, SPIN_COL.darkened(0.18) if spinning else SPIN_COL)
	ci.draw_circle(c + Vector2(-10, -14), SPIN_R * 0.45, Color(GOLD_HI, 0.45))
	ci.draw_arc(c, SPIN_R, 0, TAU, 64, GOLD_HI, 5 if hov else 3, true)
	_text(ci, label, c + Vector2(0, 2), 28, COND, INK, "center", 0, SPIN_R * 1.6)
	_add_hit("spin", Rect2(c - Vector2(SPIN_R, SPIN_R), Vector2(SPIN_R, SPIN_R) * 2.0))
	_button(ci, "cashout", Rect2(1172, by, 96, 56), _t("cashout", "CASH OUT"), false, false, 18)
	if auto_menu:
		var n := 0
		for count in [10, 25, 50, 100]:
			_button(ci, "auto%d" % count, Rect2(924, top - 50 - n * 46, 100, 40), "%d SPINS" % count, false, false, 20, [GOLD_HI, SPIN_COL.darkened(0.4)])
			n += 1


## A deck readout. `value_w` narrows the value (the bet sits between its − and + buttons).
func _deck_box(ci: CanvasItem, r: Rect2, label: String, value: String, col: Color, value_w := 0.0) -> void:
	if _lc():
		_lcars_box(ci, r)
		_text(ci, label, Vector2(r.get_center().x, r.position.y + 16), 16, RYE, _sc(_part("box").get("label", "c")), "center", 0, r.size.x - 40)
		_text(ci, value, Vector2(r.get_center().x, r.position.y + r.size.y - 26), 34, COND, _sc(_part("box").get("value", "goldHi")) if col == Color.WHITE else col,
			"center", 0, value_w if value_w > 0.0 else r.size.x - 50)
		return
	_rr(ci, r, 12, deck.box, 2, deck.box_edge)
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
			ci.draw_rect(Rect2(x.r * CELL_W + 4, 4, CELL_W - 8, REEL_H - 8), Color(WIN_COL, x.glow * (0.6 + 0.4 * sin(_now * 12.0))), false, 8)


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
	ci.draw_rect(Rect2(int(col.start) * CELL_W, 0, wpx, REEL_H), Color(SHADE.lerp(EDGE, 0.15), 0.6))
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
		ci.draw_rect(Rect2(int(col.start) * CELL_W, 0, wpx, REEL_H), Color(SHADE.lerp(EDGE, 0.15), 0.6))
		for b in range(0, ceili(4.0 / k) + 1):
			var cells := _block_cells(b)
			if cells.is_empty():
				continue
			var now_sym: String = grid[cells[0]]
			if cells.all(func(c): return grid[c] == now_sym):
				var fx: Dictionary = cell_fx.get(cells[0], {}) if cell_fx.get(cells[0], {}).get("big", false) else {}
				_sym(ci, now_sym, Rect2(int(col.start) * CELL_W + (wpx - size * 1.05) / 2.0, (b * k - int(col.offset)) * CELL_H, size * 1.05, size), fx)
	var winning := {}
	if landed and not wins.is_empty() and not win_anims.is_empty():
		for w in (wins if (_running or cycle == 0) else [wins[cycle - 1]]):
			for q in w.cells:
				winning[int(q)] = true
	for c in 20:
		var r := floori(c / 4.0)
		if not col.is_empty() and r >= int(col.start) and r < int(col.start) + int(col.k):
			var cells := _block_cells(floori(float(c % 4 + int(col.offset)) / int(col.k)))
			if cells.all(func(q): return grid[q] == grid[cells[0]]):
				continue
		var fx: Dictionary = cell_fx.get(c, {})
		if winning.has(c):
			fx = fx.duplicate()
			fx["anim"] = win_anims.get(_group(str(grid[c])), {})
		_sym(ci, str(grid[c]), Rect2(r * CELL_W, (c % 4) * CELL_H, CELL_W, CELL_H), fx)


## A tier's group for its win animation: wild, scatter, high, mid or low.
static func _group(sym: String) -> String:
	if sym == "W":
		return "wild"
	if sym in ["BS", "FS"]:
		return "scatter"
	return {"H": "high", "M": "mid"}.get(sym.left(1), "low")


## Over the reels (unclipped): dividers and the glass.
func _draw_reel_overlay(ci: CanvasItem) -> void:
	for r in range(1, 5):
		if not colossal.is_empty() and r > int(colossal.start) and r < int(colossal.start) + int(colossal.k):
			continue
		ci.draw_rect(Rect2(REEL_X + r * CELL_W - 1, REEL_Y, 2, REEL_H), Color(EDGE, 0.55))
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
		ci.draw_polyline(pts, Color(SHADE, 0.7), 9, true)
		ci.draw_polyline(pts, colr, 5, true)
		for c in w.cells:
			var r := _cell_rect(int(c)).grow(-6)
			_rr(ci, r, 10, Color(colr, 0.12), 4, colr)
		if lines.size() == 1:
			var last := _cell_rect(int(w.cells[w.cells.size() - 1]))
			_rr(ci, Rect2(last.end.x - 92, last.position.y + 6, 86, 30), 8, Color(SHADE, 0.85))
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
	_loop("spin", "reel_spin")
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
		_sfx("feature_banner")
		if p[0] == "multiplier":
			_sfx("feature_multiplier")
		elif p[0] == "colossal":
			_sfx("feature_reels")
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
			_loop("tease", "reel_tease")
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
					_sfx("scatter_land", 1.0 + 0.12 * (int(seen[s]) - 1))   # the second and third ring higher
		if ep != _epoch:
			return
		_sfx("reel_stop", 1.0 + 0.03 * r)
		x.glow = 0.0
		if not _hurry:
			await _wait(0.12)
		r += 1
	_unloop("tease")
	_unloop("spin", 0.25)
	grid = (o.after_colossal as Array).duplicate()
	landed = true
	_hurry = false
	# Wild Reels: the armadillo rolls down each one.
	for wr in o.wild_reels:
		var f := _flyer({"img": "armadillo", "x": REEL_X + int(wr) * CELL_W + CELL_W / 2.0, "y": REEL_Y - 40, "size": 130, "rot": 0.0})
		_tw(f, {"y": REEL_Y + REEL_H + 40, "rot": PI * 6}, 0.9, "inout")
		_sfx("feature_reels")
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
		_sfx("feature_wilds")
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
		_sfx("feature_upgrade")
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
		_sfx("win_small")
		message = ("LINE WINS %s (×%d)" % [Money.format(int(o.line_win)), multiplier]) if multiplier > 1 else "LINE WINS %s" % Money.format(int(o.line_win))
		await _wait(1.1)
		if int(o.repeat) > 0:
			feature_lit.repeat = true
			for k in range(2, int(o.repeat) + 1):
				await _banner("REPEAT WIN", "pays again: %d of %d" % [k, int(o.repeat)], 1.0)
				win_target += float(o.line_win)
				_sfx("win_repeat")
				for w in wins:
					for c in w.cells:
						cell_fx[int(c)] = {"scale": 1.15, "glow": 1.0}
						_tw(cell_fx[int(c)], {"scale": 1.0, "glow": 0.0}, 0.6)
				await _wait(0.5)
	if int(o.instant) > 0:
		feature_lit.instant = true
		var f := _flyer({"img": "barrel", "x": 640, "y": REEL_Y + REEL_H / 2.0, "size": 220, "s": 0.2})
		await _tw(f, {"s": 1.0}, 0.45, "back")
		_sfx("instant_win")
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
	_unloop("meter")   # caught up all at once: no "counted" ding over what comes next
	win_shown = win_target


func _start_reel(x: Dictionary, v: float, i: int) -> void:
	x.stopping = false
	var ep := _epoch
	await get_tree().create_timer(i * 0.04).timeout
	if ep != _epoch:
		return   # reset before this reel got going: leave it at rest
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
	var ep := _epoch
	await _tw(x, {"pos": target - 0.18}, 0.12 if _hurry else 0.34)
	await _tw(x, {"pos": target}, 0.14)
	if ep != _epoch:
		return
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
	_rr(ci, Rect2(-420, -66, 840, h), 22, Color(SHADE, 0.88 * a), 4, Color(GOLD, a))
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
			ci.draw_circle(Vector2.ZERO, 60, Color(SPIN_COL, 0.35 * float(f.a)))
			ci.draw_circle(Vector2.ZERO, 30, Color(GOLD_HI, 0.8 * float(f.a)))
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
		ci.draw_circle(Vector2.ZERO, float(p.r), GOLD_LO)
		ci.draw_circle(Vector2.ZERO, float(p.r) - 2.0, GOLD if sx > 0 else GOLD.lerp(GOLD_LO, 0.3))
		ci.draw_circle(Vector2(-float(p.r) * 0.3, -float(p.r) * 0.3), float(p.r) * 0.35, Color(GOLD_HI, 0.8))
		ci.draw_set_transform(Vector2.ZERO)


func _big_win(total: int, bet: int) -> void:
	var x := float(total) / float(bet)
	var title := "EPIC WIN" if x >= 50 else ("MEGA WIN" if x >= 25 else "BIG WIN")
	overlay = {"kind": "bigwin", "title": title, "shown": 0.0, "t0": _now, "done": false}
	_sfx("big_win")
	_loop("bigwin", "big_win_loop")
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
		if not ov.done and _now > float(ov.t0) + count:
			_unloop("bigwin", 0.6)   # counted: the coins stop while the total stays up
		await get_tree().process_frame
	_unloop("bigwin", 0.6)
	if overlay == ov:
		overlay = {}


func _summary(title: String, sub: String, amount: int, sound := "bonus_end") -> void:
	overlay = {"kind": "summary", "title": title, "sub": sub, "amount": amount, "t0": _now, "done": false}
	if sound != "":
		_sfx(sound)
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
	ci.draw_rect(Rect2(0, 0, W, H), Color(SHADE.darkened(0.6), 0.72))
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
			_text(ci, Money.format(int(overlay.amount)), Vector2(640, 372), 76, COND, WIN_COL, "center", 8, 560)
			_button(ci, "overlay", Rect2(560, 430, 160, 50), _t("collect", "COLLECT"), false, false, 22, [GOLD_HI, SPIN_COL.darkened(0.4)])
			_text(ci, "collects itself in %d" % maxi(1, ceili(5.0 - (_now - float(overlay.t0)))), Vector2(640, 496), 16, COND, MUTED)
		"buy":
			_wood(ci, Rect2(360, 170, 560, 340), 22)
			_gold_text(ci, "BUY BONUS", Vector2(640, 228), 50, 520)
			var bs := _buy_icon()
			if bs:
				ci.draw_texture_rect(bs, Rect2(580, 256, 120, 120), false)
			var cost := _bet() * int(rules.get("buy_cost", 45))
			var buy_text: String = texts.buy_text if _routes("buy") == ["trail"] else "Go straight to %s for %%s" % _plays(_routes("buy")).to_lower()
			_text(ci, buy_text % Money.format(cost), Vector2(640, 400), 26, COND, CREAM, "center", 0, 520)
			_text(ci, texts.buy_sub % [int(rules.get("buy_cost", 45)), Money.format(_bet()), Money.format(_bet())], Vector2(640, 430), 19, COND, MUTED, "center", 0, 520)
			_button(ci, "buy-yes", Rect2(470, 450, 160, 48), "BUY", false, Session.shown_balance + _credit_adj < cost, 22, [GOLD_HI, SPIN_COL.darkened(0.4)])
			_button(ci, "buy-no", Rect2(650, 450, 160, 48), "CANCEL")
		"cashout":
			_wood(ci, Rect2(390, 220, 500, 250), 20)
			_gold_text(ci, "CASH OUT?", Vector2(640, 270), 44, 460)
			_text(ci, "Your bonus is played out for you and paid.", Vector2(640, 330), 24, COND, CREAM, "center", 0, 460)
			_button(ci, "cash-yes", Rect2(470, 380, 160, 48), "STAND UP", false, false, 22, [GOLD_HI, SPIN_COL.darkened(0.4)])
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
	# rows: the Wild and the high pays, the mids, the lows (Armadillo: 3, 4 and 4), as many columns as each needs
	var rows := [[], [], []]
	for sym in pays:
		rows[0 if (sym == "W" or sym.begins_with("H")) else (1 if sym.begins_with("M") else 2)].append(sym)
	for row in 3:
		var n: int = rows[row].size()
		var cw := minf(280.0, 1120.0 / maxi(1, n))
		var sz := minf(104.0, cw - 130.0)
		for colx in n:
			var sym: String = rows[row][colx]
			var x0 := 640.0 - (n * cw) / 2.0 + colx * cw
			var y := 118.0 + row * 128.0
			var tex := _tex(sym)
			if tex:
				ci.draw_texture_rect(tex, Rect2(x0 + 10, y + 4 + (104.0 - sz) / 2.0, sz, sz), false)
			var p: Array = pays.get(sym, [0, 0, 0])
			for j in 3:
				var k := 5 - j
				_text(ci, "%d" % k, Vector2(x0 + sz + 32, y + 30 + j * 26), 20, COND, SPIN_COL, "left")
				_text(ci, Money.format(int(float(p[k - 3]) * lb)), Vector2(x0 + sz + 56, y + 30 + j * 26), 22, COND, CREAM, "left")
	for i in tips.size():
		_text(ci, str(tips[i]), Vector2(640, 528 + i * 28), 19, COND, GOLD_HI if i == tips.size() - 1 else CREAM, "center", 0, 1140)
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
	_sfx("pick_reveal", 1.0 + 0.1 * int(pick.tally.get(tier, 0)))   # a second of a kind rings higher
	var ep := _epoch
	await _tw(coin, {"flip": 0.5}, 0.16, "lin")
	coin.tier = tier
	await _tw(coin, {"flip": 1.0}, 0.16, "lin")
	if ep != _epoch:
		return
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
	_sfx("jackpot_win")
	var ep := _epoch
	await _wait(1.0)
	if ep != _epoch:
		return
	var all: Array = ev.get("coins", [])
	for i in pick.coins.size():
		var c: Dictionary = pick.coins[i]
		if c.tier == "" and i < all.size():
			c.tier = str(all[i])
			c.dim = true
			c.flip = 1.0
	await _wait(0.8)
	if ep != _epoch:
		return
	_coin_rain(90)
	_credit_adj += int(ev.amount)
	await _summary("%s JACKPOT" % TIER_NAMES.get(tier, tier.to_upper()), "shared by every slot on the floor", int(ev.amount), "")
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
			ci.draw_circle(Vector2.ZERO, r, Color(SHADE, a))
			ci.draw_circle(Vector2.ZERO, r - 4, Color(TIERS.get(c.tier, GOLD), a))
			ci.draw_circle(Vector2(-r * 0.3, -r * 0.3), r * 0.35, Color(1, 1, 1, 0.35 * a))
			_text(ci, TIER_NAMES.get(c.tier, c.tier), Vector2(0, 2), 26, COND, Color(1, 1, 1, a), "center", 5)
		else:
			ci.draw_circle(Vector2.ZERO, r, GOLD_LO.darkened(0.4))
			ci.draw_circle(Vector2.ZERO, r - 4, GOLD.lerp(GOLD_HI, 0.4) if hover else GOLD)
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
	var ep := _epoch
	tr.bullets = 0
	_sfx("trail_fire")
	for i in int(roll.bullets):
		tr.bullets = i + 1
		await _wait(0.09)
	await _tw(tr, {"cyl": float(tr.cyl) + TAU * (2.0 + int(roll.bullets) / 6.0)}, 0.6)
	if ep != _epoch:
		return
	var label := "%d" % int(roll.bullets)
	if int(roll.move) != int(roll.bullets):
		label = "%d × 2 = %d" % [int(roll.bullets), int(roll.move)]
	var f := _flyer({"text": label, "x": 1150, "y": 250, "text_size": 64, "s": 0.3})
	_tw(f, {"s": 1.0}, 0.25, "back")
	var evs: Array = (roll.events as Array).duplicate()
	while not evs.is_empty() and int(evs[0].pos) == int(roll.from) and ep == _epoch:
		await _trail_event(evs.pop_front())
	var at := int(roll.from)
	for p in roll.path:
		if ep != _epoch:
			return
		await _move_token(int(p), "slide" if absi(int(p) - at) > 1 else "hop")
		at = int(p)
		while not evs.is_empty() and int(evs[0].pos) == at and ep == _epoch:
			await _trail_event(evs.pop_front())
	while not evs.is_empty() and ep == _epoch:
		await _trail_event(evs.pop_front())
	f.dead = true
	tr.bullets = 0


func _move_token(i: int, how: String) -> void:
	var tk: Dictionary = trail.token
	var p := _trail_pos(i)
	var ep := _epoch
	if how == "hop":
		tk.hop = 0.0
		_sfx("trail_hop")
		_tw(tk, {"hop": 1.0}, 0.2, "lin")
		await _tw(tk, {"x": p.x, "y": p.y}, 0.2, "lin")
		tk.sq = 0.7
		_tw(tk, {"sq": 1.0}, 0.15, "back")
	else:
		await _tw(tk, {"x": p.x, "y": p.y}, 0.5, "inout")
	if ep != _epoch:
		return
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
			_pop("%s" % Money.format(int(e.pence)), WIN_COL, sx, sy)
			if e.kind == "coin" and int(e.pos) < board.size():
				board[int(e.pos)].taken = true
			_sfx("trail_coin")
			_coin_burst(sx, sy - 30, 80 if e.kind == "prizepot" else 12, 0.6)
			tr.total = int(tr.total) + int(e.pence)
			win_target = float(tr.total)
			roller = maxf(float(e.pence) * 1.4, float(_bet()))
			await _wait(1.6 if e.kind == "prizepot" else 0.55)
		"heart":
			_pop("+1 HEART", Color("ff8a80"), sx, sy)
			_sfx("trail_heart")
			board[int(e.pos)].taken = true
			tr.hearts = int(tr.hearts) + 1
			await _wait(0.6)
		"heart_used":
			_pop("SAVED BY A HEART", Color("ff8a80"), sx, sy)
			tr.snake = {"pos": int(e.pos), "t0": _now}
			shake = 0.6
			tr.hearts = int(tr.hearts) - 1
			_sfx("trail_snake")
			_after_sfx(0.45, "trail_heart")
			await _wait(0.9)
		"snake":
			_pop("SNAKE BITE!", Color("ff5a48"), sx, sy)
			tr.snake = {"pos": int(e.pos), "t0": _now}
			shake = 1.0
			_sfx("trail_snake")
			await _wait(1.2)
		"double":
			_pop("DOUBLE! ALL COINS ×2", Color("ffb347"), sx, sy)
			_sfx("trail_special")
			tr.doubled = true
			tr.double_at = _now
			for sp in board:
				if (sp.type == "coin" and not sp.get("taken", false)) or sp.type == "prizepot":
					sp.x = int(sp.x) * 2
			await _wait(1.1)
		"upgrade":
			_pop("SPIN UPGRADE: MOVES ×2", Color("7affd9"), sx, sy)
			_sfx("trail_special")
			tr.upgraded = true
			await _wait(1.0)
		"lightning":
			_pop("LIGHTNING ROLL NEXT", Color("ffe14a"), sx, sy)
			_sfx("trail_special")
			await _wait(0.9)
		"lightning_roll":
			_pop("LIGHTNING ROLL!", Color("ffe14a"), sx, sy)
			_sfx("trail_special")
			tr.lightning_at = _now
			await _wait(0.6)
		"crate":
			_pop("CRATE: COINS WITHIN %d" % int(e.r), Color("ffb347"), sx, sy)
			_sfx("trail_special")
			tr.crate = {"pos": int(e.pos), "r": int(e.r), "t0": _now}
			for j in range(maxi(1, int(e.pos) - int(e.r)), mini(board.size() - 1, int(e.pos) + int(e.r) + 1)):
				if board[j].type == "coin":
					board[j].taken = true
			if int(e.pence) > 0:
				tr.total = int(tr.total) + int(e.pence)
				win_target = float(tr.total)
				roller = maxf(float(e.pence), float(_bet()))
				_coin_burst(sx, sy - 30, 24, 0.8)
				_sfx("trail_coin")
			await _wait(1.0)
		"forward":
			_pop("FORWARD %d" % int(e.n), Color("9cff6b"), sx, sy)
			_sfx("trail_special")
			await _wait(0.6)
		"back":
			_pop("BACK %d" % int(e.n), Color("ff9e4a"), sx, sy)
			_sfx("trail_special")
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
	_rr(ci, Rect2(18, REEL_Y - 18, 1010, REEL_H + 36), 18, Color(SHADE.lerp(EDGE, 0.1), 0.35))
	# the road, in the design's edge colour
	var road := EDGE.lerp(CREAM, 0.2)
	var pts := PackedVector2Array()
	var lo := maxi(0, floori((cam - 100.0) / TILE))
	var hi := mini(board.size() - 1, ceili((cam + 1100.0) / TILE))
	for i in range(maxi(0, lo - 1), mini(board.size(), hi + 2)):
		var p := _trail_pos(i)
		pts.append(Vector2(p.x - cam, p.y))
	if pts.size() > 1:
		ci.draw_polyline(pts, Color(SHADE.lerp(EDGE, 0.15), 0.55), 64, true)
		ci.draw_polyline(pts, road.darkened(0.08), 50, true)
		ci.draw_polyline(pts, road, 44, true)
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
		var fill := ALERT.darkened(0.25) if sp.type == "snake" else (GOLD_LO.darkened(0.42) if end else SHADE.lerp(EDGE, 0.2))
		_rr(ci, Rect2(x - sz / 2.0, p.y - sz / 2.0, sz, sz), 12, Color(fill, a), 4 if (crate or light) else 2,
			Color("ffb347") if crate else (Color("ffe14a") if light else Color(EDGE, a)))
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
	_rr(ci, Rect2(40, REEL_Y - 8, 900, 18), 9, Color(SHADE, 0.8))
	if prog > 0.0:
		_rr(ci, Rect2(40, REEL_Y - 8, maxf(18.0, 900 * prog), 18), 9, EDGE.lerp(CREAM, 0.2))
	var gold := _tex("t_gold")
	if gold:
		ci.draw_texture_rect(gold, Rect2(930, REEL_Y - 28, 50, 50), false)
	var arm := _tex("armadillo")
	if arm:
		ci.draw_texture_rect(arm, Rect2(40 + 900 * prog - 20, REEL_Y - 34, 44, 44), false)
	_text(ci, "TRAIL WIN %s" % Money.format(int(tr.total)), Vector2(520, REEL_Y + 34), 34, COND, WIN_COL, "center", 6, 400)
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
		_rr(ci, Rect2(cx, REEL_Y + 24, 150, 32), 8, ALERT)
		_text(ci, "COINS DOUBLED", Vector2(cx + 75, REEL_Y + 41), 20, COND, Color.WHITE)
	_wood(ci, Rect2(1038, REEL_Y - 18, 224, REEL_H + 36), 16)
	_text(ci, texts.launcher, Vector2(1150, REEL_Y + 10), 22, COND, GOLD_HI, "center", 0, 196)
	_text(ci, texts.launcher_up if tr.upgraded else texts.launcher_hint, Vector2(1150, REEL_Y + 34), 16, COND, CREAM, "center", 0, 196)
	var cyc := Vector2(1150, REEL_Y + 150)
	var cyl := _tex("cylinder")
	ci.draw_set_transform(cyc, float(tr.cyl), Vector2.ONE)
	if cyl:
		ci.draw_texture_rect(cyl, Rect2(-78, -78, 156, 156), false)
	for k in int(tr.bullets):
		var ang := -PI / 2.0 + k * PI / 3.0
		ci.draw_circle(Vector2(cos(ang), sin(ang)) * 35.0, 13, GOLD.lerp(GOLD_LO, 0.5))
		ci.draw_circle(Vector2(cos(ang), sin(ang)) * 35.0 + Vector2(-3, -3), 6, GOLD_HI)
	ci.draw_set_transform(Vector2.ZERO)
	if tr.waiting:
		_button(ci, "fire", Rect2(cyc.x - 80, cyc.y + 100, 160, 58), "FIRE", false, false, 32, _fire_colours())
		var left := maxf(0.0, float(tr.auto_at) - _now)
		_text(ci, "fires itself in %d" % ceili(left), Vector2(cyc.x, cyc.y + 176), 16, COND, MUTED)


# ------------------------------------------------------------------ the wave battle (Red Alert)
# Your ship on the left; each wave's ships in a loose formation on the right, drifting and cloaking now and then (for
# show: a cloaked ship can't be tapped, and the server's draw is the same whichever ship is shot). It fills the
# trail's area, with its panel on the right. The wizard's mockup (game.js drawBattle) is the same scene; the timings
# match bonuses.py _BATTLE_SECONDS.
const B_AREA := Rect2(18, REEL_Y - 18, 1010, REEL_H + 36)
const HERO := Vector2(200, 352)
const BOSS_AT := Vector2(760, 385)
var _stars: Array = []


func _ship_spot(i: int, n: int) -> Vector2:
	var rows := n if n <= 2 else (2 if n <= 6 else 3)
	var cols := ceili(float(n) / rows)
	var r := i % rows
	var c := floori(float(i) / rows)
	var dx := 380.0 / (cols - 1) if cols > 1 else 0.0
	var stagger := minf(60.0, dx * 0.3) if r % 2 == 1 else 0.0   # stays clear of the panel
	var x := (510.0 + c * dx if cols > 1 else 730.0) + stagger
	return Vector2(x, 240.0 + r * (275.0 / (rows - 1)) if rows > 1 else 378.0)


func _battle_ships(n: int, born: float) -> Array:
	var out := []
	for i in n:
		var p := _ship_spot(i, n)
		out.append({"i": i, "x": p.x, "y": p.y, "phase": fmod(i * 0.618 + randf() * 0.2, 1.0), "born": born, "dead": 0.0, "evade": 0.0})
	return out


func _begin_battle(b: Dictionary) -> void:
	if _stars.is_empty():
		for i in 140:
			_stars.append(Vector4(randf() * B_AREA.size.x, randf() * B_AREA.size.y, 0.6 + randf() * 1.8, 6.0 + randf() * 40.0))
	var ships := _battle_ships((b.ships as Array).size(), _now)
	for sh in ships:
		if not b.ships[sh.i]:
			sh.dead = -10.0   # already destroyed (a resync mid-wave)
	battle = {"bet": int(b.bet), "wave": int(b.wave), "waves": int(b.waves), "max_shields": int(b.max_shields), "shields": int(b.shields),
		"ships": ships, "boss": {}, "total": int(b.total), "spins": int(b.spins), "cleared": int(b.cleared), "won": false,
		"waiting": false, "auto_at": 1e9, "aim": -1, "forced": -1, "alive": ships.size(), "beam": {}, "bolts": [], "booms": [],
		"shield_at": -10.0, "restore_at": -10.0, "hero_down": false, "alert_at": _now}
	if b.get("boss_hp") != null:
		battle.boss = {"hp": int(b.boss_hp), "max": int(b.boss_max), "t0": _now - 2.0, "hit_at": -10.0, "dead": 0.0}
	_clear_wins()


func _battle_ready() -> void:
	battle.waiting = true
	battle.auto_at = _now + 8.0
	message = ("FIRE ON THE %s  ·  SPACE OR CLICK FIRE" % texts.boss) if not battle.boss.is_empty() else "TAP A SHIP TO FIRE  ·  SPACE FIRES AT ONE"


func _ship_pos(sh: Dictionary) -> Vector2:
	var warp := maxf(0.0, 1.0 - (_now - float(sh.born)) / 0.6) * 300.0
	return Vector2(float(sh.x) + cos(_now * 0.9 + sh.i * 1.3) * 7.0 + warp, float(sh.y) + sin(_now * 1.3 + sh.i * 1.7) * 9.0)


## How cloaked a ship is (0..1): a 9-second cycle, cloaked about a fifth of it; never while it's shot, never the last
## two, never all at once (one is kept in sight); and it cloaks when it answers a shot.
func _raw_cloak(sh: Dictionary) -> float:
	if float(sh.evade) > 0.0 and _now - float(sh.evade) < 1.2:
		return sin(minf(1.0, (_now - float(sh.evade)) / 1.2) * PI)
	if int(battle.alive) < 3:
		return 0.0
	var f := fmod(_now / 9.0 + float(sh.phase), 1.0)
	if f < 0.72:
		return 0.0
	if f < 0.76:
		return (f - 0.72) / 0.04
	if f < 0.9:
		return 1.0
	if f < 0.94:
		return 1.0 - (f - 0.9) / 0.04
	return 0.0


func _cloak(sh: Dictionary) -> float:
	if int(battle.aim) == int(sh.i) or int(battle.forced) == int(sh.i):
		return 0.0
	return _raw_cloak(sh)


func _targetable() -> Array:
	return (battle.ships as Array).filter(func(sh): return float(sh.dead) == 0.0 and _now - float(sh.born) > 0.6 and _cloak(sh) < 0.5)


func _fire_battle(target: int) -> void:
	if battle.is_empty() or not battle.get("waiting", false):
		return
	if target < 0 and battle.boss.is_empty():
		var open := _targetable()
		if open.is_empty():
			open = (battle.ships as Array).filter(func(sh): return float(sh.dead) == 0.0)
		if open.is_empty():
			return
		target = int(open[randi() % open.size()].i)
	battle.waiting = false
	Net.send("battle_fire", {"index": target if battle.boss.is_empty() else null})


func _boom(at: Vector2, size: float) -> void:
	var bits := []
	for i in 14:
		bits.append(Vector2(randf() * TAU, 0.4 + randf()))
	(battle.booms as Array).append({"at": at, "size": size, "t0": _now, "bits": bits})


func _battle_pop(txt: String, colour: Color, at: Vector2, size := 40) -> void:
	var f := _flyer({"text": txt, "x": at.x, "y": at.y - 50, "text_size": size, "colour": colour, "s": 0.4})
	await _tw(f, {"s": 1.0, "y": at.y - 95}, 0.35, "back")
	await get_tree().create_timer(0.7).timeout
	await _tw(f, {"a": 0.0}, 0.3)
	f.dead = true


func _animate_shot(shot: Dictionary) -> void:
	var b := battle
	var ep := _epoch
	var boss := str(shot.target) == "boss"
	var sh: Dictionary = {} if boss else b.ships[int(shot.target)]
	b.aim = -1 if boss else int(shot.target)
	b.beam = {"boss": boss, "ship": sh, "t0": _now}
	_sfx("battle_phaser")
	await _wait(0.6)
	for e in shot.events:
		if ep != _epoch:
			return
		var p := BOSS_AT if boss else _ship_pos(sh)
		match str(e.kind):
			"return_fire":
				if not boss:
					sh.evade = _now
				(b.bolts as Array).append({"from": p, "t0": _now})
				(b.bolts as Array).append({"from": p + Vector2(0, 14), "t0": _now + 0.12})
				await _wait(0.45)
				b.shields = int(e.shields)
				b.shield_at = _now
				shake = 0.5
				_sfx("battle_hit")
				_battle_pop("SHIELDS %d/%d" % [int(e.shields), int(b.max_shields)] if int(e.shields) > 0 else "SHIELDS FAILING",
					Color("ff6a5a"), HERO + Vector2(0, -40), 34)
				await _wait(0.55)
			"shields_down":
				b.hero_down = true
				_boom(HERO + Vector2(20, 0), 150)
				shake = 1.0
				_sfx("battle_boom")
				_battle_pop("SHIELDS DOWN", Color("ff5a48"), HERO + Vector2(60, -60), 46)
				await _wait(1.6)
			"destroyed":
				sh.dead = _now
				b.aim = -1
				_boom(p, 110)
				_sfx("battle_boom")
				if e.has("spins"):
					b.spins = int(b.spins) + int(e.spins)
					_battle_pop("+%d FREE GAME%s" % [int(e.spins), "" if int(e.spins) == 1 else "S"], Color("7fd0ff"), p)
				else:
					b.total = int(b.total) + int(e.pence)
					win_target = float(b.total)
					roller = maxf(float(e.pence) * 1.4, float(_bet()))
					_battle_pop(Money.format(int(e.pence)), WIN_COL, p)
				await _wait(0.9)
			"wave_clear":
				b.total = int(b.total) + int(e.pence)
				b.cleared = int(b.cleared) + 1
				win_target = float(b.total)
				roller = maxf(float(e.pence), float(_bet()))
				_sfx("battle_wave")
				_battle_pop("WAVE %d CLEARED  +%s" % [int(e.wave) + 1, Money.format(int(e.pence))], GOLD_HI, Vector2(523, 330), 48)
				_coin_burst(523, 330, 30, 1.0)
				await _wait(1.0)
				b.shields = int(b.max_shields)
				b.restore_at = _now
				await _wait(0.8)
			"wave_start":
				b.wave = int(e.wave)
				b.ships = _battle_ships(int(e.ships), _now + 0.3)
				_battle_pop("WAVE %d OF %d" % [int(e.wave) + 1, int(b.waves)], Color("ff8a6a"), Vector2(523, 300), 44)
				await _wait(1.6)
			"boss_start":
				b.ships = []
				b.boss = {"hp": int(e.hp), "max": int(e.hp), "t0": _now, "hit_at": -10.0, "dead": 0.0}
				b.alert_at = _now
				shake = 0.6
				_sfx("battle_alert")
				_battle_pop("%s INCOMING" % texts.boss, Color("ff5a48"), Vector2(523, 220), 52)
				await _wait(2.4)
			"boss_hit":
				b.boss.hp = int(e.hp)
				b.boss.hit_at = _now
				_boom(p + Vector2(randf_range(-60, 60), randf_range(-40, 40)), 70)
				_sfx("battle_boom")
				await _wait(0.7)
			"boss_destroyed":
				b.boss.dead = _now
				b.won = true
				_boom(p, 320)
				shake = 1.2
				_sfx("battle_boom")
				_coin_rain(80)
				b.total = int(b.total) + int(e.pence)
				win_target = float(b.total)
				roller = maxf(float(e.pence), float(_bet()))
				_battle_pop("%s DESTROYED  %s" % [texts.boss, Money.format(int(e.pence))], GOLD_HI, Vector2(523, 300), 52)
				await _wait(2.6)
	b.aim = -1


func _ellipse(ci: CanvasItem, c: Vector2, rx: float, ry: float, fill: Color, edge := Color.TRANSPARENT, width := 2.0) -> void:
	ci.draw_set_transform(c, 0, Vector2(1, ry / rx))
	if fill.a > 0.0:
		ci.draw_circle(Vector2.ZERO, rx, fill)
	if edge.a > 0.0:
		ci.draw_arc(Vector2.ZERO, rx, 0, TAU, 64, edge, width * rx / ry, true)
	ci.draw_set_transform(Vector2.ZERO)


func _draw_battle(ci: CanvasItem) -> void:
	var b := battle
	var A := B_AREA
	var alive: Array = (b.ships as Array).filter(func(sh): return float(sh.dead) == 0.0)
	b.alive = alive.size()
	var hidden := not alive.is_empty() and alive.all(func(sh): return _raw_cloak(sh) >= 0.5)
	if not hidden:
		b.forced = -1
	elif not alive.any(func(sh): return int(sh.i) == int(b.forced)):
		b.forced = int(alive[0].i)
	# deep space, a dim wash of the slot's background, and drifting stars
	_rr(ci, A, 18, Color("05071a"))
	var bg := _tex("bg") if background else null
	if bg:
		ci.draw_texture_rect(bg, A.grow(-4), false, Color(1, 1, 1, 0.22))
	for st in _stars:
		var x := A.position.x + fposmod(st.x - _now * st.w, A.size.x)
		ci.draw_rect(Rect2(x, A.position.y + st.y, st.z, st.z), Color(0.86, 0.9, 1.0, 0.35 + st.z / 3.0))
	# red alert: the edges pulse red at the start and when the boss arrives
	var alert := maxf(0.0, 1.0 - (_now - float(b.alert_at)) / 3.0)
	if alert > 0.0:
		var a := 0.45 * alert * (0.6 + 0.4 * sin(_now * 10.0))
		for k in 6:
			_rr(ci, A.grow(-k * 10.0), 18, Color.TRANSPARENT, 10, Color(1, 0.12, 0.08, a * (1.0 - k / 6.0)))
	# your ship and its shields
	var hy := HERO.y + sin(_now * 1.1) * 6.0
	var hit := maxf(0.0, 1.0 - (_now - float(b.shield_at)) / 0.6)
	var up := maxf(0.0, 1.0 - (_now - float(b.restore_at)) / 0.9)
	var strength := float(b.shields) / maxf(1.0, float(b.max_shields))
	if strength > 0.0 or hit > 0.0:
		_ellipse(ci, Vector2(HERO.x, hy), 140, 100, Color(0.35, 0.67, 1.0, 0.06 + 0.08 * strength + 0.3 * hit + 0.25 * up),
			Color(0.55, 0.82, 1.0, 0.25 + 0.4 * strength + 0.6 * hit), 2.0 + 4.0 * hit)
	var hero := _tex("b_hero")
	if hero:
		ci.draw_texture_rect(hero, Rect2(HERO.x - 120, hy - 120, 240, 240), false, Color(1, 1, 1, 0.55 if b.hero_down else 1.0))
	# the enemy ships
	var n: int = (b.ships as Array).size()
	var size := 124.0 if n <= 6 else 104.0
	var enemy := _tex("b_enemy")
	var open := {}
	if b.waiting:
		for sh in _targetable():
			open[int(sh.i)] = true
	for sh in b.ships:
		if _now < float(sh.born):
			continue
		var age := _now - float(sh.dead) if float(sh.dead) != 0.0 else 0.0
		if float(sh.dead) != 0.0 and age > 0.4:
			continue
		var p := _ship_pos(sh)
		var cl := _cloak(sh)
		var z := 1.0 - age / 0.4 if float(sh.dead) != 0.0 else 1.0
		var alpha := minf(1.0, (_now - float(sh.born)) / 0.6) * (1.0 - 0.88 * cl) * z
		if enemy:
			ci.draw_texture_rect(enemy, Rect2(p.x - size / 2.0 * z, p.y - size / 2.0 * z, size * z, size * z), false, Color(1, 1, 1, alpha))
		if cl > 0.05 and float(sh.dead) == 0.0:   # the cloak's shimmer
			_ellipse(ci, p, size * 0.5, size * 0.3, Color.TRANSPARENT, Color(0.63, 0.86, 1.0, 0.35 * sin(cl * PI)), 2.0)
		if open.has(int(sh.i)):
			var r := Rect2(p - Vector2(size, size) / 2.0, Vector2(size, size))
			_add_hit("ship%d" % int(sh.i), r)
			if _hover == "ship%d" % int(sh.i):   # the targeting reticle
				var red := Color("ff5a48")
				ci.draw_arc(p, size * 0.55, 0, TAU, 48, red, 3, true)
				for k in 4:
					var ang := k * PI / 2.0 + _now
					ci.draw_line(p + Vector2(cos(ang), sin(ang)) * size * 0.45, p + Vector2(cos(ang), sin(ang)) * size * 0.7, red, 3)
	# the boss
	var bo: Dictionary = b.boss
	if not bo.is_empty() and not (float(bo.dead) != 0.0 and _now - float(bo.dead) > 0.6):
		var bz := 1.0 - (_now - float(bo.dead)) / 0.6 if float(bo.dead) != 0.0 else 1.0
		var enter := minf(1.0, (_now - float(bo.t0)) / 1.2)
		var bp := Vector2(BOSS_AT.x + (1.0 - enter) * 400.0, BOSS_AT.y + sin(_now * 0.8) * 8.0)
		var bs := 320.0 * bz
		var flash := 1.8 if _now - float(bo.hit_at) < 0.15 else 1.0
		var boss_tex := _tex("b_boss")
		if boss_tex:
			ci.draw_texture_rect(boss_tex, Rect2(bp - Vector2(bs, bs) / 2.0, Vector2(bs, bs)), false, Color(flash, flash, flash, enter * bz))
		if b.waiting and enter >= 1.0:
			_add_hit("boss", Rect2(bp - Vector2(160, 120), Vector2(320, 240)))
		_rr(ci, Rect2(bp.x - 150, bp.y - 150, 300, 20), 10, Color(0, 0, 0, 0.6))
		if int(bo.hp) > 0:
			_rr(ci, Rect2(bp.x - 150, bp.y - 150, maxf(20.0, 300.0 * float(bo.hp) / float(bo.max)), 20), 10, Color("e2402f"))
		_text(ci, texts.boss, Vector2(bp.x, bp.y - 168), 22, COND, Color("ffb4a6"), "center", 4, 300)
	# the phaser beam, the return fire and the explosions
	var bm: Dictionary = b.beam
	if not bm.is_empty() and _now - float(bm.t0) < 0.45:
		var to := BOSS_AT if bm.boss else _ship_pos(bm.ship)
		var k := 1.0 - (_now - float(bm.t0)) / 0.45
		var from := Vector2(HERO.x + 100, hy - 6)
		ci.draw_line(from, to, Color(1, 0.48, 0.19, 0.25 * k), 22)
		ci.draw_line(from, to, Color(1, 0.55, 0.24, k), 9)
		ci.draw_line(from, to, Color(1, 0.94, 0.78, k), 3)
	b.bolts = (b.bolts as Array).filter(func(x): return _now - float(x.t0) < 0.45)
	for bolt in b.bolts:
		var k := (_now - float(bolt.t0)) / 0.45
		if k < 0.0:
			continue
		var from: Vector2 = bolt.from
		var at := from.lerp(Vector2(HERO.x + 60, hy), k)
		ci.draw_set_transform(at, (Vector2(HERO.x, hy) - from).angle(), Vector2(1, 0.38))
		ci.draw_circle(Vector2.ZERO, 22, Color(0.42, 1, 0.42, 0.3))
		ci.draw_circle(Vector2.ZERO, 16, Color(0.72, 1, 0.69))
		ci.draw_set_transform(Vector2.ZERO)
	b.booms = (b.booms as Array).filter(func(x): return _now - float(x.t0) < 0.9)
	for boom in b.booms:
		var k := (_now - float(boom.t0)) / 0.9
		var r := float(boom.size) * (0.3 + k * 0.7)
		var at: Vector2 = boom.at
		ci.draw_circle(at, r, Color(0.47, 0.08, 0.0, 0.25 * (1.0 - k)))
		ci.draw_circle(at, r * 0.75, Color(1, 0.59, 0.16, 0.6 * (1.0 - k)))
		ci.draw_circle(at, r * 0.4, Color(1, 0.98, 0.82, 1.0 - k))
		for bit in boom.bits:
			ci.draw_rect(Rect2(at + Vector2(cos(bit.x), sin(bit.x)) * r * bit.y * 1.3, Vector2(4, 4)), Color(1, 0.78, 0.47, 1.0 - k))


func _draw_battle_hud(ci: CanvasItem) -> void:
	var b := battle
	var waves := int(b.waves)
	# the top: a pip a wave, then the boss, and the battle's win
	var steps := waves + 1
	var gap := 880.0 / (steps - 1)
	for k in steps:
		var x := 60.0 + k * gap
		var done: bool = k < int(b.cleared) or (k == waves and b.won)
		var now: bool = k == int(b.cleared) and not b.won
		if k < steps - 1:
			ci.draw_rect(Rect2(x + 12, REEL_Y + 1, gap - 24, 2), Color(1, 1, 1, 0.15))
		ci.draw_circle(Vector2(x, REEL_Y + 2), 14.0 if k == waves else 10.0, GOLD if done else (Color("e2402f") if now else Color(1, 1, 1, 0.15)))
	_text(ci, "%s WIN %s" % [texts.battle, Money.format(int(b.total))], Vector2(523, REEL_Y + 30), 34, COND, WIN_COL, "center", 6, 600)
	# the panel: wave, shields, ships left, what's banked, FIRE
	_wood(ci, Rect2(1038, REEL_Y - 18, 224, REEL_H + 36), 16)
	_text(ci, texts.battle, Vector2(1150, REEL_Y + 10), 26, COND, Color("ff6a5a"), "center", 0, 200)
	var stage: String = texts.boss if not b.boss.is_empty() else "WAVE %d OF %d" % [mini(int(b.wave), waves - 1) + 1, waves]
	_text(ci, stage, Vector2(1150, REEL_Y + 40), 22, COND, GOLD_HI, "center", 0, 200)
	_text(ci, "SHIELDS", Vector2(1150, REEL_Y + 76), 18, COND, CREAM)
	var ms := int(b.max_shields)
	var pw := minf(40.0, 180.0 / maxf(1.0, ms))
	for k in ms:
		_rr(ci, Rect2(1150 - ms * pw / 2.0 + k * pw + 3, REEL_Y + 88, pw - 6, 18), 5, Color("5ab4ff") if k < int(b.shields) else Color(1, 1, 1, 0.12))
	var left := (b.ships as Array).filter(func(sh): return float(sh.dead) == 0.0).size()
	var line := "HITS LEFT %d" % int(b.boss.hp) if not b.boss.is_empty() else "%s: %d LEFT" % [texts.enemy, left]
	_text(ci, line, Vector2(1150, REEL_Y + 136), 18, COND, CREAM, "center", 0, 200)
	_text(ci, "FREE GAMES WON %d" % int(b.spins), Vector2(1150, REEL_Y + 166), 18, COND, Color("7fd0ff"), "center", 0, 200)
	if b.waiting:
		_button(ci, "fire", Rect2(1070, REEL_Y + 300, 160, 58), "FIRE", false, false, 32, _fire_colours())
		_text(ci, texts.battle_hint, Vector2(1150, REEL_Y + 380), 16, COND, CREAM, "center", 0, 200)
		_text(ci, "fires itself in %d" % ceili(maxf(0.0, float(b.auto_at) - _now)), Vector2(1150, REEL_Y + 402), 16, COND, MUTED)


# ------------------------------------------------------------------ the island voyage (Dead Man's Map)
# A sea chart filling the trail's area: the start port on the left, a column of three islands a leg, the final island
# on the right, dotted sea lanes between neighbours. Click one of the lit islands to sail there (a cove needs a key);
# at Port Royal the panel's deals trade relics. The panel keeps the hold: relics, keys, artefacts, free games. The
# wizard's mockup (game.js drawVoyage) is the same scene; the timings match bonuses.py _VOYAGE_SECONDS.
const ISLE_ART := {"treasure": "v_treasure", "wreck": "v_wreck", "skull": "v_skull", "port": "v_port", "cove": "v_cove"}
const ROW_Y := [228.0, 352.0, 476.0]
const DEALS := ["artefact", "key", "spins", "sell", "leave"]


func _v_step(legs: int) -> float:
	return 860.0 / (legs + 1)


## Where an island sits: leg -1 is the start port, `legs` the final island.
func _isle_pos(leg: int, row: int, legs: int) -> Vector2:
	var x := 90.0 + (leg + 1) * _v_step(legs)
	return Vector2(x, 352.0 if leg < 0 or leg >= legs else float(ROW_Y[row]))


## What the screen shows of the voyage: it follows the events, so a find shows when it's animated, not before.
static func _voyage_shown(v: Dictionary) -> Dictionary:
	return {"relics": int(v.relics), "keys": int(v.keys), "artefacts": (v.artefacts as Array).duplicate(), "spins": int(v.spins),
		"total": int(v.total), "leg": int(v.leg), "row": -1 if v.row == null else int(v.row), "route": (v.route as Array).duplicate(),
		"awaiting": str(v.awaiting) if v.awaiting != null else "", "sunk": bool(v.sunk)}


func _begin_voyage(v: Dictionary) -> void:
	var legs := (v.map as Array).size()
	var sh := _voyage_shown(v)
	var at := _isle_pos(sh.leg, maxi(0, sh.row), legs)
	voyage = {"st": v, "legs": legs, "bet": int(v.bet), "shown": sh, "ship": {"x": at.x, "y": at.y - 34.0, "rot": 0.0, "sink": 0.0, "a": 1.0},
		"waiting": false, "auto_at": 1e9, "reveal": {}}
	_clear_wins()


func _voyage_ready() -> void:
	var st: Dictionary = voyage.st
	voyage.shown = _voyage_shown(st)
	voyage.waiting = true
	voyage.auto_at = _now + 12.0
	if str(st.awaiting) == "trade":
		message = "%s: TRADE YOUR %sS, OR SET SAIL" % [texts.voyage_port, texts.voyage_relic]
	elif int(st.leg) == int(voyage.legs) - 1:
		message = "SAIL TO %s" % texts.voyage_final
	else:
		message = "CHOOSE YOUR NEXT ISLAND  ·  CLICK ONE"


## Choose an island's row, "final" or a deal; anything else (or null) lets the server choose.
func _choose_voyage(choice) -> void:
	if voyage.is_empty() or not voyage.get("waiting", false):
		return
	var opts: Array = voyage.st.options
	if choice == null or not opts.has(choice):
		choice = opts[randi() % opts.size()] if str(voyage.st.awaiting) == "sail" else _voyage_auto_deal(opts)
	voyage.waiting = false
	Net.send("voyage_choose", {"choice": choice})


## A voyage view from the server, its rows made whole numbers (JSON gives floats) so they match the islands' ids.
static func _voyage_view(v: Dictionary) -> Dictionary:
	var out := v.duplicate(true)
	out.options = (v.options as Array).map(func(o): return int(o) if typeof(o) == TYPE_FLOAT else o)
	out.route = (v.route as Array).map(func(r): return int(r))
	return out


static func _voyage_auto_deal(opts: Array) -> String:
	for d in ["artefact", "spins", "sell", "leave"]:
		if opts.has(d):
			return d
	return "leave"


func _voyage_pop(txt: String, colour: Color, at: Vector2, size := 36) -> void:
	_battle_pop(txt, colour, at, size)


## An artefact (or a relic or key) flying from where it was found into the hold.
func _to_hold(art: String, from: Vector2, to: Vector2) -> void:
	var f := _flyer({"img": art, "x": from.x, "y": from.y, "size": 90.0, "s": 0.3})
	await _tw(f, {"s": 1.2, "y": from.y - 50.0}, 0.35, "back")
	await _tw(f, {"x": to.x, "y": to.y, "s": 0.45}, 0.55, "inout")
	f.dead = true


func _art_slot(i: int) -> Vector2:   # the hold's artefacts, a row of four
	return Vector2(1078 + i * 48, REEL_Y + 160)


func _animate_voyage(step: Dictionary) -> void:
	var Y := voyage
	var sh: Dictionary = Y.shown
	var ep := _epoch
	var legs := int(Y.legs)
	await _wait(0.3)
	for e in step.events:
		if ep != _epoch:
			return
		var here := _isle_pos(int(sh.leg), maxi(0, int(sh.row)), legs)
		match str(e.kind):
			"arrive":
				var to := _isle_pos(int(e.leg), int(e.row), legs)
				Y.ship.rot = atan2(to.y - float(Y.ship.y), to.x - float(Y.ship.x)) * 0.3
				_sfx("voyage_sail")
				await _tw(Y.ship, {"x": to.x, "y": to.y - 34.0}, 1.1, "inout")
				Y.ship.rot = 0.0
				sh.leg = int(e.leg)
				sh.row = int(e.row)
				(sh.route as Array).append(int(e.row))
				await _wait(0.3)
			"treasure", "skull", "cove":
				sh.total = int(sh.total) + int(e.pence)
				win_target = float(sh.total)
				roller = maxf(float(e.pence) * 1.4, float(_bet()))
				_sfx("voyage_find")
				_voyage_pop(Money.format(int(e.pence)), WIN_COL, here + Vector2(0, -40), 36 if str(e.kind) == "treasure" else 46)
				_coin_burst(here.x, here.y, 14 if str(e.kind) == "treasure" else 26, 0.8)
				await _wait(1.0 if str(e.kind) == "treasure" else 1.2)
			"relics":
				sh.relics = int(sh.relics) + int(e.n)
				_to_hold("v_relic", here, Vector2(1072, REEL_Y + 92))
				_voyage_pop("+%d %s%s" % [int(e.n), texts.voyage_relic, "S" if int(e.n) > 1 else ""], GOLD_HI, here + Vector2(0, -30), 30)
				await _wait(0.8)
			"key":
				sh.keys = int(sh.keys) + 1
				_sfx("voyage_find")
				_to_hold("v_key", here, Vector2(1162, REEL_Y + 92))
				_voyage_pop("+1 KEY", GOLD_HI, here + Vector2(0, -30), 30)
				await _wait(0.8)
			"artefact":
				var i := int(e.i)
				_sfx("voyage_find")
				_to_hold("v_art%d" % (i + 1), here, _art_slot(i))
				_voyage_pop(str(texts.voyage_artefacts[i]), GOLD_HI, here + Vector2(0, -70), 34)
				await _wait(0.9)
				sh.artefacts[i] = true
				await _wait(0.3)
			"unlock":
				sh.keys = int(sh.keys) - 1
				_voyage_pop("UNLOCKED", GOLD_HI, here + Vector2(0, -30), 32)
				await _wait(0.8)
			"sunk":
				sh.sunk = true
				_sfx("voyage_sink")
				_voyage_pop("SUNK!", Color("ff5a48"), here + Vector2(0, -60), 52)
				shake = 1.0
				await _tw(Y.ship, {"rot": 0.5, "sink": 1.0, "a": 0.0}, 2.0, "inout")
				await _wait(0.2)
			"port":
				sh.awaiting = "trade" if not (e.deals as Array).is_empty() else "sail"
				await _wait(0.6)
			"bought":
				sh.relics = int(sh.relics) - int(e.cost)
				sh.awaiting = "sail"
				_sfx("voyage_trade")
				if str(e.deal) == "spins":
					var n := int(rules.get("voyage", {}).get("spins_games", 1))
					sh.spins = int(sh.spins) + n
					_voyage_pop("+%d FREE GAME%s" % [n, "S" if n > 1 else ""], Color("7fd0ff"), here + Vector2(0, -30), 30)
				await _wait(0.6)
			"sold":
				sh.relics = 0
				sh.awaiting = "sail"
				sh.total = int(sh.total) + int(e.pence)
				win_target = float(sh.total)
				roller = maxf(float(e.pence), float(_bet()))
				_sfx("voyage_trade")
				_voyage_pop("SOLD %s" % Money.format(int(e.pence)), WIN_COL, here + Vector2(0, -30), 34)
				await _wait(0.9)
			"leave":
				sh.awaiting = "sail"
				await _wait(0.3)
			"final":
				var to := _isle_pos(legs, 1, legs)
				_sfx("voyage_sail")
				await _tw(Y.ship, {"x": to.x - 70.0, "y": to.y - 20.0}, 0.9, "inout")
				Y.reveal = {"t0": _now, "shown": -1, "e": e}
				var parts := [int(e.chest)]
				for p in e.parts:
					parts.append(int(p))
				parts.append_array([int(e.legend), int(e.relics)])
				for k in 7:   # the chest, four parts, the legend, the relics: 0.5s each
					if ep != _epoch:
						return
					Y.reveal.shown = k
					if parts[k] > 0:
						sh.total = int(sh.total) + parts[k]
						win_target = float(sh.total)
						roller = maxf(float(parts[k]), float(_bet()))
						_sfx("voyage_chest")
					if k == 5 and parts[k] > 0:
						_coin_rain(60)
						shake = 0.6
					await _wait(0.9 if k == 5 and parts[k] > 0 else 0.5)
				_coin_burst(523, 330, 40, 1.2)
				await _wait(0.6)


func _draw_voyage(ci: CanvasItem) -> void:
	var Y := voyage
	var st: Dictionary = Y.st
	var sh: Dictionary = Y.shown
	var A := B_AREA
	var legs := int(Y.legs)
	var size := minf(104.0, _v_step(legs) * 0.84)
	var open: Array = st.options if Y.waiting and str(st.awaiting) == "sail" else []
	# the sea, a dim wash of the slot's background, the chart's grid and the swell
	_rr(ci, A, 18, Color("0b3550"))
	_vgrad(ci, A.grow(-4), Color("0e4a66"), Color("08263c"))
	var bg := _tex("bg") if background else null
	if bg:
		ci.draw_texture_rect(bg, A.grow(-4), false, Color(1, 1, 1, 0.18))
	var x := A.position.x + 40.0
	while x < A.end.x:
		ci.draw_line(Vector2(x, A.position.y + 4), Vector2(x, A.end.y - 4), Color(1, 1, 1, 0.05), 1)
		x += 80.0
	var y := A.position.y + 40.0
	while y < A.end.y:
		ci.draw_line(Vector2(A.position.x + 4, y), Vector2(A.end.x - 4, y), Color(1, 1, 1, 0.05), 1)
		y += 80.0
	for k in 14:
		var wx := A.position.x + fmod(k * 173.0 + _now * 14.0, A.size.x)
		var wy := A.position.y + 30.0 + fmod(k * 97.0, A.size.y - 60.0)
		ci.draw_arc(Vector2(wx, wy), 16, PI * 1.15, PI * 1.85, 12, Color(0.75, 0.9, 1.0, 0.10), 2, true)
	# the sea lanes: faint between neighbours, red where you've sailed, gold to where you can go now
	for leg in range(-1, legs):
		for r in ([1] if leg < 0 else [0, 1, 2]):
			var a := _isle_pos(leg, r, legs)
			var nexts := [1] if leg == legs - 1 else ([0, 1, 2] if leg < 0 else [r - 1, r, r + 1].filter(func(n): return n >= 0 and n <= 2))
			for n in nexts:
				ci.draw_dashed_line(a, _isle_pos(leg + 1, n, legs), Color(1, 0.94, 0.78, 0.16), 2, 6)
	var px := _isle_pos(-1, 1, legs)
	var leg_i := 0
	for r in sh.route:
		var q := _isle_pos(leg_i, int(r), legs)
		ci.draw_dashed_line(px, q, Color("d8432f"), 4, 12)
		px = q
		leg_i += 1
	if not (Y.reveal as Dictionary).is_empty():
		ci.draw_dashed_line(px, _isle_pos(legs, 1, legs), Color("d8432f"), 4, 12)
	var pulse := 0.55 + 0.45 * sin(_now * 5.0)
	for o in open:
		var q := _isle_pos(legs, 1, legs) if str(o) == "final" else _isle_pos(int(sh.leg) + 1, int(o), legs)
		ci.draw_dashed_line(px, q, Color(GOLD_HI, pulse), 3, 12)
	# the islands
	var s0 := _isle_pos(-1, 1, legs)
	_isle(ci, "v_port", s0, size * 0.9, 1.0 if int(sh.leg) < 0 else 0.55, texts.voyage_start, "", false, pulse, legs)
	for leg in legs:
		for r in 3:
			var kind := str(st.map[leg][r])
			var q := _isle_pos(leg, r, legs)
			var lit := int(sh.leg) == leg - 1 and open.has(r)
			var passed := leg <= int(sh.leg) and not (leg == int(sh.leg) and r == int(sh.row))
			var locked := kind == "cove" and not (int(sh.leg) == leg and int(sh.row) == r) and not (leg > int(sh.leg) and int(sh.keys) > 0)
			_isle(ci, ISLE_ART[kind], q, size, 0.35 if passed else (0.6 if locked else 1.0), texts["voyage_" + kind], "isle%d" % r if lit else "", lit, pulse, legs)
			if locked and not passed:   # a padlock over a cove you've no key for
				var lp := q + Vector2(size * 0.3, -size * 0.32)
				ci.draw_arc(lp, 8, PI, TAU, 12, Color("c8c8cc"), 4, true)
				_rr(ci, Rect2(lp.x - 12, lp.y, 24, 18), 4, GOLD)
	var fq := _isle_pos(legs, 1, legs)
	var final_lit := open.has("final")
	_isle(ci, "v_final", fq, minf(150.0, size * 1.4), 1.0, texts.voyage_final, "final" if final_lit else "", final_lit, pulse, legs)
	# the ship
	var sp: Dictionary = Y.ship
	var ship := _tex("v_ship")
	if ship:
		ci.draw_set_transform(Vector2(float(sp.x), float(sp.y) + sin(_now * 2.0) * 3.0 + float(sp.sink) * 40.0), float(sp.rot))
		ci.draw_texture_rect(ship, Rect2(-46, -46, 92, 92), false, Color(1, 1, 1, float(sp.a)))
		ci.draw_set_transform(Vector2.ZERO)


func _isle(ci: CanvasItem, art: String, at: Vector2, s: float, a: float, label: String, id: String, lit: bool, pulse: float, legs: int) -> void:
	var bob := sin(_now * 2.4 + at.x) * 3.0 if lit else 0.0
	var c := at + Vector2(0, bob)
	if lit:
		for k in 5:   # a soft glow behind it
			ci.draw_circle(c, s * 0.7 * (1.0 - k * 0.16), Color(GOLD_HI, 0.09 * pulse))
	var tex := _tex(art)
	if tex:
		ci.draw_texture_rect(tex, Rect2(c - Vector2(s, s) / 2.0, Vector2(s, s)), false, Color(1, 1, 1, a))
	if id != "" and _hover == id:
		ci.draw_arc(c, s * 0.56, 0, TAU, 48, GOLD_HI, 3, true)
	_text(ci, label, at + Vector2(0, s / 2.0 + 8.0), 13, COND, Color(GOLD_HI if lit else CREAM, a), "center", 4, _v_step(legs) - 8.0)
	if id != "":
		_add_hit(id, Rect2(at - Vector2(s, s) / 2.0, Vector2(s, s)))


func _draw_voyage_hud(ci: CanvasItem) -> void:
	var Y := voyage
	var st: Dictionary = Y.st
	var sh: Dictionary = Y.shown
	if not (Y.reveal as Dictionary).is_empty():
		_draw_reveal(ci, Y.reveal)
	_text(ci, "%s WIN %s" % [texts.voyage_name, Money.format(int(sh.total))], Vector2(523, REEL_Y + 14), 32, COND, WIN_COL, "center", 6, 600)
	# the panel: where you are, the hold, and the deals or the next island
	var P: Dictionary = rules.get("voyage", {})
	var cx := 1150.0
	_wood(ci, Rect2(1038, REEL_Y - 18, 224, REEL_H + 36), 16)
	_text(ci, texts.voyage_name, Vector2(cx, REEL_Y + 10), 24, COND, GOLD_HI, "center", 0, 200)
	var stage := ""
	if not (Y.reveal as Dictionary).is_empty():
		stage = texts.voyage_final
	elif sh.sunk:
		stage = "SUNK"
	elif str(sh.awaiting) == "trade":
		stage = texts.voyage_port
	elif int(sh.leg) >= int(Y.legs) - 1:
		stage = "ON TO %s" % texts.voyage_final
	else:
		stage = "LEG %d OF %d" % [int(sh.leg) + 2, int(Y.legs)]
	_text(ci, stage, Vector2(cx, REEL_Y + 40), 20, COND, CREAM, "center", 0, 200)
	var relic := _tex("v_relic")
	if relic:
		ci.draw_texture_rect(relic, Rect2(1052, REEL_Y + 72, 40, 40), false)
	_text(ci, "× %d" % int(sh.relics), Vector2(1096, REEL_Y + 92), 20, COND, CREAM, "left", 0, 50)
	var key := _tex("v_key")
	if key:
		ci.draw_texture_rect(key, Rect2(1142, REEL_Y + 72, 40, 40), false)
	_text(ci, "× %d" % int(sh.keys), Vector2(1186, REEL_Y + 92), 20, COND, CREAM, "left", 0, 50)
	var held := (sh.artefacts as Array).filter(func(h): return h).size()
	_text(ci, "ARTEFACTS %d OF 4" % held, Vector2(cx, REEL_Y + 128), 16, COND, GOLD_HI, "center", 0, 200)
	for i in 4:
		var t := _tex("v_art%d" % (i + 1))
		if t:
			ci.draw_texture_rect(t, Rect2(_art_slot(i) - Vector2(22, 22), Vector2(44, 44)), false, Color(1, 1, 1, 1.0 if sh.artefacts[i] else 0.2))
	_text(ci, "FREE GAMES %d" % int(sh.spins), Vector2(cx, REEL_Y + 200), 16, COND, Color("7fd0ff"), "center", 0, 200)
	if not Y.waiting:
		return
	var left := maxf(0.0, float(Y.auto_at) - _now)
	var relics := "%sS" % texts.voyage_relic
	if str(st.awaiting) == "trade":
		var opts: Array = st.options
		var games := int(P.get("spins_games", 1))
		for i in DEALS.size():
			var d: String = DEALS[i]
			var label := ""
			match d:
				"artefact": label = "ARTEFACT · %d %s" % [int(P.get("artefact_price", 3)), relics]
				"key": label = "KEY · %d %s" % [int(P.get("key_price", 2)), relics]
				"spins": label = "%s · %d %s" % ["%d FREE GAMES" % games if games > 1 else "FREE GAME", int(P.get("spins_price", 4)), relics]
				"sell": label = "SELL · %s" % Money.format(floori(int(st.relics) * float(P.get("relic_value", 1)) * int(st.bet) + 0.5))
				_: label = "SET SAIL"
			_button(ci, "deal-" + d, Rect2(1054, REEL_Y + 220 + i * 44, 192, 38), label, false, not opts.has(d), 16,
				[GOLD_HI, SPIN_COL] if d == "leave" else [])
		_text(ci, "chooses itself in %d" % ceili(left), Vector2(cx, REEL_Y + 448), 16, COND, MUTED)
	else:
		if int(st.leg) == int(Y.legs) - 1:
			_button(ci, "final", Rect2(1060, REEL_Y + 300, 180, 52), "SAIL TO %s" % texts.voyage_final, false, false, 18, [GOLD_HI, SPIN_COL])
		else:
			_text(ci, texts.voyage_hint, Vector2(cx, REEL_Y + 320), 16, COND, CREAM, "center", 0, 200)
		_text(ci, "chooses itself in %d" % ceili(left), Vector2(cx, REEL_Y + 370), 16, COND, MUTED)


func _draw_reveal(ci: CanvasItem, R: Dictionary) -> void:
	var e: Dictionary = R.e
	var k := int(R.shown)
	var cx := 523.0
	_rr(ci, B_AREA, 18, Color(SHADE, minf(0.8, (_now - float(R.t0)) * 2.0)))
	_gold_text(ci, texts.voyage_chest, Vector2(cx, REEL_Y + 64), 40, 700)
	var s := 200.0 + 12.0 * sin(_now * 2.0)
	var chest := _tex("v_chest")
	if chest:
		ci.draw_texture_rect(chest, Rect2(cx - s / 2.0, 300 - s / 2.0, s, s), false)
	if k >= 0:
		_text(ci, Money.format(int(e.chest)), Vector2(cx, 410), 30, COND, WIN_COL, "center", 5)
	for i in 4:
		var x := cx + (i - 1.5) * 150.0
		var held := int(e.parts[i]) > 0
		var on := k >= i + 1
		var a := (1.0 if held else 0.3) if on else 0.12
		var t := _tex("v_art%d" % (i + 1))
		if t:
			ci.draw_texture_rect(t, Rect2(x - 34, 444, 68, 68), false, Color(1, 1, 1, a))
		_text(ci, str(texts.voyage_artefacts[i]), Vector2(x, 520), 15, COND, Color(CREAM, a), "center", 4, 140)
		if on:
			_text(ci, "+%s" % Money.format(int(e.parts[i])) if held else "MISSING", Vector2(x, 542), 20 if held else 15, COND,
				WIN_COL if held else MUTED, "center", 4)
	if k >= 5 and int(e.legend) > 0:
		_text(ci, "%s +%s" % [texts.voyage_legend, Money.format(int(e.legend))], Vector2(cx, 180), 44, COND, GOLD_HI, "center", 7, 800)
	if k >= 6 and int(e.relics) > 0:
		_text(ci, "%sS SOLD +%s" % [texts.voyage_relic, Money.format(int(e.relics))], Vector2(cx, 440), 18, COND, CREAM, "center", 4)


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
	if id in CLICKS or id.begins_with("auto"):
		_sfx("click")
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
				_sfx("cash_out")
				stand_requested.emit()
		return
	if not battle.is_empty() and (id.begins_with("ship") or id == "boss"):
		_fire_battle(int(id.substr(4)) if id.begins_with("ship") else -1)
		return
	if not voyage.is_empty() and (id.begins_with("isle") or id.begins_with("deal-") or id == "final"):
		_choose_voyage(int(id.substr(4)) if id.begins_with("isle") else (id.substr(5) if id.begins_with("deal-") else "final"))
		return
	if id.begins_with("coin"):
		var i := int(id.substr(4))
		if not pick.is_empty() and not pick.done and pick.coins[i].tier == "" and not pick.coins[i].asked:
			pick.coins[i].asked = true
			Net.send("jackpot_pick", {"index": i})
		return
	if id != "auto" and not id.begins_with("auto"):
		auto_menu = false
	var idle := not _running and pick.is_empty() and trail.is_empty() and battle.is_empty() and voyage.is_empty() and free.is_empty()
	match id:
		"spin":
			_spin_or_stop()
		"fire":
			if not battle.is_empty():
				_fire_battle(-1)
			else:
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
	if not pick.is_empty() or not trail.is_empty() or not battle.is_empty() or not voyage.is_empty() or not free.is_empty():
		overlay = {"kind": "cashout"}
	else:
		_sfx("cash_out")
		stand_requested.emit()


func _bet() -> int:
	return int(_ladder[_bet_idx]) if not _ladder.is_empty() else 100


func _spin_or_stop() -> void:
	if not trail.is_empty():
		return _fire()
	if not battle.is_empty():
		return _fire_battle(-1)
	if not voyage.is_empty():
		return _choose_voyage(null)
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
	_sfx("spin_press")
	Net.send("spin", {"bet": _bet()})


func _fire() -> void:
	if not trail.is_empty() and trail.get("waiting", false):
		trail.waiting = false
		Net.send("trail_fire")
