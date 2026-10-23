class_name AtmPanel
extends Control
## The lobby's cash machine (the server's bank.py), over the floor while you stand at it: a blue screen with four
## options down each side beside its side keys, a keypad, and a cash slot that deals £50 notes. It shows your bank
## balance, never your cash in hand (the top-left has that). Signed off as docs/atm/mockup/.
##
## open_atm() asks the server (atm_open) and shows "Please wait" until the `atm` state comes; every withdrawal or
## deposit is the server's to allow (atm_withdraw / atm_deposit), its reply an `atm` with `done` or the `error` the
## screen shows. Esc, Leave, Exit and Finish close it. Drawn in a 540×604 design space, scaled down to fit.

signal closed

const SIZE := Vector2(540, 604)
const FONT := BettingBar.FONT
const SCREEN_FONT := preload("res://assets/fonts/VT323-Regular.ttf")
const NOTE := preload("res://assets/atm/note50.png")
const NOTE_PENCE := 5000
const METAL := Color("2c3236")
const METAL_HI := Color("4a5257")
const LCD := Color("0c3d8f")
const LCD_DEEP := Color("072659")
const LCD_INK := Color("e8f1ff")
const LCD_DIM := Color("8fb2e6")
const LCD_HI := Color("ffe28a")
const LCD_OFF := Color("5d7cae")
const LCD_BAD := Color("ff9c8f")
const LCD_RECT := Rect2(60, 60, 420, 330)
const LCD_IN := Rect2(66, 66, 408, 318)
const ROW_H := 62.0
const PAD := Rect2(18, 404, 288, 182)
const CARD_SLOT := Rect2(322, 404, 200, 40)
const CASH_SLOT := Rect2(322, 456, 200, 54)
const KEYS := ["1", "2", "3", "cancel", "4", "5", "6", "clear", "7", "8", "9", "enter", "", "0", "", ""]

var waiting := false        # opened, the server's state not here yet
var _st := {}               # the server's last `atm`
var _st_at := 0.0           # when it came (the overdrawn countdown runs from it)
var _busy := false          # a withdrawal or deposit sent, its answer not back yet
var _screen := "home"
var _entry := ""            # the Other amount typed, whole pounds
var _msg := ""              # an error on the screen
var _done := {}             # {kind, amount} for the done screen
var _notes := 0             # notes in the cash slot
var _notes_at := -1.0       # when they started coming out
var _refreshed := false     # asked again once the overdrawn wait ran out
var _hover := ""
var _scale := 1.0
var _origin := Vector2.ZERO
var _spaced: FontVariation


func _ready() -> void:
	hide()
	set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	mouse_filter = MOUSE_FILTER_STOP
	_spaced = FontVariation.new()
	_spaced.base_font = FONT
	_spaced.spacing_glyph = 3
	set_process(false)


func open_atm() -> void:
	waiting = true
	_busy = false
	_screen = "home"
	_entry = ""
	_msg = ""
	_notes = 0
	_st = {}
	show()
	set_process(true)
	Net.send("atm_open")


func close_atm() -> void:
	if not visible:
		return
	hide()
	set_process(false)
	waiting = false
	closed.emit()


## The server's `atm`: the state, plus `done` after a withdrawal or deposit, or the `error` to show.
func apply(msg: Dictionary) -> void:
	if not visible:
		return
	waiting = false
	_busy = false
	_st = msg
	_st_at = _now()
	_refreshed = false
	if msg.has("done"):
		_done = msg.done
		_screen = "done"
		_entry = ""
		_msg = ""
		if str(_done.kind) == "withdraw":
			_notes = clampi(int(_done.amount) / NOTE_PENCE, 1, 10)
			_notes_at = _now()
	elif msg.has("error"):
		_msg = str(msg.error)
	queue_redraw()


func _now() -> float:
	return Time.get_ticks_msec() / 1000.0


func _process(_delta: float) -> void:
	if _screen == "nowd" and str(_st.get("why", "")) == "overdrawn" and _wait_left() <= 0.0 and not _refreshed:
		_refreshed = true
		Net.send("atm_open")
	queue_redraw()


func _wait_left() -> float:
	return maxf(0.0, float(_st.get("wait", 0)) - (_now() - _st_at))


# ------------------------------------------------------------------ the screens
## What the screen shows now: {title, sub, L: [4 options], R: [4 options], mid: [[text, size, colour]], lines}. An
## option is {label, id, off}; a `mid` message takes the first two rows, `lines` the first three.
func _screen_def() -> Dictionary:
	var d := {"title": "", "sub": "", "L": [null, null, null, null], "R": [null, null, null, null]}
	if waiting:
		d.title = "Please wait"
		d.mid = [["Connecting to your bank", 23, LCD_DIM]]
		d.R[3] = _opt("Exit", "leave")
		return d
	var cap := int(_st.get("cap", 0))
	var hand := Session.balance
	var back := _opt("Back", "home")
	match _screen:
		"home":
			d.title = "Welcome, %s" % Session.player.get("name", "")
			d.sub = ["Balance ", _money(int(_st.get("bank", 0)))]
			d.R = [_opt("Withdraw cash", "withdraw"), _opt("Deposit cash", "deposit", hand <= 0), _opt("Recent", "recent"),
				_opt("Exit", "leave")]
		"withdraw":
			d.title = "Withdraw cash"
			d.sub = "Up to %s, %s" % [_money(cap), _cap_reason()]
			d.L = [_pick("w", 5000, cap), _pick("w", 10000, cap), null, back]
			d.R = [_pick("w", 25000, cap), _pick("w", 50000, cap), null, _opt("Other amount", "w_other")]
			if _msg != "":
				d.mid_note = _msg
		"nowd":
			if str(_st.get("why", "")) == "carrying":
				d.title = "Withdrawals paused"
				d.mid = [["You're holding %s or more." % _money(int(_st.get("hand_under", 0))), 23, LCD_INK],
					["Withdraw again once you have less on you.", 23, LCD_DIM]]
			else:
				d.title = "Account overdrawn"
				var left := ceili(_wait_left())
				d.mid = [["Next withdrawal in", 23, LCD_DIM], ["%d:%02d" % [left / 60, left % 60], 42, LCD_HI],
					["Once every %d minutes while overdrawn" % int(_st.get("cooldown_min", 0)), 23, LCD_DIM]]
			d.R[3] = back
		"deposit":
			d.title = "Deposit cash"
			d.sub = "Choose an amount"
			d.L = [_pick("d", 5000, hand), _pick("d", 10000, hand), null, back]
			d.R = [_pick("d", 25000, hand), _opt("All my cash", "d_all", hand <= 0), null, _opt("Other amount", "d_other")]
			if _msg != "":
				d.mid_note = _msg
		"w_other", "d_other":
			var wd := _screen == "w_other"
			d.title = "Withdraw cash" if wd else "Deposit cash"
			d.sub = "Enter an amount, then press Enter"
			var blink := "_" if fmod(_now(), 1.0) < 0.5 else " "
			d.mid = [["£" + _entry + blink, 40, Color.WHITE, true]]
			if _msg != "":
				d.mid.append([_msg, 23, LCD_BAD])
			else:
				d.mid.append([("Most you can take: " + _money(cap)) if wd else "Up to the cash you're holding", 23, LCD_DIM])
			if wd:
				d.mid.append(["£50 increments only", 23, LCD_DIM])
			d.L[3] = _opt("Back", "withdraw" if wd else "deposit")
			d.R[3] = _opt("Enter", "enter")
		"recent":
			d.title = "Recent"
			var lines := []
			for h in _st.get("history", []):
				lines.append([_clock(float(h.t)) + (" Withdrew" if str(h.kind) == "withdraw" else " Deposited"), _money(int(h.amount))])
			if lines.is_empty():
				lines.append(["No ATM transactions yet", ""])
			d.lines = lines
			d.R[3] = back
		"done":
			var wd := str(_done.get("kind", "")) == "withdraw"
			d.title = "Please take your cash" if wd else "Deposit received"
			var bank := int(_st.get("bank", 0))
			d.mid = [[_money(int(_done.get("amount", 0))), 42, LCD_HI], ["Balance " + _money(bank), 23, LCD_BAD if bank < 0 else LCD_DIM]]
			d.R[2] = _opt("Another service", "home")
			d.R[3] = _opt("Finish", "leave")
	return d


func _opt(label: String, id: String, off := false) -> Dictionary:
	return {"label": label, "id": id, "off": off}


func _pick(kind: String, pence: int, most: int) -> Dictionary:
	return _opt(_money(pence), "%s%d" % [kind, pence], pence > most)


func _cap_reason() -> String:
	var t := int(_st.get("threshold", 0))
	return ("bank %s or more" if int(_st.get("bank", 0)) >= t else "bank under %s") % _money(t)


func _money(pence: int) -> String:
	return Money.format(pence, true) if pence % 100 == 0 else Money.format(pence)


func _clock(unix: float) -> String:
	var d := Time.get_datetime_dict_from_unix_time(int(unix) + int(Time.get_time_zone_from_system().get("bias", 0)) * 60)
	return "%02d:%02d" % [d.hour, d.minute]


# ------------------------------------------------------------------ doing things
func _act(id: String) -> void:
	_msg = ""
	match id:
		"leave":
			close_atm()
			return
		"home", "deposit", "recent":
			_screen = id
			_notes = 0
		"withdraw":
			_screen = "withdraw" if _st.get("can", false) else "nowd"
		"w_other", "d_other":
			_screen = id
			_entry = ""
		"enter":
			_enter()
		"d_all":
			_send("atm_deposit", Session.balance)
		_:
			if id.begins_with("w") or id.begins_with("d"):
				_send("atm_withdraw" if id[0] == "w" else "atm_deposit", int(id.substr(1)))
	queue_redraw()


func _enter() -> void:
	if _entry == "":
		_msg = "Enter an amount."
		return
	_send("atm_withdraw" if _screen == "w_other" else "atm_deposit", int(_entry) * 100)


func _send(kind: String, pence: int) -> void:
	if _busy or waiting:
		return
	_busy = true
	Net.send(kind, {"amount": pence})


func _key(k: String) -> void:
	if k == "cancel":
		if _screen == "home" or waiting:
			close_atm()
		else:
			_act("home")
		return
	if _screen != "w_other" and _screen != "d_other":
		return
	_msg = ""
	match k:
		"clear":
			_entry = ""
		"back":
			_entry = _entry.left(-1)
		"enter":
			_enter()
		_:
			if _entry.length() < 5:
				_entry = (_entry + k).lstrip("0")
	queue_redraw()


func _input(event: InputEvent) -> void:
	if not visible:
		return
	if event.is_action_pressed("cancel"):
		close_atm()
		get_viewport().set_input_as_handled()
		return
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	var code: Key = event.keycode
	if code >= KEY_0 and code <= KEY_9:
		_key(str(code - KEY_0))
	elif code >= KEY_KP_0 and code <= KEY_KP_9:
		_key(str(code - KEY_KP_0))
	elif code == KEY_BACKSPACE:
		_key("back")
	elif code == KEY_ENTER or code == KEY_KP_ENTER:
		_key("enter")
	else:
		return
	get_viewport().set_input_as_handled()


# ------------------------------------------------------------------ hit areas
func _row_y(i: int) -> float:
	return LCD_IN.position.y + 60.0 + i * ROW_H + ROW_H / 2.0


func _side_key(side: String, i: int) -> Rect2:
	return Rect2(20.0 if side == "L" else 490.0, _row_y(i) - 11.0, 30, 22)


func _pad_key(i: int) -> Rect2:
	var unit := (PAD.size.x - 20.0 - 18.0) / 4.5
	var col := i % 4
	var x := PAD.position.x + 10.0 + col * (unit + 6.0)
	return Rect2(x, PAD.position.y + 10.0 + (i / 4) * 42.0, unit * (1.5 if col == 3 else 1.0), 36)


func _leave_rect() -> Rect2:
	return Rect2(400, 18, 116, 26)


## Every press-able thing: [id, rect, enabled].
func _buttons(d: Dictionary) -> Array:
	var out := [["leave", _leave_rect(), true]]
	for side in ["L", "R"]:
		for i in 4:
			var o = d[side][i]
			out.append(["side:" + (o.id if o else ""), _side_key(side, i), o != null and not o.off])
	for i in KEYS.size():
		if KEYS[i] != "":
			out.append(["key:" + KEYS[i], _pad_key(i), true])
	return out


func _at(screen_pos: Vector2) -> Array:
	var p := (screen_pos - _origin) / _scale
	for b in _buttons(_screen_def()):
		if b[2] and b[1].has_point(p):
			return b
	return []


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		var b := _at(event.position)
		var id: String = b[0] if not b.is_empty() else ""
		if id != _hover:
			_hover = id
			mouse_default_cursor_shape = CURSOR_POINTING_HAND if id != "" else CURSOR_ARROW
	elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var b := _at(event.position)
		accept_event()
		if b.is_empty():
			return
		Sfx.play("click")
		var id: String = b[0]
		if id == "leave":
			close_atm()
		elif id.begins_with("side:"):
			_act(id.substr(5))
		elif id.begins_with("key:"):
			_key(id.substr(4))


# ------------------------------------------------------------------ drawing
func _draw() -> void:
	var vp := size
	_scale = minf(1.0, minf((vp.y - 32.0) / SIZE.y, (vp.x - 32.0) / SIZE.x))
	_origin = ((vp - SIZE * _scale) / 2.0).round()
	draw_rect(Rect2(Vector2.ZERO, vp), Color(0.016, 0.02, 0.024, 0.55))
	draw_set_transform(_origin, 0.0, Vector2(_scale, _scale))
	var d := _screen_def()
	_draw_body()
	_draw_lcd(d)
	for side in ["L", "R"]:
		for i in 4:
			var o = d[side][i]
			_draw_side_key(_side_key(side, i), o != null and not o.off, _hover == "side:" + (o.id if o else "-"))
	_draw_pad()
	_draw_slot(CARD_SLOT, "CARD · RECEIPT", false)
	_draw_slot(CASH_SLOT, "CASH", _notes > 0)
	_draw_notes()
	draw_set_transform(Vector2.ZERO)


func _box(bg: Color, border: Color, radius: int, shadow := 0) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = border
	s.set_border_width_all(1)
	s.set_corner_radius_all(radius)
	s.anti_aliasing = true
	if shadow > 0:
		s.shadow_color = Color(0, 0, 0, 0.6)
		s.shadow_size = shadow
		s.shadow_offset = Vector2(0, 8)
	return s


func _text(at: Vector2, text: String, font: Font, size: int, colour: Color, align := HORIZONTAL_ALIGNMENT_LEFT, width := -1.0) -> void:
	draw_string(font, at, text, align, width, size, colour)


func _draw_body() -> void:
	var body := _box(METAL, Color("5b646a"), 14, 24)
	body.corner_radius_bottom_left = 10
	body.corner_radius_bottom_right = 10
	draw_style_box(body, Rect2(Vector2.ZERO, SIZE))
	draw_rect(Rect2(14, 1, SIZE.x - 28, 1), Color(1, 1, 1, 0.15))
	draw_polygon(PackedVector2Array([Vector2(1, 14), Vector2(SIZE.x - 1, 14), Vector2(SIZE.x - 1, 90), Vector2(1, 90)]),
		PackedColorArray([Color(METAL_HI, 0.8), Color(METAL_HI, 0.8), Color(METAL_HI, 0.0), Color(METAL_HI, 0.0)]))
	# the brand strip, with Leave
	draw_style_box(_box(Color("0e1113"), Color.BLACK, 6), Rect2(18, 16, 504, 30))
	_text(Vector2(30, 36), "CASINO WORLD · CASH", _spaced, 13, BettingBar.BRASS_HI)
	var hot := _hover == "leave"
	var c := BettingBar.BRASS_HI if hot else BettingBar.INK
	_text(Vector2(426, 36), "LEAVE", _spaced, 13, c)
	var kbd := Rect2(476, 23, 34, 17)
	draw_style_box(_box(Color(0, 0, 0, 0), Color(c, 0.65), 4), kbd)
	_text(Vector2(kbd.position.x, 36), "Esc", FONT, 12, Color(c, 0.8), HORIZONTAL_ALIGNMENT_CENTER, kbd.size.x)


func _draw_lcd(d: Dictionary) -> void:
	draw_style_box(_box(Color("07090a"), Color("07090a"), 6), LCD_RECT)
	var r := LCD_IN
	draw_polygon(PackedVector2Array([r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)]),
		PackedColorArray([LCD, LCD, LCD_DEEP, LCD_DEEP]))
	var cx := r.position.x + r.size.x / 2.0
	# title and the line under it
	_text(Vector2(r.position.x, r.position.y + 30), d.title, SCREEN_FONT, 30, LCD_HI, HORIZONTAL_ALIGNMENT_CENTER, r.size.x)
	if d.sub is Array:   # "Balance " and the amount (red when overdrawn)
		var bank := int(_st.get("bank", 0))
		var w1 := SCREEN_FONT.get_string_size(d.sub[0], HORIZONTAL_ALIGNMENT_LEFT, -1, 21).x
		var w2 := SCREEN_FONT.get_string_size(d.sub[1], HORIZONTAL_ALIGNMENT_LEFT, -1, 21).x
		var x := cx - (w1 + w2) / 2.0
		_text(Vector2(x, r.position.y + 52), d.sub[0], SCREEN_FONT, 21, LCD_DIM)
		_text(Vector2(x + w1, r.position.y + 52), d.sub[1], SCREEN_FONT, 21, LCD_BAD if bank < 0 else Color.WHITE)
	elif d.sub != "":
		_text(Vector2(r.position.x, r.position.y + 52), d.sub, SCREEN_FONT, 21, LCD_DIM, HORIZONTAL_ALIGNMENT_CENTER, r.size.x)
	var free := [0, 1, 2, 3]
	if d.has("mid"):
		free = [2, 3]
		var total := 0.0
		for line in d.mid:
			total += line[1] + 4.0
		var y: float = _row_y(0) - ROW_H / 2.0 + (ROW_H * 2.0 - total) / 2.0
		for line in d.mid:
			y += line[1]
			_text(Vector2(r.position.x + 12, y - line[1] * 0.18), line[0], SCREEN_FONT, line[1], line[2], HORIZONTAL_ALIGNMENT_CENTER, r.size.x - 24)
			if line.size() > 3:   # the amount being typed, underlined
				draw_rect(Rect2(cx - 95, y + 2, 190, 2), LCD_HI)
			y += 4.0
	elif d.has("lines"):
		free = [3]
		var y := _row_y(0) - ROW_H / 2.0 + 30.0
		for line in d.lines:
			_text(Vector2(r.position.x + 22, y), line[0], SCREEN_FONT, 22, LCD_DIM)
			_text(Vector2(r.position.x + 22, y), line[1], SCREEN_FONT, 22, LCD_INK, HORIZONTAL_ALIGNMENT_RIGHT, r.size.x - 44)
			y += 30.0
	if d.has("mid_note"):   # an error under the amounts (a refused preset)
		_text(Vector2(r.position.x, _row_y(2) + 8), d.mid_note, SCREEN_FONT, 23, LCD_BAD, HORIZONTAL_ALIGNMENT_CENTER, r.size.x)
	for i in free:
		for side in ["L", "R"]:
			var o = d[side][i]
			if o != null:
				_draw_option(o, side, _row_y(i))
	for y in range(int(r.position.y), int(r.end.y), 3):   # scan lines
		draw_rect(Rect2(r.position.x, y + 2, r.size.x, 1), Color(0, 0, 0, 0.12))


func _draw_option(o: Dictionary, side: String, y: float) -> void:
	var r := LCD_IN
	var c := LCD_OFF if o.off else LCD_INK
	var arrow := Color(LCD_DIM, 0.4 if o.off else 1.0)
	var base := y + 9.0
	if side == "L":
		var ax := r.position.x + 12.0
		draw_colored_polygon(PackedVector2Array([Vector2(ax, y), Vector2(ax + 9, y - 6), Vector2(ax + 9, y + 6)]), arrow)
		_text(Vector2(ax + 18, base), o.label, SCREEN_FONT, 26, c)
	else:
		var ax := r.end.x - 12.0
		draw_colored_polygon(PackedVector2Array([Vector2(ax, y), Vector2(ax - 9, y - 6), Vector2(ax - 9, y + 6)]), arrow)
		_text(Vector2(r.position.x, base), o.label, SCREEN_FONT, 26, c, HORIZONTAL_ALIGNMENT_RIGHT, r.size.x - 30)


func _draw_side_key(rect: Rect2, live: bool, hot: bool) -> void:
	var face := Color("8a9398").lightened(0.12 if hot else 0.0)
	draw_rect(Rect2(rect.position + Vector2(0, 2), rect.size), Color("0a0c0d"))
	var s := _box(face, Color("0a0c0d"), 4)
	draw_style_box(s, rect)
	draw_rect(Rect2(rect.position.x + 3, rect.position.y + 1, rect.size.x - 6, 1), Color(1, 1, 1, 0.5))
	if not live:
		draw_style_box(_box(Color(METAL, 0.5), Color(0, 0, 0, 0), 4), rect)


func _draw_pad() -> void:
	draw_style_box(_box(Color("121517"), Color.BLACK, 8), PAD)
	for i in KEYS.size():
		var k: String = KEYS[i]
		if k == "":
			continue
		var r := _pad_key(i)
		var face: Color = {"cancel": Color("dc6e5e"), "clear": Color("e6c05a"), "enter": Color("66c599")}.get(k, Color("c3c8cb"))
		var ink: Color = {"cancel": Color("2a0d08"), "clear": Color("2a1d05"), "enter": Color("062114")}.get(k, Color("15191b"))
		if _hover == "key:" + k:
			face = face.lightened(0.15)
		draw_rect(Rect2(r.position + Vector2(0, 2), r.size), Color.BLACK)
		draw_style_box(_box(face, Color.BLACK, 5), r)
		draw_rect(Rect2(r.position.x + 3, r.position.y + 1, r.size.x - 6, 1), Color(1, 1, 1, 0.6))
		if k.length() > 1:
			_text(Vector2(r.position.x, r.position.y + 23), k.to_upper(), _spaced, 13, ink, HORIZONTAL_ALIGNMENT_CENTER, r.size.x)
		else:
			_text(Vector2(r.position.x, r.position.y + 25), k, FONT, 18, ink, HORIZONTAL_ALIGNMENT_CENTER, r.size.x)


func _draw_slot(r: Rect2, label: String, lit: bool) -> void:
	draw_style_box(_box(Color("0e1113"), Color.BLACK, 6), r)
	var mouth := Rect2(r.position.x + 14, r.position.y + 12, r.size.x - 28, 8)
	if lit:
		for g in [6, 4, 2]:
			draw_style_box(_box(Color(BettingBar.WIN, 0.08), Color(0, 0, 0, 0), 6), mouth.grow(g))
	draw_style_box(_box(Color.BLACK, BettingBar.WIN if lit else Color("3a4246"), 4), mouth)
	_text(Vector2(r.position.x + 10, r.end.y - 5), label, _spaced, 10, Color("6b7378"))


## The cash: one £50 note per £50 (up to ten), each sliding out of the slot's mouth in turn, over its lower lip and
## glow, landing a little lower and askew so the stack looks thick.
func _draw_notes() -> void:
	if _notes <= 0:
		return
	var w := CASH_SLOT.size.x - 36.0
	var h := w * NOTE.get_height() / NOTE.get_width()
	var top := CASH_SLOT.position.y + 16.0
	var base := Transform2D(0.0, Vector2(_scale, _scale), 0.0, _origin)
	var t := _now() - _notes_at
	for i in _notes:
		var p := clampf((t - i * 0.09) / 0.45, 0.0, 1.0)
		if p <= 0.0:
			continue
		p = 1.0 - pow(1.0 - p, 3.0)
		var dx := float((i * 37) % 7 - 3)
		var rot := deg_to_rad(float((i * 53) % 9 - 4) * 0.35 * p)
		var centre := Vector2(CASH_SLOT.position.x + 18.0 + w / 2.0 + dx, top + i * 2.0 * p + h / 2.0)
		draw_set_transform_matrix(base * Transform2D(rot, centre))
		var shown := h * p   # the part out of the mouth: the note's leading (bottom) edge first
		var dest := Rect2(-w / 2.0, -h / 2.0, w, shown)
		draw_rect(Rect2(dest.position + Vector2(0, 3), dest.size), Color(0, 0, 0, 0.3))
		var src := Rect2(0, NOTE.get_height() * (1.0 - p), NOTE.get_width(), NOTE.get_height() * p)
		draw_texture_rect_region(NOTE, dest, src)
	draw_set_transform_matrix(base)
