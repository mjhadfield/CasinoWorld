@tool
class_name RouletteWheel
extends Node2D
## The roulette wheel, drawn in code at its centre: a wooden bowl, the ball
## track, eight brass deflectors, the rotor's 37 numbered pockets in
## single-zero order and its brass turret. The rotor never stops turning.
##
## The ball is choreographed, not simulated, and every viewer sees the same
## one. launch() sets it off round the track against the wheel from the launch
## angle the server sent (relative to the rotor), slowing evenly, so where it
## reaches the pockets is known from the start -- but not the number, which the
## server draws at "No more bets", just before it gets there. land_on() then
## follows the server's landing to the winning pocket: skids over the frets,
## slowing, then small hops (the odd one back) and a rock to rest, and then the
## ball rides round with the rotor in its pocket. The arithmetic is the server's
## (engines/roulette.py: track_travel, plan_landing, landing_seconds): keep the
## two in step. Everything's timed in "spin seconds"; a server running at
## another speed scales them (track / BALL_TRACK).

signal settled(number: int)
## A sound the ball makes as it lands: "skid" (value: how long the skid lasts) or
## "hop" (a click on a fret or into a pocket; value: how hard, 0-1).
signal ball_sound(kind: String, value: float)

const WHEEL := [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
	5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
const RED := [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
const BALL_TRACK := 7.6        # launch -> the pockets: 6.0 on the track, 1.6 down the bowl
const T_TRACK := 6.0
const ARRIVAL_SPEED := 14.0    # pockets a second against the wheel as it reaches them
const SKID_GAP := 0.04
const HOP_GAP := 0.06
const SETTLE := 0.4
const OMEGA := 0.55            # the rotor, rad/s
const LAUNCH_SPEED := 9.0      # the ball as it leaves the dealer's fingers, rad/s
const STEP := TAU / 37.0
const R_BOWL := 46.0
const R_TRACK := 38.2
const R_FRET := 27.6
const R_POCKET := 25.0
const FONT := preload("res://assets/fonts/DejaVuSans-Bold.ttf")
const BRASS := Color("c9a24a")
const BRASS_HI := Color("ecd08a")
const CREAM := Color("f1e4c4")
const RED_POCKET := Color("e0453d")
const BLACK_POCKET := Color("1a0d0b")
const GREEN_POCKET := Color("1f8a52")

var rest_pocket := 0           # where the ball sits between spins (an index into WHEEL)
var _spin := {}                # {t0, scale, b0, [number, landing, k, segs, off0, tc, delta, end]}
var _rot := 0.0
var _ball_angle := 0.0
var _ball_radius := R_POCKET
var _ball_height := 0.0


func _process(_delta: float) -> void:
	_update(_now())
	queue_redraw()


func _now() -> float:
	return Time.get_ticks_msec() / 1000.0


func is_spinning() -> bool:
	return not _spin.is_empty()


## The ball sits in `number`'s pocket (between spins, and on a fresh snapshot).
func rest_on(number: int) -> void:
	_spin = {}
	rest_pocket = WHEEL.find(number)


## The dealer launches the ball at `ball` radians round from the rotor's zero;
## `elapsed` seconds ago for a late joiner.
func launch(track := BALL_TRACK, elapsed := 0.0, ball := 0.0) -> void:
	var t0 := _now() - elapsed
	_spin = {"t0": t0, "scale": maxf(track, 0.01) / BALL_TRACK, "b0": OMEGA * t0 + ball}


## "No more bets": the number and the ball's landing ([[kind, pockets, seconds]]) are known.
func land_on(number: int, landing: Array) -> void:
	if _spin.is_empty():
		launch()
	var k := WHEEL.find(number)
	var off0 := 0.0
	for seg in landing:
		off0 += float(seg[1])
	var segs := landing_segments(landing)
	var t := _spin_time(_now())
	var arrive := _rotor_at_spin_time(BALL_TRACK) + _pocket_offset(k) + off0 * STEP
	var delta := wrapf(arrive - _track_angle(BALL_TRACK), -PI, PI)   # ~0: the server worked from the same launch
	_spin.merge({"number": number, "k": k, "segs": segs, "off0": off0, "tc": minf(t, BALL_TRACK - 0.01),
		"delta": delta, "cues": _sound_cues(segs), "cue": 0}, true)


## When the landing makes its sounds (seconds after the ball reaches the pockets):
## the skid's clatter (and how long it lasts), a click on the fret before each hop
## (harder for a bigger hop), one as it drops into its pocket, a soft one as it settles.
static func _sound_cues(segs: Array) -> Array:
	var cues := []
	var t := 0.0
	var skid := 0.0
	var skidding := true
	for seg in segs:
		if seg.type == "h":
			if skidding:
				cues.append([0.0, "skid", skid])
				skidding = false
			cues.append([t, "hop", clampf(seg.h / 4.5, 0.2, 1.0)])
		t += seg.gap + seg.d
		if skidding:
			skid = t
	if skidding:
		cues.append([0.0, "skid", skid])
	cues.append([t, "hop", 0.45])
	cues.append([t + 0.18, "hop", 0.15])
	cues.sort_custom(func(a, b): return a[0] < b[0])
	return cues


## How long a landing takes once the ball reaches the pockets (as the server works it out).
static func landing_seconds(landing: Array) -> float:
	var total := SETTLE
	for seg in landing_segments(landing):
		total += seg.gap + seg.d
	return total


## The server's landing, ready to play: each skid's starting speed and how hard it slows
## (it covers its pockets in its seconds), each hop's height.
static func landing_segments(landing: Array) -> Array:
	var v := ARRIVAL_SPEED
	var segs := []
	for i in landing.size():
		var kind: String = landing[i][0]
		var length := float(landing[i][1])
		var d := float(landing[i][2])
		if kind == "s":
			var a := 2.0 * (v * d - length) / (d * d)
			segs.append({"type": "s", "len": length, "gap": SKID_GAP if i > 0 else 0.0, "d": d, "v0": v, "a": a})
			v = (v - a * d) * 0.85
		else:
			segs.append({"type": "h", "len": length, "gap": HOP_GAP, "d": d, "h": minf(4.5, 1.0 + 0.8 * absf(length))})
	return segs


# ------------------------------------------------------------------ the choreography
func _spin_time(now: float) -> float:
	return (now - float(_spin.t0)) / float(_spin.scale)


func _rotor_at_spin_time(t: float) -> float:
	return OMEGA * (float(_spin.t0) + t * float(_spin.scale))


func _pocket_offset(k: int) -> float:
	return k * STEP - PI / 2


func _pocket_angle(k: int, rot: float) -> float:
	return rot + _pocket_offset(k)


## On the track, slowing evenly from LAUNCH_SPEED to its arrival speed (against the wheel).
func _track_angle(t: float) -> float:
	var end_speed := ARRIVAL_SPEED * STEP - OMEGA
	var decel := (LAUNCH_SPEED - end_speed) / BALL_TRACK
	return float(_spin.b0) - (LAUNCH_SPEED * t - 0.5 * decel * t * t)


func _update(now: float) -> void:
	_rot = OMEGA * now
	_ball_height = 0.0
	if _spin.is_empty():
		_ball_angle = _pocket_angle(rest_pocket, _rot)
		_ball_radius = R_POCKET
		return
	var t := _spin_time(now)
	if t < BALL_TRACK:
		var a := _track_angle(t)
		if _spin.has("delta") and t > float(_spin.tc):  # steering home, spread so the speed barely changes
			var u := (t - float(_spin.tc)) / (BALL_TRACK - float(_spin.tc))
			a += float(_spin.delta) * u * u * (3.0 - 2.0 * u)
		_ball_angle = a
		if t < T_TRACK:
			_ball_radius = R_TRACK - 0.8 * t / T_TRACK
		else:
			var w := (t - T_TRACK) / (BALL_TRACK - T_TRACK)
			_ball_radius = 37.4 - (37.4 - R_FRET) * pow(w, 1.6)   # gathering pace down the bowl
			if w > 0.3 and w < 0.55:
				_ball_height = 2.4 * sin(PI * (w - 0.3) / 0.25)  # off a deflector
		return
	if not _spin.has("segs"):  # no number yet (a late "No more bets"): keep it circling the pockets' rim
		_ball_angle = _track_angle(BALL_TRACK) - (t - BALL_TRACK) * (ARRIVAL_SPEED * STEP - OMEGA)
		_ball_radius = R_FRET
		return
	var k: int = _spin.k
	var s := t - BALL_TRACK
	var cues: Array = _spin.cues
	while int(_spin.cue) < cues.size() and float(cues[_spin.cue][0]) <= s:
		var cue: Array = cues[_spin.cue]
		_spin.cue = int(_spin.cue) + 1
		if s - float(cue[0]) < 0.3:   # (a late joiner doesn't get a burst of old ones)
			ball_sound.emit(cue[1], float(cue[2]) * (float(_spin.scale) if cue[1] == "skid" else 1.0))
	var off := float(_spin.off0)
	var r := R_POCKET
	var h := 0.0
	var settled_now := true
	for seg in _spin.segs:
		if s < seg.gap:
			r = R_FRET if seg.type == "s" else R_POCKET
			settled_now = false
			break
		s -= seg.gap
		if s < seg.d:
			settled_now = false
			if seg.type == "s":  # skimming the frets, slowing evenly: a jolt over each one, sinking as it slows
				var dist: float = seg.v0 * s - 0.5 * seg.a * s * s
				var p: float = s / seg.d
				off -= dist
				h = 0.55 * (1.0 - 0.5 * p) * absf(sin(PI * dist))
				r = R_FRET - (R_FRET - R_POCKET - 0.6) * p * p
			else:
				var p: float = s / seg.d
				off -= seg.len * p
				h = seg.h * 4.0 * p * (1.0 - p)
				r = R_POCKET + 0.35 * h
			break
		s -= seg.d
		off -= seg.len
	if settled_now:
		var q := minf(1.0, s / SETTLE)
		off = 0.14 * sin(q * PI * 3.0) * (1.0 - q)   # rocking to rest
		if q >= 1.0:
			rest_pocket = k
			var number: int = _spin.number
			_spin = {}
			settled.emit(number)
	_ball_angle = _pocket_angle(k, _rot) + off * STEP
	_ball_radius = r
	_ball_height = h


# ------------------------------------------------------------------ drawing
func _colour(n: int) -> Color:
	return GREEN_POCKET if n == 0 else RED_POCKET if n in RED else BLACK_POCKET


func _ring(r0: float, r1: float, a0: float, a1: float, colour: Color) -> void:
	var pts := PackedVector2Array()
	var steps := 4
	for i in steps + 1:
		var a := lerpf(a0, a1, float(i) / steps)
		pts.append(Vector2(cos(a), sin(a)) * r1)
	for i in steps + 1:
		var a := lerpf(a1, a0, float(i) / steps)
		pts.append(Vector2(cos(a), sin(a)) * r0)
	draw_colored_polygon(pts, colour)


func _draw() -> void:
	if Engine.is_editor_hint():
		_update(0.0)
	# the bowl and the ball track
	draw_circle(Vector2(0.8, 1.6), R_BOWL + 0.8, Color(0, 0, 0, 0.3))
	draw_circle(Vector2.ZERO, R_BOWL, Color("4e2814"))
	draw_circle(Vector2(-6, -7), R_BOWL - 8, Color(0.6, 0.32, 0.17, 0.25))
	draw_arc(Vector2.ZERO, R_BOWL, 0, TAU, 72, BRASS, 1.0, true)
	draw_circle(Vector2.ZERO, 40.0, Color("4a2a17"))
	draw_arc(Vector2.ZERO, 40.0, 0, TAU, 72, Color(1, 0.86, 0.7, 0.25), 0.5, true)
	draw_circle(Vector2.ZERO, 34.0, Color("24120a"))
	for i in 8:  # the deflectors (fixed)
		var a := i * PI / 4 + PI / 8
		var c := Vector2(cos(a), sin(a)) * 35.8
		var along := Vector2(cos(a + (PI / 2 if i % 2 else 0.0)), sin(a + (PI / 2 if i % 2 else 0.0)))
		var across := along.orthogonal()
		draw_colored_polygon(PackedVector2Array([c - along * 2.2, c - across * 0.9, c + along * 2.2, c + across * 0.9]), BRASS_HI)
	# the rotor: numbers, pockets, frets
	for k in WHEEL.size():
		var n: int = WHEEL[k]
		var a := _pocket_angle(k, _rot)
		_ring(27.0, 33.0, a - STEP / 2, a + STEP / 2, _colour(n))
		_ring(22.0, 27.0, a - STEP / 2, a + STEP / 2, Color(0, 0, 0, 0.45))
		var a0 := a - STEP / 2
		draw_line(Vector2(cos(a0), sin(a0)) * 22.0, Vector2(cos(a0), sin(a0)) * 33.0, BRASS, 0.35, true)
		var label := str(n)
		draw_set_transform(Vector2(cos(a), sin(a)) * 30.0, a + PI / 2, Vector2(1.1, 1.1))
		var w := FONT.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, 3).x
		draw_string(FONT, Vector2(-w / 2, 1.05), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 3, CREAM)
		draw_set_transform(Vector2.ZERO)
	draw_arc(Vector2.ZERO, 27.0, 0, TAU, 72, BRASS, 0.5, true)
	# the cone and turret
	draw_circle(Vector2.ZERO, 22.0, Color("6a3519"))
	draw_circle(Vector2(-4, -5), 14.0, Color(0.75, 0.45, 0.22, 0.35))
	draw_arc(Vector2.ZERO, 22.0, 0, TAU, 64, BRASS, 0.6, true)
	for i in 4:
		var a := _rot + i * PI / 2
		var tip := Vector2(cos(a), sin(a)) * 11.0
		draw_line(Vector2.ZERO, tip, BRASS_HI, 1.4, true)
		draw_circle(tip, 1.5, BRASS_HI)
	draw_circle(Vector2.ZERO, 3.2, BRASS_HI)
	# the ball: in the air it rises off its shadow (towards the viewer) and looks a touch bigger
	var ground := Vector2(cos(_ball_angle), sin(_ball_angle)) * _ball_radius
	var br := 1.9 * (1.0 + _ball_height * 0.06)
	draw_set_transform(ground + Vector2(0.5, 0.6), 0, Vector2(1.0 + _ball_height * 0.06, 0.85 + _ball_height * 0.04))
	draw_circle(Vector2.ZERO, 1.9, Color(0, 0, 0, 0.38 - _ball_height * 0.05))
	draw_set_transform(Vector2.ZERO)
	var ball := ground - Vector2(0, _ball_height * 0.85)
	draw_circle(ball, br, Color("d9d3c7"))
	draw_circle(ball - Vector2(0.35, 0.35) * br, br * 0.62, Color("f4f1ea"))
	draw_circle(ball - Vector2(0.55, 0.55) * br, br * 0.25, Color.WHITE)
