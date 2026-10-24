class_name BarredScreen
extends Control
## Over everything when the casino has shut you out (the server's `barred`, from the admin page): banned, timed out
## (with the time left counting down; Net reconnects when it's up) or your account removed (reload to start again).

var _title := Label.new()
var _body := Label.new()
var _left := Label.new()
var _ends_ms := 0   # a timeout: the tick it runs out


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP   # nothing behind it can be clicked
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.72)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	var centre := CenterContainer.new()
	centre.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(centre)
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(460, 0)
	centre.add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 12)
	panel.add_child(box)
	for l in [_title, _body, _left]:
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		box.add_child(l)
	_title.add_theme_font_size_override("font_size", 22)
	_body.add_theme_font_size_override("font_size", 16)
	_left.add_theme_font_size_override("font_size", 18)
	hide()
	set_process(false)


func open(msg: Dictionary) -> void:
	var reason := str(msg.get("reason", ""))
	var why := "\nReason: " + reason if reason != "" else ""
	_left.text = ""
	_ends_ms = 0
	match str(msg.get("kind", "")):
		"ban":
			_title.text = "You've been banned"
			_body.text = "The casino has banned this account." + why
		"timeout":
			_title.text = "You've been timed out"
			_body.text = "You can come back when the timeout's over." + why
			_ends_ms = Time.get_ticks_msec() + int(float(msg.get("retry_in", 0)) * 1000.0)
		_:
			_title.text = "Your account has been removed"
			_body.text = "Reload the page to start again as a new player."
	set_process(_ends_ms > 0)
	_process(0.0)
	show()


func close() -> void:
	hide()
	set_process(false)


func _process(_delta: float) -> void:
	if _ends_ms <= 0:
		return
	var secs := maxi(0, ceili((_ends_ms - Time.get_ticks_msec()) / 1000.0))
	if secs == 0:
		_left.text = "Coming back in..."
		return
	var h := secs / 3600
	var m := (secs % 3600) / 60
	var s := secs % 60
	_left.text = "Back in " + ("%d:%02d:%02d" % [h, m, s] if h > 0 else "%d:%02d" % [m, s])
