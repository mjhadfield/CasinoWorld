extends Node
## Character looks the server builds -- the NPCs and dealers designed on the
## admin page (/admin) and the players' characters, ids "x_..." -- downloaded on
## first sight and kept for the session. Looks.frames() shows the fallback until a
## look arrives, then every avatar wearing it re-applies it (look_ready).
## Also the character designer's calls: what it offers (options) and building a
## look to see it (preview).

signal look_ready(look: String)

var _textures := {}   # look -> Texture2D
var _wanted := {}     # look -> true while downloading (or after it failed)


func texture(look: String) -> Texture2D:
	return _textures.get(look)


## Fetch a look's sheet if it isn't here or on its way already.
func want(look: String) -> void:
	if _textures.has(look) or _wanted.has(look) or not look.begins_with("x_"):
		return
	_wanted[look] = true
	if not is_inside_tree():   # (asked for before the game's running: wait until it is)
		await tree_entered
	var body = await _fetch(_base_url() + "/looks/%s.png" % look)
	if body is PackedByteArray and not body.is_empty():
		var img := Image.new()
		if img.load_png_from_buffer(body) == OK:
			_textures[look] = ImageTexture.create_from_image(img)
			_wanted.erase(look)
			look_ready.emit(look)
			return
	_wanted.erase(look)   # the next sighting tries again
	push_warning("LookLoader: couldn't load %s" % look)


## What the character designer offers (the server's art catalogue: bodies, skins, slots), or {} if it couldn't be had.
func options() -> Dictionary:
	var body = await _fetch(_base_url() + "/api/look-options")
	if body is PackedByteArray:
		var data = JSON.parse_string(body.get_string_from_utf8())
		if data is Dictionary:
			return data
	return {}


## Builds a look spec into a sheet: {"id": "x_..."} (start fetching it with want), or {"error": why}.
func preview(spec: Dictionary) -> Dictionary:
	var http := HTTPRequest.new()
	add_child(http)
	var sent := http.request(_base_url() + "/api/looks/preview", ["Content-Type: application/json"], HTTPClient.METHOD_POST,
		JSON.stringify({"look": spec}))
	if sent != OK:
		http.queue_free()
		return {"error": "Couldn't reach the casino."}
	var result: Array = await http.request_completed
	http.queue_free()
	var data = JSON.parse_string((result[3] as PackedByteArray).get_string_from_utf8()) if result[0] == HTTPRequest.RESULT_SUCCESS else null
	if result[1] == 200 and data is Dictionary and data.has("id"):
		return {"id": str(data.id)}
	return {"error": str(data.get("detail", "That look couldn't be made.")) if data is Dictionary else "Couldn't reach the casino."}


func _base_url() -> String:
	if OS.has_feature("web"):
		return str(JavaScriptBridge.eval("location.origin"))
	var ws := Net.server_url()  # ws://host:port/ws -> http://host:port
	return ws.replace("wss://", "https://").replace("ws://", "http://").trim_suffix("/ws")


## The response body, or null on any failure.
func _fetch(url: String):
	var http := HTTPRequest.new()
	add_child(http)
	if http.request(url) != OK:
		http.queue_free()
		return null
	var result: Array = await http.request_completed
	http.queue_free()
	if result[0] != HTTPRequest.RESULT_SUCCESS or result[1] != 200:
		return null
	return result[3]
