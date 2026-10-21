class_name PerfOverlay
extends Label
## The frame rate and what each frame costs, in the bottom left corner: for "it feels slow"
## on a particular device. Settings' "Show frame rate" (or F3) turns it on. Updated twice a
## second. On the web it also leaves the same numbers in `window.__godotPerf`, for
## tools/shot.py's frames: step (docs/performance.md).
##
## It also gives a new device's graphics a first look: once per session, while Settings'
## graphics_auto is on, it times ten seconds of frames on the floor and steps High down to
## Balanced under 45 a second (Balanced to Low under 30), with a toast saying so.

const EVERY := 0.5
const CHECK_AFTER := 3.0   # (the floor settling: art arriving, the first redraws)
const CHECK_FOR := 10.0

var _wait := 0.0
var _check := -1.0         # seconds into the check (-1: not running)
var _checked := false
var _frames := 0


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	offset_left = 10
	offset_top = -78
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_theme_font_size_override("font_size", 13)
	add_theme_color_override("font_color", Color("f1e4c4"))
	add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	add_theme_constant_override("outline_size", 4)
	visible = bool(Settings.value("show_fps"))
	Settings.changed.connect(func(key: String, v):
		if key == "show_fps":
			visible = bool(v))
	Session.joined.connect(func(_p):
		if not _checked and Settings.value("graphics_auto") and Settings.value("graphics") in ["high", "balanced"]:
			_checked = true
			_check = 0.0)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_F3:
		Settings.set_value("show_fps", not bool(Settings.value("show_fps")))
		get_viewport().set_input_as_handled()


func _process(delta: float) -> void:
	if _check >= 0.0:
		_time_frames(delta)
	_wait -= delta
	if _wait > 0.0:
		return
	_wait = EVERY
	var p := {
		"fps": Performance.get_monitor(Performance.TIME_FPS),
		"process_ms": Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0,
		"draw_calls": Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
		"objects": Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME),
		"nodes": Performance.get_monitor(Performance.OBJECT_NODE_COUNT),
		"video_mb": Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / 1048576.0,
		"cap": int(Settings.value("fps_cap")),
		"graphics": Settings.value("graphics"),
	}
	if visible:
		text = "%d fps%s · %.1f ms a frame\n%d draw calls · %d nodes · %d MB textures" % [p.fps,
			" (cap %d)" % p.cap if p.cap > 0 else "", p.process_ms, p.draw_calls, p.nodes, p.video_mb]
	if OS.has_feature("web"):
		JavaScriptBridge.eval("window.__godotPerf = %s" % JSON.stringify(p), true)


func _time_frames(delta: float) -> void:
	if delta > 0.25:   # a hidden tab, or a long load: start again
		_check = 0.0
		_frames = 0
		return
	_check += delta
	if _check < CHECK_AFTER:
		return
	_frames += 1
	if _check < CHECK_AFTER + CHECK_FOR:
		return
	_check = -1.0
	var fps := _frames / CHECK_FOR
	var now: String = Settings.value("graphics")
	var step := "balanced" if now == "high" and fps < 45.0 else ("low" if now == "balanced" and fps < 30.0 else "")
	if step == "" or not Settings.value("graphics_auto"):
		return
	Settings.use_preset(step)
	if get_parent().has_method("show_toast"):
		get_parent().show_toast("Graphics set to %s for smoother play: change it in Settings" % step.capitalize(), 5.0)
