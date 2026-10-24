class_name LookEditor
extends VBoxContainer
## The character designer's look controls, ported from the admin page's NPC look designer (admin_web/sections/
## npcs.js): body and skin, Randomise, then a style and a colour for every slot (hair, facial hair, top, over the
## top, legs, shoes, neck, glasses, hat), offering only what comes in the body's fit; slots that aren't required can
## be None. `spec` is the look spec the server takes (art.py): {body, skin, <slot>: [style, colour] or null}.

signal changed

## The skin swatches' colours (the admin page's).
const SKIN := {"light": Color("f3cfb3"), "amber": Color("e3a978"), "olive": Color("c99a6b"), "taupe": Color("b08668"),
	"bronze": Color("9a6646"), "brown": Color("7a4c32"), "black": Color("4a2e22")}
## A new character's look until it's changed (the admin page's new NPC).
const DEFAULT := {"body": "female", "skin": "light", "hair": ["bob", "chestnut"], "top": ["tshirt", "teal"],
	"bottom": ["pants", "navy"], "shoes": ["shoes", "black"]}
## Randomise: how likely each optional slot is to have something in it.
const ODDS := {"hair": 1.0, "beard": 0.3, "top": 1.0, "over": 0.15, "bottom": 1.0, "shoes": 1.0, "neck": 0.1, "glasses": 0.2, "hat": 0.05}

var opts := {}    # the server's catalogue: {bodies, skins, slots: [{slot, label, required, options: [{id, label, bodies, colours}]}]}
var spec := {}
var _bodies := {}   # body -> Button
var _skins := {}    # skin -> Button
var _rows := {}     # slot -> [style OptionButton, colour OptionButton]


func setup(options: Dictionary, look: Dictionary) -> void:
	opts = options
	spec = (look if not look.is_empty() else DEFAULT).duplicate(true)
	for c in get_children():
		c.queue_free()
	_bodies.clear()
	_skins.clear()
	_rows.clear()
	add_theme_constant_override("separation", 8)

	var top := HBoxContainer.new()
	top.add_theme_constant_override("separation", 6)
	add_child(top)
	for body in opts.get("bodies", []):
		var b := DoorUi.choice("Male" if body == "male" else "Female", 86)
		b.pressed.connect(func():
			spec.body = body
			_fix_fits()
			_refresh()
			changed.emit())
		top.add_child(b)
		_bodies[body] = b
	var spacer := Control.new()
	spacer.custom_minimum_size.x = 10
	top.add_child(spacer)
	for skin in opts.get("skins", []):
		var s := Button.new()
		s.toggle_mode = true
		s.focus_mode = Control.FOCUS_NONE
		s.tooltip_text = str(skin).capitalize()
		s.custom_minimum_size = Vector2(26, 26)
		s.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		s.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		var col: Color = SKIN.get(skin, Color("cccccc"))
		s.add_theme_stylebox_override("normal", BettingBar._box(col, Color(0, 0, 0, 0.4), 13, Vector4.ZERO))
		s.add_theme_stylebox_override("hover", BettingBar._box(col, Color(DoorUi.BRASS, 0.8), 13, Vector4.ZERO))
		var on := BettingBar._box(col, DoorUi.BRASS_HI, 13, Vector4.ZERO)
		on.set_border_width_all(3)
		s.add_theme_stylebox_override("pressed", on)
		s.add_theme_stylebox_override("hover_pressed", on)
		s.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
		s.pressed.connect(func():
			spec.skin = skin
			_refresh()
			changed.emit())
		top.add_child(s)
		_skins[skin] = s
	var grow := Control.new()
	grow.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top.add_child(grow)
	var rnd := DoorUi.choice("Randomise")
	rnd.toggle_mode = false
	rnd.pressed.connect(func():
		randomise()
		changed.emit())
	top.add_child(rnd)

	add_child(DoorUi.gap(2))
	var grid := GridContainer.new()
	grid.columns = 3
	grid.add_theme_constant_override("h_separation", 10)
	grid.add_theme_constant_override("v_separation", 6)
	add_child(grid)
	for slot in opts.get("slots", []):
		var name_label := DoorUi.label(str(slot.label), 18, DoorUi.MUTED)
		name_label.custom_minimum_size.x = 104
		grid.add_child(name_label)
		var style := DoorUi.dropdown()
		style.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		style.custom_minimum_size.x = 170
		var colour := DoorUi.dropdown()
		colour.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		colour.custom_minimum_size.x = 140
		grid.add_child(style)
		grid.add_child(colour)
		var key := str(slot.slot)
		_rows[key] = [style, colour]
		style.item_selected.connect(func(i: int): _style_picked(slot, style.get_item_metadata(i)))
		colour.item_selected.connect(func(i: int):
			if spec.get(key) != null:
				spec[key] = [spec[key][0], colour.get_item_metadata(i)]
				changed.emit())
	_refresh()


## A random look (any body, any skin; each optional slot filled at its ODDS).
func randomise() -> void:
	spec = {"body": opts.bodies.pick_random(), "skin": opts.skins.pick_random()}
	for slot in opts.slots:
		var fits: Array = slot.options.filter(func(o): return spec.body in o.bodies)
		var odds: float = ODDS.get(slot.slot, 0.0) * (0.0 if slot.slot == "beard" and spec.body != "male" else 1.0)
		if fits.is_empty() or (not slot.required and randf() >= odds):
			spec[slot.slot] = null
			continue
		var o: Dictionary = fits.pick_random()
		spec[slot.slot] = [o.id, o.colours.pick_random()]
	_refresh()


func _option(slot: Dictionary, id) -> Dictionary:
	for o in slot.options:
		if o.id == id:
			return o
	return {}


func _style_picked(slot: Dictionary, id) -> void:
	var key := str(slot.slot)
	if id == null or str(id) == "":
		spec[key] = null
	else:
		var o := _option(slot, id)
		var had = spec.get(key)
		var keep = had[1] if had != null and had[1] in o.colours else o.colours[0]
		spec[key] = [o.id, keep]
	_refresh()
	changed.emit()


## After a body change: anything that doesn't come in that fit comes off (or, for a required slot, the first that does).
func _fix_fits() -> void:
	for slot in opts.slots:
		var c = spec.get(slot.slot)
		if c == null:
			continue
		var o := _option(slot, c[0])
		if not o.is_empty() and spec.body in o.bodies:
			continue
		if slot.required:
			for alt in slot.options:
				if spec.body in alt.bodies:
					spec[slot.slot] = [alt.id, c[1] if c[1] in alt.colours else alt.colours[0]]
					break
		else:
			spec[slot.slot] = null


## Shows `spec`: which body and skin are picked, and each slot's styles (for this body) and colours.
func _refresh() -> void:
	for body in _bodies:
		_bodies[body].set_pressed_no_signal(spec.get("body") == body)
	for skin in _skins:
		_skins[skin].set_pressed_no_signal(spec.get("skin") == skin)
	for slot in opts.get("slots", []):
		var key := str(slot.slot)
		var style: OptionButton = _rows[key][0]
		var colour: OptionButton = _rows[key][1]
		var choice = spec.get(key)
		style.clear()
		if not slot.required:
			style.add_item("None")
			style.set_item_metadata(0, "")
		var styles: Array = slot.options.duplicate()
		styles.sort_custom(func(a, b): return str(a.label).naturalnocasecmp_to(str(b.label)) < 0)
		for o in styles:
			if spec.get("body") in o.bodies:
				style.add_item(str(o.label))
				style.set_item_metadata(style.item_count - 1, o.id)
				if choice != null and choice[0] == o.id:
					style.select(style.item_count - 1)
		if choice == null:
			style.select(0)
		colour.clear()
		var current := _option(slot, choice[0]) if choice != null else {}
		colour.disabled = current.is_empty()
		if current.is_empty():
			colour.add_item("-")
			continue
		var colours: Array = current.colours.duplicate()
		colours.sort_custom(func(a, b): return _colour_label(a).naturalnocasecmp_to(_colour_label(b)) < 0)
		for c in colours:
			colour.add_item(_colour_label(c))
			colour.set_item_metadata(colour.item_count - 1, c)
			if c == choice[1]:
				colour.select(colour.item_count - 1)


func _colour_label(c) -> String:
	return str(c).replace("_", " ").capitalize()
