class_name SettingsMenu
extends PanelContainer
## The settings panel, opened from the Settings button at the top right (or the slot screen's own). It
## edits the Settings autoload directly, so every change applies (and is saved) at once. Esc or Close
## shuts it. While it's open the floor ignores game keys.
##
## In the betting bar's look: sections are a heading over rows, each row its name on the left and its
## control on the right (a slider, a switch, or a set of choices). Add a heading and rows to grow it.

const INK := BettingBar.INK
const MUTED := BettingBar.MUTED
const BRASS := BettingBar.BRASS
const BRASS_HI := BettingBar.BRASS_HI
const FONT := BettingBar.FONT
const CONTROL_W := 236.0   # every row's control, so they line up down the right

var _sliders := {}   # setting key -> HSlider
var _readouts := {}  # setting key -> Label showing the percentage
var _choices := {}   # setting key -> [[Button, value], ...]
var _switches := {}  # setting key -> [BettingBar.BarSwitch, value when on]
var _grabber: ImageTexture
var _grabber_hi: ImageTexture


func _ready() -> void:
	hide()
	mouse_filter = MOUSE_FILTER_STOP
	add_theme_stylebox_override("panel", BettingBar._box(Color(0.04, 0.047, 0.05, 0.97), Color(BRASS, 0.55), 14, Vector4(24, 16, 24, 16)))
	get_viewport().size_changed.connect(_place)
	_grabber = _dot_texture(9.0, BRASS_HI)
	_grabber_hi = _dot_texture(10.0, Color("fff2cc"))

	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	box.custom_minimum_size = Vector2(480, 0)
	add_child(box)
	var top := HBoxContainer.new()
	box.add_child(top)
	var title := _label("SETTINGS", 26, BRASS_HI)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top.add_child(title)
	var close := BettingBar.BarButton.new()
	close.setup("Close", "Esc", "ghost")
	close.pressed.connect(close_menu)
	top.add_child(close)

	_heading(box, "Sound")
	_slider_row(box, "Master volume", "master_volume")
	_slider_row(box, "Effects", "effects_volume", "Cards, chips, results, buttons")
	_slider_row(box, "Background room", "ambience_volume", "The murmur of the casino")
	_switch_row(box, "Mute all sound", "muted", true, false)

	_heading(box, "Graphics")
	_choice_row(box, "Quality", "graphics", [["High", "high"], ["Balanced", "balanced"], ["Low", "low"], ["Custom", "custom"]])
	_choice_row(box, "Frame rate", "fps_cap", [["30", 30], ["60", 60], ["Max", 0]], "Frames a second; Max is as fast as it can")
	_choice_row(box, "Resolution", "resolution", [["Sharp", "sharp"], ["Fast", "fast"]], "Fast draws at 720p and scales up")
	_switch_row(box, "Free seats glow and breathe", "seat_glow", true, false)
	_switch_row(box, "Fewer coins, no shaking", "slot_effects", "reduced", "full", "At the slot machines")
	_switch_row(box, "Show the frame rate", "show_fps", true, false, "Also F3")
	Settings.changed.connect(func(_k, _v): _refresh())

	var foot := _label("Saved on this device as you change them.", 15, MUTED)
	foot.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(_gap(4))
	box.add_child(foot)


func _label(text: String, size: int, colour: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", FONT)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", colour)
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	return l


func _gap(h: float) -> Control:
	var c := Control.new()
	c.custom_minimum_size.y = h
	return c


## A section's name in brass capitals, with a hairline running off to the right.
func _heading(parent: Control, text: String) -> void:
	parent.add_child(_gap(8))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	parent.add_child(row)
	var label := _label(text.to_upper(), 14, BRASS)
	row.add_child(label)
	var line := ColorRect.new()
	line.color = Color(BRASS, 0.25)
	line.custom_minimum_size = Vector2(0, 1)
	line.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	line.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(line)


## A row: its name (and an optional muted hint under it) on the left; the caller adds the control.
func _row(parent: Control, text: String, hint := "") -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 16)
	row.custom_minimum_size.y = 38
	parent.add_child(row)
	var names := VBoxContainer.new()
	names.add_theme_constant_override("separation", -3)
	names.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	names.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_child(names)
	names.add_child(_label(text, 19, INK))
	if hint != "":
		names.add_child(_label(hint, 14, MUTED))
	return row


func _slider_row(parent: Control, text: String, key: String, hint := "") -> void:
	var row := _row(parent, text, hint)
	var slider := HSlider.new()
	slider.min_value = 0.0
	slider.max_value = 1.0
	slider.step = 0.05
	slider.custom_minimum_size = Vector2(CONTROL_W - 52.0, 24)
	slider.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	slider.focus_mode = Control.FOCUS_NONE
	slider.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	var track := BettingBar._box(Color("2b3133"), Color(0, 0, 0, 0), 3, Vector4(0, 3, 0, 3))
	slider.add_theme_stylebox_override("slider", track)
	slider.add_theme_stylebox_override("grabber_area", BettingBar._box(Color(BRASS, 0.85), Color(0, 0, 0, 0), 3, Vector4(0, 3, 0, 3)))
	slider.add_theme_stylebox_override("grabber_area_highlight", BettingBar._box(BRASS, Color(0, 0, 0, 0), 3, Vector4(0, 3, 0, 3)))
	slider.add_theme_icon_override("grabber", _grabber)
	slider.add_theme_icon_override("grabber_highlight", _grabber_hi)
	row.add_child(slider)
	var readout := _label("", 17, MUTED)
	readout.custom_minimum_size = Vector2(40, 0)
	readout.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	row.add_child(readout)
	slider.value_changed.connect(func(v: float):
		readout.text = "%d%%" % roundi(v * 100)
		Settings.set_value(key, v))
	_sliders[key] = slider
	_readouts[key] = readout


## Choices side by side in a dark tray, the current one in brass: `options` is [[label, value]]. Quality
## picks a preset, and its Custom only shows (lit, not clickable) once a row below has been changed by
## hand; the others are set by hand (Settings.set_graphics).
func _choice_row(parent: Control, text: String, key: String, options: Array, hint := "") -> void:
	var row := _row(parent, text, hint)
	var tray := PanelContainer.new()
	tray.add_theme_stylebox_override("panel", BettingBar._box(Color("161b1d"), Color("2b3133"), 9, Vector4(3, 3, 3, 3)))
	tray.custom_minimum_size.x = CONTROL_W
	tray.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(tray)
	var segs := HBoxContainer.new()
	segs.add_theme_constant_override("separation", 3)
	tray.add_child(segs)
	var buttons := []
	for o in options:
		var b := Button.new()
		b.text = o[0]
		b.focus_mode = Control.FOCUS_NONE
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		b.custom_minimum_size = Vector2(0, 32)
		b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		b.add_theme_font_override("font", FONT)
		b.add_theme_font_size_override("font_size", 16)
		var value = o[1]
		if key == "graphics" and value == "custom":
			b.mouse_filter = Control.MOUSE_FILTER_IGNORE
		b.pressed.connect(func():
			if key == "graphics":
				Settings.use_preset(value)
				Settings.set_value("graphics_auto", false)
			else:
				Settings.set_graphics(key, value)
			_refresh())
		segs.add_child(b)
		buttons.append([b, value])
	_choices[key] = buttons


func _style_choice(b: Button, on: bool) -> void:
	var bg := BRASS if on else Color(0, 0, 0, 0)
	var hover := Color("d6b05a") if on else Color("232a2d")
	for state in ["normal", "pressed", "disabled", "focus"]:
		b.add_theme_stylebox_override(state, BettingBar._box(bg, Color(0, 0, 0, 0), 6, Vector4(10, 0, 10, 0)))
	b.add_theme_stylebox_override("hover", BettingBar._box(hover, Color(0, 0, 0, 0), 6, Vector4(10, 0, 10, 0)))
	var ink := Color("1b1307") if on else INK
	for c in ["font_color", "font_hover_color", "font_pressed_color", "font_hover_pressed_color"]:
		b.add_theme_color_override(c, ink)


## A switch on the right: `on` when it's on, `off` when not. Graphics rows go through Settings.set_graphics
## (they make the Quality "Custom"); the rest are plain settings.
func _switch_row(parent: Control, text: String, key: String, on, off, hint := "") -> void:
	var row := _row(parent, text, hint)
	var holder := Control.new()
	holder.custom_minimum_size = Vector2(CONTROL_W, 38)
	row.add_child(holder)
	var sw := BettingBar.BarSwitch.new()
	sw.words = ""
	holder.add_child(sw)
	sw.position = Vector2(CONTROL_W - 34.0, 0)   # its track's right edge in line with the trays'
	sw.toggled.connect(func(ticked: bool):
		if key in ["muted", "show_fps"]:
			Settings.set_value(key, on if ticked else off)
		else:
			Settings.set_graphics(key, on if ticked else off))
	_switches[key] = [sw, on]


## A soft-edged dot for the sliders' handles.
static func _dot_texture(r: float, colour: Color) -> ImageTexture:
	var n := int(ceil(r * 2.0)) + 2
	var img := Image.create(n, n, false, Image.FORMAT_RGBA8)
	var c := Vector2(n, n) / 2.0
	for y in n:
		for x in n:
			var d := Vector2(x + 0.5, y + 0.5).distance_to(c)
			img.set_pixel(x, y, Color(colour, clampf(r - d + 0.5, 0.0, 1.0)))
	return ImageTexture.create_from_image(img)


func _refresh() -> void:
	for key in _sliders:
		_sliders[key].set_value_no_signal(float(Settings.value(key)))
		_readouts[key].text = "%d%%" % roundi(float(Settings.value(key)) * 100)
	for key in _choices:
		for pair in _choices[key]:
			var on: bool = Settings.value(key) == pair[1]
			_style_choice(pair[0], on)
			if key == "graphics" and pair[1] == "custom":
				pair[0].visible = on
	for key in _switches:
		_switches[key][0].set_pressed_no_signal(Settings.value(key) == _switches[key][1])
		_switches[key][0].queue_redraw()


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
	position = ((get_viewport().get_visible_rect().size - size) / 2).round()


func _input(event: InputEvent) -> void:
	if visible and event.is_action_pressed("cancel"):
		close_menu()
		get_viewport().set_input_as_handled()
