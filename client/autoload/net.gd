extends Node
## WebSocket link to the Casino World server. Scenes talk to the server only
## through this autoload: call send(), and listen on message_received.
## The server is authoritative -- the client sends intents, never results.

signal connected
signal disconnected
signal message_received(msg: Dictionary)
## A `resync` reply arrived: everything before it was dropped, and fresh state follows.
signal resynced(msg: Dictionary)

const PROTOCOL_VERSION := 6
## Used when running from the editor / a desktop build. Override with CASINO_SERVER_URL.
const DESKTOP_URL := "ws://127.0.0.1:8660/ws"
const RECONNECT_DELAYS := [1.0, 2.0, 5.0, 10.0]
## A frame gap longer than this means we were suspended (no visibility event, e.g. a desktop
## build or a debugger), so whatever piled up is stale: resync rather than replay it.
const STALL_SECONDS := 3.0
## No `resync` reply by then (an older server, say): reconnect, which joins afresh.
const RESYNC_TIMEOUT_MS := 5000

var _socket := WebSocketPeer.new()
var _was_open := false
var _attempt := 0
var _retry_in := 0.0
var _away := false        # told the server we're hidden, so it has stopped sending
var _resyncing := false   # dropping buffered messages until the server's `resync` marker
var _resync_sent_ms := 0
var _last_frame_ms := 0
## Barred by the casino (`barred`): no reconnecting until this tick (-1: not until the page is reloaded).
var _barred_until_ms := 0
var _on_visibility: JavaScriptObject  # kept alive: JS holds it as the visibilitychange listener


func _ready() -> void:
	_connect_now()
	if OS.has_feature("web"):
		# A hidden tab stops Godot's loop but the socket keeps buffering, so returning would
		# replay minutes of table events. Instead the server pauses while we're hidden and
		# sends a fresh snapshot when we're back.
		_on_visibility = JavaScriptBridge.create_callback(_visibility_changed)
		JavaScriptBridge.get_interface("document").addEventListener("visibilitychange", _on_visibility)


func _visibility_changed(_args: Array) -> void:
	if JavaScriptBridge.eval("document.hidden"):
		if is_open():
			send("away")
			_away = true
	elif _away:
		_away = false
		resync()


## Drop whatever has been received and ask the server for the whole picture again.
func resync() -> void:
	if not is_open() or _resyncing:
		return
	_resyncing = true
	_resync_sent_ms = Time.get_ticks_msec()
	send("resync")


func is_open() -> bool:
	return _socket.get_ready_state() == WebSocketPeer.STATE_OPEN


func send(type: String, data: Dictionary = {}) -> void:
	if not is_open():
		push_warning("Net.send(%s) dropped: not connected" % type)
		return
	var msg := data.duplicate()
	msg["type"] = type
	_socket.send_text(JSON.stringify(msg))


func server_url() -> String:
	if OS.has_feature("web"):
		# Served by the same FastAPI app, so connect back to wherever the page came from.
		var https: bool = JavaScriptBridge.eval("location.protocol") == "https:"
		var host: String = JavaScriptBridge.eval("location.host")
		return ("wss://" if https else "ws://") + host + "/ws"
	var override := OS.get_environment("CASINO_SERVER_URL")
	return override if override != "" else DESKTOP_URL


func _connect_now() -> void:
	_away = false
	_resyncing = false
	_socket = WebSocketPeer.new()
	var url := server_url()
	if _socket.connect_to_url(url) != OK:
		push_warning("Net: could not start connection to %s" % url)


func _process(delta: float) -> void:
	var now := Time.get_ticks_msec()
	if _last_frame_ms > 0 and now - _last_frame_ms > STALL_SECONDS * 1000.0 and Session.entity_id != "":
		resync()
	_last_frame_ms = now
	if _resyncing and now - _resync_sent_ms > RESYNC_TIMEOUT_MS:
		_resyncing = false
		_socket.close()
	_socket.poll()
	match _socket.get_ready_state():
		WebSocketPeer.STATE_OPEN:
			if not _was_open:
				_was_open = true
				_attempt = 0
				print("[Net] connected to ", server_url())
				connected.emit()
			while _socket.get_available_packet_count() > 0:
				var parsed = JSON.parse_string(_socket.get_packet().get_string_from_utf8())
				if not parsed is Dictionary:
					continue
				if parsed.get("type") == "barred":   # banned, timed out or removed: the server hangs up next
					var wait = parsed.get("retry_in")
					_barred_until_ms = now + int(float(wait) * 1000.0) if wait != null else -1
				if _resyncing:
					if parsed.get("type") != "resync":
						continue  # stale: the snapshot after the marker replaces it
					_resyncing = false
					print("[Net] resynced")
					resynced.emit(parsed)
				message_received.emit(parsed)
		WebSocketPeer.STATE_CLOSED:
			if _barred_until_ms < 0 or now < _barred_until_ms:
				if _was_open:
					_was_open = false
					disconnected.emit()
				return
			if _was_open:
				_was_open = false
				print("[Net] disconnected (code %d)" % _socket.get_close_code())
				disconnected.emit()
				_retry_in = RECONNECT_DELAYS[0]
			elif _retry_in <= 0.0:
				_retry_in = RECONNECT_DELAYS[min(_attempt, RECONNECT_DELAYS.size() - 1)]
				_attempt += 1
			_retry_in -= delta
			if _retry_in <= 0.0:
				_connect_now()
