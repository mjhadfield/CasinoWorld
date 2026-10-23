class_name BettingBar
extends Control
## The seated controls, signed off on the Betting Bar mockup (docs/betting_ui/mockup/): one bar at the foot of the
## screen over a short, firm fade. The table's name, how many are seated and what you have on the felt sit on the
## left, centred on the bar (your balance is the HUD's, top left). The chips are dead
## centre, in the table's own style, with the line above them saying what's happening (its countdown draining in
## gold under it). The commit button (Ready, Repeat Bet until you've bet, or Craps' dice) hugs the chips on the left;
## Undo, Clear and the Auto rebet and Sit out switches (Craps: Working) hug them on the right. A decision (Play/Fold, Hit/Stand...) takes the chips'
## place while it's open. The table's jackpot, if it has one, sits top left under your balance; Paytable and Stand
## up top right, left of the HUD's Settings.
## The HUD feeds it (set_chips, update_view) and passes its signals on.

signal chip_picked(value: int)
signal undo_pressed
signal rebet_pressed
signal clear_pressed
signal auto_toggled(on: bool)
signal sit_out_toggled(on: bool)
signal ready_pressed
signal action(id: String)
signal stand_pressed
signal paytable_toggled(on: bool)

const FONT := preload("res://assets/fonts/BarlowCondensed-Bold.ttf")
const INK := Color("ece4d2")
const MUTED := Color("9ba39e")
const BRASS := Color("c9a24a")
const BRASS_HI := Color("ecd396")
const PAPER := Color("f6efdc")
const WIN := Color("5fd3a0")
const LOSS := Color("ef7a6b")
const WARN := Color("f2c14e")
const CORNER_BG := Color(0.04, 0.047, 0.05, 0.94)   # the corners' pills: near solid, so a wall's edge doesn't show through
const PAD_TOP := 30.0      # the fade's ramp, above the line
const ROW_GAP := 18.0      # the line to the chips (a picked chip lifts clear of the timer)
const PAD_BOTTOM := 14.0
const CHIP := 50.0
const CHIP_PHONE := 36.0
const BUTTON_H := 50.0     # Ready and the decisions: as tall as the chips
const SIDE_GAP := 16.0     # the chips to Ready on one side, to Undo on the other
const TOP_LEFT_Y := 64.0   # under the HUD's wallet pill, top left

## The top of the bar's fade, in screen pixels (the Master Table's pills and the Pai Gow sorter sit above it).
var bar_top := 0.0
var selected_chip := 100
## The HUD's Settings button and its gap, top right: the corner buttons sit left of it.
var right_inset := 124.0

var _fade: TextureRect
var _info: RichTextLabel
var _timer: ColorRect
var _timer_fill: ColorRect
var _where: VBoxContainer   # bottom left: the table, its seats, what's on the felt
var _title: Label
var _seats: Label
var _felt: HBoxContainer
var _felt_amount: Label
var _commit: HBoxContainer
var _ready_btn: BarButton
var _chips: HBoxContainer
var _decide: HBoxContainer
var _tools: HBoxContainer
var _undo: BarButton
var _clear: BarButton
var _auto: BarSwitch
var _sit_out: BarSwitch
var _jackpot: PanelContainer
var _jackpot_in: Label
var _jackpot_amount: Label
var _corner: HBoxContainer
var _pay: BarButton
var _shown := ""          # the action list the dynamic buttons were built from


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = MOUSE_FILTER_IGNORE
	_fade = TextureRect.new()
	_fade.mouse_filter = MOUSE_FILTER_IGNORE
	_fade.stretch_mode = TextureRect.STRETCH_SCALE
	_fade.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	add_child(_fade)
	_info = RichTextLabel.new()
	_info.bbcode_enabled = true
	_info.fit_content = true
	_info.scroll_active = false
	_info.autowrap_mode = TextServer.AUTOWRAP_OFF
	_info.mouse_filter = MOUSE_FILTER_IGNORE
	_info.add_theme_font_override("normal_font", FONT)
	_info.add_theme_font_size_override("normal_font_size", 18)
	_info.add_theme_color_override("default_color", INK)
	_info.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.9))
	_info.add_theme_constant_override("shadow_offset_y", 1)
	add_child(_info)
	_timer = ColorRect.new()
	_timer.color = Color(1, 1, 1, 0.1)
	_timer.size = Vector2(260, 3)
	_timer.mouse_filter = MOUSE_FILTER_IGNORE
	_timer_fill = ColorRect.new()
	_timer_fill.color = BRASS_HI
	_timer_fill.size = Vector2(260, 3)
	_timer.add_child(_timer_fill)
	add_child(_timer)
	_build_where()
	_commit = HBoxContainer.new()
	_commit.add_theme_constant_override("separation", 8)
	_commit.alignment = BoxContainer.ALIGNMENT_END
	add_child(_commit)
	_ready_btn = BarButton.new()
	_ready_btn.setup("Ready", "Space", "primary")
	_ready_btn.pressed.connect(func(): (rebet_pressed if _ready_btn.words == "Repeat Bet" else ready_pressed).emit())
	_commit.add_child(_ready_btn)
	_chips = HBoxContainer.new()
	_chips.add_theme_constant_override("separation", 9)
	add_child(_chips)
	_decide = HBoxContainer.new()
	_decide.add_theme_constant_override("separation", 10)
	_decide.hide()
	add_child(_decide)
	_tools = HBoxContainer.new()
	_tools.add_theme_constant_override("separation", 7)
	add_child(_tools)
	_undo = BarButton.new()
	_undo.setup("Undo", "", "tool", "undo")
	_undo.tooltip_text = "Take back your last chip"
	_undo.pressed.connect(undo_pressed.emit)
	_tools.add_child(_undo)
	_clear = BarButton.new()
	_clear.setup("Clear", "", "tool", "clear")
	_clear.tooltip_text = "Take back the bets you can"
	_clear.pressed.connect(clear_pressed.emit)
	_tools.add_child(_clear)
	_auto = BarSwitch.new()
	_auto.words = "Auto"
	_auto.tooltip_text = "Put the same bets down every round"
	_auto.toggled.connect(auto_toggled.emit)
	_tools.add_child(_auto)
	_sit_out = BarSwitch.new()
	_sit_out.words = "Sit out"
	_sit_out.tooltip_text = "Sit out every hand until you bet or switch it off"
	_sit_out.toggled.connect(sit_out_toggled.emit)
	_tools.add_child(_sit_out)
	_build_corners()
	resized.connect(_layout)


func _build_where() -> void:
	_where = VBoxContainer.new()
	_where.add_theme_constant_override("separation", 0)
	_where.mouse_filter = MOUSE_FILTER_IGNORE
	add_child(_where)
	_title = _label("", 26, INK)
	_title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	_where.add_child(_title)
	_seats = _label("", 17, MUTED)
	_where.add_child(_seats)
	_felt = HBoxContainer.new()
	_felt.add_theme_constant_override("separation", 5)
	_where.add_child(_felt)
	_felt_amount = _label("£0", 17, BRASS_HI)
	_felt.add_child(_felt_amount)
	_felt.add_child(_label("on the felt", 17, MUTED))


func _build_corners() -> void:
	_jackpot = PanelContainer.new()
	_jackpot.position = Vector2(12, TOP_LEFT_Y)
	add_child(_jackpot)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 0)
	_jackpot.add_child(box)
	var top := HBoxContainer.new()
	top.add_theme_constant_override("separation", 8)
	box.add_child(top)
	var title := _label("JACKPOT", 13, BRASS)
	title.add_theme_constant_override("outline_size", 0)
	top.add_child(title)
	_jackpot_in = _label("Your £1 is in", 12, Color("1b1307"))
	_jackpot_in.add_theme_stylebox_override("normal", _box(BRASS_HI, BRASS_HI, 8, Vector4(7, 0, 7, 0)))
	_jackpot_in.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	top.add_child(_jackpot_in)
	_jackpot_amount = _label("", 32, BRASS_HI)
	box.add_child(_jackpot_amount)
	_light_jackpot(false)

	_corner = HBoxContainer.new()
	_corner.add_theme_constant_override("separation", 8)
	add_child(_corner)
	_pay = BarButton.new()
	_pay.setup("Paytable", "", "ghost", "paytable")
	_pay.toggle_mode = true
	_pay.toggled.connect(func(on: bool):
		_pay.queue_redraw()
		paytable_toggled.emit(on))
	_corner.add_child(_pay)
	var stand := BarButton.new()
	stand.setup("Stand up", "Esc", "ghost", "stand")
	stand.pressed.connect(stand_pressed.emit)
	_corner.add_child(stand)


func _label(text: String, size: int, colour: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", FONT)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", colour)
	l.mouse_filter = MOUSE_FILTER_IGNORE
	return l


static func _box(bg: Color, border: Color, radius: int, margins := Vector4(12, 8, 12, 8)) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = border
	s.set_border_width_all(1)
	s.set_corner_radius_all(radius)
	s.content_margin_left = margins.x
	s.content_margin_top = margins.y
	s.content_margin_right = margins.z
	s.content_margin_bottom = margins.w
	s.anti_aliasing = true
	return s


## A corner pill lifted off whatever's under it (carpet, a wall, a wall's edge) by a soft shadow.
static func _lifted(s: StyleBoxFlat) -> StyleBoxFlat:
	s.shadow_color = Color(0, 0, 0, 0.45)
	s.shadow_size = 8
	s.shadow_offset = Vector2(0, 2)
	return s


func _light_jackpot(lit: bool) -> void:
	_jackpot.add_theme_stylebox_override("panel", _box(Color(0.086, 0.063, 0.027, 0.93), BRASS_HI if lit else Color(BRASS, 0.6), 12, Vector4(16, 8, 16, 9)))
	_jackpot_in.visible = lit


# ------------------------------------------------------------------ fed by the HUD
## The table's chips (pence), drawn in `design` (its table style; {} for the game's own chips, as Roulette and Craps).
func set_chips(values: Array, selected: int, design: Dictionary) -> void:
	for c in _chips.get_children():
		c.queue_free()
	selected_chip = selected
	for i in values.size():
		var chip := BarChip.new()
		chip.value = int(values[i])
		chip.design = design
		chip.tooltip_text = "%s  ·  key %d" % [Money.format(int(values[i]), true), i + 1]
		chip.pressed.connect(pick.bind(int(values[i])))
		_chips.add_child(chip)
	_mark_chips()


## Picks a chip (a click on it, or its key).
func pick(value: int) -> void:
	if value == selected_chip:
		return
	selected_chip = value
	_mark_chips()
	chip_picked.emit(value)


func chip_values() -> Array:
	return _chips.get_children().filter(func(c): return not c.is_queued_for_deletion()).map(func(c): return c.value)


func _mark_chips() -> void:
	for c in _chips.get_children():
		c.selected = c.value == selected_chip


func set_auto(on: bool) -> void:
	_auto.set_pressed_no_signal(on)
	_auto.queue_redraw()


func auto_on() -> bool:
	return _auto.button_pressed


func set_sit_out(on: bool) -> void:
	_sit_out.set_pressed_no_signal(on)
	_sit_out.queue_redraw()


func close_paytable() -> void:
	_pay.set_pressed_no_signal(false)
	_pay.queue_redraw()


## What the bar offers right now (the floor's _seated_view): can_bet, can_ready, can_undo, has_bets, can_rebet,
## is_ready, sit_out, actions ([{id, label, key?, place?, pressed?}]; place "commit" goes beside the chips on the
## left, "switch" is a switch on the right, anything else is a decision in the chips' place), info, hand, hide,
## timer (0-1, or -1 for none), on_felt, title, seats, jackpot (or -1), jackpot_mine.
func update_view(s: Dictionary) -> void:
	var can_bet: bool = s.get("can_bet", false)
	var actions: Array = s.get("actions", [])
	var hide: Array = s.get("hide", [])
	var decisions := actions.filter(func(a): return not a.get("place", "") in ["commit", "switch"])
	var deciding := not decisions.is_empty()
	_build_actions(actions)
	_chips.visible = not deciding
	_decide.visible = deciding
	for c in _chips.get_children():
		c.disabled = not can_bet
		c.short = can_bet and c.value > Session.shown_balance
	# the right: Undo, Clear, the Auto rebet and Sit out switches
	_tools.visible = not deciding
	_undo.disabled = not s.get("can_undo", false)
	var has_bets: bool = s.get("has_bets", false)
	_clear.disabled = not (can_bet and has_bets)
	_auto.visible = not "auto_rebet" in hide
	_sit_out.visible = not "ready" in hide and s.get("sit_out", true)
	# the left: Ready (Repeat Bet until you've bet, once there's a last round to repeat), or the table's own commit
	# buttons (Craps' dice)
	var is_ready: bool = s.get("is_ready", false)
	var repeat: bool = can_bet and not has_bets and not is_ready and s.get("can_rebet", false) and not "rebet" in hide
	_ready_btn.visible = not "ready" in hide and not deciding and (s.get("can_ready", false) or is_ready or repeat)
	if is_ready:
		_ready_btn.setup("Ready" if has_bets else "Sitting out", "", "done")
		_ready_btn.disabled = true
	elif repeat:
		_ready_btn.setup("Repeat Bet", "Space", "normal")
		_ready_btn.tooltip_text = "Put last round's bets down again"
		_ready_btn.disabled = false
	else:
		_ready_btn.setup("Ready", "Space", "primary" if has_bets else "quiet")
		_ready_btn.tooltip_text = ""
		_ready_btn.disabled = not has_bets
	# the left: the table, its seats, what's on the felt
	_title.text = str(s.get("title", ""))
	_seats.text = str(s.get("seats", ""))
	_seats.visible = _seats.text != ""
	var felt := int(s.get("on_felt", 0))
	_felt_amount.text = Money.format(felt, true)
	_felt.modulate.a = 1.0 if felt > 0 else 0.0
	# the line above the chips, and its countdown
	_info.text = "[center]%s[/center]" % format_info(str(s.get("info", "")), str(s.get("hand", "")))
	var t := float(s.get("timer", -1.0))
	_timer.visible = t >= 0.0
	if t >= 0.0:
		_timer_fill.size.x = _timer.size.x * clampf(t, 0.0, 1.0)
		_timer_fill.color = WARN if s.get("timer_low", false) else BRASS_HI
	# top left: the jackpot
	var jp := float(s.get("jackpot", -1.0))
	_jackpot.visible = jp > 0.0
	if jp > 0.0:
		_jackpot_amount.text = Money.format(int(jp))
		var mine: bool = s.get("jackpot_mine", false)
		if mine != _jackpot_in.visible:
			_light_jackpot(mine)
	_layout()


## A game's line for the bar: its " -- " joins become dots, a countdown at the end ("-- 9s") turns gold, «x» is gold,
## and your hand's name leads in paper white. Square brackets are the game's own text, not markup.
static func format_info(info: String, hand := "") -> String:
	var s := info.replace("[", "[lb]")
	var tail := RegEx.create_from_string("\\s*--\\s*(\\d+)s$")
	s = tail.sub(s, "  ·  «$1»")
	s = s.replace(" -- ", "  ·  ").replace("...", "…")
	s = s.replace("«", "[color=#%s]" % BRASS_HI.to_html(false)).replace("»", "[/color]")
	if hand != "":
		s = "[color=#%s]%s[/color]%s" % [PAPER.to_html(false), hand.replace("[", "[lb]"), "  ·  " + s if s != "" else ""]
	return s


## The action buttons, rebuilt only when what's on offer changes.
func _build_actions(actions: Array) -> void:
	var sig := JSON.stringify(actions)
	if sig == _shown:
		return
	_shown = sig
	for box in [_decide]:
		for c in box.get_children():
			c.queue_free()
	for c in _commit.get_children():
		if c != _ready_btn:
			c.queue_free()
	for c in _tools.get_children():
		if c is BarSwitch and c != _auto:
			c.queue_free()
	for a in actions:
		var place: String = a.get("place", "")
		var words := str(a.label)
		var key := str(a.get("key", ""))
		var m := RegEx.create_from_string("\\s*\\[(.+)\\]\\s*$").search(words)   # ("Play £25  [P]": the key goes in its box)
		if m:
			words = words.substr(0, m.get_start()).strip_edges()
		if place == "switch":
			var sw := BarSwitch.new()
			sw.words = RegEx.create_from_string("\\s*\\[.*$").sub(words, "")
			sw.tooltip_text = "%s  (%s)" % [sw.words, key] if key != "" else sw.words
			sw.set_pressed_no_signal(bool(a.get("pressed", false)))
			sw.toggled.connect(func(_on): action.emit(str(a.id)))
			_tools.add_child(sw)
			continue
		var b := BarButton.new()
		var kind: String = a.get("kind", "")
		if kind == "":
			kind = "done" if a.get("pressed", false) else ("primary" if place == "commit" else _decision_kind(str(a.id)))
		b.setup(words, key if not a.get("pressed", false) else "", kind)
		b.pressed.connect(action.emit.bind(str(a.id)))
		if place == "commit":
			_commit.add_child(b)
			_commit.move_child(b, _ready_btn.get_index())
		else:
			_decide.add_child(b)


## A decision's look: folding outlined in red, Play (Stand, Let it ride, Insurance) in brass, the rest plain.
static func _decision_kind(id: String) -> String:
	if id in ["fold", "no_insurance"]:
		return "fold"
	return "primary" if id in ["play", "stand", "ride", "insure"] else "normal"


# ------------------------------------------------------------------ layout
func _process(_delta: float) -> void:
	if visible:
		_layout()


func _layout() -> void:
	var vs := get_viewport_rect().size
	if vs.x <= 0:
		return
	var narrow := vs.x < 1180.0
	var phone := vs.x < 700.0
	_undo.compact = narrow
	_clear.compact = narrow
	for b in _commit.get_children():
		if b is BarButton:
			b.hide_key = narrow
	for c in _chips.get_children():
		c.custom_minimum_size = Vector2.ONE * (CHIP_PHONE if phone else CHIP)
	var info_h := maxf(22.0, _info.get_content_height())
	var block_h := info_h + 10.0   # the line, then its timer
	var row_h := (CHIP_PHONE if phone else CHIP)
	var centre: Control = _decide if _decide.visible else _chips
	var cs := centre.get_combined_minimum_size()
	var commit := _commit.get_combined_minimum_size()
	var tools := _tools.get_combined_minimum_size()
	var wallet := _where.get_combined_minimum_size()
	wallet.x = maxf(wallet.x, _natural_width(_title))
	var base_h: float
	if phone:
		base_h = PAD_TOP + block_h + 14.0 + row_h + 12.0 + tools.y + 14.0 + maxf(commit.y, wallet.y) + PAD_BOTTOM
	else:
		base_h = PAD_TOP + block_h + ROW_GAP + maxf(row_h, cs.y) + PAD_BOTTOM
	var top := vs.y - base_h
	bar_top = top
	_fade.position = Vector2(0, top)
	_fade.size = Vector2(vs.x, base_h)
	_fade_texture(base_h)
	var info_w := minf(vs.x - 40.0, 1000.0)
	_info.size = Vector2(info_w, info_h)
	_info.position = Vector2((vs.x - info_w) / 2.0, top + PAD_TOP)
	_timer.position = Vector2((vs.x - _timer.size.x) / 2.0, top + PAD_TOP + info_h + 7.0)
	var row_y := top + PAD_TOP + block_h + (14.0 if phone else ROW_GAP)
	var mid := row_y + maxf(row_h, cs.y) / 2.0
	_place(centre, Vector2((vs.x - cs.x) / 2.0, mid - cs.y / 2.0), cs)
	var chips_w := _chips.get_combined_minimum_size().x
	var left := (vs.x - chips_w) / 2.0
	if phone:
		var tools_y := row_y + row_h + 12.0
		_place(_tools, Vector2((vs.x - tools.x) / 2.0, tools_y), tools)
		var foot := tools_y + tools.y + 14.0
		wallet.x = minf(wallet.x, vs.x - 16.0 - commit.x - 12.0 - 16.0)
		_place(_where, Vector2(16, foot + (maxf(commit.y, wallet.y) - wallet.y) / 2.0), wallet)
		_place(_commit, Vector2(vs.x - 16.0 - commit.x, foot), commit)
	else:
		_place(_commit, Vector2(left - SIDE_GAP - commit.x, mid - commit.y / 2.0), commit)
		_place(_tools, Vector2(left + chips_w + SIDE_GAP, mid - tools.y / 2.0), tools)
		var commit_left := left - SIDE_GAP - commit.x if commit.x > 0 else left
		wallet.x = minf(wallet.x, commit_left - 22.0 - 16.0)   # a long table name trims rather than run under Ready
		_place(_where, Vector2(22, top + PAD_TOP + (base_h - PAD_TOP - PAD_BOTTOM - wallet.y) / 2.0), wallet)
	var corner := _corner.get_combined_minimum_size()
	_place(_corner, Vector2(vs.x - right_inset - corner.x, 12), corner)
	_jackpot.size = Vector2.ZERO


## A label's width with nothing trimmed (its minimum shrinks to the ellipsis once it may trim).
static func _natural_width(l: Label) -> float:
	return FONT.get_string_size(l.text, HORIZONTAL_ALIGNMENT_LEFT, -1, l.get_theme_font_size("font_size")).x


func _place(c: Control, at: Vector2, sz: Vector2) -> void:
	c.position = at.round()
	c.size = sz


var _fade_for := -1.0
## The fade: clear to dark over its first 26 pixels, then near-solid to the foot of the screen.
func _fade_texture(h: float) -> void:
	if is_equal_approx(h, _fade_for):
		return
	_fade_for = h
	var g := Gradient.new()
	g.set_offset(0, 0.0)
	g.set_color(0, Color(0.031, 0.039, 0.043, 0.0))
	g.set_offset(1, 1.0)
	g.set_color(1, Color(0.031, 0.039, 0.043, 0.94))
	g.add_point(clampf(26.0 / h, 0.01, 0.99), Color(0.031, 0.039, 0.043, 0.9))
	var tex := GradientTexture2D.new()
	tex.gradient = g
	tex.fill_from = Vector2(0, 0)
	tex.fill_to = Vector2(0, 1)
	tex.width = 4
	tex.height = 256
	_fade.texture = tex


# ------------------------------------------------------------------ the pieces
## A chip in the bar: the table's own, lifting with a gold ring when it's the one picked.
class BarChip extends Button:
	var value := 100
	var design := {}
	var selected := false:
		set(v):
			selected = v
			queue_redraw()
	var short := false:   # more than you have left: dimmed
		set(v):
			if v != short:
				short = v
				queue_redraw()

	func _init() -> void:
		flat = true
		focus_mode = FOCUS_NONE
		custom_minimum_size = Vector2(CHIP, CHIP)
		mouse_entered.connect(queue_redraw)
		mouse_exited.connect(queue_redraw)
		mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND

	func _draw() -> void:
		var r := minf(size.x, size.y) / 2.0
		var lift := 0.0
		if not disabled:
			lift = -6.0 if selected else (-2.5 if is_hovered() else 0.0)
		var centre := size / 2.0 + Vector2(0, lift)
		var dim := 0.35 if disabled or short else 1.0
		if modulate.a != dim:
			modulate.a = dim
		if selected and not disabled:
			draw_circle(centre, r + 7.0, Color(BRASS_HI, 0.12))
			draw_arc(centre, r + 4.0, 0, TAU, 48, BRASS_HI, 2.0, true)
		ChipFace.draw(self, centre, r, value, str(value / 100), design)


## A button in the bar's look: its words, an optional key in a box, an optional drawn glyph. Kinds: primary (brass),
## normal, quiet, fold (red edge), done (a gold outline), tool (a small pill, Undo/Clear), ghost (the corners).
class BarButton extends Button:
	const WIDE := 1.4     # letter spacing on the big buttons' capitals
	var words := ""
	var key := ""
	var kind := "normal"
	var glyph := ""
	var compact := false:   # just the glyph (a tool on a narrow screen)
		set(v):
			if v != compact:
				compact = v
				_size()
	var hide_key := false:
		set(v):
			if v != hide_key:
				hide_key = v
				_size()
	var _font: FontVariation

	func _init() -> void:
		focus_mode = FOCUS_NONE
		text = ""
		mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		mouse_entered.connect(queue_redraw)
		mouse_exited.connect(queue_redraw)

	func setup(w: String, k: String, kd: String, g := "") -> void:
		if w == words and k == key and kd == kind and g == glyph:
			return
		words = w
		key = k
		kind = kd
		glyph = g
		var big := kind in ["primary", "normal", "quiet", "fold", "done"]
		_font = FontVariation.new()
		_font.base_font = FONT
		_font.spacing_glyph = int(WIDE) if big else 0
		var radius := 10 if big else 999
		var bg: Color = {"primary": BRASS, "normal": Color("232a2d"), "quiet": Color(0.137, 0.165, 0.176, 0.85), "fold": Color("232a2d"),
			"done": Color(0.055, 0.047, 0.031, 0.6), "tool": Color(0.137, 0.165, 0.176, 0.85), "ghost": CORNER_BG}[kind]
		var edge: Color = {"primary": BRASS, "normal": Color("39413f"), "quiet": Color("39413f"), "fold": Color(LOSS, 0.55),
			"done": Color(BRASS, 0.45), "tool": Color("39413f"), "ghost": Color(1, 1, 1, 0.1)}[kind]
		var hover_edge := Color(BRASS, 0.7) if kind != "primary" else BRASS
		var hover_bg: Color = Color("d6b05a") if kind == "primary" else bg
		var box := func(b: Color, e: Color) -> StyleBoxFlat:
			var st := BettingBar._box(b, e, radius, Vector4.ZERO)
			return BettingBar._lifted(st) if kind == "ghost" else st
		add_theme_stylebox_override("normal", box.call(bg, edge))
		add_theme_stylebox_override("hover", box.call(hover_bg, hover_edge))
		add_theme_stylebox_override("pressed", box.call(hover_bg, hover_edge if kind != "ghost" else BRASS))
		add_theme_stylebox_override("hover_pressed", box.call(hover_bg, BRASS))
		add_theme_stylebox_override("disabled", box.call(bg, edge))
		add_theme_stylebox_override("focus", StyleBoxEmpty.new())
		_size()
		queue_redraw()

	func _font_size() -> int:
		return {"tool": 15, "ghost": 16}.get(kind, 19)

	func _shown_words() -> String:
		return words.to_upper() if kind in ["primary", "normal", "quiet", "fold", "done"] else words

	func _key_w() -> float:
		return 0.0 if key == "" or hide_key else FONT.get_string_size(key.to_upper(), HORIZONTAL_ALIGNMENT_LEFT, -1, 12).x + 10.0

	func _size() -> void:
		var h: float = {"tool": 40.0, "ghost": 40.0}.get(kind, BUTTON_H)
		var pad: float = {"tool": 14.0, "ghost": 15.0}.get(kind, 24.0)
		var w := 0.0
		if glyph != "":
			w += 17.0
		if not (compact and glyph != ""):
			w += _font.get_string_size(_shown_words(), HORIZONTAL_ALIGNMENT_LEFT, -1, _font_size()).x + (8.0 if glyph != "" else 0.0)
			if _key_w() > 0:
				w += 9.0 + _key_w()
		else:
			pad = (h - 17.0) / 2.0
		custom_minimum_size = Vector2(w + pad * 2.0, h)
		update_minimum_size()

	func _colour() -> Color:
		return {"primary": Color("1b1307"), "quiet": INK, "done": BRASS_HI}.get(kind, INK)

	func _draw() -> void:
		var dim := 0.4 if disabled else 1.0
		if modulate.a != dim:
			modulate.a = dim
		var col := _colour()
		if kind == "ghost" and button_pressed:
			col = BRASS_HI
		var fs := _font_size()
		var show_words := not (compact and glyph != "")
		var tw := _font.get_string_size(_shown_words(), HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x if show_words else 0.0
		var total := (17.0 if glyph != "" else 0.0) + (8.0 if glyph != "" and show_words else 0.0) + tw + (9.0 + _key_w() if show_words and _key_w() > 0 else 0.0)
		var x := (size.x - total) / 2.0
		var mid := size.y / 2.0
		if glyph != "":
			_draw_glyph(Vector2(x + 8.5, mid), col)
			x += 17.0 + (8.0 if show_words else 0.0)
		if show_words:
			var asc := _font.get_ascent(fs)
			var desc := _font.get_descent(fs)
			draw_string(_font, Vector2(x, mid + (asc - desc) / 2.0 - 1.0), _shown_words(), HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col)
			x += tw
			if _key_w() > 0:
				x += 9.0
				var kc := Color(col, 0.6)
				var r := Rect2(x, mid - 9.0, _key_w(), 18.0)
				draw_style_box(BettingBar._box(Color(0, 0, 0, 0), kc, 4, Vector4.ZERO), r)
				var ka := FONT.get_ascent(12)
				draw_string(FONT, Vector2(x + 5.0, mid + (ka - FONT.get_descent(12)) / 2.0 - 0.5), key.to_upper(), HORIZONTAL_ALIGNMENT_LEFT, -1, 12, kc)

	func _draw_glyph(c: Vector2, col: Color) -> void:
		match glyph:
			"undo":
				draw_arc(c + Vector2(1.5, 1.5), 5.0, -PI / 2.0, PI / 2.0, 12, col, 1.8, true)
				draw_line(c + Vector2(1.5, -3.5), c + Vector2(-5, -3.5), col, 1.8, true)
				draw_line(c + Vector2(1.5, 6.5), c + Vector2(-1.5, 6.5), col, 1.8, true)
				draw_polyline(PackedVector2Array([c + Vector2(-2, -7), c + Vector2(-5.5, -3.5), c + Vector2(-2, 0)]), col, 1.8, true)
			"rebet":
				draw_arc(c, 6.0, -PI * 0.2, PI * 1.55, 20, col, 1.8, true)
				draw_polyline(PackedVector2Array([c + Vector2(6.5, -7.5), c + Vector2(6.5, -3.0), c + Vector2(2.0, -3.0)]), col, 1.8, true)
			"clear":
				draw_line(c + Vector2(-5, -5), c + Vector2(5, 5), col, 1.8, true)
				draw_line(c + Vector2(5, -5), c + Vector2(-5, 5), col, 1.8, true)
			"paytable":
				draw_style_box(BettingBar._box(Color(0, 0, 0, 0), col, 2, Vector4.ZERO), Rect2(c - Vector2(6, 7), Vector2(12, 14)))
				for y in [-3.0, 0.5, 4.0]:
					draw_line(c + Vector2(-3, y), c + Vector2(3 if y < 3 else 1, y), col, 1.4, true)
			"settings":
				draw_arc(c, 5.0, 0, TAU, 24, col, 1.8, true)
				draw_circle(c, 1.8, col)
				for i in 8:
					var d := Vector2.from_angle(i * TAU / 8.0)
					draw_line(c + d * 5.5, c + d * 8.0, col, 2.4, true)
			"stand":
				draw_polyline(PackedVector2Array([c + Vector2(-2, -7), c + Vector2(-6.5, -7), c + Vector2(-6.5, 7), c + Vector2(-2, 7)]), col, 1.6, true)
				draw_line(c + Vector2(-2, 0), c + Vector2(7, 0), col, 1.6, true)
				draw_polyline(PackedVector2Array([c + Vector2(3.5, -3.5), c + Vector2(7, 0), c + Vector2(3.5, 3.5)]), col, 1.6, true)


## A small on/off switch with its name beside it (Auto rebet, Sit out, Craps' Working).
class BarSwitch extends Button:
	var words := "Auto"

	func _init() -> void:
		toggle_mode = true
		flat = true
		focus_mode = FOCUS_NONE
		mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		toggled.connect(func(_on): queue_redraw())
		custom_minimum_size = Vector2(0, 40)

	func _notification(what: int) -> void:
		if what == NOTIFICATION_READY or what == NOTIFICATION_THEME_CHANGED:
			custom_minimum_size.x = 8.0 + 26.0 + 7.0 + FONT.get_string_size(words.to_upper(), HORIZONTAL_ALIGNMENT_LEFT, -1, 13).x + words.length() * 1.6 + 10.0

	func _draw() -> void:
		var on := button_pressed
		var mid := size.y / 2.0
		var track := Rect2(8, mid - 7, 26, 14)
		draw_style_box(BettingBar._box(Color("5a4920") if on else Color("2b3133"), Color(0, 0, 0, 0), 7, Vector4.ZERO), track)
		draw_circle(Vector2(track.position.x + (19.0 if on else 7.0), mid), 5.0, BRASS_HI if on else MUTED)
		var col := BRASS_HI if on else MUTED
		var x := 41.0
		for ch in words.to_upper():
			draw_string(FONT, Vector2(x, mid + (FONT.get_ascent(13) - FONT.get_descent(13)) / 2.0 - 0.5), ch, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, col)
			x += FONT.get_string_size(ch, HORIZONTAL_ALIGNMENT_LEFT, -1, 13).x + 1.6
