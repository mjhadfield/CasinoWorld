extends Node
## This device's preferences, kept in user:// (IndexedDB on the web build) and
## applied as they change. Sound goes through audio buses that send to
## "Master": "Effects" (cards, chips, results, buttons) and "Ambience" (the
## room's background murmur). The Sfx autoload puts every sound on one of
## them, so the volume sliders cover everything.
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
}
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


func value(key: String):
	return _values.get(key, DEFAULTS.get(key))


func set_value(key: String, v) -> void:
	if not DEFAULTS.has(key) or _values[key] == v:
		return
	_values[key] = v
	_apply_audio()
	_save()
	changed.emit(key, v)


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
