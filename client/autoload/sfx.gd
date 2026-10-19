extends Node
## Game sounds. `play(key)` for the player's own interface (buttons, "your
## turn", the countdown tick, the slot machine in front of you); `play_at(key,
## position, trim, table)` for things happening at a table, which fade with
## distance from the camera -- so you hear the table you're at (and, walking
## past, the nearest one), not the whole floor. `start_loop(key)` plays a
## moment round and round until `stop_loop(handle)` (the reels spinning, the
## win meter counting up).
##
## Sounds come in sets (server/casino_server/sounds.py): the whole casino, each
## table game, every slot machine, and each machine. Each table plays from its
## game's set, and a set without its own sound for a moment plays the one
## above's -- so Armadillo Goes West has its own reel stop, and its buttons
## click like everything else's. `focus` is the table you're at: `play()` and
## `start_loop()` use its set unless told another.
##
## Each moment can have several variants, picked at random so repeats don't
## sound identical, and a minimum gap between plays, so a burst (seven cards
## turning over at once) is a few sounds, not a machine gun. Everything plays
## on the Effects bus; the room loop on Ambience. Volumes live in Settings.
##
## Which sounds play is picked on the admin page's Sounds tab: on connecting, and
## whenever the server says "sounds_changed", this fetches /api/sounds/manifest
## and downloads any files it doesn't have yet. Until then (or if the server
## can't be reached) the sounds built into the game play: assets/audio/,
## credits in CREDITS.md. They cover the casino's first moments only; the rest
## wait for the server.

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
const MIN_GAP := {"dice_bounce": 0.03, "ball_hop": 0.04, "deal": 0.1, "flip": 0.15, "bet": 0.06, "payout": 0.12, "sweep": 0.12, "result": 0.05,
	"reel_stop": 0.05, "scatter_land": 0.05, "trail_hop": 0.05, "trail_coin": 0.06, "feature_wilds": 0.08, "click": 0.03}
const HEARING := 340.0  # px from the camera at which a table sound has faded out
const DOWNLOADS := 6    # files fetched at once

## The table you're at ("" walking the floor): `play()` uses its sound set.
var focus := ""

var _built_in := {}     # key -> {streams, gain_db}: until the server's sets arrive
var _sets := {}         # set -> {parent, moments: {key -> {streams, gain_db}}}
var _tables := {}       # table id -> set
var _last := {}         # key (+ where on the floor) -> when it last played
var _loops := {}        # handle -> AudioStreamPlayer
var _next_loop := 0
var _room: AudioStreamPlayer
var _room_source: AudioStream   # what it's looping a copy of
var _downloaded := {}   # file URL -> AudioStream (kept, so switching back is instant)
var _manifest_version := -1
var _loading := 0       # bumps on every reload, so an older one that finishes late is dropped


func _ready() -> void:
	for key in BUILT_IN:
		_built_in[key] = {"streams": BUILT_IN[key].map(func(n): return load(DIR + n + ".ogg")),
			"gain_db": BUILT_IN_GAIN_DB.get(key, 0.0)}
	Net.connected.connect(reload)
	Net.message_received.connect(func(msg: Dictionary):
		if msg.get("type") == "sounds_changed" and int(msg.get("version", -1)) != _manifest_version:
			reload())


## A sound for you alone, at full volume wherever you are. `pitch` raises or
## lowers it (1.0 as recorded), e.g. each reel stop a step higher.
func play(key: String, pitch := 1.0, table := "") -> void:
	var c := _choice(key, table if table != "" else focus)
	var stream := _pick(key, c)
	if stream == null:
		return
	var player := AudioStreamPlayer.new()
	player.stream = stream
	player.bus = "Effects"
	player.volume_db = c.gain_db
	player.pitch_scale = pitch
	player.finished.connect(player.queue_free)
	add_child(player)
	player.play()


## A table's sound at a spot on the floor (global position), heard nearby only.
func play_at(key: String, at: Vector2, trim_db := 0.0, table := "") -> void:
	var scene := get_tree().current_scene
	if scene == null or not scene is Node2D:
		return
	var c := _choice(key, table)
	var stream := _pick(key, c, str(at.snapped(Vector2(200, 200))))  # each table keeps its own gap
	if stream == null:
		return
	var player := AudioStreamPlayer2D.new()
	player.stream = stream
	player.bus = "Effects"
	player.volume_db = c.gain_db + trim_db
	player.max_distance = HEARING
	player.attenuation = 1.6
	player.panning_strength = 0.4
	player.finished.connect(player.queue_free)
	scene.add_child(player)
	player.global_position = at
	player.play()


## Play a moment round and round until stop_loop(handle). 0 if it has no sound.
func start_loop(key: String, table := "") -> int:
	var c := _choice(key, table if table != "" else focus)
	var streams: Array = c.get("streams", [])
	if streams.is_empty():
		return 0
	var stream: AudioStream = (streams.pick_random() as AudioStream).duplicate()  # looping a copy leaves one-shots alone
	_set_loop(stream)
	var player := AudioStreamPlayer.new()
	player.stream = stream
	player.bus = "Effects"
	player.volume_db = c.gain_db
	add_child(player)
	player.play()
	_next_loop += 1
	_loops[_next_loop] = player
	return _next_loop


## Fade a loop out (and forget it). A 0 or stopped handle is ignored.
func stop_loop(handle: int, fade := 0.15) -> void:
	var player: AudioStreamPlayer = _loops.get(handle)
	if player == null:
		return
	_loops.erase(handle)
	var tw := player.create_tween()
	tw.tween_property(player, "volume_db", player.volume_db - 40.0, fade)
	tw.tween_callback(player.queue_free)


## The casino's background murmur, looping quietly under everything.
func start_room() -> void:
	if _room == null:
		_room = AudioStreamPlayer.new()
		_room.bus = "Ambience"
		add_child(_room)
	var c := _choice("room", "")
	var streams: Array = c.get("streams", [])
	if streams.is_empty():
		return
	var source: AudioStream = streams[0]
	_room.volume_db = c.gain_db
	if _room_source != source or not _room.playing:
		var stream := source.duplicate()
		_set_loop(stream)
		_room_source = source
		_room.stream = stream
		_room.play()


## What a moment plays at a table: its set's own sound, else the nearest set above's.
func _choice(key: String, table: String) -> Dictionary:
	var s = _tables.get(table, "casino")
	for i in 8:   # the tree is three deep; this only stops a bad manifest looping forever
		if not s is String or not _sets.has(s):
			break
		var m: Dictionary = _sets[s].moments.get(key, {})
		if not m.is_empty():
			return m
		s = _sets[s].parent
	return _built_in.get(key, {})


func _pick(key: String, c: Dictionary, scope := "") -> AudioStream:
	var options: Array = c.get("streams", [])
	if options.is_empty():
		return null
	var now := Time.get_ticks_msec() / 1000.0
	var slot := key + scope
	if now - float(_last.get(slot, -10.0)) < MIN_GAP.get(key, 0.0):
		return null
	_last[slot] = now
	return options.pick_random()


# ------------------------------------------------------------------ the server's picks
## Fetch the admin page's choices and swap them in once their files are here.
func reload() -> void:
	_loading += 1
	var serial := _loading
	var manifest = await _get_json(_base_url() + "/api/sounds/manifest")
	if serial != _loading or not manifest is Dictionary or not manifest.get("sets") is Dictionary:
		return
	var wanted := {}
	for s in manifest.sets:
		for key in manifest.sets[s].get("moments", {}):
			for url in manifest.sets[s].moments[key].get("files", []):
				if not _downloaded.has(url):
					wanted[url] = true
	await _download_all(wanted.keys(), serial)
	if serial != _loading:
		return
	var sets := {}
	for s in manifest.sets:
		var moments := {}
		var info: Dictionary = manifest.sets[s]
		for key in info.get("moments", {}):
			var streams := []
			for url in info.moments[key].get("files", []):
				if _downloaded.has(url):
					streams.append(_downloaded[url])
			if not streams.is_empty():   # nothing usable: the set above (or the built-in) plays
				moments[key] = {"streams": streams, "gain_db": float(info.moments[key].get("gain_db", 0.0))}
		sets[s] = {"parent": info.get("parent"), "moments": moments}
	_sets = sets
	_tables = manifest.get("tables", {})
	_manifest_version = int(manifest.get("version", 0))
	if _room != null:
		start_room()
	print("[Sfx] sounds from the server (version %d, %d files)" % [_manifest_version, _downloaded.size()])


## Fetch several files at a time; returns when they're all in (or have failed).
func _download_all(urls: Array, serial: int) -> void:
	var queue := urls.duplicate()
	var busy := [0]
	for i in mini(DOWNLOADS, queue.size()):
		busy[0] += 1
		_download_worker(queue, busy, serial)
	while busy[0] > 0:
		await get_tree().process_frame


func _download_worker(queue: Array, busy: Array, serial: int) -> void:
	while not queue.is_empty() and serial == _loading:
		var url: String = queue.pop_back()
		var stream := await _download_stream(_base_url() + url)
		if stream != null:
			_downloaded[url] = stream
	busy[0] -= 1


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
