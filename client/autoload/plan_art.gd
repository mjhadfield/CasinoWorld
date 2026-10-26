extends Node
## The floor plan's pictures from its asset library (plan_assets.py): furniture, decor, rugs and floor textures,
## fetched from the server at runtime so new art needs no export. On connecting, and whenever the server says
## "plan_art_changed", this fetches /api/plan/art and downloads the pictures it doesn't have; `art_changed` tells
## the furniture and the rooms' floors to draw again.

signal art_changed

var _assets := {}      # id -> {"mount", "body", "by_facing", "facings": {facing: {"url", "anchor", "mirror"}}}
var _floors := {}      # id -> URL
var _floor_scales := {}   # id -> its tile's pixels per game pixel (only the floors drawn finer than 1:1)
var _downloaded := {}  # URL -> Texture2D
var _version := -1
var _loading := 0
const DECODE_MS := 8


func _ready() -> void:
	Net.connected.connect(reload)
	Net.message_received.connect(func(msg: Dictionary):
		if msg.get("type") == "plan_art_changed" and int(msg.get("version", -1)) != _version:
			reload())


## A library asset's details (mount, body, by_facing, facings), or {} if it isn't here (yet).
func asset(id: String) -> Dictionary:
	return _assets.get(id, {})


## The picture for an asset facing a way (its "down" one if it has none for that way): {texture, anchor, mirror,
## scale}, or {} until it's downloaded. The anchor is in game pixels; a scale of 2 is a picture drawn at twice that.
func picture(id: String, facing: String) -> Dictionary:
	var a: Dictionary = _assets.get(id, {})
	var f: Dictionary = a.get("facings", {}).get(facing, a.get("facings", {}).get("down", {}))
	var tex: Texture2D = _downloaded.get(str(f.get("url", "")))
	if tex == null:
		return {}
	var anchor: Array = f.get("anchor", [0, 0])
	return {"texture": tex, "anchor": Vector2(float(anchor[0]), float(anchor[1])), "mirror": bool(f.get("mirror", false)),
			"scale": maxf(1.0, float(f.get("scale", 1)))}


## A floor texture by name, or null (drawn as plain colour).
func floor_texture(id: String) -> Texture2D:
	return _downloaded.get(str(_floors.get(id, "")))


## How many of a floor texture's pixels make one game pixel (1, or 2 for the finer Vegas floors).
func floor_scale(id: String) -> float:
	return maxf(1.0, float(_floor_scales.get(id, 1)))


func reload() -> void:
	_loading += 1
	var serial := _loading
	var manifest = await SlotArt._get_json(SlotArt._base_url() + "/api/plan/art")
	if serial != _loading or not manifest is Dictionary or not manifest.get("assets") is Dictionary:
		return
	var wanted := []
	for id in manifest.assets:
		for f in manifest.assets[id].get("facings", {}).values():
			wanted.append(str(f.get("url", "")))
	for id in manifest.get("floors", {}):
		wanted.append(str(manifest.floors[id]))
	var bodies := await SlotArt._fetch_all(wanted.filter(func(u): return u != "" and not _downloaded.has(u)))
	if serial != _loading:
		return
	var started := Time.get_ticks_msec()
	for url in bodies:
		if Time.get_ticks_msec() - started > DECODE_MS:   # (a few a frame, so the game doesn't stall)
			await get_tree().process_frame
			if serial != _loading:
				return
			started = Time.get_ticks_msec()
		var img := Image.new()
		if img.load_png_from_buffer(bodies[url]) == OK:
			_downloaded[url] = ImageTexture.create_from_image(img)
	_assets = manifest.assets
	_floors = manifest.get("floors", {})
	_floor_scales = manifest.get("floor_scales", {})
	_version = int(manifest.get("version", 0))
	art_changed.emit()
