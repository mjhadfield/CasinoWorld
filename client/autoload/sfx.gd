extends Node
## Game sounds. `play(key)` for the player's own interface (buttons, "your
## turn", the countdown tick); `play_at(key, position)` for things happening
## at a table, which fade with distance from the camera -- so you hear the
## table you're at (and, walking past, the nearest one), not the whole floor.
##
## Each key can have several variants, picked at random so repeats don't
## sound identical. A key also has a minimum gap between plays, so a burst
## (seven cards turning over at once) is a few sounds, not a machine gun.
## Everything plays on the Effects bus; the room loop on Ambience. Volumes
## live in Settings.
##
## Which sounds play is picked on the server's maintenance page (/maintenance):
## on connecting, and whenever the server says "sounds_changed", this fetches
## /api/sounds/manifest and downloads any files it doesn't have yet. Until
## then (or if the server can't be reached) the sounds built into the game
## play: assets/audio/, credits in CREDITS.md.

const DIR := "res://assets/audio/"
const BUILT_IN := {
	"deal": ["deal_2", "deal_3", "deal_4", "deal_5", "deal_6"],
	"flip": ["flip"],
	"shuffle": ["shuffle_1", "shuffle_2"],
	"bet": ["bet_1", "bet_2"],
	"payout": ["payout_1", "payout_4", "payout_5", "payout_6"],
	"sweep": ["sweep"],
	"result": ["result"],
	"turn": ["turn"],
	"tick": ["tick"],
	"click": ["click"],
	"room": ["room_loop"],
	"ball_spin": ["ball_spin"],
	"ball_drop": ["ball_drop"],
	"ball_rattle": ["ball_rattle"],
	"ball_hop": ["ball_hop_1", "ball_hop_2", "ball_hop_3", "ball_hop_4", "ball_hop_5"],
	"dice_out": ["dice_out_1", "dice_out_2"],
	"dice_land": ["dice_land_1", "dice_land_2", "dice_land_3"],
	"dice_bounce": ["dice_bounce_1", "dice_bounce_2", "dice_bounce_3", "dice_bounce_4"],
	# slots (placeholders from the library until Mike picks them on the admin page)
	"reel_spin": ["reel_spin"],
	"reel_stop": ["reel_stop_1", "reel_stop_2"],
	"reel_tease": ["reel_tease"],
	"win_small": ["win_small"],
	"win_bangup": ["win_bangup"],
	"big_win": ["big_win"],
	"feature_wilds": ["feature_wilds"],
	"feature_reels": ["feature_reels"],
	"feature_multiplier": ["feature_multiplier"],
	"feature_upgrade": ["feature_upgrade"],
	"instant_win": ["instant_win"],
	"bonus_trigger": ["bonus_trigger"],
	"trail_fire": ["trail_fire"],
	"trail_hop": ["trail_hop"],
	"trail_coin": ["trail_coin"],
	"trail_snake": ["trail_snake"],
	"pick_reveal": ["pick_reveal"],
	"jackpot_win": ["jackpot_win"],
}
const BUILT_IN_GAIN_DB := {"click": -6.0, "tick": -4.0, "flip": -3.0, "dice_bounce": -3.0, "reel_spin": -6.0, "reel_stop": -3.0, "win_bangup": -3.0, "trail_hop": -4.0}
const MIN_GAP := {"dice_bounce": 0.03, "ball_hop": 0.04, "deal": 0.1, "flip": 0.15, "bet": 0.06, "payout": 0.12, "sweep": 0.12, "result": 0.05, "reel_stop": 0.05, "trail_hop": 0.05, "trail_coin": 0.06, "feature_wilds": 0.08}
const HEARING := 340.0  # px from the camera at which a table sound has faded out

var _streams := {}  # key -> [AudioStream]
var _gain_db := {}  # key -> volume trim
var _last := {}     # key (+ where on the floor) -> when it last played
var _room: AudioStreamPlayer
var _downloaded := {}  # file URL -> AudioStream (kept, so switching back is instant)
var _manifest_version := -1
var _loading := 0      # bumps on every reload, so an older one that finishes late is dropped


func _ready() -> void:
	for key in BUILT_IN:
		_streams[key] = BUILT_IN[key].map(func(n): return load(DIR + n + ".ogg"))
	_gain_db = BUILT_IN_GAIN_DB.duplicate()
	Net.connected.connect(reload)
	Net.message_received.connect(func(msg: Dictionary):
		if msg.get("type") == "sounds_changed" and int(msg.get("version", -1)) != _manifest_version:
			reload())


## A sound for you alone, at full volume wherever you are.
func play(key: String) -> void:
	var stream := _pick(key)
	if stream == null:
		return
	var player := AudioStreamPlayer.new()
	player.stream = stream
	player.bus = "Effects"
	player.volume_db = _gain_db.get(key, 0.0)
	player.finished.connect(player.queue_free)
	add_child(player)
	player.play()


## A sound at a spot on the floor (global position), heard nearby only.
func play_at(key: String, at: Vector2, trim_db := 0.0) -> void:
	var scene := get_tree().current_scene
	if scene == null or not scene is Node2D:
		return
	var stream := _pick(key, str(at.snapped(Vector2(200, 200))))  # each table keeps its own gap
	if stream == null:
		return
	var player := AudioStreamPlayer2D.new()
	player.stream = stream
	player.bus = "Effects"
	player.volume_db = _gain_db.get(key, 0.0) + trim_db
	player.max_distance = HEARING
	player.attenuation = 1.6
	player.panning_strength = 0.4
	player.finished.connect(player.queue_free)
	scene.add_child(player)
	player.global_position = at
	player.play()


## The casino's background murmur, looping quietly under everything.
func start_room() -> void:
	if _room == null:
		_room = AudioStreamPlayer.new()
		_room.bus = "Ambience"
		add_child(_room)
	var options: Array = _streams.get("room", [])
	if options.is_empty():
		return
	var stream: AudioStream = options[0]
	_set_loop(stream)
	_room.volume_db = _gain_db.get("room", 0.0)
	if _room.stream != stream or not _room.playing:
		_room.stream = stream
		_room.play()


# ------------------------------------------------------------------ the server's picks
## Fetch the maintenance page's choices and swap them in as they arrive.
func reload() -> void:
	_loading += 1
	var serial := _loading
	var manifest = await _get_json(_base_url() + "/api/sounds/manifest")
	if serial != _loading or not manifest is Dictionary or not manifest.get("moments") is Dictionary:
		return
	var moments: Dictionary = manifest.moments
	for key in moments:
		var urls: Array = moments[key].get("files", [])
		var streams := []
		for url in urls:
			if not _downloaded.has(url):
				var stream := await _download_stream(_base_url() + str(url))
				if serial != _loading:
					return
				if stream != null:
					_downloaded[url] = stream
			if _downloaded.has(url):
				streams.append(_downloaded[url])
		if not streams.is_empty():  # nothing usable: keep what's there
			_streams[key] = streams
			_gain_db[key] = float(moments[key].get("gain_db", 0.0))
	_manifest_version = int(manifest.get("version", 0))
	if _room != null:
		start_room()
	print("[Sfx] sounds from the server (version %d)" % _manifest_version)


func _base_url() -> String:
	if OS.has_feature("web"):
		return str(JavaScriptBridge.eval("location.origin"))
	var ws := Net.server_url()  # ws://host:port/ws -> http://host:port
	return ws.replace("wss://", "https://").replace("ws://", "http://").trim_suffix("/ws")


func _get_json(url: String):
	var body = await _fetch(url)
	return JSON.parse_string(body.get_string_from_utf8()) if body is PackedByteArray else null


func _download_stream(url: String) -> AudioStream:
	var body = await _fetch(url)
	if not body is PackedByteArray or body.is_empty():
		return null
	match url.get_slice("?", 0).get_extension().to_lower():
		"ogg":
			return AudioStreamOggVorbis.load_from_buffer(body)
		"mp3":
			var mp3 := AudioStreamMP3.new()
			mp3.data = body
			return mp3
		"wav":
			return AudioStreamWAV.load_from_buffer(body)
	return null


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
		push_warning("Sfx: couldn't fetch %s (%s / HTTP %s)" % [url, result[0], result[1]])
		return null
	return result[3]


static func _set_loop(stream: AudioStream) -> void:
	if stream is AudioStreamOggVorbis or stream is AudioStreamMP3:
		stream.loop = true
	elif stream is AudioStreamWAV:
		stream.loop_mode = AudioStreamWAV.LOOP_FORWARD
		stream.loop_end = int(stream.get_length() * stream.mix_rate)


func _pick(key: String, scope := "") -> AudioStream:
	var options: Array = _streams.get(key, [])
	if options.is_empty():
		return null
	var now := Time.get_ticks_msec() / 1000.0
	var slot := key + scope
	if now - float(_last.get(slot, -10.0)) < MIN_GAP.get(key, 0.0):
		return null
	_last[slot] = now
	return options.pick_random()
