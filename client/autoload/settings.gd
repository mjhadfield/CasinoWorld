extends Node
## This device's preferences, kept in user:// (IndexedDB on the web build) and
## applied as they change. Sound goes through audio buses that send to
## "Master": "Effects" (cards, chips, results, buttons) and "Ambience" (the
## room's background murmur). The Sfx autoload puts every sound on one of
## them, so the volume sliders cover everything.
##
## Graphics come as presets (High, Balanced, Low) over four settings; changing one of
## those by hand makes it "custom". A new device starts on High and steps itself down
## once if the floor runs slowly there (PerfOverlay's check; docs/performance.md).
##
## Other scripts read a setting with Settings.value(key) and hear about changes
## through `changed`.

signal changed(key: String, value)

const SAVE_PATH := "user://settings.cfg"
const DEFAULTS := {
	"master_volume": 0.8,   # 0..1
	"effects_volume": 1.0,  # 0..1
	"ambience_volume": 0.12,  # 0..1: very quiet unless you turn it up
	"muted": false,
	"show_fps": false,  # the frame-rate corner (PerfOverlay; F3)
	"graphics": "high",     # a PRESETS name, or "custom"
	"graphics_auto": true,  # may step itself down (until you choose)
	"fps_cap": 60,          # 30, 60 or 0 (no cap)
	"resolution": "sharp",  # "sharp": the screen's own pixels; "fast": drawn at 720p and scaled up
	"seat_glow": true,      # free chairs breathe while you walk (else they glow steadily)
	"slot_effects": "full", # "reduced": half the coins, no screen shake
	"show_minimap": true,       # the minimap, top right (off: nothing there at all)
	"minimap_collapsed": true,  # folded to its map button until opened
	"minimap_size": "small",    # small, medium or large
	"minimap_labels": "all",    # "all": the rooms next door name their tables too; "here": only yours
	"minimap_zoom": 2,          # its +/- step, from its smallest view (Minimap.ZOOMS)
	"hcf_four_colour": true,    # High Card Flush's cards in four suit colours, over the table style's
}
const PRESETS := {
	"high": {"fps_cap": 60, "resolution": "sharp", "seat_glow": true, "slot_effects": "full"},
	"balanced": {"fps_cap": 60, "resolution": "sharp", "seat_glow": false, "slot_effects": "reduced"},
	"low": {"fps_cap": 30, "resolution": "fast", "seat_glow": false, "slot_effects": "reduced"},
}
## On the web, Engine.max_fps waits out the rest of each frame inside it (the CPU spins), so
## the cap there skips the browser's frames instead: a frame runs once it's due, the next one
## due 1/cap seconds after. (On a 144Hz screen a 60 cap comes out at about 58.)
const WEB_CAP := """(() => {
  if (!window.__fpsCapShim) {
    window.__fpsCapShim = true;
    const raf = window.requestAnimationFrame.bind(window);
    let due = 0;
    window.requestAnimationFrame = (cb) => raf(function tick(t) {
      const cap = window.__fpsCap || 0;
      if (cap > 0 && t < due - 1) { window.__rafSkipped = true; raf(tick); return; }
      due = (cap > 0 && t - due < 100) ? due + 1000 / cap : t + (cap > 0 ? 1000 / cap : 0);
      cb(t);
    });
  }
  window.__fpsCap = %d;
})()"""
const BUSES := {"master_volume": "Master", "effects_volume": "Effects", "ambience_volume": "Ambience"}

var _values := DEFAULTS.duplicate()


func _ready() -> void:
	# The Effects and Ambience buses come from res://default_bus_layout.tres. Don't add
	# buses in code: on the web build, AudioServer.add_bus() rewires Master's output into
	# the new bus instead of the speakers, and every sound goes silent.
	var file := ConfigFile.new()
	if file.load(SAVE_PATH) == OK:
		for key in DEFAULTS:
			var v = file.get_value("settings", key, DEFAULTS[key])
			if typeof(v) == typeof(DEFAULTS[key]) or (typeof(DEFAULTS[key]) == TYPE_FLOAT and typeof(v) == TYPE_INT):
				_values[key] = v
	_apply_audio()
	_apply_graphics()


func value(key: String):
	return _values.get(key, DEFAULTS.get(key))


func set_value(key: String, v) -> void:
	if not DEFAULTS.has(key) or _values[key] == v:
		return
	_values[key] = v
	_apply_audio()
	_apply_graphics()
	_save()
	changed.emit(key, v)


## A graphics preset's settings, all at once.
func use_preset(name: String) -> void:
	for key in PRESETS[name]:
		set_value(key, PRESETS[name][key])
	set_value("graphics", name)


## Change one graphics setting by hand: the preset becomes whichever matches, else "custom",
## and it won't step itself down any more.
func set_graphics(key: String, v) -> void:
	set_value(key, v)
	set_value("graphics_auto", false)
	var now := "custom"
	for name in PRESETS:
		if PRESETS[name].keys().all(func(k): return _values[k] == PRESETS[name][k]):
			now = name
	set_value("graphics", now)


func _apply_graphics() -> void:
	if OS.has_feature("web"):
		JavaScriptBridge.eval(WEB_CAP % int(_values.fps_cap), true)
	else:
		Engine.max_fps = int(_values.fps_cap)
	get_tree().root.content_scale_mode = Window.CONTENT_SCALE_MODE_VIEWPORT if _values.resolution == "fast" \
		else Window.CONTENT_SCALE_MODE_CANVAS_ITEMS


func _apply_audio() -> void:
	for key in BUSES:
		var bus := AudioServer.get_bus_index(BUSES[key])
		var volume: float = clampf(float(_values[key]), 0.0, 1.0)
		AudioServer.set_bus_volume_db(bus, linear_to_db(volume) if volume > 0.0 else -80.0)
		AudioServer.set_bus_mute(bus, volume <= 0.0)
	AudioServer.set_bus_mute(AudioServer.get_bus_index("Master"), _values.muted or float(_values.master_volume) <= 0.0)


func _save() -> void:
	var file := ConfigFile.new()
	for key in _values:
		file.set_value("settings", key, _values[key])
	file.save(SAVE_PATH)
