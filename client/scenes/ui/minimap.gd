class_name Minimap
extends Control
## The top-right corner, walking or seated (signed off on the Minimap mockup, docs/minimap/mockup/): a small map of
## your room and every room one doorway away (rooms joined by archways count as one), with the tables, slot banks and
## ATM drawn in their kinds' colours and named, a full table faint, other real players as dots (no NPCs) and you as a
## brass arrow. When that won't fit at a readable scale it pans with you instead, and a door to a room further on
## gets a tab with that room's name. At a turned table it turns with the view. + and - zoom it, in steps from the
## smallest view (everything shown, or the least it pans at).
##
## Walking, a table, slot bank or ATM the map names (Settings: minimap_labels) is clickable: it guides you there the
## way Find does, to that one rather than the nearest of its kind.
##
## It starts folded to a map button (Settings: minimap_collapsed); its x folds it again, and Settings › Show the
## minimap takes it away. Its size and whether the rooms next door name their tables are settings too.
##
## Find (walking only) lists what the casino has; the floor works out the nearest of a kind and the way there, and
## the guide chip under the map says where you're headed, with Walk there and x. The floor feeds it all: set_world
## when the floor's built, follow() every frame, show_find() and set_route() for Find.

signal find_opened
signal find_picked(kind: String)
## A named table, slot bank (its cabinets) or ATM clicked on the map: guide there.
signal map_picked(targets: Array)
signal walk_pressed
signal guide_closed
## Its corner changed (shown, folded, resized): what the HUD lays out round it.
signal corner_changed

const INK := BettingBar.INK
const MUTED := BettingBar.MUTED
const BRASS := BettingBar.BRASS
const BRASS_HI := BettingBar.BRASS_HI
const FONT := BettingBar.FONT
const WIDTHS := {"small": 200.0, "medium": 240.0, "large": 280.0}
const MAP_RATIO := 0.9      # the map's height to its width
const HEAD_H := 30.0
const MIN_SCALE := 0.16     # smaller than this and the tables get too small to read: it pans instead
const MAX_SCALE := 0.32
const ZOOMS := [1.0, 1.4, 2.0, 2.8, 4.0, 5.6]   # the +/- steps, on its smallest view
const ZOOM_MAX := 0.6
const PAD := 10.0
## Each kind's colour on the map, and its name there when the table's own is too long.
const KINDS := {
	"master_table": [Color("d4ad55"), "Master"],
	"roulette": [Color("3fa36b"), "Roulette"],
	"craps": [Color("3f9aa3"), "Craps"],
	"slot": [Color("9a6fd0"), "Slots"],
	"atm": [Color("7fb7c9"), "ATM"],
}
const CARDS := Color("c0473f")   # every other card table
const SHORT := {"three_card_poker": "3 Card", "pai_gow_fortune": "Pai Gow", "pai_gow_face_up": "Face Up", "mississippi_stud": "Stud",
	"ultimate_texas_holdem": "Hold'em", "let_it_ride": "Let It Ride", "high_card_flush": "Flush"}
## The tables' footprints (their bodies) upright, about where they stand: plan_catalogue.json's `body` at 0.
const BODIES := {"roulette": Rect2(-177.5, -123.5, 355, 133), "craps": Rect2(-198.5, -130.5, 397, 140)}
const CARD_BODY := Rect2(-163.5, -149.5, 327, 158)
const CABINET := Rect2(-16, -30, 32, 30)   # a cabinet facing down, as the map draws it

var _panel: PanelContainer
var _here: Label
var _find_btn: MapButton
var _map: Control
var _zoom_in: MapButton
var _zoom_out: MapButton
var _fold: BettingBar.BarButton
var _find: PanelContainer
var _find_rows: VBoxContainer
var _guide: PanelContainer
var _guide_name: Label
var _guide_dist: Label
var _walk: Button

var _rooms := {}      # room id -> PlanRoom (the floor's)
var _tables := {}     # table id -> FloorGame (the floor's own, so a swapped Master Table shows)
var _zone_of := {}
var _room_id := ""
var _pos := Vector2.ZERO
var _facing := "up"
var _turn := 0.0
var _people := PackedVector2Array()
var _route := PackedVector2Array()
var _target: Variant = null
var _mode := "walking"
var _redraw_in := 0.0
var _drawn := []      # what the map last drew from, to redraw only on a change
var _zoom_top := 0    # the last zoom step that still zooms in this room (past it, ZOOM_MAX)
var _hits := []       # [screen rect, [what it guides to]]: what a click on the map picks, as last drawn


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = MOUSE_FILTER_IGNORE
	_build_panel()
	_build_find()
	_build_guide()
	_fold = BettingBar.BarButton.new()
	_fold.setup("Map", "", "ghost", "map")
	_fold.compact = true
	_fold.tooltip_text = "Show the minimap"
	_fold.pressed.connect(func(): Settings.set_value("minimap_collapsed", false))
	add_child(_fold)
	Settings.changed.connect(func(key: String, _v):
		if key == "minimap_size":
			close_find()   # (its rows are sized for the old one)
		if key.begins_with("minimap") or key == "show_minimap":
			_layout())
	get_viewport().size_changed.connect(_layout)
	_layout()


func _build_panel() -> void:
	_panel = PanelContainer.new()
	_panel.add_theme_stylebox_override("panel", BettingBar._lifted(BettingBar._box(BettingBar.CORNER_BG, Color(BRASS, 0.38), 12, Vector4(1, 0, 1, 1))))
	add_child(_panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 0)
	_panel.add_child(box)
	var head := HBoxContainer.new()
	head.custom_minimum_size.y = HEAD_H
	head.add_theme_constant_override("separation", 4)
	box.add_child(head)
	var gap := Control.new()
	gap.custom_minimum_size.x = 7
	head.add_child(gap)
	_here = _label("", 15, BRASS_HI)
	_here.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_here.clip_text = true
	_here.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	head.add_child(_here)
	_find_btn = MapButton.new("find", "FIND")
	_find_btn.tooltip_text = "Find the nearest table"
	_find_btn.pressed.connect(func():
		if _find.visible:
			close_find()
		else:
			find_opened.emit())
	head.add_child(_find_btn)
	var x := MapButton.new("close")
	x.tooltip_text = "Fold the minimap"
	x.pressed.connect(func(): Settings.set_value("minimap_collapsed", true))
	head.add_child(x)
	var line := ColorRect.new()
	line.color = Color(BRASS, 0.18)
	line.custom_minimum_size.y = 1
	box.add_child(line)
	_map = Control.new()
	_map.clip_contents = true
	_map.mouse_filter = MOUSE_FILTER_PASS
	_map.draw.connect(_draw_map)
	_map.gui_input.connect(_map_input)
	box.add_child(_map)
	var zoom := VBoxContainer.new()
	zoom.add_theme_constant_override("separation", 4)
	_map.add_child(zoom)
	_zoom_in = MapButton.new("plus", "", true)
	_zoom_in.tooltip_text = "Zoom in"
	_zoom_in.pressed.connect(func(): Settings.set_value("minimap_zoom", mini(int(Settings.value("minimap_zoom")) + 1, ZOOMS.size() - 1)))
	zoom.add_child(_zoom_in)
	_zoom_out = MapButton.new("minus", "", true)
	_zoom_out.tooltip_text = "Zoom out"
	_zoom_out.pressed.connect(func(): Settings.set_value("minimap_zoom", maxi(mini(int(Settings.value("minimap_zoom")), _zoom_top) - 1, 0)))
	zoom.add_child(_zoom_out)
	_map.resized.connect(func(): zoom.position = _map.size - zoom.get_combined_minimum_size() - Vector2(6, 6))


func _build_find() -> void:
	_find = PanelContainer.new()
	_find.hide()
	_find.add_theme_stylebox_override("panel", BettingBar._lifted(BettingBar._box(BettingBar.CORNER_BG, Color(BRASS, 0.45), 12, Vector4(6, 6, 6, 6))))
	add_child(_find)
	_find_rows = VBoxContainer.new()
	_find_rows.add_theme_constant_override("separation", 0)
	_find.add_child(_find_rows)


func _build_guide() -> void:
	_guide = PanelContainer.new()
	_guide.hide()
	_guide.add_theme_stylebox_override("panel", BettingBar._lifted(BettingBar._box(BettingBar.CORNER_BG, BRASS, 20, Vector4(13, 5, 6, 5))))
	add_child(_guide)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	_guide.add_child(row)
	_guide_name = _label("", 16, INK)
	_guide_name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_guide_name.clip_text = true
	_guide_name.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	row.add_child(_guide_name)
	_guide_dist = _label("", 16, MUTED)
	row.add_child(_guide_dist)
	_walk = Button.new()
	_walk.text = "WALK THERE"
	_walk.focus_mode = FOCUS_NONE
	_walk.mouse_default_cursor_shape = CURSOR_POINTING_HAND
	_walk.custom_minimum_size = Vector2(0, 28)
	_walk.add_theme_font_override("font", FONT)
	_walk.add_theme_font_size_override("font_size", 15)
	for c in ["font_color", "font_hover_color", "font_pressed_color"]:
		_walk.add_theme_color_override(c, Color("1b1307"))
	_walk.add_theme_stylebox_override("normal", BettingBar._box(BRASS, BRASS, 14, Vector4(12, 0, 12, 0)))
	_walk.add_theme_stylebox_override("hover", BettingBar._box(Color("d6b05a"), BRASS, 14, Vector4(12, 0, 12, 0)))
	_walk.add_theme_stylebox_override("pressed", BettingBar._box(Color("d6b05a"), BRASS, 14, Vector4(12, 0, 12, 0)))
	_walk.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	_walk.pressed.connect(walk_pressed.emit)
	row.add_child(_walk)
	var x := MapButton.new("close", "", true)
	x.tooltip_text = "Stop guiding [Esc]"
	x.pressed.connect(guide_closed.emit)
	row.add_child(x)


func _label(text: String, size: int, colour: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", FONT)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", colour)
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.mouse_filter = MOUSE_FILTER_IGNORE
	return l


# ------------------------------------------------------------------ the corner
func is_open() -> bool:
	return _panel.visible


## The HUD's mode: hidden at a slot's full-screen game; Find (and the guide) only while walking.
func set_mode(mode: String) -> void:
	_mode = mode
	if mode != "walking":
		close_find()
	_layout()


## How wide the corner is (the map, the folded button, or nothing), for what sits to its left.
func corner_width() -> float:
	if _panel.visible:
		return _panel.size.x
	return _fold.size.x if _fold.visible else 0.0


## Where the map's corner ends, for what opens under it (the paytable). 0: nothing there.
func corner_bottom() -> float:
	if _panel.visible:
		return _panel.position.y + _panel.size.y
	return _fold.position.y + _fold.size.y if _fold.visible else 0.0


## The small map, whose Find list keeps to its width.
func _compact() -> bool:
	return str(Settings.value("minimap_size")) == "small"


func _width() -> float:
	var vs := get_viewport_rect().size
	return roundf(minf(WIDTHS.get(str(Settings.value("minimap_size")), WIDTHS.large), maxf(160.0, vs.x * 0.36)))


func _layout() -> void:
	if _panel == null:
		return
	var vs := get_viewport_rect().size
	var on := bool(Settings.value("show_minimap")) and _mode != "slot"
	var folded := bool(Settings.value("minimap_collapsed"))
	_panel.visible = on and not folded
	_fold.visible = on and folded
	_find_btn.visible = _mode == "walking"
	var w := _width()
	_map.custom_minimum_size = Vector2(w, roundf(w * MAP_RATIO))
	_panel.size = Vector2.ZERO
	_panel.reset_size()
	_panel.position = Vector2(vs.x - BettingBar.CORNER_INSET.x - _panel.size.x, BettingBar.CORNER_INSET.y)
	_fold.size = Vector2(_fold.get_combined_minimum_size().x, 40)
	_fold.position = Vector2(vs.x - BettingBar.CORNER_INSET.x - _fold.size.x, BettingBar.CORNER_INSET.y)
	if not _panel.visible:
		close_find()
	_guide.visible = _target != null and _mode == "walking" and on
	var y := corner_bottom() + 8.0
	_guide.reset_size()
	_guide.size.x = maxf(_guide.get_combined_minimum_size().x, _panel.size.x if _panel.visible else 0.0)
	_guide.position = Vector2(vs.x - BettingBar.CORNER_INSET.x - _guide.size.x, y)
	if _guide.visible:
		y += _guide.size.y + 8.0
	_find.reset_size()
	if _compact():   # the small map: its list exactly as wide, long names cut short
		_find.size.x = _panel.size.x
	else:
		_find.size.x = maxf(_find.get_combined_minimum_size().x, maxf(230.0, _panel.size.x))
	_find.position = Vector2(vs.x - BettingBar.CORNER_INSET.x - _find.size.x, y)
	_drawn = []
	_map.queue_redraw()
	corner_changed.emit()


# ------------------------------------------------------------------ fed by the floor
## The floor's rooms, tables (its own dictionaries: they stay current, a swapped Master Table too) and zones.
func set_world(rooms: Dictionary, tables: Dictionary, zone_of: Dictionary) -> void:
	_rooms = rooms
	_tables = tables
	_zone_of = zone_of
	_drawn = []


## Every frame: the room you're in, where you are and which way you face (World's frame), how far the floor's
## turned, and where the other real players are.
func follow(room_id: String, pos: Vector2, facing: String, turn: float, people: PackedVector2Array, delta: float) -> void:
	_room_id = room_id
	_pos = pos
	_facing = facing
	_turn = turn
	_people = people
	if _rooms.has(room_id) and _here.text != str(_rooms[room_id].data.get("name", "")).to_upper():
		_here.text = str(_rooms[room_id].data.get("name", "")).to_upper()
	if not _panel.visible:
		return
	_redraw_in -= delta
	var now := [room_id, pos.snapped(Vector2(2, 2)), facing, snappedf(turn, 0.01), people, _route.size()]
	if now != _drawn or _redraw_in <= 0.0:   # (and four times a second anyway: who's sitting where)
		_drawn = now
		_redraw_in = 0.25
		_map.queue_redraw()


## The way to a Find target (World's frame), with what it is and how far (an empty path: guiding's over).
func set_route(path: PackedVector2Array, target: Variant = null, what := "", metres := 0) -> void:
	var was := _target != null
	_route = path
	_target = target if not path.is_empty() else null
	if _target != null:
		_guide_name.text = "Guiding to " + what
		_guide_dist.text = "%d m" % maxi(metres, 1)
	if was != (_target != null):
		_layout()
	else:
		_map.queue_redraw()


func guiding() -> bool:
	return _target != null


## Find's list: [{kind, name, count, free, metres}], nearest first within each kind.
func show_find(options: Array) -> void:
	for c in _find_rows.get_children():
		c.queue_free()
	var head := _label("FIND THE NEAREST", 13, MUTED)
	head.custom_minimum_size.y = 24
	_find_rows.add_child(head)
	if options.is_empty():
		_find_rows.add_child(_label("Nothing to find here yet", 16, MUTED))
	var small := _compact()
	for o in options:
		var b := Button.new()
		b.focus_mode = FOCUS_NONE
		b.mouse_default_cursor_shape = CURSOR_POINTING_HAND
		b.custom_minimum_size = Vector2(0, 30 if small else 32)
		b.add_theme_stylebox_override("normal", StyleBoxEmpty.new())
		b.add_theme_stylebox_override("hover", BettingBar._box(Color(BRASS, 0.12), Color(0, 0, 0, 0), 8, Vector4.ZERO))
		b.add_theme_stylebox_override("pressed", BettingBar._box(Color(BRASS, 0.2), Color(0, 0, 0, 0), 8, Vector4.ZERO))
		b.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
		var row := HBoxContainer.new()
		row.set_anchors_preset(Control.PRESET_FULL_RECT)
		row.offset_left = 6 if small else 8
		row.offset_right = -6 if small else -8
		row.add_theme_constant_override("separation", 7 if small else 9)
		row.mouse_filter = MOUSE_FILTER_IGNORE
		b.add_child(row)
		var swatch := Panel.new()
		swatch.custom_minimum_size = Vector2(10, 10) if small else Vector2(12, 12)
		swatch.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		swatch.mouse_filter = MOUSE_FILTER_IGNORE
		swatch.add_theme_stylebox_override("panel", BettingBar._box(kind_colour(o.kind), kind_colour(o.kind), 3, Vector4.ZERO))
		row.add_child(swatch)
		var n := _label(str(o.name), 15 if small else 17, INK)
		n.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		if small:
			n.clip_text = true
			n.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
			b.tooltip_text = str(o.name)
		row.add_child(n)
		var bits := []
		if int(o.count) > 1:
			bits.append(str(o.count))
		if not o.free:
			bits.append("full")
		if int(o.metres) > 0:
			bits.append("%d m" % o.metres)
		var meta := _label((" · " if small else "  ·  ").join(bits), 13 if small else 15, BettingBar.LOSS if not o.free else MUTED)
		row.add_child(meta)
		if not small:
			b.custom_minimum_size.x = 12 + 9 + n.get_combined_minimum_size().x + 9 + meta.get_combined_minimum_size().x + 16 + 24
		var kind: String = o.kind
		b.pressed.connect(func():
			close_find()
			find_picked.emit(kind))
		_find_rows.add_child(b)
	_find.show()
	_find_btn.button_pressed = true
	_layout.call_deferred()


func close_find() -> void:
	if _find and _find.visible:
		_find.hide()
		_find_btn.button_pressed = false
		_find_btn.queue_redraw()


func find_open() -> bool:
	return _find.visible


## Esc closes Find's list, else stops the guiding.
func _input(event: InputEvent) -> void:
	if not event.is_action_pressed("cancel"):
		return
	if _find.visible:
		close_find()
		get_viewport().set_input_as_handled()
	elif _target != null and _mode == "walking":
		guide_closed.emit()
		get_viewport().set_input_as_handled()


# ------------------------------------------------------------------ what's what
## A table's kind on the map (and in Find): "master_table", its game, "slot".
static func kind_of(t: FloorGame) -> String:
	if t is SlotCabinet:
		return "slot"
	var c := t as CasinoTable
	return "master_table" if c.is_master else c.game


static func kind_colour(kind: String) -> Color:
	return KINDS[kind][0] if KINDS.has(kind) else CARDS


## What a kind's called in Find (its tables' own name for roulette and craps, which the plan may label).
static func kind_name(kind: String, t: Node = null) -> String:
	match kind:
		"master_table":
			return "Master Table"
		"slot":
			return "Slots"
		"atm":
			return "ATM"
		"roulette", "craps":
			return (t as CasinoTable).game_label if t is CasinoTable else kind.capitalize()
	return MasterPanel.name_of(kind)


# ------------------------------------------------------------------ the map
## The rooms on the map: your zone, and every zone one doorway on -- less any room the plan leaves off the minimap.
func _map_rooms() -> Dictionary:
	var shown := {}
	if not _rooms.has(_room_id):
		return shown
	for id in _rooms:
		if _zone_of.get(id) == _zone_of.get(_room_id):
			shown[id] = true
	for id in shown.keys():
		for o in _rooms[id].openings:
			var to = o.get("to")
			if to != null and _rooms.has(str(to)):
				for id2 in _rooms:
					if _zone_of.get(id2) == _zone_of.get(str(to)):
						shown[id2] = true
	for id in shown.keys():
		if _rooms[id].data.get("map_hidden", false):
			shown.erase(id)
	return shown


func _draw_map() -> void:
	var shown := _map_rooms()
	if shown.is_empty():
		return
	var w := _map.size.x
	var h := _map.size.y
	var box := Rect2()
	for id in shown:
		box = _rooms[id].rect if box.size == Vector2.ZERO else box.merge(_rooms[id].rect)
	var fit := minf((w - 2.0 * PAD) / box.size.x, (h - 2.0 * PAD) / box.size.y)
	var base := clampf(fit, MIN_SCALE, MAX_SCALE)
	var least := minf(fit, base)
	var z := clampi(int(Settings.value("minimap_zoom")), 0, ZOOMS.size() - 1)
	_zoom_top = ZOOMS.size() - 1
	for i in ZOOMS.size():
		if least * ZOOMS[i] >= ZOOM_MAX:
			_zoom_top = i
			break
	var sc := maxf(least, minf(ZOOM_MAX, least * ZOOMS[z]))
	_zoom_out.disabled = z <= 0
	_zoom_in.disabled = z >= _zoom_top
	var centre := box.get_center()
	if sc > fit * 1.001:   # it won't all fit: keep as much of it in view as it can, with you in the middle 80%
		var half := Vector2(w, h) / 2.0 / sc * 0.8
		centre = centre.clamp(_pos - half, _pos + half)
	var xf := Transform2D(_turn, Vector2(w, h) / 2.0) * Transform2D(0.0, Vector2(sc, sc), 0.0, Vector2.ZERO) * Transform2D(0.0, -centre)
	var px := 1.0 / sc
	var here_zone = _zone_of.get(_room_id)
	var all_names := str(Settings.value("minimap_labels")) == "all"
	var picking := _mode == "walking"
	_hits = []
	_map.draw_set_transform_matrix(xf)
	for id in shown:   # the rooms: yours lit, the others dim
		var r: PlanRoom = _rooms[id]
		var mine: bool = _zone_of.get(id) == here_zone
		var inner := _inner(r)
		_map.draw_rect(inner, _floor_colour(r, 0.55 if mine else 0.22))
		_map.draw_rect(inner, Color(BRASS_HI, 0.55 if mine else 0.22), false, 1.2 * px)
	for id in shown:   # doorways: dashed brass if they lead on, red to the street
		var r: PlanRoom = _rooms[id]
		for o in r.openings:
			var seg := _door_line(r, o)
			var leads: bool = o.get("to") != null
			if leads:
				_map.draw_dashed_line(seg[0], seg[1], BRASS_HI, 2.4 * px, 3.0 * px)
			else:
				_map.draw_line(seg[0], seg[1], Color(BettingBar.LOSS, 0.8), 2.4 * px)
	var labels := []
	var banks := {}   # cabinets side by side are one bank
	for t in _tables.values():
		if not is_instance_valid(t) or not shown.has(_room_of(t)):
			continue
		var kind := kind_of(t)
		var full: bool = t.free_seats().is_empty()
		if kind == "slot":
			_bank(banks, t)
			continue
		var body: Rect2 = BODIES.get(kind, CARD_BODY)
		var col := kind_colour(kind)
		if full:
			col.a = 0.42
		var at := _at(t)
		_map.draw_set_transform_matrix(xf * Transform2D(t.rotation, at))
		_map.draw_rect(body, col)
		if kind == "roulette":
			_map.draw_circle(Vector2(-115, -57), 46, Color(0, 0, 0, 0.35))
		_map.draw_set_transform_matrix(xf)
		if _zone_of.get(_room_of(t)) == here_zone or all_names:
			if picking:
				_hits.append([_screen_rect(xf * Transform2D(t.rotation, at), body), [t]])
			var text: String = KINDS[kind][1] if KINDS.has(kind) else SHORT.get(kind, (t as CasinoTable).game_label)
			var sub := ""
			if kind == "master_table" and (t as CasinoTable).master_game != "":
				sub = (t as CasinoTable).game_label
			elif full:
				sub = "Full"
			labels.append({"at": at + Vector2(0, body.get_center().y).rotated(t.rotation), "text": text, "sub": sub,
				"w": body.size.x * sc, "near": _zone_of.get(_room_of(t)) != here_zone, "full": full})
	for b in banks.values():
		var col := kind_colour("slot")
		if b.free == 0:
			col.a = 0.42
		_map.draw_rect(b.rect, col)
		for c in b.cabs:
			_map.draw_line(Vector2(_at(c).x, b.rect.position.y), Vector2(_at(c).x, b.rect.end.y), Color(0, 0, 0, 0.35), 2.0 * px)
		if _zone_of.get(b.room) == here_zone or all_names:
			if picking:
				_hits.append([_screen_rect(xf, b.rect), b.cabs])
			labels.append({"at": b.rect.get_center(), "text": "Slots", "sub": "Full" if b.free == 0 else "", "w": maxf(b.rect.size.x, 200.0) * sc,
				"near": _zone_of.get(b.room) != here_zone, "full": b.free == 0})
	if _target != null:
		for i in range(1, _route.size()):
			_map.draw_dashed_line(_route[i - 1], _route[i], BRASS_HI, 2.2 * px, 5.0 * px)
		_map.draw_arc(_target, 7.0 * px, 0, TAU, 20, BRASS_HI, 2.0 * px)
		_map.draw_circle(_target, 2.5 * px, BRASS_HI)
	for p in _people:
		if shown.has(_room_at(p)):
			_map.draw_circle(p, 3.6 * px, Color(0, 0, 0, 0.6))
			_map.draw_circle(p, 2.8 * px, INK)
	_map.draw_set_transform_matrix(Transform2D.IDENTITY)
	# ...and on top, upright whatever the turn: the rooms' names, the doors' tabs, the labels, you
	var placed: Array[Rect2] = []   # (labels keep off the ATMs, the names and each other)
	for f in get_tree().get_nodes_in_group("interactables"):   # the ATMs: a square saying so where tables are named
		if f.interact != "atm" or not shown.has(_room_of(f)):
			continue
		var q: Vector2 = xf * (_at(f) + Vector2(0, -10))
		var near: bool = _zone_of.get(_room_of(f)) != here_zone
		if near and not all_names:
			_map.draw_rect(Rect2(q - Vector2(5, 5), Vector2(10, 10)), Color(kind_colour("atm"), 0.7))
			continue
		var sq := Rect2(q - Vector2(11, 11), Vector2(22, 22))
		_map.draw_style_box(BettingBar._box(Color(kind_colour("atm"), 0.7 if near else 1.0), Color(0, 0, 0, 0.6), 3, Vector4.ZERO), sq)
		_text(q, "ATM", 9, Color("0b0d0e"))
		placed.append(sq)
		if picking:
			_hits.append([sq, [f]])
	for id in shown:
		var r: PlanRoom = _rooms[id]
		var s := _screen_rect(xf, _inner(r))
		var text := str(r.data.get("name", "")).to_upper()
		var tw := FONT.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 11).x
		var top := maxf(s.position.y, 0.0)
		if s.end.y - top < 24.0 or tw > s.size.x - 8.0 or top + 9.0 > h:
			continue
		var cx := clampf((maxf(s.position.x, 0.0) + minf(s.end.x, w)) / 2.0, tw / 2.0 + 4.0, w - tw / 2.0 - 4.0)
		var nr := Rect2(cx - tw / 2.0 - 2.0, top + 2.0, tw + 4.0, 14.0)
		if placed.any(func(q): return q.intersects(nr)):
			continue   # (an ATM against the back wall: the header names your room anyway)
		placed.append(nr)
		_text(Vector2(cx, top + 9.0), text, 11, Color(BRASS_HI, 0.95) if _zone_of.get(id) == here_zone else Color(INK, 0.6))
	for l in labels:
		var at: Vector2 = xf * l.at
		var tw := FONT.get_string_size(l.text, HORIZONTAL_ALIGNMENT_LEFT, -1, 11).x
		if tw > l.w + 18.0:
			continue
		var hgt := 22.0 if l.sub != "" else 13.0
		var r := Rect2(at.x - tw / 2.0 - 3.0, at.y - hgt / 2.0, tw + 6.0, hgt)
		if r.position.x < 2 or r.position.y < 2 or r.end.x > w - 2 or r.end.y > h - 2 or placed.any(func(q): return q.intersects(r)):
			continue
		placed.append(r)
		if picking:   # (a name is clickable too, where it overhangs its table)
			for hit in _hits:
				if hit[0].has_point(at):
					hit[0] = hit[0].merge(r)
					break
		var a := 0.7 if l.near else 1.0
		_map.draw_style_box(BettingBar._box(Color(0.04, 0.047, 0.05, 0.75 * a), Color(0, 0, 0, 0), 3, Vector4.ZERO), r)
		_text(Vector2(at.x, at.y - (4.0 if l.sub != "" else 0.0)), l.text, 11, Color(INK, (0.6 if l.full else 1.0) * a))
		if l.sub != "":
			_text(Vector2(at.x, at.y + 6.0), l.sub, 9, Color(BettingBar.LOSS if l.full else BRASS_HI, a))
	for id in shown:   # a door to a room further on: a tab with its name, pointing through it
		var r: PlanRoom = _rooms[id]
		for o in r.openings:
			var to = o.get("to")
			if to == null or shown.has(str(to)) or not _rooms.has(str(to)) or _rooms[str(to)].data.get("map_hidden", false):
				continue
			var seg := _door_line(r, o)
			var mid: Vector2 = (seg[0] + seg[1]) / 2.0
			var out: Vector2 = {"top": Vector2.UP, "bottom": Vector2.DOWN, "left": Vector2.LEFT, "right": Vector2.RIGHT}[str(o.side)]
			var a: Vector2 = xf * mid
			var dir: Vector2 = ((xf * (mid + out)) - a).normalized()
			_tab(a + dir * 12.0, str(_rooms[str(to)].data.get("name", "")), dir, w, h)
	_arrow(xf * _pos, Vector2.from_angle({"up": -PI / 2.0, "down": PI / 2.0, "left": PI, "right": 0.0}.get(_facing, -PI / 2.0) + _turn), 7.0)
	if _target != null:   # off the map: an arrow on its edge pointing there
		var q: Vector2 = xf * (_target as Vector2)
		if not Rect2(6, 6, w - 12, h - 12).has_point(q):
			var d := (q - Vector2(w, h) / 2.0).normalized()
			var k := minf((w / 2.0 - 10.0) / maxf(absf(d.x), 0.001), (h / 2.0 - 10.0) / maxf(absf(d.y), 0.001))
			_arrow(Vector2(w, h) / 2.0 + d * k, d, 7.0)


## A click on something the map names guides you there; the pointing hand over it.
func _map_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		_map.mouse_default_cursor_shape = CURSOR_POINTING_HAND if not _hit_at(event.position).is_empty() else CURSOR_ARROW
	elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var targets := _hit_at(event.position)
		if not targets.is_empty():
			close_find()
			map_picked.emit(targets)
			_map.accept_event()


## What's under `at` on the map (the last drawn first), still on the floor.
func _hit_at(at: Vector2) -> Array:
	for i in range(_hits.size() - 1, -1, -1):
		if _hits[i][0].has_point(at):
			var alive: Array = _hits[i][1].filter(func(n): return is_instance_valid(n))
			if not alive.is_empty():
				return alive
	return []


## A room inside its walls (its back wall's lower half counts: the map shows where you can walk).
func _inner(r: PlanRoom) -> Rect2:
	return Rect2(r.rect.position + Vector2(r.wall.side, r.wall.top * 0.5),
		r.rect.size - Vector2(2.0 * r.wall.side, r.wall.top * 0.5 + r.wall.bottom))


## A doorway as a line along the room's inner edge, in World's frame.
func _door_line(r: PlanRoom, o: Dictionary) -> Array:
	var g: Rect2 = r._gap(o)
	g.position += r.position
	var i := _inner(r)
	match str(o.side):
		"top":
			return [Vector2(g.position.x, i.position.y), Vector2(g.end.x, i.position.y)]
		"bottom":
			return [Vector2(g.position.x, i.end.y), Vector2(g.end.x, i.end.y)]
		"left":
			return [Vector2(i.position.x, g.position.y), Vector2(i.position.x, g.end.y)]
	return [Vector2(i.end.x, g.position.y), Vector2(i.end.x, g.end.y)]


## A room's floor colour on the map: its tint, lifted towards the house ink.
func _floor_colour(r: PlanRoom, k: float) -> Color:
	var tint := Color(str(r.data.get("floor", {}).get("tint", "#ffffff")))
	var base := Color("2c3134") if tint.is_equal_approx(Color.WHITE) else tint.darkened(0.55)
	return base.lerp(INK, k * 0.35)


func _bank(banks: Dictionary, c: FloorGame) -> void:
	var room := _room_of(c)
	var turn: float = {"up": PI, "left": PI / 2.0, "right": -PI / 2.0}.get(str(c.get("facing")), 0.0)
	var rect := Transform2D(turn, _at(c)) * CABINET
	for key in banks:
		var b: Dictionary = banks[key]
		if b.room == room and b.rect.grow(24.0).intersects(rect):
			b.rect = b.rect.merge(rect)
			b.cabs.append(c)
			b.free += c.free_seats().size()
			return
	banks[c.table_id] = {"room": room, "rect": rect, "cabs": [c], "free": c.free_seats().size()}


func _room_of(n: Node2D) -> String:
	var p := n.get_parent()
	return (p as PlanRoom).id if p is PlanRoom else _room_at(n.position)


## Where something in a room is in World's frame (rooms place what's in them from their corner).
func _at(n: Node2D) -> Vector2:
	var p := n.get_parent()
	return n.position + ((p as PlanRoom).position if p is PlanRoom else Vector2.ZERO)


func _room_at(p: Vector2) -> String:
	for id in _rooms:
		if _rooms[id].contains(p):
			return id
	return ""


func _screen_rect(xf: Transform2D, r: Rect2) -> Rect2:
	var out := Rect2(xf * r.position, Vector2.ZERO)
	for c in [Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)]:
		out = out.expand(xf * c)
	return out


func _text(centre: Vector2, text: String, size: int, colour: Color) -> void:
	var tw := FONT.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	_map.draw_string(FONT, Vector2(centre.x - tw / 2.0, centre.y + (FONT.get_ascent(size) - FONT.get_descent(size)) / 2.0), text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, size, colour)


func _tab(at: Vector2, text: String, dir: Vector2, w: float, h: float) -> void:
	var tw := FONT.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 11).x
	var r := Rect2(at.x - tw / 2.0 - 12.0, at.y - 8.0, tw + 20.0, 16.0)
	r.position = r.position.clamp(Vector2(3, 3), Vector2(w - r.size.x - 3.0, h - r.size.y - 3.0))
	_map.draw_style_box(BettingBar._box(Color(0.08, 0.07, 0.05, 0.92), Color(BRASS_HI, 0.7), 8, Vector4.ZERO), r)
	_map.draw_string(FONT, Vector2(r.position.x + 6.0, r.position.y + 8.0 + (FONT.get_ascent(11) - FONT.get_descent(11)) / 2.0), text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 11, BRASS_HI)
	_arrow(Vector2(r.end.x - 7.0, r.position.y + 8.0), dir, 4.0, false)


## An arrowhead at `at` pointing along `dir`.
func _arrow(at: Vector2, dir: Vector2, s: float, outlined := true) -> void:
	var side := dir.orthogonal()
	var pts := PackedVector2Array([at + dir * s * 1.25, at - dir * s * 0.8 - side * s * 0.8, at - dir * s * 0.35, at - dir * s * 0.8 + side * s * 0.8])
	_map.draw_colored_polygon(pts, BRASS_HI)
	if outlined:
		pts.append(pts[0])
		_map.draw_polyline(pts, Color("0b0d0e"), 1.5, true)


## The map's own small buttons: a glyph (find, close, plus, minus) with an optional word, a brass edge on hover.
class MapButton extends Button:
	var glyph := ""
	var words := ""
	var round_ := false

	func _init(g: String, w := "", is_round := false) -> void:
		glyph = g
		words = w
		round_ = is_round
		focus_mode = FOCUS_NONE
		mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		var h := 24.0 if is_round else 22.0
		var wd := h if w == "" else 17.0 + BettingBar.FONT.get_string_size(w, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x + 12.0
		custom_minimum_size = Vector2(wd, h)
		size_flags_vertical = Control.SIZE_SHRINK_CENTER
		var bg := Color(0.04, 0.047, 0.05, 0.85) if is_round else Color(0, 0, 0, 0)
		var edge := Color(BettingBar.BRASS, 0.45) if is_round else Color(0, 0, 0, 0)
		var radius := 12 if is_round else 6
		add_theme_stylebox_override("normal", BettingBar._box(bg, edge, radius, Vector4.ZERO))
		add_theme_stylebox_override("hover", BettingBar._box(Color(BettingBar.BRASS, 0.12), Color(BettingBar.BRASS, 0.6), radius, Vector4.ZERO))
		add_theme_stylebox_override("pressed", BettingBar._box(Color(BettingBar.BRASS, 0.16), Color(BettingBar.BRASS, 0.6), radius, Vector4.ZERO))
		add_theme_stylebox_override("hover_pressed", BettingBar._box(Color(BettingBar.BRASS, 0.16), Color(BettingBar.BRASS, 0.6), radius, Vector4.ZERO))
		add_theme_stylebox_override("disabled", BettingBar._box(bg, edge, radius, Vector4.ZERO))
		add_theme_stylebox_override("focus", StyleBoxEmpty.new())
		toggle_mode = glyph == "find"

	func _draw() -> void:
		modulate.a = 0.35 if disabled else 1.0
		var col := BettingBar.BRASS_HI if round_ or button_pressed else BettingBar.INK
		if glyph == "close" and not round_:
			col = BettingBar.MUTED
		var c := Vector2(size.y / 2.0 + (3.0 if words != "" else 0.0), size.y / 2.0) if words != "" else size / 2.0
		match glyph:
			"find":
				draw_arc(c + Vector2(-1, -1), 4.2, 0, TAU, 16, col, 1.7, true)
				draw_line(c + Vector2(2, 2), c + Vector2(5.5, 5.5), col, 1.8, true)
			"close":
				draw_line(c + Vector2(-4, -4), c + Vector2(4, 4), col, 1.7, true)
				draw_line(c + Vector2(4, -4), c + Vector2(-4, 4), col, 1.7, true)
			"plus":
				draw_line(c + Vector2(-4.5, 0), c + Vector2(4.5, 0), col, 2.0, true)
				draw_line(c + Vector2(0, -4.5), c + Vector2(0, 4.5), col, 2.0, true)
			"minus":
				draw_line(c + Vector2(-4.5, 0), c + Vector2(4.5, 0), col, 2.0, true)
		if words != "":
			var f := BettingBar.FONT
			draw_string(f, Vector2(c.x + 9.0, size.y / 2.0 + (f.get_ascent(14) - f.get_descent(14)) / 2.0 - 0.5), words,
				HORIZONTAL_ALIGNMENT_LEFT, -1, 14, col)
