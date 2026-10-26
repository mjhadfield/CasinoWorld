extends Node2D
## The casino floor: everyone walking around (you, other players, NPCs), the
## tables, and the camera. Free chairs glow while you're walking: click one to
## sit there (you walk over first if it's far), or stand by a table or slot with a
## free chair and the HUD offers it (Play): press E or the prompt. The camera glides
## onto the table and stays in this same world, so the floor carries on around you.
## Stand up and the camera glides back. You can't walk through the chairs, the tables
## or anyone else (see LocalPlayer).
##
## Walk up to the lobby's ATM (a piece in group "interactables") and the HUD offers it (Use ATM): press E, the prompt,
## or click the machine (from afar you walk over first). Its screen (AtmPanel) holds you still until you leave it.
## The prompt sits under your feet.
##
## The server owns the table and the world; this scene routes its messages to
## the right avatar or table and turns your clicks into requests.
##
## The floor is built from the server's floor plan (the welcome's `world`; plan.py): each room a PlanRoom under
## World/Rooms with its walls, doorways, tables, cabinets and decor, rebuilt when the plan changes (a `world`
## message: once you've stood up, if you're sitting). Rooms joined by archways show together; a room through a door
## shows once you're in its doorway, and the rest are hidden (people in them too, and their sounds). The camera
## keeps to the rooms on show.
##
## Everything on the floor is under World, and every position the floor and the
## server deal in is in World's frame. A table can be turned (`rotation`: a turned
## blackjack table has its dealer's back to the room's far side), and
## sitting at one turns World about the table so it shows the right way up; World's
## Y-sort turns with it, so who's in front of whom stays right. Standing turns it
## back. The camera stays unturned, and avatars stand upright whatever the turn.
##
## The HUD's minimap is fed from here every frame (where you are, which room, the turn, the other real players), and
## its Find is worked out here: the nearest table of a kind by the navigation map's path (one with a free seat if
## there is one), drawn on the floor (RouteLine) and the map until you get there, sit down anywhere, or stop it.
## Find's way is planned the way a person would walk it: on a second, roomier navigation map (WIDE_CLEARANCE) that
## keeps well off the tables and walls, and rounded at the corners as far as the floor allows. Walk there walks
## exactly that way.
##
## A preview (Session.preview: the admin page's Preview button) builds the draft's floor instead, to walk round
## alone: nobody else is there, and the tables can't be sat at.

const WALK_ZOOM := Vector2(2, 2)
const TABLE_ZOOM := Vector2(2.8, 2.8)
const ENTITY_SCENE := preload("res://scenes/world/entity_avatar.tscn")
const MAIN_BET_NAMES := {"ante": "an Ante", "bet": "a Blackjack bet", "player": "a Player, Banker or Tie bet"}

@onready var world: Node2D = $World
@onready var player: CharacterBody2D = $World/LocalPlayer
@onready var camera: Camera2D = $Camera
@onready var hud: CanvasLayer = $HUD
@onready var entities_root: Node2D = $World/Entities
@onready var nav: NavigationRegion2D = $Nav   # (outside World, never turned: the nav map is in World's frame)
@onready var rooms_root: Node2D = $World/Rooms

var tables := {}    # table id -> FloorGame (a CasinoTable, or a SlotCabinet)
var points := {}    # "room/name" -> position (the floor plan's points)
var rooms := {}     # room id -> PlanRoom
var spawn := ""     # the point players appear at
var _world_rev := -1
var _pending_world = null   # a new floor plan that came while you sat: built once you're up and walking
var _zone_of := {}  # room id -> its zone (rooms joined by archways show together)
var _shown := {}    # the room ids on show
var _here := ""     # the room you're in
var entities := {}  # entity id -> EntityAvatar (everyone but you)
var state := "walking"  # walking | seated (at a table) | slot (at a slot cabinet, full screen)
var _heading_for := {}  # {table, seat} while walking over to a stool you clicked
var _heading_atm: Furniture = null   # the ATM you clicked from afar, while you walk over
var _atm_near: Furniture = null      # the ATM you're standing at (offered by the prompt)
var _play_near := {}                 # else the free chair you're standing by: {table, seat} (Play, on the prompt)
var _kick_near := {}                 # else an NPC's chair you're standing by: {table, seat} (Take seat, on the prompt)
var _kick_wait := {}                 # {table, seat} while you wait for the NPC you asked to get up (kick_waiting)
var active_table: CasinoTable = null
var active_slot: SlotCabinet = null   # the cabinet you're sitting at (state "slot")
var _slot_waiting := false   # sat at a cabinet, its game not open yet (the sit-down, then the camera, come first)
var _slot_snapshot := {}     # the cabinet's table_state that came while waiting, for the game once it opens
var slot_screen: SlotScreen
var my_seat := -1
var my_bets := {}
var my_ready := false
var sitting_out := false   # the bar's Sit out switch: Ready with no bets each time betting opens
var played_a_hand := false
var my_hand := ""  # your hand's name or total (shown in the HUD bar)
var _actions: Array = []  # the action buttons on offer right now (for their keys)
var _camera_tween: Tween
var _limits := []          # the camera's limits (lifted while the floor is turned)
var _bake_pending := false # a navigation bake waiting for the floor to be upright
var _was_my_turn := false
var _last_tick := -1      # the countdown second last ticked
var _placed: Array = []   # this round's chips, newest last ([spot, amount added]): what Undo takes back
var _round_start := -1    # your balance as this round's betting opened (its result flashes in the bar at the next)
var _staked := false      # whether you had bets in this round
var route_line: RouteLine  # Find's way there, on the floor
var _guide := {}           # while Find guides you: {kind, name, goal, path, replan}
var _wide_nav: NavigationRegion2D   # the floor baked again with room to spare, for Find's ways (on its own map)
var _wide_map: RID
var _wide_query := NavigationPathQueryParameters2D.new()   # (simplified: the rounding makes its curves)
var _wide_result := NavigationPathQueryResult2D.new()
var _arriving := false     # off the floor to pick another character: its welcome starts you at the spawn point
const GUIDE_ARRIVED := 24.0   # this close to where you'd stand, you're there
const PX_PER_METRE := 32.0
const WIDE_CLEARANCE := 24.0  # how far Find's ways keep off things (you're 9 wide: Nav's agent_radius)
const CORNERS := [96.0, 64.0, 40.0, 24.0, 12.0]   # how far before a corner its curve starts, widest first


func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE and _wide_map.is_valid():
		NavigationServer2D.free_rid(_wide_map)


func _enter_tree() -> void:
	UiTheme.install()   # (before the HUD builds its controls)


func _ready() -> void:
	slot_screen = SlotScreen.new()
	hud.add_slot_screen(slot_screen)
	slot_screen.stand_requested.connect(func(): Net.send("stand"))
	slot_screen.settings_requested.connect(hud.settings_menu.toggle)
	player.add_to_group("door_openers")
	player.add_to_group("local_player")
	camera.global_position = player.global_position
	camera.zoom = WALK_ZOOM
	camera.limit_smoothed = true
	_limits = [camera.limit_left, camera.limit_top, camera.limit_right, camera.limit_bottom]
	Sfx.audible = func(at: Vector2) -> bool: return _seen(world.to_local(at))
	get_viewport().size_changed.connect(_fit_limits)
	PlanArt.art_changed.connect(func(): _bake_navigation.call_deferred())   # (furniture blocks once its picture's in)
	Sfx.start_room()
	route_line = RouteLine.new()
	world.add_child(route_line)
	_wide_map = NavigationServer2D.map_create()
	NavigationServer2D.map_set_cell_size(_wide_map, nav.navigation_polygon.cell_size)
	NavigationServer2D.map_set_active(_wide_map, true)
	_wide_query.map = _wide_map
	_wide_query.simplify_path = true
	_wide_query.simplify_epsilon = 6.0
	_wide_nav = NavigationRegion2D.new()
	_wide_nav.navigation_polygon = nav.navigation_polygon.duplicate()
	_wide_nav.navigation_polygon.agent_radius = WIDE_CLEARANCE
	add_child(_wide_nav)
	_wide_nav.set_navigation_map(_wide_map)
	hud.minimap.find_opened.connect(func(): hud.minimap.show_find(_find_options()))
	hud.minimap.find_picked.connect(_guide_to)
	hud.minimap.map_picked.connect(func(targets: Array): _guide_to(Minimap.kind_of(targets[0]) if targets[0] is FloorGame else "atm", targets))
	hud.minimap.walk_pressed.connect(func():
		if not _guide.is_empty() and state == "walking":
			_heading_for = {}
			_heading_atm = null
			player.walk_along(_guide.path))
	hud.minimap.guide_closed.connect(_stop_guide)

	hud.rebet_pressed.connect(func():
		_placed.clear()
		_set_sitting_out(false)
		Net.send("rebet"))
	hud.auto_rebet_toggled.connect(func(on: bool):
		if on:
			_set_sitting_out(false)
		Net.send("auto_rebet", {"on": on}))
	hud.sit_out_toggled.connect(func(on: bool):
		if on and hud.auto_rebet_on():
			Net.send("auto_rebet", {"on": false})
		_set_sitting_out(on))
	hud.clear_pressed.connect(func():
		_placed.clear()
		Net.send("clear_bets"))
	hud.undo_pressed.connect(_undo)
	hud.chip_selected.connect(func(value: int):
		if active_table and "chip_value" in active_table:
			active_table.chip_value = value)
	hud.ready_pressed.connect(_on_ready)
	hud.action.connect(_on_action)
	hud.stand_pressed.connect(_request_stand)
	hud.stand_confirmed.connect(func(): Net.send("stand"))
	hud.switch_pressed.connect(func(): hud.front_door.open_switch(state == "walking"))
	Session.character_left.connect(func(_reason, _name): _off_the_floor())
	hud.interact_pressed.connect(_interact)
	hud.atm.closed.connect(func():
		if state == "walking":
			player.set_controls(true))
	hud.master.chosen.connect(func(game: String): Net.send("choose_game", {"game": game}))
	hud.master.voted.connect(func(accept: bool): Net.send("game_vote", {"accept": accept}))
	hud.master.cancel_queued.connect(func(): Net.send("cancel_game_change"))
	Net.message_received.connect(_on_message)
	Net.resynced.connect(_on_resynced)
	Settings.changed.connect(func(key: String, _v):
		if key == "seat_glow":
			_redraw_chairs())
	Net.disconnected.connect(_on_disconnected)


## The walkable floor: every room (the outlines overlap a pixel, so the baker joins them), less its wall bodies --
## which leave the doorways open -- and everything else in group navigation_obstacles. It reads the obstacles where
## they are now, so it waits while the floor is turned. Find's roomier copy (_wide_nav) is baked alongside.
func _bake_navigation() -> void:
	if not is_zero_approx(world.rotation):
		_bake_pending = true
		return
	_bake_pending = false
	for region in [nav, _wide_nav]:
		var poly: NavigationPolygon = region.navigation_polygon
		poly.clear_outlines()
		if rooms.is_empty():
			continue
		for r in rooms.values():
			var b: Rect2 = r.rect.grow(1)
			poly.add_outline(PackedVector2Array([b.position, Vector2(b.end.x, b.position.y), b.end, Vector2(b.position.x, b.end.y)]))
		region.bake_navigation_polygon(false)


# ------------------------------------------------------------------ the floor plan
## Build the floor from the plan (see the top). Every table and cabinet is made afresh; after a change (not the
## first build) a resync brings their states and everyone's places again.
func _build_world(w: Dictionary) -> void:
	if state != "walking":
		_pending_world = w
		return
	_pending_world = null
	var first := _world_rev < 0
	for r in rooms.values():
		rooms_root.remove_child(r)   # (out of the tree now, so the bake leaves it out)
		r.queue_free()
	rooms.clear()
	tables.clear()
	points.clear()
	_heading_for = {}
	for data in w.get("rooms", []):
		var r := PlanRoom.new()
		r.build(data, w)
		rooms_root.add_child(r)
		rooms[r.id] = r
		for g in r.games:
			_register(g)
		for k in r.points:
			points[k] = r.points[k].at
	_world_rev = int(w.get("rev", 0))
	spawn = str(w.get("spawn", ""))
	_zone_rooms(w)
	if first or w.has("start") or _room_at(player.position) == "":
		var start: Dictionary = w.get("start", {})
		player.position = Vector2(float(start.x), float(start.y)) if not start.is_empty() else _fallback_point()
		player.stop()
		camera.global_position = player.global_position
		camera.reset_smoothing()
	_here = ""
	_update_rooms(true)
	_restyle_tables()
	_redraw_chairs()
	_bake_navigation()
	_offer_seats(state == "walking")
	hud.minimap.set_world(rooms, tables, _zone_of)
	_stop_guide()
	if not first and Session.preview == "":
		Net.resync()


## A table or cabinet the floor just made: wire up what the floor listens to.
func _register(t: FloorGame) -> void:
	tables[t.table_id] = t
	if not t is CasinoTable:
		return
	t.spot_clicked.connect(_on_spot_clicked)
	t.spot_removed.connect(_on_spot_removed)
	t.dealer_clicked.connect(_on_dealer_clicked.bind(t))
	t.box_clicked.connect(_on_box_clicked.bind(t))
	t.my_hand_changed.connect(func(text: String):
		if t == active_table:
			my_hand = text)
	if t.has_signal("sort_requested"):  # Pai Gow: your cards open in the sorter, and close once set
		t.sort_requested.connect(func(cards: Array):
			if t == active_table:
				Sfx.play("turn")
				hud.sorter.look = t.style()
				hud.sorter.under = t.dealer_cards_bottom
				hud.sorter.open(cards, t.face_up))
		t.sort_finished.connect(func():
			if t == active_table:
				hud.sorter.close())
		t.claim_requested.connect(func(cards: Array, bonus):
			if t == active_table:
				Sfx.play("turn")
				hud.sorter.look = t.style()
				hud.sorter.under = t.dealer_cards_bottom
				hud.sorter.open_claim(cards, bonus))


## Where players appear (the plan's spawn point), else the middle of the first room.
func _fallback_point() -> Vector2:
	if points.has(spawn):
		return points[spawn]
	for r in rooms.values():
		return r.rect.get_center()
	return Vector2.ZERO


## Rooms joined by archways are one zone: they show together.
func _zone_rooms(w: Dictionary) -> void:
	_zone_of.clear()
	var zone := 0
	for id in rooms:
		if _zone_of.has(id):
			continue
		var todo := [id]
		while not todo.is_empty():
			var r: String = todo.pop_back()
			if _zone_of.has(r):
				continue
			_zone_of[r] = zone
			for o in rooms[r].openings:
				if o.kind == "archway" and o.get("to") != null and rooms.has(str(o.to)) and not _zone_of.has(str(o.to)):
					todo.append(str(o.to))
		zone += 1


func _room_at(p: Vector2) -> String:
	for id in rooms:
		if rooms[id].contains(p):
			return id
	return ""


## Which rooms show: your room's zone, and the zone through a door you're in (or right by) -- never an NPCs-only
## room, which NPCs just step out of. The camera keeps to them.
func _update_rooms(force := false) -> void:
	var here := _room_at(player.position)
	if here == "":
		here = _here
	var shown := {}
	if here != "" and rooms.has(here):
		for id in rooms:
			if _zone_of[id] == _zone_of[here]:
				shown[id] = true
		for id in shown.keys():
			for o in rooms[id].openings:
				if o.kind != "door" or o.get("to") == null or not rooms.has(str(o.to)) or rooms[str(o.to)].npc_only:
					continue
				var g: Rect2 = rooms[id]._gap(o)
				if Rect2(g.position + rooms[id].position, g.size).grow(40).has_point(player.position):
					for id2 in rooms:
						if _zone_of[id2] == _zone_of[str(o.to)]:
							shown[id2] = true
	else:
		for id in rooms:
			shown[id] = true
	if not force and here == _here and shown == _shown:
		return
	_here = here
	_shown = shown
	for id in rooms:
		rooms[id].visible = shown.has(id)
	_fit_limits()


## The camera's limits: round the rooms on show (with a strip above the back wall), centred on a room smaller than
## the view.
func _fit_limits() -> void:
	var box := Rect2()
	var any := false
	for id in _shown:
		box = rooms[id].rect if not any else box.merge(rooms[id].rect)
		any = true
	if not any:
		return
	box = box.grow_individual(0, 40, 0, 10)
	var view := get_viewport_rect().size / WALK_ZOOM
	var dx := maxf(0.0, view.x - box.size.x) / 2.0
	var dy := maxf(0.0, view.y - box.size.y) / 2.0
	box = box.grow_individual(dx, dy, dx, dy)
	_limits = [int(floor(box.position.x)), int(floor(box.position.y)), int(ceil(box.end.x)), int(ceil(box.end.y))]
	if is_zero_approx(world.rotation):
		_set_limits(true)


## Whether a place on the floor (World's frame) is in a room on show: people elsewhere are hidden, and not heard.
func _seen(p: Vector2) -> bool:
	if _shown.is_empty():
		return true
	for id in _shown:
		if rooms.has(id) and rooms[id].rect.grow(8).has_point(p):
			return true
	return false


func _process(delta: float) -> void:
	# Under a slot's full-screen game the floor isn't drawn (it plays on: the tables keep up).
	var covered := slot_screen.covers_floor()
	if world.visible == covered:
		world.visible = not covered
	if state == "walking" and (_camera_tween == null or not _camera_tween.is_running()):
		camera.global_position = player.global_position
	if state == "walking":
		_update_rooms()
		if _pending_world != null and player.controls_enabled:
			_build_world(_pending_world)
	for e in entities.values():
		e.visible = _seen(e.position)
	_check_heading()
	_check_kick_wait()
	_offer_interaction()
	_update_cursor()
	if state == "seated" and active_table:
		var view := _seated_view()
		hud.update_seated(view)
		_play_cues(view)
	var people := PackedVector2Array()
	for e in entities.values():
		if e.kind == "player":
			people.append(e.position)
	hud.minimap.follow(_here, player.position, player.avatar.facing, world.rotation, people, delta)
	_update_guide(delta)


## Your cues: a chime when it's your turn, and a tick each second through the
## last five of a timer you're up against (betting before you're Ready, or a
## decision -- the Pai Gow sorter included). A Rebet's short countdown is silent.
func _play_cues(view: Dictionary) -> void:
	var my_turn: bool = view.my_turn
	if my_turn and not _was_my_turn:
		Sfx.play("turn")
	_was_my_turn = my_turn
	var mine: bool = my_turn or hud.sorter.is_open() or (active_table.phase == "betting" and view.can_bet and not my_ready
		and not view.get("quiet_betting", false))
	var left := active_table.timer_left()
	var second := ceili(left)
	if mine and not active_table.timer_quiet and left > 0.0 and second <= 5 and second != _last_tick:
		Sfx.play("tick")
	_last_tick = second if left > 0.0 else -1


# ------------------------------------------------------------------ input
func _unhandled_input(event: InputEvent) -> void:
	if hud.is_typing():
		return
	if event.is_action_pressed("interact"):
		if state == "walking":
			_interact()
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("cancel"):
		if state == "seated":
			_request_stand()
		elif state == "slot":
			if _slot_waiting:
				Net.send("stand")
			else:
				slot_screen.cancel_pressed()
		get_viewport().set_input_as_handled()
	elif state == "seated" and event is InputEventKey and event.pressed and not event.echo and _action_key(event):
		get_viewport().set_input_as_handled()
	elif state == "seated" and event.is_action_pressed("ready_up"):
		if _can_bet():
			_on_ready()
		get_viewport().set_input_as_handled()
	elif state == "seated" and event is InputEventKey and event.pressed and not event.echo:
		var key: Key = event.physical_keycode
		if key >= KEY_1 and key <= KEY_5 and _can_bet():   # the bar's chips, left to right
			if hud.pick_chip(key - KEY_1):
				get_viewport().set_input_as_handled()
		elif key == KEY_BACKSPACE:
			_undo()
			get_viewport().set_input_as_handled()


## The action buttons' keys, ahead of Ready and Undo: Space plays on (Hit, Play, Let it ride, Roll...) and Backspace
## stops (Stand, Fold, Check, Pull back), with letters and numbers for the rest (Double D, Split P, bigger bets 2-4).
func _action_key(event: InputEventKey) -> bool:
	for a in _actions:
		if a.get("key", "") != "" and event.physical_keycode == OS.find_keycode_from_string(a.key):
			_on_action(str(a.id))
			return true
	return false


## A click on a glowing chair, caught before the click-to-walk sees it.
func _input(event: InputEvent) -> void:
	if state != "walking" or hud.is_typing():
		return
	if not (event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT):
		return
	if get_viewport().gui_get_hovered_control() != null:
		return   # (the HUD's: the minimap over a chair, say)
	var at := get_global_mouse_position()
	for f in get_tree().get_nodes_in_group("interactables"):
		if f.is_visible_in_tree() and f.hit(at):
			if f == _atm_near:
				_open_atm()
			else:
				_heading_atm = f
				_heading_for = {}
				player.walk_to(world.to_local(f.stand_spot()))
			get_viewport().set_input_as_handled()
			return
	for t in tables.values():
		var seat: int = t.stool_at(t.to_local(at))
		if seat >= 0:
			_take_seat(t, seat)
			get_viewport().set_input_as_handled()
			return



## The pointing hand over anything a click on the floor would use: an ATM or a free chair while you're walking,
## your bet spots (and the master table's dealer) while you're sat. The HUD's own buttons set theirs.
var _hand := false
func _update_cursor() -> void:
	var hand := false
	if state in ["walking", "seated"] and not hud.is_typing() and get_viewport().gui_get_hovered_control() == null:
		var at := get_global_mouse_position()
		if state == "walking":
			for f in get_tree().get_nodes_in_group("interactables"):
				if f.is_visible_in_tree() and f.hit(at):
					hand = true
					break
		var near: Array = tables.values() if state == "walking" else [active_table]
		for t in near:
			if hand:
				break
			hand = t != null and t.clickable_at(t.to_local(at))
	if hand != _hand:
		_hand = hand
		Input.set_default_cursor_shape(Input.CURSOR_POINTING_HAND if hand else Input.CURSOR_ARROW)


# ------------------------------------------------------------------ Find
## Find's list: each kind on the floor (and the ATM), how many, whether any has a free seat, and how far the nearest is.
func _find_options() -> Array:
	var groups := {}
	for t in tables.values():
		groups.get_or_add(Minimap.kind_of(t), []).append(t)
	for f in _atms():
		groups.get_or_add("atm", []).append(f)
	var out := []
	for kind in groups:
		var near := _nearest(kind)
		out.append({"kind": kind, "name": Minimap.kind_name(kind, groups[kind][0]), "count": groups[kind].size(),
			"free": near.get("free", false), "metres": roundi(near.get("length", 0.0) / PX_PER_METRE)})
	var order := func(o: Dictionary) -> String:   # the Master Table, the card games, roulette, craps, the slots, the ATM
		var rank: int = {"master_table": 0, "roulette": 2, "craps": 3, "slot": 4, "atm": 5}.get(o.kind, 1)
		return "%d%s" % [rank, o.name]
	out.sort_custom(func(a, b): return order.call(a) < order.call(b))
	return out


func _atms() -> Array:
	return get_tree().get_nodes_in_group("interactables").filter(func(f): return f.interact == "atm" and f.is_inside_tree())


## The nearest of a kind by the walk there (or of `among`: a slot bank's cabinets, say), preferring one with a free
## seat: {goal, path, length, free}, or {}.
func _nearest(kind: String, among := []) -> Dictionary:
	var best := {}
	var targets: Array = among if not among.is_empty() else _atms() if kind == "atm" \
		else tables.values().filter(func(t): return Minimap.kind_of(t) == kind)
	for t in targets:
		var goal: Vector2
		var free := true
		if t is FloorGame:
			var seats: Array = t.free_seats()
			free = not seats.is_empty()
			var from: Vector2 = t.to_local(player.global_position)
			var seat: int = 0
			for s in seats:   # its free seat nearest you
				if seat not in seats or t.seat_pos(s).distance_to(from) < t.seat_pos(seat).distance_to(from):
					seat = s
			goal = _on_floor(t, Seating.approach(t, seat, from))
		else:
			goal = world.to_local(t.stand_spot())
		var path := _path_to(goal)
		if path.is_empty():
			continue
		var length := _length(path)
		if best.is_empty() or (free and not best.free) or (free == best.free and length < best.length):
			best = {"goal": goal, "path": path, "length": length, "free": free}
	return best


## The way from you to `goal` (World's frame; the maps are in it, and Find only runs while it's upright): along the
## roomy map where it can, with the tight one (Nav) from where you stand onto it and off it to `goal`, which are
## usually closer to things than it goes. The tight way alone if the roomy one's no good (a narrow doorway, say).
func _path_to(goal: Vector2) -> PackedVector2Array:
	var map := player.get_world_2d().navigation_map
	if NavigationServer2D.map_get_iteration_id(map) <= 0:
		return PackedVector2Array([player.position, goal])
	var tight := NavigationServer2D.map_get_path(map, player.position, goal, true)
	if NavigationServer2D.map_get_iteration_id(_wide_map) <= 0 or tight.is_empty():
		return tight
	_wide_query.start_position = player.position
	_wide_query.target_position = goal
	NavigationServer2D.query_path(_wide_query, _wide_result)
	var wide := _wide_result.path
	if wide.size() < 2:
		return tight
	var route := NavigationServer2D.map_get_path(map, player.position, wide[0], true)
	route.append_array(wide.slice(1))
	route.append_array(NavigationServer2D.map_get_path(map, wide[wide.size() - 1], goal, true).slice(1))
	var out := PackedVector2Array()
	for p in route:   # (where the pieces meet, a point can come twice)
		if out.is_empty() or out[out.size() - 1].distance_to(p) > 1.0:
			out.append(p)
	return out if _length(out) < _length(tight) * 1.3 + 48.0 else tight


static func _length(path: PackedVector2Array) -> float:
	var length := 0.0
	for i in range(1, path.size()):
		length += path[i - 1].distance_to(path[i])
	return length


## `path` with each corner rounded: a curve from a point before it to one after (half way to the next corner at
## most), as wide as it can be with all of it somewhere you can stand (on the tight map) and no tighter than the
## floor's ribbon can bend round (RouteLine.HALF_WIDTH), else the corner as it was.
func _rounded(path: PackedVector2Array) -> PackedVector2Array:
	if path.size() < 3:
		return path
	var map := player.get_world_2d().navigation_map
	var standable := func(q: Vector2) -> bool:
		return NavigationServer2D.map_get_closest_point(map, q).distance_to(q) < 1.0
	var out := PackedVector2Array([path[0]])
	for i in range(1, path.size() - 1):
		var p := path[i]
		var back := path[i - 1] - p
		var on := path[i + 1] - p
		var curve := PackedVector2Array([p])
		var half_turn := absf(back.angle_to(-on)) / 2.0
		for reach in CORNERS:
			var d := minf(reach, minf(back.length(), on.length()) / 2.0)
			if d * cos(half_turn) ** 2 < (RouteLine.HALF_WIDTH + 2.0) * sin(half_turn):   # (its tightest radius)
				continue
			var a := p + back.normalized() * d
			var b := p + on.normalized() * d
			var steps := maxi(2, ceili(d / 6.0))
			var pts := PackedVector2Array()
			for k in steps + 1:
				var t := float(k) / steps
				pts.append(a.lerp(p, t).lerp(p.lerp(b, t), t))
			if Array(pts).all(standable):
				curve = pts
				break
		for q in curve:   # (one corner's curve can end where the next one's starts)
			if out[out.size() - 1].distance_to(q) > 0.5:
				out.append(q)
	if out[out.size() - 1].distance_to(path[path.size() - 1]) > 0.5:
		out.append(path[path.size() - 1])
	return out


## Find's pick (the nearest of a kind), or the map's (one table, bank or ATM: `among`).
func _guide_to(kind: String, among := []) -> void:
	if state != "walking":
		return
	var near := _nearest(kind, among)
	if near.is_empty():
		hud.show_toast("There's no way there from here")
		return
	var first = among[0] if not among.is_empty() else tables.values().filter(func(t): return Minimap.kind_of(t) == kind).front() if kind != "atm" else null
	var what: String = Minimap.kind_name(kind, first if first is FloorGame else null)
	what = {"slot": "a slot", "atm": "the ATM"}.get(kind, what)
	_guide = {"kind": kind, "name": what + ("" if near.free else " (full)"), "goal": near.goal, "replan": 0.4}
	_show_guide(near.path)


func _show_guide(path: PackedVector2Array) -> void:
	path = _rounded(path)
	_guide.path = path
	route_line.path = path
	hud.minimap.set_route(path, _guide.goal, _guide.name, roundi(_length(path) / PX_PER_METRE))


func _stop_guide() -> void:
	_guide = {}
	if route_line:
		route_line.path = PackedVector2Array()
	hud.minimap.set_route(PackedVector2Array())


## While guiding: the way re-planned as you go, and over once you're there or sat down anywhere.
func _update_guide(delta: float) -> void:
	if _guide.is_empty():
		return
	if state != "walking":
		_stop_guide()
		return
	if player.position.distance_to(_guide.goal) < GUIDE_ARRIVED:
		hud.show_toast("You're at %s" % str(_guide.name).trim_suffix(" (full)"))
		_stop_guide()
		return
	route_line.trim_to(player.position)
	_guide.replan -= delta
	if _guide.replan > 0.0 or not is_zero_approx(world.rotation):
		return
	_guide.replan = 0.4
	var target = player.target()
	if target != null and target == _guide.goal:   # walking it (Walk there): the floor's way stays, the map's shortens
		var rest: PackedVector2Array = player.remaining_path()
		hud.minimap.set_route(rest, _guide.goal, _guide.name, roundi(_length(rest) / PX_PER_METRE))
		return
	var path := _path_to(_guide.goal)
	if not path.is_empty():
		_show_guide(path)


# ------------------------------------------------------------------ taking a seat
const SIT_REACH := 70.0     # stopped this close to a chair you clicked (something in the way), you sit down from there
const PLAY_REACH := 40.0    # standing this close to a free chair, it's offered (Play), and a click on it sits you at once


## Sit at a free chair: walk over to its side (Seating.approach), then take it -- the sit-down
## plays from there once the server says it's yours.
func _take_seat(t: FloorGame, seat: int) -> void:
	if not Net.is_open():
		hud.show_toast("Not connected to the casino")
		return
	var goal := _on_floor(t, Seating.approach(t, seat, t.to_local(player.global_position)))
	var beside := player.global_position.distance_to(t.to_global(t.chair_pos(seat))) <= PLAY_REACH
	if beside or player.position.distance_to(goal) <= 4.0:
		_heading_for = {}
		Net.send("sit", {"table": t.table_id, "seat": seat})
	else:
		_heading_for = {"table": t, "seat": seat, "goal": goal}
		player.walk_to(goal)


## Walking over to a chair you clicked: sit on arriving (or on stopping close, if
## something's in the way); give up if you stop short, steer elsewhere, or someone takes it first.
## Walking over to the ATM you clicked: use it on arriving, if you got there.
func _check_heading() -> void:
	if _heading_atm != null and state == "walking" and not player.is_walking_to_target():
		var f := _heading_atm
		_heading_atm = null
		_offer_interaction()
		if f == _atm_near:
			_open_atm()
	if _heading_for.is_empty() or state != "walking":
		return
	var t: FloorGame = _heading_for.table
	var seat: int = _heading_for.seat
	var now_heading = player.target()
	if not seat in t.free_seats() or (now_heading != null and now_heading.distance_to(_heading_for.goal) > 1.0):
		_heading_for = {}  # taken, or you've steered somewhere else
		return
	if player.is_walking_to_target():
		return
	var goal: Vector2 = _heading_for.goal
	_heading_for = {}
	if player.position.distance_to(goal) <= 6.0 or player.global_position.distance_to(t.to_global(t.stool_pos(seat))) <= SIT_REACH:
		Net.send("sit", {"table": t.table_id, "seat": seat})


# ------------------------------------------------------------------ the prompt: the ATM, Play
const ATM_REACH := 24.0   # this close to the spot in front of an ATM, it's offered


## What E does where you're standing, offered on the HUD's prompt under your feet: the ATM you're at, else the
## nearest free chair you're by (Play), else the nearest NPC's chair (Take seat: ask them to move).
func _offer_interaction() -> void:
	var atm: Furniture = null
	var play := {}
	var kick := {}
	if state == "walking" and not hud.atm.visible and player.controls_enabled:
		var best_d := ATM_REACH
		for f in get_tree().get_nodes_in_group("interactables"):
			var d: float = player.global_position.distance_to(f.stand_spot())
			if f.is_visible_in_tree() and d < best_d:
				atm = f
				best_d = d
		best_d = PLAY_REACH
		for t in tables.values() if atm == null else []:
			if not t.offer_seats or not t.is_visible_in_tree():
				continue
			for seat in t.free_seats():
				var d := player.global_position.distance_to(t.to_global(t.chair_pos(seat)))
				if d < best_d:
					play = {"table": t, "seat": seat}
					best_d = d
		best_d = PLAY_REACH
		for t in tables.values() if atm == null and play.is_empty() and _kick_wait.is_empty() else []:
			if not t.offer_seats or not t.is_visible_in_tree():
				continue
			for seat in t.occupants:
				if t.occupants[seat].get("human", true):
					continue
				var d := player.global_position.distance_to(t.to_global(t.chair_pos(seat)))
				if d < best_d:
					kick = {"table": t, "seat": seat}
					best_d = d
	if atm != _atm_near or play != _play_near or kick != _kick_near:
		_atm_near = atm
		_play_near = play
		_kick_near = kick
		if atm:
			hud.show_prompt("Use ATM")
		elif not play.is_empty():
			hud.show_prompt("Play")
		elif not kick.is_empty():
			hud.show_prompt("Take seat")
		else:
			hud.hide_prompt()
	if hud.prompt.visible:
		hud.place_prompt(player.get_global_transform_with_canvas().origin)


## E, or the prompt: whatever it's offering.
func _interact() -> void:
	if _atm_near:
		_open_atm()
	elif not _play_near.is_empty():
		_take_seat(_play_near.table, _play_near.seat)
	elif not _kick_near.is_empty():
		_ask_kick(_kick_near.table, _kick_near.seat)


## Take seat: check they mean it, then ask the NPC sitting there to move. They get up now and you sit down
## (`seated`), or they finish what they're in first (`kick_waiting`).
func _ask_kick(t: FloorGame, seat: int) -> void:
	if not Net.is_open():
		hud.show_toast("Not connected to the casino")
		return
	hud.ask("Are you sure? Kicking someone out of their seat is kind of rude you know.", "Yes", "No", func():
		if state == "walking" and t.occupants.has(seat) and not t.occupants[seat].get("human", true):
			Net.send("kick", {"table": t.table_id, "seat": seat}))


## Waiting for an NPC to give up their seat: walk away from it and the wait's over (they keep it).
func _check_kick_wait() -> void:
	if _kick_wait.is_empty():
		return
	var t: FloorGame = _kick_wait.table
	if state != "walking" or not is_instance_valid(t):
		_kick_wait = {}
		return
	if player.global_position.distance_to(t.to_global(t.chair_pos(_kick_wait.seat))) > SIT_REACH:
		Net.send("kick_cancel")
		hud.show_toast("You walked away, so %s keeps the seat" % _kick_wait.name)
		_kick_wait = {}


func _open_atm() -> void:
	if not Net.is_open():
		hud.show_toast("Not connected to the casino")
		return
	player.set_controls(false)   # (which reports where you are first: the server checks you're at the machine)
	hud.hide_prompt()
	hud.atm.open_atm()


## Every table in its table style again.
func _restyle_tables() -> void:
	for t in tables.values():
		if t is CasinoTable:
			t.restyle()


func _redraw_chairs() -> void:
	for t in tables.values():
		t.redraw_chairs()


func _offer_seats(on: bool) -> void:
	on = on and Session.preview == ""   # (a preview only looks)
	for t in tables.values():
		t.offer_seats = on


func _sat_down(msg: Dictionary) -> void:
	var g: FloorGame = tables.get(msg.table)
	if g is SlotCabinet:
		_sat_down_slot(g, msg)
		return
	var t := g as CasinoTable
	if t == null:
		return
	active_table = t
	Sfx.focus = t.table_id
	my_seat = int(msg.seat)
	state = "seated"
	_heading_for = {}
	_offer_seats(false)
	t.my_seat = my_seat
	t.mode = "seated"
	my_bets = t.zero_bets()
	my_ready = false
	sitting_out = false
	played_a_hand = false
	my_hand = ""
	hud.setup_table(msg.get("rules", {}), t.chip_design())
	hud.set_auto_rebet(false)
	hud.set_sit_out(false)
	_round_start = Session.balance
	_staked = false
	if "chip_value" in t:
		t.chip_value = hud.selected_chip
	_placed.clear()
	hud.set_mode("seated")
	var ask: Dictionary = t.on_seated_prompt()
	if not ask.is_empty():
		hud.ask(ask.text, ask.yes, ask.no, func(): Net.send(ask.message[0], ask.message[1]))
	var sat: Tween = player.sit_at(t, my_seat)
	if Seating.style(t.table_id).slot_screen == "after_sit":   # (the style's timing: the camera waits for the sit too)
		await sat.finished
		if state != "seated" or active_table != t:
			return
	_camera_to(world.to_local(t.focus_point()), TABLE_ZOOM, wrapf(-t.rotation, -PI, PI))  # a turned table, the right way up
	if t is MasterTable:   # a blank Master Table: what would you like to play?
		await get_tree().create_timer(0.6).timeout
		if state == "seated" and active_table is MasterTable and not hud.master.menu_open():
			_open_master_menu(active_table)


## Sitting at a slot cabinet: you sit down, the camera comes in, then the full-screen game grows
## out of its screen (or all at once, if the seating style says so).
func _sat_down_slot(c: SlotCabinet, msg: Dictionary) -> void:
	active_slot = c
	Sfx.focus = c.table_id
	my_seat = int(msg.seat)
	state = "slot"
	_heading_for = {}
	_offer_seats(false)
	c.my_seat = my_seat
	c.mode = "seated"
	hud.set_mode("slot")
	var sat: Tween = player.sit_at(c, my_seat)
	if Seating.style(c.table_id).slot_screen == "after_sit":
		_slot_waiting = true
		_slot_snapshot = {}
		await sat.finished
		if state != "slot" or active_slot != c:
			return
		await _camera_to(world.to_local(c.focus_point()), TABLE_ZOOM).finished
		if state != "slot" or active_slot != c:
			return
	else:
		_camera_to(world.to_local(c.focus_point()), TABLE_ZOOM)
	_slot_waiting = false
	slot_screen.open(c, msg.get("rules", {}), _screen_rect_of(c))
	if not _slot_snapshot.is_empty():
		slot_screen.apply_snapshot(_slot_snapshot)
		_slot_snapshot = {}


## The cabinet's little screen, in viewport pixels (where the full-screen game grows from).
func _screen_rect_of(c: SlotCabinet) -> Rect2:
	var r := c.screen_rect()
	var xf := get_viewport().get_canvas_transform()
	return Rect2(xf * r.position, r.size * xf.get_scale())


# ------------------------------------------------------------------ seated
func _on_spot_clicked(spot: String) -> void:
	if not _can_bet():
		return
	var flat: Dictionary = active_table.flat_spots()
	if flat.has(spot):  # on/off, a fixed amount (the £1 Jackpot)
		_set_sitting_out(false)
		Net.send("bet", {"spot": spot, "amount": 0 if int(my_bets.get(spot, 0)) else int(flat[spot])})
		return
	var old := int(my_bets.get(spot, 0))
	var add := active_table.step_bet(spot, old, hud.selected_chip, true) - old
	if add <= 0:
		return
	var trial := my_bets.duplicate()
	trial[spot] = old + add
	if active_table.max_cost(trial) * active_table.boxes() > Session.balance:
		if active_table.max_cost(trial) <= Session.balance:
			hud.show_toast("You wouldn't have enough to match that on your second box.")
			return
		var main := active_table.main_spot()
		hud.show_toast("You wouldn't have enough to match that Ante with a Play bet." if spot == "ante"
			else "You wouldn't have enough left to double." if spot == main else "Not enough balance for that.")
		return
	my_bets = trial  # optimistic; the server's bet_changed confirms it
	_placed.append([spot, add])
	_set_sitting_out(false)
	Net.send("bet", {"spot": spot, "add": add})


func _on_spot_removed(spot: String) -> void:
	if not _can_bet() or int(my_bets.get(spot, 0)) == 0:
		return
	if active_table.flat_spots().has(spot):
		Net.send("bet", {"spot": spot, "amount": 0})
		return
	var old := int(my_bets[spot])
	my_bets[spot] = active_table.step_bet(spot, old, hud.selected_chip, false)
	Net.send("bet", {"spot": spot, "add": int(my_bets[spot]) - old})


## Undo: your last chip this round comes back off the layout.
func _undo() -> void:
	if not _can_bet() or _placed.is_empty():
		return
	var last: Array = _placed.pop_back()
	var spot: String = last[0]
	var amount: int = mini(int(last[1]), int(my_bets.get(spot, 0)))
	if amount <= 0:
		return
	my_bets[spot] = int(my_bets[spot]) - amount
	Net.send("bet", {"spot": spot, "add": -amount})


func _on_ready() -> void:
	if _total(my_bets) == 0 and not active_table is CrapsTable:   # Space with no bets is Repeat Bet (sitting out is
		if played_a_hand:                                           # the switch's job; Space rolls at Craps)
			hud.rebet_pressed.emit()
		return
	if not active_table.can_ready():
		return
	var main := active_table.main_spot()
	if _total(my_bets) > 0 and not active_table.has_main_bet(my_bets):
		hud.show_toast("Side bets need %s alongside them." % MAIN_BET_NAMES.get(main, "a main bet"))
		return
	Net.send("ready")


## The Sit out switch: on, it Readies you with no bets now and each time betting opens, so you sit the hands out
## (three at a busy table still stands you up). Betting, Repeat Bet or ticking Auto rebet turns it off.
func _set_sitting_out(on: bool) -> void:
	if on != sitting_out:
		sitting_out = on
		hud.set_sit_out(on)
	_sit_out_now()


func _sit_out_now() -> void:
	if sitting_out and state == "seated" and active_table.sit_out_ok() and active_table.can_ready() and not my_ready \
			and _total(my_bets) == 0:
		Net.send("ready")


## An action button (or its key): the table says what to send.
func _on_action(id: String) -> void:
	if state != "seated" or not _actions.any(func(a): return str(a.id) == id):
		return
	var msg: Array = active_table.action_message(id)
	if not msg.is_empty():
		Net.send(msg[0], msg[1])


## A chair's pill while you're sat: play the free seat beside you as a second box (every bet you make is matched on
## it), or give your second box back.
func _on_box_clicked(seat: int, t: CasinoTable) -> void:
	if state != "seated" or t != active_table:
		return
	if seat == t.my_box:
		hud.ask("Stop playing your second box?", "Drop", "Keep", func(): Net.send("drop_box"))
	else:
		hud.ask("Play second box? Your bets will be matched", "Yes", "Cancel",
			func(): Net.send("second_box", {"seat": seat}))


func _request_stand() -> void:
	if state != "seated":
		return
	if active_table.deciding():
		hud.confirm_stand(active_table.stand_warning())
	else:
		Net.send("stand")


## Chips can go down in the betting window -- or, out of the hand being played, any time,
## for the next hand (not at Roulette).
func _can_bet() -> bool:
	return state == "seated" and active_table.can_place_bets() and not my_ready


func _seated_view() -> Dictionary:
	var t := active_table
	var ctx := {"can_bet": _can_bet(), "has_bets": _total(my_bets) > 0, "my_ready": my_ready, "my_bets": my_bets}
	var view: Dictionary = t.seated_view(ctx)
	_actions = view.get("actions", [])
	var my_turn: bool = view.get("my_turn", false)
	# the bar's draining line: a countdown you're up against (betting before you're Ready, a decision, the sorter)
	var timed: bool = my_turn or hud.sorter.is_open() or (t.phase == "betting" and ctx.can_bet and not my_ready)
	# The line only speaks when there's a decision on the clock, or the table's `prompt` asks for it (a hovered spot's
	# payout, the Master table's "click the dealer"). It doesn't narrate the hand: that's on the felt and the dealer says it.
	var info: String = view.get("info", "") if timed or view.get("prompt", false) else ""
	var hand := my_hand if timed and t.in_hand and t.phase != "betting" else ""
	var left := t.timer_left()
	return {"can_bet": ctx.can_bet, "can_ready": ctx.can_bet and t.can_ready(), "can_undo": ctx.can_bet and not _placed.is_empty(),
		"has_bets": ctx.has_bets, "can_rebet": played_a_hand, "sit_out": t.sit_out_ok(),
		"is_ready": my_ready, "my_turn": my_turn, "actions": _actions, "info": info, "hand": hand,
		"hide": view.get("hide", []), "quiet_betting": view.get("quiet_betting", false),
		"timer": t.timer_fraction() if timed and left > 0.0 else -1.0, "timer_low": left < 5.0,
		"on_felt": _total(my_bets) * t.boxes(), "title": t.game_title(),
		"seats": "%d of %d %s" % [t.occupants.values().filter(func(o): return not o.has("box_of")).size(), t.seat_count(),
			"at the rail" if t is CrapsTable else "seated"]}


## A round's over (the next one's betting opens): what it won or lost you flashes beside the bar's balance.
func _flash_round() -> void:
	if _staked and _round_start >= 0:
		var net := Session.balance - _round_start
		if net != 0:
			hud.flash_result(net)
	_round_start = Session.balance
	_staked = false


func _leave_table() -> void:
	if active_slot:
		return _leave_slot()
	var t := active_table
	Sfx.focus = ""
	state = "walking"
	var stand := player.position
	if t:
		t.mode = ""
		t.my_seat = -1
		t.my_box = -1
		stand = _on_floor(t, t.stand_pos(my_seat))
		player.stand_at(t, my_seat)
	my_seat = -1
	active_table = null
	_actions = []
	hud.set_mode("walking")
	hud.clear_my_hand()
	my_hand = ""
	Session.hold_balance(false)
	_offer_seats(true)
	_camera_to_player(stand)


func _leave_slot() -> void:
	var c := active_slot
	Sfx.focus = ""
	state = "walking"
	c.mode = ""
	c.my_seat = -1
	var stand := _on_floor(c, c.stand_pos(my_seat))
	player.stand_at(c, my_seat)
	if _slot_waiting:
		_slot_waiting = false
		_slot_snapshot = {}
	else:
		slot_screen.close(_screen_rect_of(c))
	my_seat = -1
	active_slot = null
	hud.set_mode("walking")
	Session.hold_balance(false)
	_offer_seats(true)
	_camera_to_player(stand)


# ------------------------------------------------------------------ camera
## Glide the camera onto `at` (a point on the floor, in World's frame) at `zoom`, with
## the floor turned by `turn` about it. Through the glide, the floor point under the
## camera moves steadily to `at` as the turn goes, so it all turns and travels as one.
func _camera_to(at: Vector2, zoom: Vector2, turn := 0.0) -> Tween:
	if _camera_tween:
		_camera_tween.kill()
	camera.position_smoothing_enabled = false
	var c0 := camera.get_screen_center_position()   # (where it shows: clamped at a wall, or still smoothing)
	var a0 := world.to_local(c0)
	if is_zero_approx(turn):
		at = _within_limits(at, zoom)   # upright, the limits hold again at the end: end where they'd show
	var z0 := camera.zoom
	var t0 := world.rotation
	if not (is_zero_approx(t0) and is_zero_approx(turn)):
		_set_limits(false)   # the turned room isn't where the limits are
	_camera_tween = create_tween().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN_OUT)
	_camera_tween.tween_method(func(u: float):
		var c := c0.lerp(at, u)
		var th := lerpf(t0, turn, u)
		world.transform = Transform2D(th, c - a0.lerp(at, u).rotated(th))
		camera.global_position = c
		camera.zoom = z0.lerp(zoom, u), 0.0, 1.0, 0.6)
	_camera_tween.tween_callback(func():
		if is_zero_approx(turn):
			world.transform = Transform2D.IDENTITY
			_set_limits(true)
			if _bake_pending:
				_bake_navigation())
	return _camera_tween


func _camera_to_player(at: Vector2) -> void:
	_camera_to(at, WALK_ZOOM).tween_callback(func(): camera.position_smoothing_enabled = true)


## Where the camera would show if it were centred on `at` at `zoom`, its limits holding.
func _within_limits(at: Vector2, zoom: Vector2) -> Vector2:
	var half := get_viewport_rect().size / zoom / 2.0
	var lo := Vector2(_limits[0], _limits[1]) + half
	var hi := Vector2(_limits[2], _limits[3]) - half
	return Vector2(clampf(at.x, lo.x, maxf(lo.x, hi.x)), clampf(at.y, lo.y, maxf(lo.y, hi.y)))


func _set_limits(on: bool) -> void:
	var far := 10000000
	camera.limit_left = _limits[0] if on else -far
	camera.limit_top = _limits[1] if on else -far
	camera.limit_right = _limits[2] if on else far
	camera.limit_bottom = _limits[3] if on else far


# ------------------------------------------------------------------ server messages
func _on_message(msg: Dictionary) -> void:
	match msg.get("type"):
		"welcome":
			hud.barred.close()   # (back after a timeout)
			Seating.configure(msg.get("seating", {}))
			TableStyle.configure(msg.get("table_styles", {}))
			var w: Dictionary = msg.get("world", {})
			if int(w.get("rev", -1)) != _world_rev or rooms.is_empty():
				_build_world(w)
			else:
				_restyle_tables()
				_redraw_chairs()
			if _arriving:   # a character picked (not a resync or a reconnect): in at the spawn point
				_arriving = false
				player.position = _fallback_point()
				camera.global_position = player.global_position
				camera.reset_smoothing()
			player.avatar.look = Session.look
			player.avatar.display_name = Session.player.get("name", "") if Session.preview == "" else "Preview"
			if Session.preview != "":
				hud.show_toast("Previewing the floor plan's draft: saving it on the admin page shows the changes here.", 6.0)
		"world":   # the floor plan changed (published, or the draft saved, in a preview)
			_build_world(msg.get("world", {}))
		"world_snapshot":
			for id in entities.keys():
				entities[id].queue_free()
			entities.clear()
			for e in msg.entities:
				_spawn(e, "")
		"entity_spawn":
			_spawn(msg.entity, str(msg.get("at", "")))
		"entity_move":
			var e = entities.get(msg.id)
			if e:
				e.apply_move(Vector2(msg.x, msg.y), msg.dir, msg.anim)
		"entity_walk":
			var e = entities.get(msg.id)
			if e:
				e.walk_to(_resolve_target(msg.target), float(msg.duration))
		"entity_update":  # renamed, or (an NPC) restyled on the admin page
			var e = entities.get(msg.id)
			if e:
				if msg.has("name"):
					e.display_name = msg.name
				if msg.has("look"):
					e.look = msg.look
		"entity_despawn":
			var e = entities.get(msg.id)
			if e:
				entities.erase(msg.id)
				e.queue_free()
		"table_state":
			var g = tables.get(msg.table)
			if g is SlotCabinet:
				_on_slot_state(g, msg)
			else:
				_on_table_state(msg)
		"table_event":
			var g = tables.get(msg.table)
			if g is SlotCabinet:
				_on_slot_event(g, msg.event)
			elif g != null:
				_on_table_event(g, msg.event)
		"slot_jackpots":
			SlotScreen.set_meters(msg.get("meters", {}), msg.get("rates"))
		"seated":
			_kick_wait = {}
			_sat_down(msg)
		"kick_waiting":   # the NPC you asked is in a hand: they move once it's settled, if you're still here
			var t = tables.get(msg.table)
			if t != null:
				_kick_wait = {"table": t, "seat": int(msg.seat), "name": str(msg.name)}
				hud.show_toast("%s will give you the seat once their bets are settled" % msg.name, 4.0)
		"seating":   # the admin page changed the seating styles
			Seating.configure(msg.get("seating", {}))
			for t in tables.values():
				t.place_chair_backs()   # (and their bodies: the chairs may be bigger or smaller)
			_redraw_chairs()
			_bake_navigation()
		"table_styles":   # the admin page changed the table styles
			TableStyle.configure(msg.get("table_styles", {}))
			_restyle_tables()
		"atm":
			hud.atm.apply(msg)
			var done: Dictionary = msg.get("done", {})
			if not done.is_empty():
				hud.wallet.flash_result(int(done.amount) * (1 if str(done.kind) == "withdraw" else -1))
		"pg_check":
			hud.sorter.on_check(msg)
		"pg_suggest":
			hud.sorter.on_suggest(msg)
		"notice":
			hud.show_toast(msg.get("message", ""), 4.0)
		"barred":   # the admin page banned, timed out or removed you (Net holds off reconnecting)
			hud.atm.close_atm()
			hud.barred.open(msg)
		"error":
			if hud.front_door.takes_errors():
				return   # (the character designer shows it)
			hud.show_toast(msg.get("message", "error"))
			hud.atm.close_atm()   # (the server wouldn't let you use it: you weren't at it)
			if hud.sorter.is_open():
				hud.sorter.open_again()


func _on_slot_state(c: SlotCabinet, msg: Dictionary) -> void:
	c.apply_snapshot(msg)
	var seats: Array = msg.get("seats", [])
	if not seats.is_empty() and seats[0] != null and entities.has(seats[0].entity):
		entities[seats[0].entity].sit_at(c, 0, false)
	if msg.get("meters") != null:
		SlotScreen.set_meters(msg.meters, msg.get("rates"))
	if c == active_slot and state == "slot":
		if _slot_waiting:
			_slot_snapshot = msg
		else:
			slot_screen.apply_snapshot(msg)


func _on_slot_event(c: SlotCabinet, ev: Dictionary) -> void:
	c.handle_event(ev)
	if ev.has("meters"):
		SlotScreen.set_meters(ev.meters, ev.get("rates"))
	match ev.kind:
		"seated":
			if ev.entity != Session.entity_id and entities.has(ev.entity):
				entities[ev.entity].sit_at(c, 0)
		"stood":
			if ev.entity == Session.entity_id:
				_leave_table()
			elif entities.has(ev.entity):
				entities[ev.entity].stand_at(c, 0)
	if c == active_slot and state == "slot" and not _slot_waiting:
		slot_screen.on_event(ev)


func _on_table_state(msg: Dictionary) -> void:
	var t: CasinoTable = tables.get(msg.table)
	if t == null:
		return
	if msg.has("master"):   # a Master Table: its game's own table (MasterTable while it's blank)
		var want := str(msg.master.get("game", ""))
		if t.master_game != want:   # (a resync, or joining: no animation)
			var mine = msg.get("my_seat")
			t = _replace_master(t, want, int(mine) if mine != null else -1, msg.master.get("rules", {}))
		_apply_master(t, msg.master)
	t.apply_snapshot(msg)
	var seats: Array = msg.get("seats", [])
	for i in seats.size():
		var s = seats[i]
		if s != null and s.get("box_of") == null and entities.has(s.entity):   # (nobody sits at a second box)
			entities[s.entity].sit_at(t, i, false)
	if t == active_table and state == "seated":
		var mine = seats[my_seat] if my_seat < seats.size() else null
		if mine != null:
			for spot in t.bet_spots():
				my_bets[spot] = int(mine.bets.get(spot, 0))
			my_ready = mine.get("ready", false)
			hud.set_auto_rebet(mine.get("auto_rebet", false))
			_sit_out_now()


func _on_table_event(t: CasinoTable, ev: Dictionary) -> void:
	if t == null:
		return
	if str(ev.kind).begins_with("master_"):
		_on_master_event(t, ev)
		return
	t.handle_event(ev)
	var mine := state == "seated" and t == active_table
	match ev.kind:
		"seated":
			if ev.entity != Session.entity_id and entities.has(ev.entity):
				entities[ev.entity].sit_at(t, int(ev.seat))
		"stood":
			if ev.entity == Session.entity_id:
				_leave_table()
			elif entities.has(ev.entity):
				entities[ev.entity].stand_at(t, int(ev.seat))
		"bet_changed":
			if mine and int(ev.seat) == my_seat:
				my_bets = ev.bets.duplicate()
				hud.set_pending(t.pending_cost(my_bets) * t.boxes())
		"box_taken":
			if mine and int(ev.of) == my_seat:
				hud.set_pending(t.pending_cost(my_bets) * t.boxes())
		"box_dropped":
			if mine and int(ev.of) == my_seat:
				hud.set_pending(t.pending_cost(my_bets) * t.boxes())
				if ev.get("reason", "") == "game_change":
					hud.show_toast("Your second box ended with the change of game.", 4.0)
		"ready":
			if mine and int(ev.seat) == my_seat:
				my_ready = true
		"bets_closed", "no_more_bets":
			if mine:
				my_ready = false
				_placed.clear()
				hud.set_pending(0)
				if ev.seats.any(func(x): return t.is_mine(int(x))):
					played_a_hand = true
					_staked = true
		"throw":  # Craps: dice are out -- the chips you put down are paid for now
			if mine:
				_staked = _staked or _total(my_bets) > 0
				_placed.clear()
				hud.set_pending(0)
		"roll_result":  # Craps: what's left of your bets after the roll
			if mine:
				my_bets = t.zero_bets()
				var after: Dictionary = ev.get("after", {})
				for spot in after.get(str(my_seat), {}):
					my_bets[spot] = int(after[str(my_seat)][spot])
				hud.set_pending(0)
		"spin":  # Roulette: Ready only meant "spin" -- you can add late bets now
			if mine:
				my_ready = false
		"roll_open":  # Craps: the next roll's betting
			if mine:
				_flash_round()
		"betting_open":
			if mine:
				_flash_round()
				my_bets = t.zero_bets()   # (any bets you queued come straight back as bet_changed)
				my_ready = false
				my_hand = ""
				hud.set_pending(0)
				_sit_out_now()
		"auto_rebet":
			if mine and int(ev.seat) == my_seat:
				hud.set_auto_rebet(ev.on)
				var why: String = ev.get("reason", "")
				if why == "timeout":
					hud.show_toast("Auto rebet is off -- you ran out of time.", 4.0)
				elif why != "":
					hud.show_toast("Auto rebet is off: %s" % why, 4.0)
		"bet_under_min":   # betting closed with a bet under the table minimum: it came back (the bet_changed after it)
			if mine and int(ev.seat) == my_seat:
				hud.show_toast(str(ev.get("text", "")), 4.0)
		"queued_dropped":
			if mine and int(ev.seat) == my_seat:
				_placed.clear()
				hud.set_pending(0)
				hud.show_toast("Your bets for this hand came back: %s" % ev.get("reason", ""), 4.0)
		"jackpot_won":
			hud.show_banner("%s hit the JACKPOT!\n%s" % [ev.name, Money.format(int(ev.amount))])


## Back from a hidden tab: fresh snapshots follow, so drop what they replace.
func _on_resynced(msg: Dictionary) -> void:
	if state == "slot":
		if msg.get("table") == null or tables.get(msg.table) != active_slot:
			_leave_table()
			hud.show_toast("You were stood up while you were away.", 4.0)
		else:
			slot_screen.on_resynced()
		return
	if state != "seated":
		return
	if msg.get("table") == null or tables.get(msg.table) != active_table:
		_leave_table()
		hud.show_toast("You were stood up while you were away.", 4.0)
		return
	_placed.clear()
	my_hand = ""      # (the table's snapshot names your hand again if you're in one)
	if hud.sorter.is_open():
		hud.sorter.close()  # (Pai Gow reopens it if you're still setting)


## Off the floor and back at the character select (switching, or the character was picked in another window): as a
## dropped connection, without the toast. The next character's `welcome` puts you back at the spawn point.
func _off_the_floor() -> void:
	_arriving = true
	_stop_guide()
	hud.atm.close_atm()
	if state == "seated" or state == "slot":
		_leave_table()
	for id in entities.keys():
		entities[id].queue_free()
	entities.clear()


func _on_disconnected() -> void:
	hud.atm.close_atm()
	if state == "seated" or state == "slot":
		_leave_table()
		hud.show_toast("Lost connection to the casino -- reconnecting...")
	for id in entities.keys():
		entities[id].queue_free()
	entities.clear()


# ------------------------------------------------------------------ entities
func _spawn(e: Dictionary, at: String) -> void:
	if e.id == Session.entity_id or entities.has(e.id):
		return
	var node = ENTITY_SCENE.instantiate()
	entities_root.add_child(node)
	node.add_to_group("door_openers")
	node.entity_id = e.id
	node.kind = e.get("kind", "player")
	node.look = e.get("look", "player_default")
	node.display_name = e.get("name", "")
	if e.get("x") != null:
		node.place(Vector2(e.x, e.y))
	else:
		node.place(_resolve_target(at) if at != "" else _fallback_point())
	node.set_action(e.get("anim", "idle") if e.get("anim") in ["idle", "walk"] else "idle", e.get("dir", "down"))
	entities[e.id] = node
	if e.get("walk") != null:
		var duration := float(e.walk.get("duration", 0.0))
		var remaining := float(e.walk.remaining)
		node.walk_to(_resolve_target(e.walk.target), remaining, 1.0 - remaining / duration if duration > 0.0 else 0.0)


func _resolve_target(target: String) -> Vector2:
	var parts := target.split(":")
	if parts[0] == "point" and parts.size() == 2 and points.has(parts[1]):
		return points[parts[1]]
	if parts[0] == "seat" and parts.size() == 3 and tables.has(parts[1]):
		var t: FloorGame = tables[parts[1]]
		return _on_floor(t, t.stand_pos(int(parts[2])))
	return _fallback_point()


# ------------------------------------------------------------------ Master Tables
## A Master Table's node for `game` ("" blank: MasterTable) in `old`'s place: that game's own table, with the same id,
## place and turn, on the floor's books in place of `old` (which the caller ghosts or frees). `bare`: its felt shows
## without its printing for now (MasterSwap draws the printing changing over it).
func _master_node(old: CasinoTable, game: String, bare := false) -> CasinoTable:
	var t: CasinoTable = PlanRoom.TABLE_SCENES[game if game != "" else "master_table"].instantiate()
	t.table_id = old.table_id
	t.is_master = true
	t.master_game = game
	t.game = "master_table"
	t.game_label = MasterPanel.name_of(game) if game != "" else old.game_label if old is MasterTable else "Master Table"
	t.limits = old.limits
	if game == "pai_gow_face_up":
		t.set("face_up", true)
	t.position = old.position
	t.rotation = old.rotation
	t.on_screen_now = old.on_screen_now   # (so its felt is painted at once, not when its notifier first fires)
	if bare:
		(t.get_node("Felt") as TableFelt).layer = "base"
	t.add_to_group("navigation_obstacles")
	var room := old.get_parent()
	room.add_child(t)
	t.dealer.look = old.dealer.look   # (the same dealer stays on: the snapshot that follows would say so a frame late)
	t.dealer.display_name = old.dealer.display_name
	if room is PlanRoom:
		var i: int = room.games.find(old)
		if i >= 0:
			room.games[i] = t
	_register(t)
	t.offer_seats = state == "walking" and Session.preview == ""
	Sfx.set_table_set(t.table_id, game if game != "" else "casino")
	return t


## A Master Table that's playing something else than its node shows (joining, or back from a hidden tab): swap
## the node at once. You keep your seat (`seat`: yours in the new game's, from the snapshot).
func _replace_master(old: CasinoTable, game: String, seat: int, rules: Dictionary) -> CasinoTable:
	var t := _master_node(old, game)
	_follow_master(old, t, seat, rules)
	old.get_parent().remove_child(old)
	old.queue_free()
	return t


## You were sitting at `old`, and it's now `t`: you sit at `t` in `seat` (its seat numbers may differ: six seats or
## five), with its chips and rules.
func _follow_master(old: CasinoTable, t: CasinoTable, seat: int, rules: Dictionary) -> void:
	if state != "seated" or active_table != old or seat < 0:
		return
	old.mode = ""
	old.my_seat = -1
	old.my_box = -1
	active_table = t
	my_seat = seat
	t.my_seat = seat
	t.mode = "seated"
	my_bets = t.zero_bets()
	my_ready = false
	played_a_hand = false
	my_hand = ""
	_placed.clear()
	hud.setup_table(rules, t.chip_design())
	hud.set_pending(0)
	hud.clear_my_hand()
	if "chip_value" in t:
		t.chip_value = hud.selected_chip
	Seating.sit_down(player, player.avatar, t, seat, false)


## The server's view of a Master Table (its snapshot's `master`): on the table, and on your HUD if you're sitting there.
func _apply_master(t: CasinoTable, m: Dictionary) -> void:
	t.master = m
	var now := Time.get_ticks_msec() / 1000.0
	t.master_revert_end = now + float(m.revert) if m.get("revert") != null else 0.0
	if state != "seated" or t != active_table:
		return
	hud.master.show_queued(str(m.queued) if m.get("queued") != null else "")
	var v = m.get("vote")
	if v == null:
		hud.master.hide_vote()
	elif my_seat in v.voters.map(func(x): return int(x)) and not my_seat in v.agreed.map(func(x): return int(x)):
		hud.master.show_vote("Switch to %s?  %%d" % MasterPanel.name_of(str(v.game)), float(v.seconds), true)
	else:
		hud.master.show_vote("Waiting for the others to agree to %s  ·  %%d" % MasterPanel.name_of(str(v.game)), float(v.seconds), false)


func _on_master_event(t: CasinoTable, ev: Dictionary) -> void:
	var mine := state == "seated" and t == active_table
	match ev.kind:
		"master_change":   # a new game: its table takes this one's place, the change animating over it
			var b := _master_node(t, str(ev.game), true)
			var seat := -1
			if mine:   # (JSON numbers are floats: find() needs ints)
				seat = (ev.get("map", []) as Array).map(func(x): return int(x)).find(my_seat)
			MasterSwap.start(t, b, ev)
			_follow_master(t, b, seat, ev.get("rules", {}))
			if mine:
				hud.master.close_all()
		"master_vote":
			t.master["vote"] = {"game": ev.game, "by": ev.by, "voters": ev.voters, "agreed": [], "seconds": ev.seconds}
			if mine and int(ev.by) != my_seat:
				var asks := "%s wants to switch to %s.  Agree?  %%d" % [str(ev.get("name", "Someone")), MasterPanel.name_of(str(ev.game))]
				hud.master.show_vote(asks if my_seat in ev.voters.map(func(x): return int(x)) else "Waiting for the others  ·  %d",
					float(ev.seconds), my_seat in ev.voters.map(func(x): return int(x)))
			elif mine:
				hud.master.show_vote("Asking the others about %s  ·  %%d" % MasterPanel.name_of(str(ev.game)), float(ev.seconds), false)
		"master_vote_end":
			t.master["vote"] = null
			if mine:
				hud.master.hide_vote()   # (the dealer says how it went)
		"master_queued":
			t.master["queued"] = ev.game
			if mine:
				hud.master.show_queued(str(ev.game) if ev.game != null else "")
		"master_revert":
			t.master_revert_end = Time.get_ticks_msec() / 1000.0 + float(ev.seconds) if ev.get("seconds") != null else 0.0


## You clicked the dealer at the Master Table you're sitting at.
func _on_dealer_clicked(t: CasinoTable) -> void:
	if state != "seated" or t != active_table or not t.is_master:
		return
	if t.phase == "changing":
		return
	if t.master.get("vote") != null:
		hud.show_toast("A change is already being asked about.")
		return
	if t.master.get("queued") != null:
		t.dealer.say("%s is next, after this hand." % MasterPanel.name_of(str(t.master.queued)))
		return
	t.dealer.say("What would you like to play?" if t.master_game == "" else
		"Let's finish this hand first. What would you like next?" if t.in_hand else "Fancy a change? What would you like to play?")
	_open_master_menu(t)


func _open_master_menu(t: CasinoTable) -> void:
	var others := 0
	for seat in t.occupants:
		if seat != my_seat and t.occupants[seat].get("human", false):
			others += 1
	var note := "The table changes to suit the game."
	var warn := false
	if t.in_hand or (t.phase != "betting" and t.master_game != ""):
		note = "This hand finishes first, then the table changes."
		warn = true
	elif others > 0:
		note = "The others at the table will be asked first."
		warn = true
	elif t.master_game != "":
		note = "Any bets on the felt come back to you first."
	hud.master.open_menu(t.table_id, t.master_game, t.occupants.size() >= t.seat_count(), note, warn)


# ------------------------------------------------------------------ helpers
## A point at a table or cabinet (its own coordinates), on the floor (World's frame).
func _on_floor(t: FloorGame, p: Vector2) -> Vector2:
	return world.to_local(t.to_global(p))


static func _total(b: Dictionary) -> int:
	var t := 0
	for spot in b:
		t += int(b[spot])
	return t
