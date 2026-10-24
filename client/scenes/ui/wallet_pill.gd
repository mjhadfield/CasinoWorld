class_name WalletPill
extends HBoxContainer
## Top left, right of the HUD's Settings, walking or seated: whether you're online, your name, your cash in hand (less what's on the
## felt) with a round's result flashing beside it. (Your bank balance is at the lobby's ATM.) In the betting bar's
## look, the same height as the Settings button beside it. Clicking it opens the character select (`pressed`).

signal pressed

var _panel: PanelContainer
var _dot: Control
var _name: Label
var _balance: Label
var _delta: Label
var _delta_tween: Tween
var _online := false


func _ready() -> void:
	add_theme_constant_override("separation", 8)
	mouse_filter = MOUSE_FILTER_IGNORE
	_panel = PanelContainer.new()
	_panel.custom_minimum_size.y = 40
	_panel.add_theme_stylebox_override("panel", BettingBar._lifted(BettingBar._box(BettingBar.CORNER_BG, Color(0.79, 0.64, 0.29, 0.3), 20, Vector4(13, 0, 16, 0))))
	_panel.mouse_filter = MOUSE_FILTER_STOP
	_panel.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_panel.tooltip_text = "Switch character"
	_panel.gui_input.connect(func(event: InputEvent):
		if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
			Sfx.play("click")
			pressed.emit())
	add_child(_panel)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	_panel.add_child(row)
	_dot = Control.new()
	_dot.custom_minimum_size = Vector2(10, 10)
	_dot.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_dot.tooltip_text = "Connecting..."
	_dot.mouse_filter = MOUSE_FILTER_PASS   # (a click on it is the pill's)
	_dot.draw.connect(func():
		var c := BettingBar.WIN if _online else BettingBar.WARN
		_dot.draw_circle(Vector2(5, 5), 6.5, Color(c, 0.25))
		_dot.draw_circle(Vector2(5, 5), 4.5, c))
	row.add_child(_dot)
	_name = _label("", 17, BettingBar.MUTED)
	row.add_child(_name)
	_balance = _label("£—", 25, BettingBar.INK)
	row.add_child(_balance)
	_delta = _label("", 19, BettingBar.WIN)
	_delta.hide()
	row.add_child(_delta)


func _label(text: String, size: int, colour: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", BettingBar.FONT)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", colour)
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.mouse_filter = MOUSE_FILTER_IGNORE
	return l


func set_player_name(text: String) -> void:
	_name.text = text
	_name.visible = text != ""


func set_balance(pence: int) -> void:
	_balance.text = Money.format(pence)


func set_online(on: bool) -> void:
	_online = on
	_dot.tooltip_text = "Online" if on else "Connecting..."
	_dot.queue_redraw()


## A round's result beside the balance: green for a win, red for a loss, fading after a few seconds.
func flash_result(net: int) -> void:
	_delta.text = ("+" if net > 0 else "−") + Money.format(absi(net), true)
	_delta.add_theme_color_override("font_color", BettingBar.WIN if net > 0 else BettingBar.LOSS)
	if _delta_tween:
		_delta_tween.kill()
	_delta.modulate.a = 1.0
	_delta.show()
	_delta_tween = create_tween()
	_delta_tween.tween_interval(3.2)
	_delta_tween.tween_property(_delta, "modulate:a", 0.0, 0.6)
	_delta_tween.tween_callback(_delta.hide)
