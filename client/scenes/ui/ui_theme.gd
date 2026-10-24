class_name UiTheme
## The client's own theme, merged into Godot's default theme so every control picks it up, including those under
## a CanvasLayer like the HUD (a theme set on a window stops at one). The panels still style their own buttons and
## text. So far it's the scroll bars: a slim rounded brass grabber on a faint track, no arrow buttons; `hug_edge`
## moves a box's bar out to its edge.

const BAR := 8   # the scroll bar's thickness
const EDGE := 4  # between a hugging bar and the edge of its box


static func install() -> void:
	ThemeDB.get_default_theme().merge_with(build())


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
	t.set_constant("scrollbar_v_separation", "ScrollContainer", 0)   # (hug_edge leaves the gap; Godot 4.7 skips this anyway)
	t.set_constant("scrollbar_h_separation", "ScrollContainer", 0)
	return t


## Puts the vertical bar of `scroller` (a ScrollContainer or RichTextLabel down the right of its box) out in the
## box's right padding, `pad` wide, EDGE from the edge. Its rows keep that padding, so they line up with the rest of
## the box. Call it once the ScrollContainer has its one child.
static func hug_edge(scroller: Control, pad: float) -> void:
	var out := maxf(pad - EDGE, 0.0)
	var gap := maxf(out - BAR, 0.0)   # (the rows' end to the bar)
	if scroller is ScrollContainer:
		var sc := scroller as ScrollContainer
		sc.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_RESERVE   # (the rows are as wide with the bar as without)
		var rows: Control = sc.get_child(0)
		var m := MarginContainer.new()
		m.size_flags_horizontal = rows.size_flags_horizontal
		m.size_flags_vertical = rows.size_flags_vertical
		m.add_theme_constant_override("margin_right", int(gap))
		sc.remove_child(rows)
		m.add_child(rows)
		sc.add_child(m)
	else:
		var sb := StyleBoxEmpty.new()
		sb.content_margin_right = gap
		scroller.add_theme_stylebox_override("normal", sb)
	# (wider than the box gives it, after every layout of the box: past the padding, which nothing clips)
	(scroller.get_parent() as Container).sort_children.connect(func(): scroller.size.x += out)


static func _pill(colour: Color) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = colour
	s.set_corner_radius_all(BAR / 2)
	s.set_content_margin_all(BAR / 2.0)   # (what sets the bar's thickness)
	s.anti_aliasing = true
	return s
