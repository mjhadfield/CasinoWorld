class_name Looks
## Character looks -> SpriteFrames, from sheets in the art module's layout (64x64
## frames; rows: walk x4, idle x4, sit x4, in up/left/down/right order): the
## built-in looks (tools/build_art.py) or ones the server builds for the admin
## page's NPCs ("x_...", fetched by LookLoader). Cached, so every avatar with
## the same look shares one SpriteFrames.

const FRAME := 64
const DIRS := ["up", "left", "down", "right"]
const FALLBACK := "player_default"

static var _cache := {}


static func frames(look: String) -> SpriteFrames:
	if _cache.has(look):
		return _cache[look]
	var path := "res://assets/sprites/characters/%s.png" % look
	var sheet: Texture2D = null
	if ResourceLoader.exists(path):
		sheet = load(path)
	elif look.begins_with("x_"):  # designed on the admin page: the server builds it
		var loader := _loader()
		if loader:
			sheet = loader.texture(look)
			if sheet == null:
				loader.want(look)
				return frames(FALLBACK)  # for now (avatars re-apply on look_ready)
	if sheet == null:
		push_warning("Unknown look '%s', using %s" % [look, FALLBACK])
		return frames(FALLBACK)
	var sf := SpriteFrames.new()
	sf.remove_animation("default")
	for d in DIRS.size():
		_add(sf, "walk_" + DIRS[d], sheet, d, range(1, 9), 10.0, true)   # frame 0 is the standing pose
		_add(sf, "idle_" + DIRS[d], sheet, 4 + d, range(0, 2), 1.5, true)
		_add(sf, "sit_" + DIRS[d], sheet, 8 + d, [0], 1.0, false)
	_cache[look] = sf
	return sf


static func _add(sf: SpriteFrames, anim: String, sheet: Texture2D, row: int, cols, fps: float, loop: bool) -> void:
	sf.add_animation(anim)
	sf.set_animation_speed(anim, fps)
	sf.set_animation_loop(anim, loop)
	for col in cols:
		var atlas := AtlasTexture.new()
		atlas.atlas = sheet
		atlas.region = Rect2(col * FRAME, row * FRAME, FRAME, FRAME)
		sf.add_frame(anim, atlas)


## The LookLoader autoload (looked up, not named, so the editor's tool scripts don't need it).
static func _loader() -> Node:
	var tree := Engine.get_main_loop() as SceneTree
	return tree.root.get_node_or_null("LookLoader") if tree else null


## The facing ("up"/"down"/"left"/"right") for a movement vector.
static func dir_from(v: Vector2, current := "down") -> String:
	if v.length() < 0.01:
		return current
	if absf(v.x) > absf(v.y):
		return "right" if v.x > 0 else "left"
	return "down" if v.y > 0 else "up"
