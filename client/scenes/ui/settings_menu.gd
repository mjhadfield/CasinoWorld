class_name SettingsMenu
extends PanelContainer
## The settings panel, opened from the Settings button at the top right. It
## edits the Settings autoload directly, so every change applies (and is saved)
## at once. Esc or Close shuts it. While it's open the floor ignores game keys.
##
## Sections are plain rows built in code: add a heading and rows to grow it.

var _sliders := {}   # setting key -> HSlider
var _readouts := {}  # setting key -> Label showing the percentage
var _mute: CheckBox
var _choices := {}   # setting key -> [OptionButton, [values in its order]]
var _checks := {}    # setting key -> [CheckBox, value when ticked]


func _ready() -> void:
	hide()
	mouse_filter = MOUSE_FILTER_STOP
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.06, 0.03, 0.02, 0.94)
	style.border_color = Color("c9a24a")
	style.set_border_width_all(2)
	style.set_corner_radius_all(10)
	style.set_content_margin_all(18)
	add_theme_stylebox_override("panel", style)
	get_viewport().size_changed.connect(_place)

	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 10)
	box.custom_minimum_size = Vector2(420, 0)
	add_child(box)
	var title := Label.new()
	title.text = "Settings"
	title.add_theme_font_size_override("font_size", 22)
	title.add_theme_color_override("font_color", Color("ffd76a"))
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(title)

	_heading(box, "Sound")
	_slider_row(box, "Master volume", "master_volume")
	_slider_row(box, "Effects (cards, chips, results)", "effects_volume")
	_slider_row(box, "Background room", "ambience_volume")
	_mute = CheckBox.new()
	_mute.text = "Mute all sound"
	_mute.focus_mode = Control.FOCUS_NONE
	_mute.add_theme_font_size_override("font_size", 16)
	_mute.toggled.connect(func(on): Settings.set_value("muted", on))
	box.add_child(_mute)

	_heading(box, "Graphics")
	_choice_row(box, "Quality", "graphics", [["High", "high"], ["Balanced", "balanced"], ["Low", "low"], ["Custom", "custom"]])
	_choice_row(box, "Frame rate", "fps_cap", [["30 a second", 30], ["60 a second", 60], ["As fast as it can", 0]])
	_choice_row(box, "Resolution", "resolution", [["Sharp", "sharp"], ["Fast (720p, scaled up)", "fast"]])
	_check_row(box, "Free seats glow and breathe", "seat_glow", true)
	_check_row(box, "Fewer coins and no shaking at the slots", "slot_effects", "reduced", "full")
	_check_row(box, "Show the frame rate  [F3]", "show_fps", true)
	Settings.changed.connect(func(_k, _v): _refresh())

	var close := Button.new()
	close.text = "Close  [Esc]"
	close.custom_minimum_size = Vector2(140, 40)
	close.focus_mode = Control.FOCUS_NONE
	close.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	close.add_theme_font_size_override("font_size", 16)
	close.pressed.connect(close_menu)
	box.add_child(close)


func _heading(parent: Control, text: String) -> void:
	var label := Label.new()
	label.text = text.to_upper()
	label.add_theme_font_size_override("font_size", 14)
	label.add_theme_color_override("font_color", Color("c9a24a"))
	parent.add_child(label)


func _slider_row(parent: Control, text: String, key: String) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	parent.add_child(row)
	var label := Label.new()
	label.text = text
	label.custom_minimum_size = Vector2(200, 0)
	label.add_theme_font_size_override("font_size", 16)
	label.add_theme_color_override("font_color", Color("f1e4c4"))
	row.add_child(label)
	var slider := HSlider.new()
	slider.min_value = 0.0
	slider.max_value = 1.0
	slider.step = 0.05
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	slider.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	slider.focus_mode = Control.FOCUS_NONE
	row.add_child(slider)
	var readout := Label.new()
	readout.custom_minimum_size = Vector2(48, 0)
	readout.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	readout.add_theme_font_size_override("font_size", 16)
	row.add_child(readout)
	slider.value_changed.connect(func(v: float):
		readout.text = "%d%%" % roundi(v * 100)
		Settings.set_value(key, v))
	_sliders[key] = slider
	_readouts[key] = readout


## A drop-down for a graphics setting: `options` is [[label, value]]. Quality picks a preset;
## the others are set by hand (Settings.set_graphics).
func _choice_row(parent: Control, text: String, key: String, options: Array) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	parent.add_child(row)
	var label := Label.new()
	label.text = text
	label.custom_minimum_size = Vector2(200, 0)
	label.add_theme_font_size_override("font_size", 16)
	label.add_theme_color_override("font_color", Color("f1e4c4"))
	row.add_child(label)
	var pick := OptionButton.new()
	pick.focus_mode = Control.FOCUS_NONE
	pick.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	pick.add_theme_font_size_override("font_size", 15)
	var values := []
	for o in options:
		pick.add_item(o[0])
		values.append(o[1])
	if key == "graphics":
		pick.set_item_disabled(values.find("custom"), true)   # (shown, not chosen: it's what changing a row makes)
	pick.item_selected.connect(func(i: int):
		if key == "graphics":
			Settings.use_preset(values[i])
			Settings.set_value("graphics_auto", false)
		else:
			Settings.set_graphics(key, values[i]))
	row.add_child(pick)
	_choices[key] = [pick, values]


## A tick box for a graphics setting (or the frame-rate corner): `on` when ticked, else `off`.
func _check_row(parent: Control, text: String, key: String, on, off = false) -> void:
	var check := CheckBox.new()
	check.text = text
	check.focus_mode = Control.FOCUS_NONE
	check.add_theme_font_size_override("font_size", 16)
	check.toggled.connect(func(ticked: bool):
		if key == "show_fps":
			Settings.set_value(key, ticked)
		else:
			Settings.set_graphics(key, on if ticked else off))
	parent.add_child(check)
	_checks[key] = [check, on]


func _refresh() -> void:
	for key in _sliders:
		_sliders[key].set_value_no_signal(float(Settings.value(key)))
		_readouts[key].text = "%d%%" % roundi(float(Settings.value(key)) * 100)
	_mute.set_pressed_no_signal(bool(Settings.value("muted")))
	for key in _choices:
		var i: int = _choices[key][1].find(Settings.value(key))
		if i >= 0:
			_choices[key][0].select(i)
	for key in _checks:
		_checks[key][0].set_pressed_no_signal(Settings.value(key) == _checks[key][1])


func open_menu() -> void:
	_refresh()
	show()
	_place.call_deferred()


func close_menu() -> void:
	hide()


func toggle() -> void:
	if visible:
		close_menu()
	else:
		open_menu()


## Centred on screen.
func _place() -> void:
	if not visible:
		return
	reset_size()
	position = (get_viewport().get_visible_rect().size - size) / 2


func _input(event: InputEvent) -> void:
	if visible and event.is_action_pressed("cancel"):
		close_menu()
		get_viewport().set_input_as_handled()
