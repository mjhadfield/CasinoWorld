extends Node
## Client-side mirror of what the server says about this player: who they
## are, their balance, and the progressive jackpot. Display only -- the
## server's wallet is the source of truth.
##
## The server issues a token on first join; it's kept in user:// (IndexedDB on
## the web build), so each device or browser stays the same player.

signal joined(player: Dictionary)
signal balance_changed(pence: int)

const SAVE_PATH := "user://session.cfg"

var player := {}
var entity_id := ""
var look := "player_default"
var needs_name := false
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


func _ready() -> void:
	if OS.has_feature("web"):
		var p = JavaScriptBridge.eval("new URLSearchParams(location.search).get('preview') || ''")
		preview = str(p) if p != null else ""
	Net.message_received.connect(_on_message)
	Net.disconnected.connect(func(): on_floor = false)
	Net.resynced.connect(func(_msg): _held = false)  # the payout it waited on was dropped; a fresh wallet follows


func _on_message(msg: Dictionary) -> void:
	match msg.get("type"):
		"hello":
			if int(msg.get("protocol", -1)) != Net.PROTOCOL_VERSION:
				push_warning("Server protocol %s != client %d" % [msg.get("protocol"), Net.PROTOCOL_VERSION])
			var join := {"token": _load_token()}
			if preview != "":
				join["preview"] = preview
			Net.send("join", join)
		"welcome":
			player = msg.get("player", {})
			entity_id = str(msg.get("entity_id", ""))
			look = str(msg.get("look", look))
			needs_name = bool(msg.get("needs_name", false))
			on_floor = true
			if preview == "":
				_save_token(str(msg.get("token", "")))
			joined.emit(player)
		"wallet":
			balance = int(msg.get("balance", 0))
			if not _held:
				shown_balance = balance
				balance_changed.emit(shown_balance)
		"jackpot":
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


func choose_name(new_name: String) -> void:
	Net.send("set_name", {"name": new_name})


## The jackpot right now, in pence (fractional, so a meter can roll smoothly).
func jackpot_now() -> float:
	var amount := _jackpot_amount + _jackpot_rate * (_now() - _jackpot_received_at)
	return minf(amount, _jackpot_ceiling) if _jackpot_ceiling > 0.0 else amount


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
