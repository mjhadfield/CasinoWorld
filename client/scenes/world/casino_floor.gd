extends Node2D
## The casino floor: everyone walking around (you, other players, NPCs), the
## tables, and the camera. Free stools glow with SIT while you're walking:
## click one to sit there (you walk over first if it's far), or stand on one and
## press E. The camera glides onto the table and stays in this same world, so
## the floor carries on around you. Stand up and the camera glides back.
##
## The server owns the table and the world; this scene routes its messages to
## the right avatar or table and turns your clicks into requests.

const WALK_ZOOM := Vector2(2, 2)
const TABLE_ZOOM := Vector2(2.8, 2.8)
const ENTITY_SCENE := preload("res://scenes/world/entity_avatar.tscn")
const MAIN_BET_NAMES := {"ante": "an Ante", "bet": "a Blackjack bet", "player": "a Player, Banker or Tie bet"}

@onready var player: CharacterBody2D = $LocalPlayer
@onready var camera: Camera2D = $Camera
@onready var hud: CanvasLayer = $HUD
@onready var entities_root: Node2D = $Entities
@onready var nav: NavigationRegion2D = $Nav

var tables := {}    # table id -> FloorGame (a CasinoTable, or a SlotCabinet)
var points := {}    # floor point name -> position
var entities := {}  # entity id -> EntityAvatar (everyone but you)
var state := "walking"  # walking | seated (at a table) | slot (at a slot cabinet, full screen)
var _heading_for := {}  # {table, seat} while walking over to a stool you clicked
var active_table: CasinoTable = null
var active_slot: SlotCabinet = null   # the cabinet you're sitting at (state "slot")
var slot_screen: SlotScreen
var my_seat := -1
var my_bets := {}
var my_ready := false
var played_a_hand := false
var my_hand := ""  # your hand's name or total (shown in the HUD bar)
var _actions: Array = []  # the action buttons on offer right now (for their keys)
var _camera_tween: Tween
var _was_my_turn := false
var _last_tick := -1      # the countdown second last ticked
var _placed: Array = []   # this round's chips, newest last ([spot, amount added]): what Undo takes back


func _ready() -> void:
	for t in get_tree().get_nodes_in_group("tables"):
		tables[t.table_id] = t
		t.spot_clicked.connect(_on_spot_clicked)
		t.spot_removed.connect(_on_spot_removed)
		t.my_hand_changed.connect(func(text: String):
			if t == active_table:
				my_hand = text)
		if t.has_signal("sort_requested"):  # Pai Gow: your cards open in the sorter, and close once set
			t.sort_requested.connect(func(cards: Array):
				if t == active_table:
					Sfx.play("turn")
					hud.sorter.open(cards, t.face_up))
			t.sort_finished.connect(func():
				if t == active_table:
					hud.sorter.close())
			t.claim_requested.connect(func(cards: Array, bonus):
				if t == active_table:
					Sfx.play("turn")
					hud.sorter.open_claim(cards, bonus))
	for c in get_tree().get_nodes_in_group("slot_cabinets"):
		tables[c.table_id] = c
	slot_screen = SlotScreen.new()
	hud.add_slot_screen(slot_screen)
	slot_screen.stand_requested.connect(func(): Net.send("stand"))
	slot_screen.settings_requested.connect(hud.settings_menu.toggle)
	for m in get_tree().get_nodes_in_group("floor_points"):
		points[str(m.name)] = m.global_position
	player.global_position = points.get("entrance", Vector2(700, 1110))
	camera.global_position = player.global_position
	camera.zoom = WALK_ZOOM
	_bake_navigation()
	_offer_seats(true)
	Sfx.start_room()

	hud.rebet_pressed.connect(func():
		_placed.clear()
		Net.send("rebet"))
	hud.auto_rebet_toggled.connect(func(on: bool): Net.send("auto_rebet", {"on": on}))
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
	hud.name_entered.connect(Session.choose_name)
	Net.message_received.connect(_on_message)
	Net.resynced.connect(_on_resynced)
	Net.disconnected.connect(_on_disconnected)


func _bake_navigation() -> void:
	var poly: NavigationPolygon = nav.navigation_polygon
	poly.clear_outlines()
	var size: Vector2 = $Room.SIZE
	poly.add_outline(PackedVector2Array([Vector2(14, 74), Vector2(size.x - 14, 74), size - Vector2(14, 14), Vector2(14, size.y - 14)]))
	nav.bake_navigation_polygon(false)


func _process(_delta: float) -> void:
	if state == "walking" and (_camera_tween == null or not _camera_tween.is_running()):
		camera.global_position = player.global_position
	_check_heading()
	if state == "seated" and active_table:
		var view := _seated_view()
		hud.update_seated(view)
		_play_cues(view)


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
			_sit_on_stool_underfoot()
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("cancel"):
		if state == "seated":
			_request_stand()
		elif state == "slot":
			slot_screen.cancel_pressed()
		get_viewport().set_input_as_handled()
	elif state == "seated" and event.is_action_pressed("ready_up"):
		if _can_bet():
			_on_ready()
		get_viewport().set_input_as_handled()
	elif state == "seated" and event is InputEventKey and event.pressed and not event.echo:
		for a in _actions:  # the action buttons' keys: P/F, H/S/D/P, I/N
			if a.get("key", "") != "" and event.physical_keycode == OS.find_keycode_from_string(a.key):
				_on_action(str(a.id))
				get_viewport().set_input_as_handled()
				return


## A click on a glowing stool, caught before the click-to-walk sees it.
func _input(event: InputEvent) -> void:
	if state != "walking" or hud.is_typing():
		return
	if not (event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT):
		return
	var at := get_global_mouse_position()
	for t in tables.values():
		var seat: int = t.stool_at(t.to_local(at))
		if seat >= 0:
			_take_seat(t, seat)
			get_viewport().set_input_as_handled()
			return


# ------------------------------------------------------------------ taking a seat
const SIT_REACH := 70.0     # this close to a stool you clicked, you just sit down
const UNDERFOOT := 16.0     # standing this close to a stool, E sits you on it


## E: the free stool you're standing on, if any.
func _sit_on_stool_underfoot() -> void:
	var best_table: FloorGame = null
	var best_seat := -1
	var best_d := UNDERFOOT
	for t in tables.values():
		if not t.offer_seats:
			continue
		for seat in t.free_seats():
			var d := player.global_position.distance_to(t.to_global(t.stool_pos(seat)))
			if d < best_d:
				best_table = t
				best_seat = seat
				best_d = d
	if best_table:
		_take_seat(best_table, best_seat)


## Sit at a free stool: straight away if it's close, else walk over first.
func _take_seat(t: FloorGame, seat: int) -> void:
	if not Net.is_open():
		hud.show_toast("Not connected to the casino")
		return
	var stool: Vector2 = t.to_global(t.stool_pos(seat))
	if player.global_position.distance_to(stool) <= SIT_REACH:
		_heading_for = {}
		Net.send("sit", {"table": t.table_id, "seat": seat})
	else:
		var goal: Vector2 = t.to_global(t.chair_pos(seat) + Vector2(0, 14))  # just in front of the stool
		_heading_for = {"table": t, "seat": seat, "goal": goal}
		player.walk_to(goal)


## Walking over to a stool you clicked: sit on arriving; give up if you stop
## short (walked into something), steer elsewhere, or someone takes it first.
func _check_heading() -> void:
	if _heading_for.is_empty() or state != "walking":
		return
	var t: FloorGame = _heading_for.table
	var seat: int = _heading_for.seat
	var now_heading = player.target()
	if not seat in t.free_seats() or (now_heading != null and now_heading.distance_to(_heading_for.goal) > 1.0):
		_heading_for = {}  # taken, or you've steered somewhere else
		return
	if player.global_position.distance_to(t.to_global(t.stool_pos(seat))) <= SIT_REACH:
		_heading_for = {}
		player.stop()
		Net.send("sit", {"table": t.table_id, "seat": seat})
	elif not player.is_walking_to_target():
		_heading_for = {}


## Cabinets of slots built with the admin page's Slot design wizard: the welcome lists them (where they stand,
## which way they face, their look). Each is added once, beside Armadillo's in the scene so it draws in the same
## order, then the walkable floor is baked again round them.
const SLOT_CABINET := preload("res://scenes/slots/slot_cabinet.tscn")

func _add_built_cabinets(list: Array) -> void:
	var anchor := get_tree().get_first_node_in_group("slot_cabinets")
	var added := false
	for cab in list:
		var id := str(cab.get("id", ""))
		if id.is_empty() or tables.has(id):
			continue
		var c: SlotCabinet = SLOT_CABINET.instantiate()
		c.table_id = id
		c.variant = str(cab.get("variant", "armadillo"))
		c.look = cab.get("cabinet", {})
		c.position = Vector2(float(cab.get("x", 0)), float(cab.get("y", 0)))
		c.add_to_group("navigation_obstacles")
		if anchor:
			anchor.add_sibling(c)
		else:
			add_child(c)
		c.facing = str(cab.get("facing", "down"))
		c.offer_seats = state == "walking"
		tables[id] = c
		added = true
	if added:
		_bake_navigation()


func _offer_seats(on: bool) -> void:
	for t in tables.values():
		t.offer_seats = on


func _sat_down(msg: Dictionary) -> void:
	var g: FloorGame = tables.get(msg.table)
	if g is SlotCabinet:
		return _sat_down_slot(g, msg)
	var t := g as CasinoTable
	if t == null:
		return
	active_table = t
	Sfx.focus = t.table_id
	my_seat = int(msg.seat)
	state = "seated"
	_heading_for = {}
	_offer_seats(false)
	_camera_to(t.focus_point(), TABLE_ZOOM)
	t.my_seat = my_seat
	t.mode = "seated"
	my_bets = t.zero_bets()
	my_ready = false
	played_a_hand = false
	my_hand = ""
	hud.setup_table(msg.get("rules", {}))
	hud.set_auto_rebet(false)
	if "chip_value" in t:
		t.chip_value = hud.selected_chip
	_placed.clear()
	hud.set_mode("seated")
	player.sit_at(t.to_global(t.chair_pos(my_seat)), t.sit_facing(my_seat), t.seat_pose())
	var ask: Dictionary = t.on_seated_prompt()
	if not ask.is_empty():
		hud.ask(ask.text, ask.yes, ask.no, func(): Net.send(ask.message[0], ask.message[1]))


## Sitting at a slot cabinet: the full-screen game grows out of its screen.
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
	player.sit_at(c.to_global(c.chair_pos(my_seat)), c.sit_facing(my_seat), c.seat_pose(), c.sit_z(my_seat))
	_camera_to(c.focus_point(), TABLE_ZOOM)
	slot_screen.open(c, msg.get("rules", {}), _screen_rect_of(c))


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
		Net.send("bet", {"spot": spot, "amount": 0 if int(my_bets.get(spot, 0)) else int(flat[spot])})
		return
	var trial := my_bets.duplicate()
	trial[spot] = int(my_bets.get(spot, 0)) + hud.selected_chip
	if active_table.max_cost(trial) > Session.balance:
		var main := active_table.main_spot()
		hud.show_toast("You wouldn't have enough to match that Ante with a Play bet." if spot == "ante"
			else "You wouldn't have enough left to double." if spot == main else "Not enough balance for that.")
		return
	my_bets = trial  # optimistic; the server's bet_changed confirms it
	_placed.append([spot, hud.selected_chip])
	Net.send("bet", {"spot": spot, "add": hud.selected_chip})


func _on_spot_removed(spot: String) -> void:
	if not _can_bet() or int(my_bets.get(spot, 0)) == 0:
		return
	if active_table.flat_spots().has(spot):
		Net.send("bet", {"spot": spot, "amount": 0})
		return
	my_bets[spot] = maxi(0, int(my_bets[spot]) - hud.selected_chip)
	Net.send("bet", {"spot": spot, "add": -hud.selected_chip})


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
	if not active_table.can_ready():
		return
	var main := active_table.main_spot()
	if _total(my_bets) > 0 and not active_table.has_main_bet(my_bets):
		hud.show_toast("Side bets need %s alongside them." % MAIN_BET_NAMES.get(main, "a main bet"))
		return
	Net.send("ready")


## An action button (or its key): the table says what to send.
func _on_action(id: String) -> void:
	if state != "seated" or not _actions.any(func(a): return str(a.id) == id):
		return
	var msg: Array = active_table.action_message(id)
	if not msg.is_empty():
		Net.send(msg[0], msg[1])


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
	var info: String = view.get("info", "")
	if t.in_hand and my_hand != "" and t.phase != "betting":
		info = "%s  ·  %s" % [my_hand, info] if info != "" else my_hand
	elif ctx.can_bet and not t.accepting_bets():
		info = "Bets you put down now play the next hand" + ("  ·  %s" % info if info != "" else "")
	return {"can_bet": ctx.can_bet, "can_ready": ctx.can_bet and t.can_ready(), "can_undo": ctx.can_bet and not _placed.is_empty(),
		"has_bets": ctx.has_bets, "can_rebet": played_a_hand,
		"is_ready": my_ready, "my_turn": view.get("my_turn", false), "actions": _actions, "info": info,
		"hide": view.get("hide", []), "quiet_betting": view.get("quiet_betting", false)}


func _leave_table() -> void:
	if active_slot:
		return _leave_slot()
	var t := active_table
	Sfx.focus = ""
	state = "walking"
	if t:
		t.mode = ""
		t.my_seat = -1
		player.stand_at(t.to_global(t.stand_pos(my_seat)))
	my_seat = -1
	active_table = null
	_actions = []
	hud.set_mode("walking")
	hud.clear_my_hand()
	my_hand = ""
	Session.hold_balance(false)
	_offer_seats(true)
	_camera_to_player()


func _leave_slot() -> void:
	var c := active_slot
	Sfx.focus = ""
	state = "walking"
	c.mode = ""
	c.my_seat = -1
	player.stand_at(c.to_global(c.stand_pos(my_seat)))
	slot_screen.close(_screen_rect_of(c))
	my_seat = -1
	active_slot = null
	hud.set_mode("walking")
	Session.hold_balance(false)
	_offer_seats(true)
	_camera_to_player()


# ------------------------------------------------------------------ camera
func _camera_to(pos: Vector2, zoom: Vector2) -> Tween:
	if _camera_tween:
		_camera_tween.kill()
	camera.position_smoothing_enabled = false
	_camera_tween = create_tween().set_parallel().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN_OUT)
	_camera_tween.tween_property(camera, "global_position", pos, 0.6)
	_camera_tween.tween_property(camera, "zoom", zoom, 0.6)
	return _camera_tween


func _camera_to_player() -> void:
	_camera_to(player.global_position, WALK_ZOOM).chain().tween_callback(func(): camera.position_smoothing_enabled = true)


# ------------------------------------------------------------------ server messages
func _on_message(msg: Dictionary) -> void:
	match msg.get("type"):
		"welcome":
			_add_built_cabinets(msg.get("cabinets", []))
			player.avatar.look = Session.look
			player.avatar.display_name = Session.player.get("name", "")
			if Session.needs_name:
				hud.show_name_prompt(Session.player.get("name", ""))
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
			_sat_down(msg)
		"pg_check":
			hud.sorter.on_check(msg)
		"pg_suggest":
			hud.sorter.on_suggest(msg)
		"notice":
			hud.show_toast(msg.get("message", ""), 4.0)
		"error":
			hud.show_toast(msg.get("message", "error"))
			if hud.sorter.is_open():
				hud.sorter.open_again()


func _on_slot_state(c: SlotCabinet, msg: Dictionary) -> void:
	c.apply_snapshot(msg)
	var seats: Array = msg.get("seats", [])
	if not seats.is_empty() and seats[0] != null and entities.has(seats[0].entity):
		entities[seats[0].entity].sit_at(c.to_global(c.chair_pos(0)), c.sit_facing(0), c.seat_pose(), c.sit_z(0))
	if msg.get("meters") != null:
		SlotScreen.set_meters(msg.meters, msg.get("rates"))
	if c == active_slot and state == "slot":
		slot_screen.apply_snapshot(msg)


func _on_slot_event(c: SlotCabinet, ev: Dictionary) -> void:
	c.handle_event(ev)
	if ev.has("meters"):
		SlotScreen.set_meters(ev.meters, ev.get("rates"))
	match ev.kind:
		"seated":
			if ev.entity != Session.entity_id and entities.has(ev.entity):
				entities[ev.entity].sit_at(c.to_global(c.chair_pos(0)), c.sit_facing(0), c.seat_pose(), c.sit_z(0))
		"stood":
			if ev.entity == Session.entity_id:
				_leave_table()
			elif entities.has(ev.entity):
				entities[ev.entity].stand_at(c.to_global(c.stand_pos(0)))
	if c == active_slot and state == "slot":
		slot_screen.on_event(ev)


func _on_table_state(msg: Dictionary) -> void:
	var t: CasinoTable = tables.get(msg.table)
	if t == null:
		return
	t.apply_snapshot(msg)
	var seats: Array = msg.get("seats", [])
	for i in seats.size():
		var s = seats[i]
		if s != null and entities.has(s.entity):
			entities[s.entity].sit_at(t.to_global(t.chair_pos(i)), t.sit_facing(i), t.seat_pose())
	if t == active_table and state == "seated":
		var mine = seats[my_seat] if my_seat < seats.size() else null
		if mine != null:
			for spot in t.bet_spots():
				my_bets[spot] = int(mine.bets.get(spot, 0))
			my_ready = mine.get("ready", false)
			hud.set_auto_rebet(mine.get("auto_rebet", false))


func _on_table_event(t: CasinoTable, ev: Dictionary) -> void:
	if t == null:
		return
	t.handle_event(ev)
	var mine := state == "seated" and t == active_table
	match ev.kind:
		"seated":
			if ev.entity != Session.entity_id and entities.has(ev.entity):
				entities[ev.entity].sit_at(t.to_global(t.chair_pos(int(ev.seat))), t.sit_facing(int(ev.seat)), t.seat_pose())
		"stood":
			if ev.entity == Session.entity_id:
				_leave_table()
			elif entities.has(ev.entity):
				entities[ev.entity].stand_at(t.to_global(t.stand_pos(int(ev.seat))))
		"bet_changed":
			if mine and int(ev.seat) == my_seat:
				my_bets = ev.bets.duplicate()
				hud.set_pending(t.pending_cost(my_bets))
		"ready":
			if mine and int(ev.seat) == my_seat:
				my_ready = true
		"bets_closed", "no_more_bets":
			if mine:
				my_ready = false
				_placed.clear()
				hud.set_pending(0)
				if my_seat in ev.seats.map(func(x): return int(x)):
					played_a_hand = true
		"throw":  # Craps: dice are out -- the chips you put down are paid for now
			if mine:
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
		"betting_open":
			if mine:
				my_bets = t.zero_bets()   # (any bets you queued come straight back as bet_changed)
				my_ready = false
				my_hand = ""
				hud.set_pending(0)
		"auto_rebet":
			if mine and int(ev.seat) == my_seat:
				hud.set_auto_rebet(ev.on)
				var why: String = ev.get("reason", "")
				if why == "timeout":
					hud.show_toast("Auto rebet is off -- you ran out of time.", 4.0)
				elif why != "":
					hud.show_toast("Auto rebet is off: %s" % why, 4.0)
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


func _on_disconnected() -> void:
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
	node.entity_id = e.id
	node.kind = e.get("kind", "player")
	node.look = e.get("look", "player_default")
	node.display_name = e.get("name", "")
	if e.get("x") != null:
		node.place(Vector2(e.x, e.y))
	else:
		node.place(points.get(at if at != "" else "entrance", Vector2(800, 1450)))
	node.set_action(e.get("anim", "idle") if e.get("anim") in ["idle", "walk"] else "idle", e.get("dir", "down"))
	entities[e.id] = node
	if e.get("walk") != null:
		node.walk_to(_resolve_target(e.walk.target), float(e.walk.remaining))


func _resolve_target(target: String) -> Vector2:
	var parts := target.split(":")
	if parts[0] == "point" and points.has(parts[1]):
		return points[parts[1]]
	if parts[0] == "seat" and parts.size() == 3 and tables.has(parts[1]):
		var t: FloorGame = tables[parts[1]]
		return t.to_global(t.stand_pos(int(parts[2])))
	return points.get("entrance", Vector2(800, 1450))


# ------------------------------------------------------------------ helpers
static func _total(b: Dictionary) -> int:
	var t := 0
	for spot in b:
		t += int(b[spot])
	return t
