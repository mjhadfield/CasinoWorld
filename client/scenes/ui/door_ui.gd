class_name DoorUi
## The front door's controls (character select and designer), in the betting bar's look: labels, brass choice
## buttons, dark dropdowns and text boxes. Static helpers, like BettingBar's _box.

const INK := BettingBar.INK
const MUTED := BettingBar.MUTED
const BRASS := BettingBar.BRASS
const BRASS_HI := BettingBar.BRASS_HI
const FONT := BettingBar.FONT
const FIELD_BG := Color("1b2123")
const FIELD_EDGE := Color("39413f")


static func label(text: String, size: int, colour := INK) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", FONT)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", colour)
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


static func gap(h: float) -> Control:
	var c := Control.new()
	c.custom_minimum_size.y = h
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return c


## A section's name in brass capitals with a hairline off to the right (as the Settings panel's).
static func heading(text: String) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	row.add_child(label(text.to_upper(), 14, BRASS))
	var line := ColorRect.new()
	line.color = Color(BRASS, 0.25)
	line.custom_minimum_size = Vector2(0, 1)
	line.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	line.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(line)
	return row


## One of a set of choices (Male/Female, Easy/Normal/Hard): brass when it's the one picked.
static func choice(text: String, min_w := 0.0) -> Button:
	var b := Button.new()
	b.text = text
	b.toggle_mode = true
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size = Vector2(min_w, 36)
	b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	b.add_theme_font_override("font", FONT)
	b.add_theme_font_size_override("font_size", 18)
	b.add_theme_color_override("font_color", MUTED)
	b.add_theme_color_override("font_hover_color", INK)
	b.add_theme_color_override("font_pressed_color", Color("1a1408"))
	b.add_theme_color_override("font_hover_pressed_color", Color("1a1408"))
	var off := BettingBar._box(FIELD_BG, FIELD_EDGE, 8, Vector4(14, 4, 14, 4))
	var hover := BettingBar._box(FIELD_BG, Color(BRASS, 0.7), 8, Vector4(14, 4, 14, 4))
	var on := BettingBar._box(BRASS, BRASS, 8, Vector4(14, 4, 14, 4))
	b.add_theme_stylebox_override("normal", off)
	b.add_theme_stylebox_override("hover", hover)
	b.add_theme_stylebox_override("pressed", on)
	b.add_theme_stylebox_override("hover_pressed", on)
	b.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	return b


static func dropdown() -> OptionButton:
	var o := OptionButton.new()
	o.focus_mode = Control.FOCUS_NONE
	o.custom_minimum_size = Vector2(0, 34)
	o.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	o.fit_to_longest_item = false
	o.add_theme_font_override("font", FONT)
	o.add_theme_font_size_override("font_size", 17)
	o.add_theme_color_override("font_color", INK)
	o.add_theme_color_override("font_disabled_color", Color(MUTED, 0.5))
	o.add_theme_stylebox_override("normal", BettingBar._box(FIELD_BG, FIELD_EDGE, 8, Vector4(12, 2, 12, 2)))
	o.add_theme_stylebox_override("hover", BettingBar._box(FIELD_BG, Color(BRASS, 0.7), 8, Vector4(12, 2, 12, 2)))
	o.add_theme_stylebox_override("pressed", BettingBar._box(FIELD_BG, BRASS, 8, Vector4(12, 2, 12, 2)))
	o.add_theme_stylebox_override("disabled", BettingBar._box(Color(FIELD_BG, 0.5), Color(FIELD_EDGE, 0.5), 8, Vector4(12, 2, 12, 2)))
	o.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	var pop := o.get_popup()
	pop.add_theme_font_override("font", FONT)
	pop.add_theme_font_size_override("font_size", 17)
	pop.add_theme_color_override("font_color", INK)
	pop.add_theme_color_override("font_hover_color", Color("1a1408"))
	pop.add_theme_stylebox_override("panel", BettingBar._box(Color(0.06, 0.07, 0.075, 0.98), Color(BRASS, 0.5), 8, Vector4(4, 4, 4, 4)))
	pop.add_theme_stylebox_override("hover", BettingBar._box(BRASS_HI, BRASS_HI, 6, Vector4(8, 2, 8, 2)))
	return o


static func text_box(placeholder: String, max_length: int) -> LineEdit:
	var e := LineEdit.new()
	e.placeholder_text = placeholder
	e.max_length = max_length
	e.custom_minimum_size = Vector2(0, 42)
	e.add_theme_font_override("font", FONT)
	e.add_theme_font_size_override("font_size", 22)
	e.add_theme_color_override("font_color", INK)
	e.add_theme_color_override("font_placeholder_color", Color(MUTED, 0.6))
	e.add_theme_color_override("caret_color", BRASS_HI)
	e.add_theme_stylebox_override("normal", BettingBar._box(FIELD_BG, FIELD_EDGE, 8, Vector4(14, 4, 14, 4)))
	e.add_theme_stylebox_override("focus", BettingBar._box(FIELD_BG, BRASS, 8, Vector4(14, 4, 14, 4)))
	return e


static func button(words: String, kind := "normal", key := "") -> BettingBar.BarButton:
	var b := BettingBar.BarButton.new()
	b.setup(words, key, kind)
	return b
