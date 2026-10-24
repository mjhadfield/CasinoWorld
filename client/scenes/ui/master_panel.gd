class_name MasterPanel
extends Control
## What a Master Table puts on the HUD while you sit at it (server tables/master.py; signed off on the mockup,
## docs/master_table/mockup/): the dealer's menu of games, each with a picture of its layout in the table's style
## (keys 1-9 pick one, Esc closes it); the card asking you to agree when someone else asks for a game; and the pill
## saying which game comes after this hand, with ✕ to stay on this one. The floor opens and closes them and sends
## what's chosen.

signal chosen(game: String)
signal voted(accept: bool)
signal cancel_queued

## The games, in the menu's order (the server's master.GAMES), with what the menu says about each.
const GAMES := [
	["three_card_poker", "Three Card Poker", "Beat the dealer's three cards. Pair Plus and Prime pay on your hand alone."],
	["blackjack", "Blackjack", "Get closer to 21 than the dealer. Pays 3 to 2, with four side bets."],
	["pai_gow_fortune", "Fortune Pai Gow", "Set seven cards into a low two and a high five. 5% commission."],
	["pai_gow_face_up", "Face Up Pai Gow", "The dealer's hand is shown before you set yours. No commission."],
	["mississippi_stud", "Mississippi Stud", "Two cards and three to come. Raise up to 3x on each street."],
	["ultimate_texas_holdem", "Ultimate Texas Hold'em", "Hold'em against the dealer. Bet big early or check to the river."],
	["let_it_ride", "Let It Ride", "Three equal bets, and you can pull two of them back. Tens or better pays."],
	["high_card_flush", "High Card Flush", "Seven cards: the longest flush wins. Raise on five or more."],
	["baccarat", "Baccarat", "Back the Player, the Banker or a Tie. No decisions to make."],
]
const FIVE_SEATS := ["let_it_ride", "high_card_flush"]
const GOLD := Color("ecd396")
const MUTED := Color("9ba39e")
const WARN := Color("f2c14e")
const THUMB := Rect2(-166, -150, 332, 160)   # what a menu picture shows of a table, in its coordinates
const THUMB_PPU := 0.66

var _menu: PanelContainer
var _scroll: ScrollContainer
var _title: Label
var _sub: Label
var _rows := {}        # game -> {button, tags}
var _vote: PanelContainer
var _vote_text: Label
var _vote_buttons: Array = []
var _vote_until := 0.0
var _vote_line := ""
var _queued: PanelContainer
var _queued_text: Label
var _thumbs := {}      # table id -> {game: Texture2D}
var _thumbs_for := ""


static func name_of(game: String) -> String:
	for g in GAMES:
		if g[0] == game:
			return g[1]
	return "Master Table"


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = MOUSE_FILTER_IGNORE
	_build_menu()
	_build_vote()
	_build_queued()


func _panel(bg: Color, border: Color) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = border
	s.set_border_width_all(1)
	s.set_corner_radius_all(10)
	s.set_content_margin_all(12)
	return s


func _label(text: String, size: int, colour: Color, font: Font = null) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", colour)
	if font:
		l.add_theme_font_override("font", font)
	return l


# ------------------------------------------------------------------ the dealer's menu
func _build_menu() -> void:
	_menu = PanelContainer.new()
	UiKit.make_card(_menu, Vector4(16, 14, 16, 14))
	_menu.position = Vector2(16, 64)
	_menu.custom_minimum_size = Vector2(400, 0)
	_menu.hide()
	add_child(_menu)
	# (Nothing sizes the panel but itself, and a size only ever grows to fit: on the first open its wrapped lines are
	# measured before they've had a width, so it comes out too tall. Shrink it back as they settle.)
	_menu.minimum_size_changed.connect(func():
		if _menu.visible:
			_menu.size = Vector2.ZERO)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 8)
	_menu.add_child(box)
	_title = _label("What would you like to play?", 20, GOLD, TableStyle.FONTS.cinzel)
	box.add_child(_title)
	_sub = _label("", 14, MUTED)
	_sub.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(_sub)
	box.add_child(HSeparator.new())
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.custom_minimum_size = Vector2(0, 300)
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	box.add_child(scroll)
	_scroll = scroll
	var list := VBoxContainer.new()
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_theme_constant_override("separation", 2)
	scroll.add_child(list)
	for i in GAMES.size():
		list.add_child(_row(i))
	var foot := HBoxContainer.new()
	foot.add_child(_label("Keys 1-9 pick a game", 13, MUTED))
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	foot.add_child(spacer)
	var close := UiKit.button("Not now", "Esc", "ghost")
	close.pressed.connect(close_menu)
	foot.add_child(close)
	box.add_child(foot)


func _row(i: int) -> Button:
	var g: Array = GAMES[i]
	var b := Button.new()
	b.flat = true
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size = Vector2(0, 80)
	b.add_theme_stylebox_override("hover", _panel(Color(0.79, 0.64, 0.29, 0.1), Color(0.79, 0.64, 0.29, 0.45)))
	b.pressed.connect(func(): _pick(str(g[0])))
	var row := HBoxContainer.new()
	row.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_MINSIZE, 6)
	row.add_theme_constant_override("separation", 12)
	row.mouse_filter = MOUSE_FILTER_IGNORE
	b.add_child(row)
	var thumb := TextureRect.new()
	thumb.custom_minimum_size = Vector2(110, 54)
	thumb.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	thumb.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	thumb.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	thumb.mouse_filter = MOUSE_FILTER_IGNORE
	row.add_child(thumb)
	var text := VBoxContainer.new()
	text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	text.add_theme_constant_override("separation", 1)
	text.mouse_filter = MOUSE_FILTER_IGNORE
	row.add_child(text)
	var name := _label("%s   %d" % [g[1], i + 1], 16, Color("ece4d2"), TableStyle.FONTS.cinzel)
	text.add_child(name)
	var blurb := _label(str(g[2]), 12, MUTED)
	blurb.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	blurb.custom_minimum_size = Vector2(250, 0)
	text.add_child(blurb)
	var tags := _label("", 11, GOLD)
	text.add_child(tags)
	for n in [name, blurb, tags]:
		n.mouse_filter = MOUSE_FILTER_IGNORE
	_rows[g[0]] = {"button": b, "tags": tags, "thumb": thumb}
	return b


## Open the menu at table `table_id`: `current` is the game being played ("" at the blank table); `full`, whether
## every seat's taken (a six-seat game moving to a five-seat one needs one free); `note`, a line under the title.
func open_menu(table_id: String, current: String, full: bool, note: String, warn := false) -> void:
	_title.text = "What would you like to play?" if current == "" else "Change the game"
	_sub.text = note
	_sub.add_theme_color_override("font_color", WARN if warn else MUTED)
	var five_now: bool = current in FIVE_SEATS   # (already five seats: another five-seat game loses no one)
	for g in GAMES:
		var r: Dictionary = _rows[g[0]]
		var five: bool = g[0] in FIVE_SEATS
		var blocked := five and full and not five_now
		r.button.disabled = g[0] == current or blocked
		r.button.modulate.a = 0.45 if r.button.disabled and g[0] != current else 1.0
		var tags := []
		if g[0] == current:
			tags.append("PLAYING NOW")
		if five:
			tags.append("NEEDS A FREE SEAT" if blocked else "SEATS FIVE")
		r.tags.text = "  ·  ".join(tags)
		r.tags.add_theme_color_override("font_color", WARN if blocked else GOLD)
		r.tags.visible = not tags.is_empty()
	_show_thumbs(table_id)
	_menu.size = Vector2.ZERO
	var room := get_viewport_rect().size
	_scroll.custom_minimum_size.y = clampf(room.y - 400, 140, 700)   # (clear of the top bar and the seated bar)
	_menu.show()


func close_menu() -> void:
	_menu.hide()


func menu_open() -> bool:
	return _menu.visible


func _pick(game: String) -> void:
	var r: Dictionary = _rows.get(game, {})
	if r.is_empty() or r.button.disabled:
		return
	close_menu()
	chosen.emit(game)


func _input(event: InputEvent) -> void:
	if not _menu.visible or not (event is InputEventKey and event.pressed and not event.echo):
		return
	if event.keycode == KEY_ESCAPE:
		close_menu()
		get_viewport().set_input_as_handled()
	elif event.keycode >= KEY_1 and event.keycode <= KEY_9:
		_pick(str(GAMES[event.keycode - KEY_1][0]))
		get_viewport().set_input_as_handled()


## Each game's layout, painted once in the table's style (a felt painter in a viewport, as FeltCache paints).
func _show_thumbs(table_id: String) -> void:
	if _thumbs.has(table_id):
		for g in _thumbs[table_id]:
			_rows[g].thumb.texture = _thumbs[table_id][g]
		return
	_thumbs[table_id] = {}
	var made := []
	for g in GAMES:
		var t: CasinoTable = PlanRoom.TABLE_SCENES[g[0]].instantiate()
		t.table_id = table_id
		if g[0] == "pai_gow_face_up":
			t.set("face_up", true)
		var felt: Node2D = t.get_node("Felt")
		var vp := SubViewport.new()
		vp.transparent_bg = true
		vp.disable_3d = true
		vp.size = Vector2i(ceili(THUMB.size.x * THUMB_PPU), ceili(THUMB.size.y * THUMB_PPU))
		vp.render_target_update_mode = SubViewport.UPDATE_ONCE
		var painter: TableFelt = felt.get_script().new()
		painter.painting = true
		painter.table_ref = t
		painter.position = felt.position
		painter.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
		vp.add_child(painter)
		add_child(vp)
		vp.canvas_transform = Transform2D(0.0, Vector2(THUMB_PPU, THUMB_PPU), 0.0, -THUMB.position * THUMB_PPU)
		made.append([g[0], vp, t])
	await RenderingServer.frame_post_draw
	for m in made:
		var tex := ImageTexture.create_from_image(m[1].get_texture().get_image())
		_thumbs[table_id][m[0]] = tex
		_rows[m[0]].thumb.texture = tex
		m[1].queue_free()
		m[2].queue_free()


# ------------------------------------------------------------------ asking you to agree
func _build_vote() -> void:
	_vote = PanelContainer.new()
	UiKit.make_card(_vote, Vector4(18, 10, 10, 10))
	_vote.hide()
	add_child(_vote)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	_vote.add_child(row)
	_vote_text = UiKit.text("", 18)
	_vote_text.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(_vote_text)
	for pair in [["Switch", true, "primary"], ["Keep playing", false, "normal"]]:
		var b := UiKit.button(pair[0], "", pair[2])
		b.pressed.connect(func():
			hide_vote()
			voted.emit(pair[1]))
		row.add_child(b)
		_vote_buttons.append(b)


## Someone's asked for a game: `line` says so (with %d for the seconds left); `answer` shows Switch and Keep playing.
func show_vote(line: String, seconds: float, answer: bool) -> void:
	_vote_line = line
	_vote_until = Time.get_ticks_msec() / 1000.0 + seconds
	for b in _vote_buttons:
		b.visible = answer
	_vote.show()
	_tick_vote()


func hide_vote() -> void:
	_vote.hide()


func _tick_vote() -> void:
	var left := ceili(maxf(0.0, _vote_until - Time.get_ticks_msec() / 1000.0))
	_vote_text.text = _vote_line % left if "%d" in _vote_line else _vote_line
	_vote.size = Vector2.ZERO
	_stack()


# ------------------------------------------------------------------ the next game
func _build_queued() -> void:
	_queued = PanelContainer.new()
	var s := UiKit.strip_style(20)
	s.content_margin_top = 4
	s.content_margin_bottom = 4
	_queued.add_theme_stylebox_override("panel", s)
	_queued.hide()
	add_child(_queued)
	var row := HBoxContainer.new()
	_queued.add_child(row)
	_queued_text = UiKit.text("", 17)
	_queued_text.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(_queued_text)
	var x := Button.new()
	x.text = "✕"
	x.flat = true
	x.focus_mode = Control.FOCUS_NONE
	x.tooltip_text = "Stay on this game"
	x.add_theme_color_override("font_color", UiKit.MUTED)
	x.add_theme_color_override("font_hover_color", UiKit.BRASS_HI)
	x.pressed.connect(cancel_queued.emit)
	row.add_child(x)


## The game agreed on for after this hand ("" when there's none).
func show_queued(game: String) -> void:
	_queued.visible = game != ""
	if game == "":
		return
	_queued_text.text = "After this hand: %s" % name_of(game)
	_queued.size = Vector2.ZERO
	_stack()


## The pill and the vote card, centred just above the betting bar (the pill nearer it).
func _stack() -> void:
	var room := get_viewport_rect().size
	var hud := get_parent()
	var y: float = hud.bar.bar_top if hud and "bar" in hud and hud.bar and hud.bar.visible and hud.bar.bar_top > 0 else room.y - 170.0
	y -= 8.0
	for p in [_queued, _vote]:
		if p.visible:
			p.position = Vector2(round((room.x - p.size.x) / 2.0), round(y - p.size.y))
			y -= p.size.y + 8.0


func close_all() -> void:
	close_menu()
	hide_vote()
	show_queued("")


func _process(_delta: float) -> void:
	if _vote.visible:
		_tick_vote()
	elif _queued.visible:
		_stack()
