class_name FrontDoor
extends Control
## The way in: over the floor before you're on it. While connecting it's the loading screen; then the character
## select (up to Session.max_characters cards: Play, Edit, Delete, and New while there's room); then the designer
## for a new character (name, difficulty, look) or a change to one (name, look). Making a character takes you
## straight in as it. On the floor, clicking your name and cash (the wallet) opens the select again to switch
## character (`open_switch`), with Close; switching is only offered on foot.
##
## It follows Session: shown whenever you're not on the floor (and not previewing the floor plan), hidden once a
## `welcome` puts you there.

const TITLE_FONT := preload("res://assets/fonts/Cinzel-SemiBold.ttf")
const CARD := Vector2(240, 360)
const DIFFICULTY := [["easy", "Easy"], ["normal", "Normal"], ["hard", "Hard"]]

var switching := false   # opened from the wallet, on the floor
var can_switch := true   # (not while seated or at a slot)
var _mode := "select"    # select | design (the loading screen is whenever there's nothing to choose from yet)
var _notice := ""        # over the cards: why you're back here
var _deleting := -1      # the card asking you to type its name
var _editing := -1       # design: the character being changed, or -1 for a new one
var _busy := false       # design: waiting for the server's answer
var _difficulty := "normal"
var _options := {}       # the designer's catalogue (LookLoader.options), once fetched
var _preview_seq := 0

var _bg: ColorRect
var _loading: VBoxContainer
var _status: Label
var _select: VBoxContainer
var _subtitle: Label
var _notice_label: Label
var _cards: HBoxContainer
var _select_foot: HBoxContainer
var _design: PanelContainer
var _design_title: Label
var _name_edit: LineEdit
var _difficulty_box: VBoxContainer
var _difficulty_buttons := {}
var _difficulty_note: Label
var _editor: LookEditor
var _preview: LookPreview
var _preview_idle: LookPreview
var _preview_note: Label
var _error: Label
var _save: BettingBar.BarButton
var _scroll: ScrollContainer
var _preview_timer: Timer


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_bg = ColorRect.new()
	add_child(_bg)
	_bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var centre := CenterContainer.new()
	add_child(centre)
	centre.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_loading = _build_loading()
	_select = _build_select()
	_design = _build_design()
	for v in [_loading, _select, _design]:   # (one shows at a time, in the middle)
		centre.add_child(v)
	_preview_timer = Timer.new()
	_preview_timer.one_shot = true
	_preview_timer.wait_time = 0.25
	_preview_timer.timeout.connect(_build_preview)
	add_child(_preview_timer)
	get_viewport().size_changed.connect(_fit)
	Net.connected.connect(_update)
	Net.disconnected.connect(_update)
	Net.message_received.connect(_on_message)
	Session.account_received.connect(_on_account)
	Session.joined.connect(func(_p):
		switching = false
		_mode = "select"
		_notice = ""
		_update())
	Session.character_left.connect(func(reason: String, character_name: String):
		switching = false
		_mode = "select"
		_notice = "You're playing %s in another window." % character_name if reason == "elsewhere" else ""
		_update())
	_fit()
	_update()


# ------------------------------------------------------------------ what shows
func _update() -> void:
	if Session.preview != "" or (Session.on_floor and not switching):
		hide()
		return
	show()
	_bg.color = Color(0.02, 0.025, 0.03, 0.82) if switching else Color(0.03, 0.035, 0.04, 1.0)
	var waiting := not Session.account_ready or Session.pending_pick >= 0
	_loading.visible = waiting
	_select.visible = not waiting and _mode == "select"
	_design.visible = not waiting and _mode == "design"
	if waiting:
		_status.text = ("Walking in..." if Session.pending_pick >= 0 else "Opening the doors...") if Net.is_open() else "Connecting..."
	elif _mode == "select":
		_fill_select()


## Opened from the wallet on the floor: the select, to switch to another character (`allowed`: you're on foot).
func open_switch(allowed: bool) -> void:
	if not Session.account_ready:
		return
	switching = true
	can_switch = allowed
	_mode = "select"
	_notice = ""
	_deleting = -1
	_update()


func close_switch() -> void:
	switching = false
	_update()


func _input(event: InputEvent) -> void:
	if not visible or not event.is_action_pressed("ui_cancel"):
		return
	if _mode == "design" and not _busy:
		_mode = "select"
		_update()
	elif switching:
		close_switch()
	else:
		return
	get_viewport().set_input_as_handled()


func _on_account() -> void:
	if _mode == "design" and _busy and _editing >= 0:   # a change saved
		_busy = false
		_mode = "select"
	_update()


func _on_message(msg: Dictionary) -> void:
	match msg.get("type"):
		"character_made":   # in as the new character
			_busy = false
			_mode = "select"
			if not Session.on_floor or can_switch:
				Session.pick(int(msg.id))
			_update()
		"error":
			if visible and _mode == "design" and _busy:
				_busy = false
				_show_error(str(msg.get("message", "")))


## Whether a server error belongs here (the floor leaves it to us instead of toasting it).
func takes_errors() -> bool:
	return visible and _mode == "design"


# ------------------------------------------------------------------ loading
func _build_loading() -> VBoxContainer:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 14)
	box.add_child(_title())
	_status = DoorUi.label("Connecting...", 22, DoorUi.MUTED)
	_status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(_status)
	return box


func _title() -> Label:
	var t := DoorUi.label("THE HADFIELD CASINO", 46, DoorUi.BRASS_HI)
	t.add_theme_font_override("font", TITLE_FONT)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	return t


# ------------------------------------------------------------------ the select
func _build_select() -> VBoxContainer:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 10)
	box.add_child(_title())
	_subtitle = DoorUi.label("", 22, DoorUi.MUTED)
	_subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(_subtitle)
	_notice_label = DoorUi.label("", 18, BettingBar.WARN)
	_notice_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(_notice_label)
	box.add_child(DoorUi.gap(10))
	_cards = HBoxContainer.new()
	_cards.alignment = BoxContainer.ALIGNMENT_CENTER
	_cards.add_theme_constant_override("separation", 18)
	box.add_child(_cards)
	box.add_child(DoorUi.gap(12))
	_select_foot = HBoxContainer.new()
	_select_foot.alignment = BoxContainer.ALIGNMENT_CENTER
	_select_foot.add_theme_constant_override("separation", 16)
	box.add_child(_select_foot)
	return box


func _fill_select() -> void:
	var playing := int(Session.player.get("id", -1)) if Session.on_floor else -1
	_subtitle.text = ("Switch character" if switching else "Choose your character") if not Session.characters.is_empty() else "Make a character to play as"
	_notice_label.text = _notice if _notice != "" else ("Stand up to switch character." if switching and not can_switch else "")
	_notice_label.visible = _notice_label.text != ""
	for c in _cards.get_children():
		c.queue_free()
	for c in Session.characters:
		_cards.add_child(_card(c, int(c.id) == playing))
	if Session.characters.size() < Session.max_characters:
		_cards.add_child(_new_card())
	for c in _select_foot.get_children():
		c.queue_free()
	if switching:
		var close := DoorUi.button("Close", "ghost", "Esc")
		close.pressed.connect(close_switch)
		_select_foot.add_child(close)
	else:
		var left := Session.max_characters - Session.characters.size()
		_select_foot.add_child(DoorUi.label("Up to %d characters, each with its own money." % Session.max_characters if left > 0 else "", 16, DoorUi.MUTED))


func _card_box(lit: bool) -> PanelContainer:
	var card := PanelContainer.new()
	card.custom_minimum_size = CARD
	card.add_theme_stylebox_override("panel", BettingBar._lifted(BettingBar._box(Color(0.055, 0.065, 0.07, 0.97),
		DoorUi.BRASS if lit else Color(DoorUi.BRASS, 0.3), 14, Vector4(16, 14, 16, 14))))
	return card


func _card(c: Dictionary, playing: bool) -> PanelContainer:
	var id := int(c.id)
	var card := _card_box(playing or (not switching and id == Session.last_character))
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 4)
	card.add_child(box)
	var pic := LookPreview.new()
	pic.look = str(c.get("look", "player_default"))
	pic.walking = false
	pic.custom_minimum_size = Vector2(0, 150)
	box.add_child(pic)
	card.mouse_entered.connect(func(): pic.walking = true)
	card.mouse_exited.connect(func(): pic.walking = false)
	var n := DoorUi.label(str(c.name), 28, DoorUi.INK)
	n.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	n.clip_text = true
	box.add_child(n)
	var level := DoorUi.label(str(c.get("difficulty", "normal")).to_upper(), 14, DoorUi.BRASS)
	level.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(level)
	var money := DoorUi.label("Cash %s   Bank %s" % [Money.format(int(c.get("balance", 0))), Money.format(int(c.get("bank", 0)))], 17, DoorUi.MUTED)
	money.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(money)
	var state := ""
	if playing:
		state = "Playing now"
	elif c.get("online", false):
		state = "On in another window"
	var st := DoorUi.label(state, 15, BettingBar.WIN if playing else BettingBar.WARN)
	st.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(st)
	var grow := Control.new()
	grow.size_flags_vertical = Control.SIZE_EXPAND_FILL
	box.add_child(grow)
	if id == _deleting:
		_delete_controls(box, c)
		return card
	var play := DoorUi.button("Back to the floor" if playing else "Play", "primary")
	play.disabled = not playing and switching and not can_switch
	play.pressed.connect(func():
		if playing:
			close_switch()
		else:
			Session.pick(id)
			_update())
	box.add_child(play)
	var lip_gap := Control.new()   # room for Play's lip
	lip_gap.custom_minimum_size.y = 4
	box.add_child(lip_gap)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 8)
	box.add_child(row)
	var edit := DoorUi.button("Edit", "ghost")
	edit.disabled = playing or c.get("online", false)
	edit.pressed.connect(func(): _open_design(id))
	row.add_child(edit)
	var del := DoorUi.button("Delete", "ghost")
	del.disabled = playing or c.get("online", false)
	del.pressed.connect(func():
		_deleting = id
		_fill_select())
	row.add_child(del)
	return card


## Deleting asks for the character's name to be typed, as it takes their money and history with it.
func _delete_controls(box: VBoxContainer, c: Dictionary) -> void:
	var ask := DoorUi.label("Type %s to delete them, their money and history, for good." % c.name, 15, BettingBar.LOSS)
	ask.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	ask.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(ask)
	var typed := DoorUi.text_box(str(c.name), 16)
	box.add_child(typed)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 8)
	box.add_child(row)
	var yes := DoorUi.button("Delete", "fold")
	yes.disabled = true
	typed.text_changed.connect(func(t: String): yes.disabled = t.strip_edges() != str(c.name))
	yes.pressed.connect(func():
		_deleting = -1
		Session.delete_character(int(c.id)))
	row.add_child(yes)
	var no := DoorUi.button("Keep", "ghost")
	no.pressed.connect(func():
		_deleting = -1
		_fill_select())
	row.add_child(no)
	typed.grab_focus.call_deferred()


func _new_card() -> PanelContainer:
	var card := _card_box(false)
	var b := Button.new()
	b.text = "+\nNew"
	b.focus_mode = Control.FOCUS_NONE
	b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	b.add_theme_font_override("font", DoorUi.FONT)
	b.add_theme_font_size_override("font_size", 34)
	b.add_theme_color_override("font_color", DoorUi.BRASS)
	b.add_theme_color_override("font_hover_color", DoorUi.BRASS_HI)
	for s in ["normal", "pressed", "focus"]:
		b.add_theme_stylebox_override(s, StyleBoxEmpty.new())
	b.add_theme_stylebox_override("hover", BettingBar._box(Color(DoorUi.BRASS, 0.06), Color(0, 0, 0, 0), 10, Vector4.ZERO))
	b.pressed.connect(func(): _open_design(-1))
	card.add_child(b)
	return card


# ------------------------------------------------------------------ the designer
func _build_design() -> PanelContainer:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", BettingBar._box(Color(0.04, 0.047, 0.05, 0.98), Color(DoorUi.BRASS, 0.55), 14, Vector4(24, 16, 24, 16)))
	var outer := VBoxContainer.new()
	outer.add_theme_constant_override("separation", 10)
	panel.add_child(outer)
	_design_title = DoorUi.label("NEW CHARACTER", 26, DoorUi.BRASS_HI)
	outer.add_child(_design_title)
	var cols := HBoxContainer.new()
	cols.add_theme_constant_override("separation", 24)
	outer.add_child(cols)

	var left := VBoxContainer.new()   # (narrower than the previews' frames, whose sides are empty)
	left.custom_minimum_size.x = 200
	left.add_theme_constant_override("separation", 6)
	cols.add_child(left)
	_preview = LookPreview.new()
	_preview.fill_height = true
	_preview.custom_minimum_size = Vector2(200, 256)
	left.add_child(_preview)
	_preview_idle = LookPreview.new()
	_preview_idle.walking = false
	_preview_idle.fill_height = true
	_preview_idle.custom_minimum_size = Vector2(200, 128)
	left.add_child(_preview_idle)
	_preview_note = DoorUi.label("", 16, DoorUi.MUTED)
	_preview_note.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_preview_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	left.add_child(_preview_note)

	_scroll = ScrollContainer.new()
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_scroll.custom_minimum_size = Vector2(620, 480)   # (the rows; UiTheme.hug_edge puts the bar out in the padding)
	cols.add_child(_scroll)
	var right := VBoxContainer.new()
	right.add_theme_constant_override("separation", 8)
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_scroll.add_child(right)
	UiTheme.hug_edge(_scroll, 24)
	right.add_child(DoorUi.heading("Name"))
	_name_edit = DoorUi.text_box("What should everyone call you?", 16)
	_name_edit.text_submitted.connect(func(_t): _submit())
	right.add_child(_name_edit)
	_difficulty_box = VBoxContainer.new()
	_difficulty_box.add_theme_constant_override("separation", 6)
	right.add_child(_difficulty_box)
	_difficulty_box.add_child(DoorUi.gap(4))
	_difficulty_box.add_child(DoorUi.heading("Difficulty"))
	var levels := HBoxContainer.new()
	levels.add_theme_constant_override("separation", 6)
	_difficulty_box.add_child(levels)
	for d in DIFFICULTY:
		var b := DoorUi.choice(d[1], 110)
		b.pressed.connect(func():
			_difficulty = d[0]
			_show_difficulty())
		levels.add_child(b)
		_difficulty_buttons[d[0]] = b
	_difficulty_note = DoorUi.label("", 16, DoorUi.MUTED)
	_difficulty_box.add_child(_difficulty_note)
	right.add_child(DoorUi.gap(4))
	right.add_child(DoorUi.heading("Appearance"))
	_editor = LookEditor.new()
	_editor.changed.connect(func():
		_preview_note.text = "Dressing..."
		_preview_timer.start())
	right.add_child(_editor)

	var foot := HBoxContainer.new()
	foot.add_theme_constant_override("separation", 12)
	outer.add_child(foot)
	_error = DoorUi.label("", 17, BettingBar.LOSS)
	_error.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_error.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	foot.add_child(_error)
	var back := DoorUi.button("Back", "ghost", "Esc")
	back.pressed.connect(func():
		if not _busy:
			_mode = "select"
			_update())
	foot.add_child(back)
	_save = DoorUi.button("Create", "primary")
	_save.pressed.connect(_submit)
	foot.add_child(_save)
	return panel


func _open_design(id: int) -> void:
	_editing = id
	_busy = false
	_deleting = -1
	_mode = "design"
	var c := Session.character(id) if id >= 0 else {}
	_design_title.text = "CHANGE %s" % str(c.name).to_upper() if id >= 0 else "NEW CHARACTER"
	_save.setup("Save" if id >= 0 else "Create", "", "primary")
	_name_edit.text = str(c.get("name", ""))
	_difficulty_box.visible = id < 0
	_difficulty = "normal"
	_show_difficulty()
	_error.text = ""
	_update()
	_scroll.scroll_vertical = 0
	if _options.is_empty():
		_preview_note.text = "Opening the wardrobe..."
		_options = await LookLoader.options()
		if _options.is_empty():
			_preview_note.text = ""
			_show_error("Couldn't load the wardrobe. Go back and try again.")
			return
	var spec = c.get("spec")
	_editor.setup(_options, spec if spec is Dictionary else {})
	_preview.look = str(c.get("look", "player_default")) if id >= 0 else "player_default"
	_preview_idle.look = _preview.look
	_build_preview()
	if id < 0:
		_name_edit.grab_focus.call_deferred()


func _show_difficulty() -> void:
	for d in _difficulty_buttons:
		_difficulty_buttons[d].set_pressed_no_signal(d == _difficulty)
	var bank := int(Session.difficulties.get(_difficulty, 0))
	_difficulty_note.text = {"easy": "Starts with %s in the bank. A gentle start.",
		"normal": "Starts with %s in the bank. The usual casino.",
		"hard": "Starts with %s in the bank. Every pound counts."}[_difficulty] % Money.format(bank, true)


## Builds the look being designed on the server (its sheet), then shows it.
func _build_preview() -> void:
	_preview_seq += 1
	var seq := _preview_seq
	var r: Dictionary = await LookLoader.preview(_editor.spec.duplicate(true))
	if seq != _preview_seq:
		return   # (changed again while it was building)
	if r.has("error"):
		_preview_note.text = str(r.error)
		return
	LookLoader.want(r.id)
	_preview.look = r.id
	_preview_idle.look = r.id
	_preview_note.text = ""


func _submit() -> void:
	if _busy or _editor.opts.is_empty():
		return
	var n := _name_edit.text.strip_edges()
	if n == "":
		_show_error("Give your character a name.")
		_name_edit.grab_focus()
		return
	_error.text = ""
	_busy = true
	if _editing >= 0:
		Session.edit_character(_editing, n, _editor.spec)
	else:
		Session.create_character(n, _editor.spec, _difficulty)


func _show_error(text: String) -> void:
	_error.text = text


## The designer fits a short screen: its list of choices scrolls.
func _fit() -> void:
	var h := get_viewport_rect().size.y
	_scroll.custom_minimum_size.y = clampf(h - 230.0, 260.0, 520.0)
