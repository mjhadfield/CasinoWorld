class_name UiTheme
## The client's own theme, set on the root window so every control picks it up (the panels still style their own
## buttons and text). So far it's the scroll bars: a slim rounded brass grabber on a faint track, no arrow buttons,
## and a gap between a ScrollContainer's rows and its bar.

const BAR := 8   # the scroll bar's thickness
const GAP := 10  # between a ScrollContainer's contents and its bar


static func install(window: Window) -> void:
	window.theme = build()


static func build() -> Theme:
	var t := Theme.new()
	var none := ImageTexture.new()   # (no arrow buttons)
	for bar in ["VScrollBar", "HScrollBar"]:
		var track := _pill(Color(1, 1, 1, 0.05))
		t.set_stylebox("scroll", bar, track)
		t.set_stylebox("scroll_focus", bar, track)
		t.set_stylebox("grabber", bar, _pill(Color(BettingBar.BRASS, 0.45)))
		t.set_stylebox("grabber_highlight", bar, _pill(Color(BettingBar.BRASS, 0.75)))
		t.set_stylebox("grabber_pressed", bar, _pill(BettingBar.BRASS_HI))
		for icon in ["increment", "increment_highlight", "increment_pressed", "decrement", "decrement_highlight", "decrement_pressed"]:
			t.set_icon(icon, bar, none)
	t.set_constant("scrollbar_v_separation", "ScrollContainer", GAP)
	t.set_constant("scrollbar_h_separation", "ScrollContainer", GAP)
	return t


static func _pill(colour: Color) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = colour
	s.set_corner_radius_all(BAR / 2)
	s.set_content_margin_all(BAR / 2.0)   # (what sets the bar's thickness)
	s.anti_aliasing = true
	return s
