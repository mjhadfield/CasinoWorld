@tool
class_name CrapsDice
extends Node2D
## The two dice on the craps table, drawn in code: translucent red casino dice
## with white pips, rising off their shadows when they're in the air.
##
## The throw is choreographed on the server (engines/craps.plan_throw): the faces
## are drawn first, then each die's path -- an arc from the shooter's hand, into
## the far wall's pyramids, back off them, a hop and a slide -- so this only plays
## the plan back, and every viewer sees the same throw land on the same faces.
## The plan already has the dice bouncing off any stacks of chips in their way.
## Before the throw the stickman pushes the dice out to the shooter; afterwards
## he hooks them back to the middle. Everything is in table coordinates.

## A die hit something: "land" (first touch down on the felt) or "bounce" (the wall and
## the hops after), with how hard (0-1) -- the table plays the sounds.
signal knock(kind: String, strength: float)

const SIZE := 6.2
# Where the dice wait: in front of the stickman, and pushed out to the shooter's hand (the
# server's HAND_Y). Both are far enough in that no one's head at the rail covers them, as
# the tallest hair would at the felt's edge (the dice are drawn over people).
const HOME := [Vector2(-4.5, -13), Vector2(4.5, -13)]
const HAND_Y := -13.0
const PIPS := {1: [Vector2(0, 0)], 2: [Vector2(-1, -1), Vector2(1, 1)], 3: [Vector2(-1, -1), Vector2(0, 0), Vector2(1, 1)],
	4: [Vector2(-1, -1), Vector2(1, -1), Vector2(-1, 1), Vector2(1, 1)],
	5: [Vector2(-1, -1), Vector2(1, -1), Vector2(0, 0), Vector2(-1, 1), Vector2(1, 1)],
	6: [Vector2(-1, -1), Vector2(1, -1), Vector2(-1, 0), Vector2(1, 0), Vector2(-1, 1), Vector2(1, 1)]}
var tone: Array = TableStyle.DICE.red   # their lit and shaded sides, from the table's style (TableStyle.DICE)

var dice := [{"p": HOME[0], "h": 0.0, "f": 5, "r": 0.2}, {"p": HOME[1], "h": 0.0, "f": 2, "r": -0.1}]
var _plan := []           # the throw being played: each die's segments
var _plan_start := 0.0    # (local seconds) when the plan's t = 0 is
var _knocks := []         # [time, kind, strength] still to sound for this throw
var _slide := {}          # a straight slide of both dice: {from: [..], to: [..], start, seconds}


func _now() -> float:
	return Time.get_ticks_msec() / 1000.0


## The stickman pushes the dice to the shooter (`out` seconds), then they're thrown. `elapsed`
## is how far into all that we already are (a snapshot taken mid-throw).
func throw(plan: Array, out: float, shooter_at: Vector2, elapsed := 0.0) -> void:
	var start := _now() - elapsed
	if elapsed < out:
		_slide_to([shooter_at + Vector2(-3, -1), shooter_at + Vector2(3, -1)], out - elapsed, start + elapsed)
	_plan = plan
	_plan_start = start + out
	_knocks = []
	for segs in plan:
		var strengths := [1.0, 1.0, 0.6, 0.35]   # (an older server's plans: landing, the wall, off the wall, the last hop)
		for i in segs.size() - 1:
			var t := float(segs[i].t1)
			var strength: float = float(segs[i].kn) if segs[i].has("kn") else (strengths[i] if i < strengths.size() else 0.0)
			if strength > 0.0 and _plan_start + t >= _now():   # (kn: the server's -- the wall, the hops, a stack of chips)
				_knocks.append([t, "land" if i == 0 else "bounce", strength])
	_knocks.sort_custom(func(a, b): return a[0] < b[0])
	set_process(true)


## Where the dice lie (after a throw, until they're fetched): [[x, y, face, turn], ...].
func rest(at: Array) -> void:
	_plan = []
	_slide = {}
	for i in mini(2, at.size()):
		dice[i] = {"p": Vector2(float(at[i][0]), float(at[i][1])), "h": 0.0, "f": int(at[i][2]), "r": float(at[i][3])}
	queue_redraw()


## The stickman hooks the dice back to the middle.
func fetch(seconds: float) -> void:
	_plan = []
	_slide_to(HOME, seconds, _now())


func home() -> void:
	_plan = []
	_slide = {}
	for i in 2:
		dice[i].p = HOME[i]
		dice[i].h = 0.0
	queue_redraw()


func is_moving() -> bool:
	return not _plan.is_empty() or not _slide.is_empty()


func _slide_to(to: Array, seconds: float, start: float) -> void:
	_slide = {"from": [dice[0].p, dice[1].p], "to": to, "start": start, "seconds": maxf(seconds, 0.01)}
	set_process(true)


func _process(_delta: float) -> void:
	if Engine.is_editor_hint():
		return
	var now := _now()
	if not _slide.is_empty():
		var u := clampf((now - float(_slide.start)) / float(_slide.seconds), 0.0, 1.0)
		var e := 2 * u * u if u < 0.5 else 1 - pow(-2 * u + 2, 2) / 2
		for i in 2:
			dice[i].p = (_slide.from[i] as Vector2).lerp(_slide.to[i], e)
			dice[i].h = 0.0
		if u >= 1.0:
			_slide = {}
	if not _plan.is_empty() and now >= _plan_start and _slide.is_empty():
		var t := now - _plan_start
		var done := true
		for i in mini(2, _plan.size()):
			dice[i] = _die_at(_plan[i], t)
			if t < float(_plan[i][-1].t1):
				done = false
		while not _knocks.is_empty() and t >= float(_knocks[0][0]):
			var k: Array = _knocks.pop_front()
			knock.emit(k[1], k[2])
		if done:
			_plan = []
	queue_redraw()
	if _plan.is_empty() and _slide.is_empty():
		set_process(false)


static func _die_at(segs: Array, t: float) -> Dictionary:
	var last: Dictionary = segs[-1]
	if t >= float(last.t1):
		return {"p": Vector2(float(last.x1), float(last.y1)), "h": 0.0, "f": int(last.f), "r": float(last.r1)}
	var s: Dictionary = segs[0]
	for seg in segs:
		if t < float(seg.t1):
			s = seg
			break
	var u := clampf((t - float(s.t0)) / maxf(float(s.t1) - float(s.t0), 0.001), 0.0, 1.0)
	var e := 1.0 - (1.0 - u) * (1.0 - u) if s.k == "slide" else u
	var h := 4.0 * float(s.h) * u * (1.0 - u) if s.k == "air" else 0.0
	return {"p": Vector2(lerpf(float(s.x0), float(s.x1), e), lerpf(float(s.y0), float(s.y1), e)), "h": h,
		"f": int(s.f), "r": lerpf(float(s.r0), float(s.r1), e)}


func _draw() -> void:
	var order := [0, 1] if dice[0].h <= dice[1].h else [1, 0]   # the higher one over the other
	for i in order:
		draw_die(self, dice[i].p, float(dice[i].h), int(dice[i].f), float(dice[i].r), SIZE, tone)


## A die at `at` (its spot on the felt), `h` up off it, showing `face`, turned `turn`, in `tone` (lit, shaded).
static func draw_die(ci: CanvasItem, at: Vector2, h: float, face: int, turn: float, size := SIZE, tone: Array = TableStyle.DICE.red) -> void:
	var s := size * (1.0 + h * 0.025)
	ci.draw_set_transform(at + Vector2(0.6, 0.9), 0, Vector2(1, 0.78))
	ci.draw_circle(Vector2.ZERO, 3.6 + h * 0.06, Color(0, 0, 0, maxf(0.12, 0.42 - h * 0.012)))
	ci.draw_set_transform(at - Vector2(0, h * 0.85), turn)
	var half := s / 2
	var r := s * 0.18
	var body := PackedVector2Array()
	for c in [[Vector2(half - r, -half + r), -PI / 2], [Vector2(half - r, half - r), 0.0],
			[Vector2(-half + r, half - r), PI / 2], [Vector2(-half + r, -half + r), PI]]:
		for k in 5:
			var a: float = c[1] + k * (PI / 2) / 4
			body.append(c[0] + Vector2(cos(a), sin(a)) * r)
	var colours := PackedColorArray()
	for p in body:
		colours.append((tone[0] as Color).lerp(tone[1], clampf((p.x + p.y) / (2 * s) + 0.5, 0, 1)))
	ci.draw_polygon(body, colours)
	body.append(body[0])
	ci.draw_polyline(body, Color(1, 1, 1, 0.35), 0.3, true)
	for pip in PIPS.get(face, PIPS[1]):
		_dot(ci, pip * s * 0.27, s * 0.085)
	ci.draw_set_transform(Vector2.ZERO)


## A pip: a small polygon (draw_circle's antialiasing blurs when scaled).
static func _dot(ci: CanvasItem, at: Vector2, radius: float) -> void:
	var pts := PackedVector2Array()
	for k in 12:
		pts.append(at + Vector2.from_angle(k * TAU / 12) * radius)
	ci.draw_colored_polygon(pts, Color.WHITE)
