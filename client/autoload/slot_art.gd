extends Node
## The slot machines' pictures: the signed-off vector set built into the game
## (assets/slots/<variant>/<id>.png, from tools/build_slot_art.py), with anything
## picked on the admin page's Slots > Art tab swapped in over it. On connecting, and
## whenever the server says "slot_art_changed", this fetches /api/slots/art/manifest
## and downloads the pictures it names; `art_changed` tells cabinets and the screen
## to redraw.

signal art_changed

const DIR := "res://assets/slots/%s/%s.png"
const ARMADILLO := ["W", "H1", "H2", "M1", "M2", "M3", "M4", "L1", "L2", "L3", "L4", "BS", "FS", "barrel",
	"armadillo", "cylinder", "t_coin", "t_double", "t_forward", "t_heart", "t_lightning", "t_crate",
	"t_upgrade", "t_gold", "t_snake", "logo"]

var _built_in := {}    # "variant/id" -> Texture2D
var _picked := {}      # "variant/id" -> Texture2D (the admin page's choice)
var _downloaded := {}  # URL -> Texture2D
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
	var picked := {}
	for variant in manifest.variants:
		var assets: Dictionary = manifest.variants[variant]
		for id in assets:
			var url := str(assets[id])
			if not _downloaded.has(url):
				var body = await _fetch(_base_url() + url)
				if serial != _loading:
					return
				var img := Image.new()
				if body is PackedByteArray and img.load_png_from_buffer(body) == OK:
					img.generate_mipmaps()
					_downloaded[url] = ImageTexture.create_from_image(img)
			if _downloaded.has(url):
				picked[variant + "/" + id] = _downloaded[url]
	_picked = picked
	_version = int(manifest.get("version", 0))
	art_changed.emit()


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
