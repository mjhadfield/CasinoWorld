extends Node
## The slot machines' pictures: the signed-off vector set built into the game
## (assets/slots/<variant>/<id>.png, from tools/build_slot_art.py), with anything
## picked on the admin page's Slots > Art tab swapped in over it. On connecting, and
## whenever the server says "slot_art_changed", this fetches /api/slots/art/manifest
## and downloads the pictures it names; `art_changed` tells cabinets and the screen
## to redraw. A slot built with the Slot design wizard has no built-in set: the manifest
## names every picture it draws, and its display and interface fonts (font()).

signal art_changed

const DIR := "res://assets/slots/%s/%s.png"
const UI_FALLBACK := preload("res://assets/fonts/BarlowCondensed-Bold.ttf")
const ARMADILLO := ["W", "H1", "H2", "M1", "M2", "M3", "M4", "L1", "L2", "L3", "L4", "BS", "FS", "barrel",
	"armadillo", "cylinder", "t_coin", "t_double", "t_forward", "t_heart", "t_lightning", "t_crate",
	"t_upgrade", "t_gold", "t_snake", "logo"]

var _built_in := {}    # "variant/id" -> Texture2D
var _picked := {}      # "variant/id" -> Texture2D (the admin page's choice)
var _downloaded := {}  # URL -> Texture2D (or a FontFile, for a built slot's fonts)
var _fonts := {}       # "variant/role" -> FontFile: a built slot's display and interface fonts
var _version := -1
var _loading := 0


func _ready() -> void:
	for id in ARMADILLO:
		var path := DIR % ["armadillo", id]
		if ResourceLoader.exists(path):
			_built_in["armadillo/" + id] = load(path)
	Net.connected.connect(reload)
	Net.message_received.connect(func(msg: Dictionary):
		if msg.get("type") == "slot_art_changed" and int(msg.get("version", -1)) != _version:
			reload())


## A built slot's font ("display" or "ui"), or null: the screen then uses Armadillo's.
func font(variant: String, role: String) -> Font:
	return _fonts.get(variant + "/" + role)


## A slot picture (or null if it has none).
func tex(variant: String, id: String) -> Texture2D:
	var key := variant + "/" + id
	return _picked.get(key, _built_in.get(key))


func reload() -> void:
	_loading += 1
	var serial := _loading
	var manifest = await _get_json(_base_url() + "/api/slots/art/manifest")
	if serial != _loading or not manifest is Dictionary or not manifest.get("variants") is Dictionary:
		return
	var font_urls: Dictionary = manifest.get("fonts", {}) if manifest.get("fonts") is Dictionary else {}
	# Everything not already here, downloaded at once (a built slot brings two dozen pictures and its fonts).
	var wanted := []
	for variant in manifest.variants:
		for id in manifest.variants[variant]:
			wanted.append(str(manifest.variants[variant][id]))
	for variant in font_urls:
		for role in font_urls[variant]:
			wanted.append(str(font_urls[variant][role]))
	var bodies := await _fetch_all(wanted.filter(func(u): return not _downloaded.has(u)))
	if serial != _loading:
		return
	for url in bodies:
		var body: PackedByteArray = bodies[url]
		if url.contains("/fonts/"):
			var f := FontFile.new()
			f.data = body
			f.fallbacks = [UI_FALLBACK]   # a glyph the slot's font lacks (StarTrek Film has no £) comes from the house font
			_downloaded[url] = f
		else:
			var img := Image.new()
			if img.load_png_from_buffer(body) == OK:
				img.generate_mipmaps()
				_downloaded[url] = ImageTexture.create_from_image(img)
	var picked := {}
	for variant in manifest.variants:
		for id in manifest.variants[variant]:
			var url := str(manifest.variants[variant][id])
			if _downloaded.has(url):
				picked[variant + "/" + id] = _downloaded[url]
	var fonts := {}
	for variant in font_urls:
		for role in font_urls[variant]:
			var url := str(font_urls[variant][role])
			if _downloaded.has(url):
				fonts[variant + "/" + role] = _downloaded[url]
	_picked = picked
	_fonts = fonts
	_version = int(manifest.get("version", 0))
	art_changed.emit()


## Downloads every URL at once; url -> body for those that came back. (Each request records its own result as it
## completes, so none is missed by waiting on them in turn.)
func _fetch_all(urls: Array) -> Dictionary:
	var out := {}
	var left := [urls.size()]
	for url in urls:
		var http := HTTPRequest.new()
		add_child(http)
		http.request_completed.connect(func(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray):
			if result == HTTPRequest.RESULT_SUCCESS and code == 200 and body.size() > 0:
				out[url] = body
			left[0] -= 1
			http.queue_free())
		if http.request(_base_url() + url) != OK:
			left[0] -= 1
			http.queue_free()
	while left[0] > 0:
		await get_tree().process_frame
	return out


func _base_url() -> String:
	if OS.has_feature("web"):
		return str(JavaScriptBridge.eval("location.origin"))
	var ws := Net.server_url()
	return ws.replace("wss://", "https://").replace("ws://", "http://").trim_suffix("/ws")


func _get_json(url: String):
	var body = await _fetch(url)
	return JSON.parse_string(body.get_string_from_utf8()) if body is PackedByteArray else null


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
