extends Node
## Client-side mirror of what the server says about this player: their account's
## characters, the one they're playing, the casino they're in, its balance, and the
## progressive jackpot. Display only -- the server's wallet is the source of truth.
##
## The server issues an account token on first join; it's kept in user://
## (IndexedDB on the web build), so each device or browser stays the same account.
## Joining gets the character select (`account`); picking a character gets the
## casino chooser (`casinos`); nobody is on a floor until they enter a casino.
## After a dropped connection the same character is picked again into the same
## casino (`resume`), so a blip doesn't bounce you back to the select. A page
## opened with ?casino=<id> goes straight into that casino (a hidden one too).

signal joined(player: Dictionary)
signal balance_changed(pence: int)
## The character select's state arrived (or changed): characters, max_characters, difficulties, last_character.
signal account_received
## Off the floor and back at the select: "switch" (you left), "elsewhere" (picked in another window).
signal character_left(reason: String, character_name: String)
## The casino chooser's list arrived (or changed): casinos, last_casino.
signal casinos_received
## Off the casino's floor: "leave" (back to the chooser), "reload" (it reopens with new tables: a welcome follows).
signal casino_left(reason: String)

const SAVE_PATH := "user://session.cfg"

var player := {}
var entity_id := ""
var look := "player_default"
var characters: Array = []    # [{id, name, look, difficulty, balance, bank, online}]
var max_characters := 3
var difficulties := {}        # easy/normal/hard -> starting bank, pence
var last_character := -1      # id last played, or -1
var account_ready := false    # an `account` has come on this connection
var pending_pick := -1        # a character asked for and not yet on the floor as
var _resume := -1             # the character to pick again after a reconnect
var _resume_casino := ""      # and the casino to go back into
var casinos: Array = []       # the chooser: [{id, name, blurb, players, npcs, tables}]
var last_casino := ""         # the casino this character was last in
var casinos_ready := false    # a `casinos` has come for the character picked
var casino := {}              # {id, name}: the casino you're in (from the welcome)
var pending_casino := ""      # a casino asked for and not yet in
## The page's ?casino=<id>: straight into that casino on picking (and a preview of its draft).
var want_casino := ""
## A floor-plan preview (the admin page's Preview: the page's address ends ?preview=<room>): the draft's floor to
## walk round alone. The server gives it no body and no tables to play.
var preview := ""
var on_floor := false     # welcomed on this connection: until then the server refuses everything but join
var balance := 0          # latest from the server
var shown_balance := 0    # what the HUD shows: held back while a payout is still animating
var _held := false

# Jackpot meter: the server sends {amount, rate}; the client extrapolates.
var _jackpot_amount := 0.0
var _jackpot_rate := 0.0
var _jackpot_ceiling := 0.0
var _jackpot_received_at := 0.0
# The table a jackpot was just won at -> [what its meter showed before the win, until when]: its sign keeps
# showing that until the win is shown there (JackpotSign), so the drop doesn't give it away.
var _jackpot_holds := {}
const JACKPOT_HOLD_MAX := 90.0


func _ready() -> void:
	if OS.has_feature("web"):
		var p = JavaScriptBridge.eval("new URLSearchParams(location.search).get('preview') || ''")
		preview = str(p) if p != null else ""
		var c = JavaScriptBridge.eval("new URLSearchParams(location.search).get('casino') || ''")
		want_casino = str(c) if c != null else ""
	Net.message_received.connect(_on_message)
	Net.disconnected.connect(func():
		if on_floor:
			_resume = int(player.get("id", -1))
			_resume_casino = str(casino.get("id", ""))
		on_floor = false
		pending_pick = -1
		pending_casino = ""
		casinos_ready = false
		account_ready = false)
	Net.resynced.connect(func(_msg): _held = false)  # the payout it waited on was dropped; a fresh wallet follows


func _on_message(msg: Dictionary) -> void:
	match msg.get("type"):
		"hello":
			if int(msg.get("protocol", -1)) != Net.PROTOCOL_VERSION:
				push_warning("Server protocol %s != client %d" % [msg.get("protocol"), Net.PROTOCOL_VERSION])
			var join := {"token": _load_token()}
			if preview != "":
				join["preview"] = preview
				if want_casino != "":
					join["casino"] = want_casino
			Net.send("join", join)
		"account":
			characters = msg.get("characters", [])
			max_characters = int(msg.get("max", 3))
			difficulties = msg.get("difficulties", {})
			last_character = int(msg.get("last")) if msg.get("last") != null else -1
			account_ready = true
			if preview == "":
				_save_token(str(msg.get("token", "")))
			if _resume >= 0 and not on_floor and pending_pick < 0:   # back after a dropped connection
				pending_pick = _resume
				_resume = -1
				var again := {"id": pending_pick, "resume": true}
				if _resume_casino != "":
					again["casino"] = _resume_casino
				_resume_casino = ""
				Net.send("pick_character", again)
			account_received.emit()
		"character_left":
			on_floor = false
			entity_id = ""
			casinos_ready = false
			pending_casino = ""
			if str(msg.get("reason", "")) != "switch":   # (a switch's pick follows its leave)
				pending_pick = -1
			_resume = -1
			character_left.emit(str(msg.get("reason", "")), str(msg.get("name", "")))
		"casinos":
			casinos = msg.get("list", [])
			last_casino = str(msg.get("last")) if msg.get("last") != null else ""
			casinos_ready = true
			pending_pick = -1
			casinos_received.emit()
		"casino_left":
			on_floor = false
			entity_id = ""
			var why := str(msg.get("reason", ""))
			if why == "reload":   # (it reopens: its welcome is on the way)
				pending_casino = str(casino.get("id", ""))
			casino_left.emit(why)
		"welcome":
			player = msg.get("player", {})
			entity_id = str(msg.get("entity_id", ""))
			look = str(msg.get("look", look))
			casino = msg.get("casino", {})
			on_floor = true
			pending_pick = -1
			pending_casino = ""
			joined.emit(player)
		"wallet":
			balance = int(msg.get("balance", 0))
			if not _held:
				shown_balance = balance
				balance_changed.emit(shown_balance)
		"jackpot":
			var won_at: String = msg.get("table", "")
			if won_at != "" and jackpot_held(won_at) < 0.0:   # (a second win in the same hand keeps the first's)
				_jackpot_holds[won_at] = [jackpot_now(), _now() + JACKPOT_HOLD_MAX]
			_jackpot_amount = float(msg.get("amount", 0))
			_jackpot_rate = float(msg.get("rate", 0))
			_jackpot_ceiling = float(msg.get("ceiling", 0))
			_jackpot_received_at = _now()


## While held, the shown balance doesn't change (a payout's chips are still
## sliding back to you); releasing it catches up to the real balance.
func hold_balance(on: bool) -> void:
	_held = on
	if not on and shown_balance != balance:
		shown_balance = balance
		balance_changed.emit(shown_balance)


## Play as one of your characters (from the select, or switching: leave first): the casino chooser next, or
## straight into the page's ?casino=.
func pick(id: int) -> void:
	pending_pick = id
	casinos_ready = false
	if on_floor:
		Net.send("leave_character")
	var msg := {"id": id}
	if want_casino != "":
		msg["casino"] = want_casino
	Net.send("pick_character", msg)


## Onto a casino's floor (from the chooser, or switching casino: leave the one you're in first).
func enter_casino(id: String) -> void:
	pending_casino = id
	if on_floor:
		Net.send("leave_casino")
	Net.send("enter_casino", {"casino": id})


## The chooser's list again, fresh (opening it on the floor).
func list_casinos() -> void:
	Net.send("list_casinos")


## Back from the chooser to the character select.
func leave_character() -> void:
	Net.send("leave_character")


func create_character(character_name: String, spec: Dictionary, difficulty: String) -> void:
	Net.send("create_character", {"name": character_name, "look": spec, "difficulty": difficulty})


func edit_character(id: int, character_name: String, spec: Dictionary) -> void:
	Net.send("edit_character", {"id": id, "name": character_name, "look": spec})


func delete_character(id: int) -> void:
	Net.send("delete_character", {"id": id})


func character(id: int) -> Dictionary:
	for c in characters:
		if int(c.id) == id:
			return c
	return {}


## The jackpot right now, in pence (fractional, so a meter can roll smoothly).
func jackpot_now() -> float:
	var amount := _jackpot_amount + _jackpot_rate * (_now() - _jackpot_received_at)
	return minf(amount, _jackpot_ceiling) if _jackpot_ceiling > 0.0 else amount


## What a table's jackpot sign shows while the win there hasn't been shown yet, or -1 if it isn't holding.
func jackpot_held(table_id: String) -> float:
	var hold: Array = _jackpot_holds.get(table_id, [])
	if hold.is_empty() or _now() > float(hold[1]):
		return -1.0
	return float(hold[0])


## The win's been shown at that table: its sign shows the meter again.
func release_jackpot(table_id: String) -> void:
	_jackpot_holds.erase(table_id)


func _now() -> float:
	return Time.get_ticks_msec() / 1000.0


func _load_token() -> String:
	var cfg := ConfigFile.new()
	if cfg.load(SAVE_PATH) != OK:
		return ""
	return str(cfg.get_value("player", "token", ""))


func _save_token(token: String) -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("player", "token", token)
	cfg.save(SAVE_PATH)
