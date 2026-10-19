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


func open_menu() -> void:
	for key in _sliders:
		_sliders[key].set_value_no_signal(float(Settings.value(key)))
		_readouts[key].text = "%d%%" % roundi(float(Settings.value(key)) * 100)
	_mute.set_pressed_no_signal(bool(Settings.value("muted")))
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
