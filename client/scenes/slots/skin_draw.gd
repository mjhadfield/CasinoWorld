class_name SkinDraw
## The shapes a slot's skin (the Slot design wizard's Scene step) is drawn from, as polygons any CanvasItem can draw:
## LCARS elbows, pills and bars, frosted glass, and the ticking number readouts. The wizard's mockup draws the same
## shapes on its canvas (admin_web/design/mockup/game.js, "the skin's shapes"); docs/slots/scenes.md describes skins.

const ARC_STEPS := 10


## Points round an arc about c, from angle a0 to a1 (radians).
static func _arc(out: PackedVector2Array, c: Vector2, r: float, a0: float, a1: float) -> void:
	for i in ARC_STEPS + 1:
		var a := lerpf(a0, a1, float(i) / ARC_STEPS)
		out.append(c + Vector2(cos(a), sin(a)) * r)


## A bar with round ends: "both", "left", "right" or "none" (a half circle each, or as round as a short bar allows).
static func pill(r: Rect2, round := "both") -> PackedVector2Array:
	var L := round == "both" or round == "left"
	var R := round == "both" or round == "right"
	var rad := minf(r.size.y / 2.0, r.size.x / 2.0 if L and R else r.size.x)
	var x := r.position.x
	var y := r.position.y
	var w := r.size.x
	var h := r.size.y
	var p := PackedVector2Array()
	if R:
		_arc(p, Vector2(x + w - rad, y + rad), rad, -PI / 2.0, 0.0)
		_arc(p, Vector2(x + w - rad, y + h - rad), rad, 0.0, PI / 2.0)
	else:
		p.append(Vector2(x + w, y))
		p.append(Vector2(x + w, y + h))
	if L:
		_arc(p, Vector2(x + rad, y + h - rad), rad, PI / 2.0, PI)
		_arc(p, Vector2(x + rad, y + rad), rad, PI, PI * 1.5)
	else:
		p.append(Vector2(x, y + h))
		p.append(Vector2(x, y))
	return p


## A rounded rectangle.
static func rounded(r: Rect2, rad: float) -> PackedVector2Array:
	rad = minf(rad, minf(r.size.x, r.size.y) / 2.0)
	var p := PackedVector2Array()
	_arc(p, Vector2(r.end.x - rad, r.position.y + rad), rad, -PI / 2.0, 0.0)
	_arc(p, Vector2(r.end.x - rad, r.end.y - rad), rad, 0.0, PI / 2.0)
	_arc(p, Vector2(r.position.x + rad, r.end.y - rad), rad, PI / 2.0, PI)
	_arc(p, Vector2(r.position.x + rad, r.position.y + rad), rad, PI, PI * 1.5)
	return p


## An LCARS elbow in the box r: a vertical arm (`arm` wide) turning into a bar (`bar` high) through a rounded outer
## corner `rad`, the turn at `corner` ("tl", "tr", "bl" or "br").
static func elbow(r: Rect2, corner: String, arm: float, bar: float, rad: float) -> PackedVector2Array:
	var w := r.size.x
	var h := r.size.y
	rad = minf(rad, minf(w, h))
	var ri := maxf(2.0, minf(rad * 0.45, minf(w - arm, h - bar)))
	var p := PackedVector2Array([Vector2(w, 0), Vector2(rad, 0)])   # the top-left shape...
	_arc(p, Vector2(rad, rad), rad, -PI / 2.0, -PI)
	p.append(Vector2(0, h))
	p.append(Vector2(arm, h))
	_arc(p, Vector2(arm + ri, bar + ri), ri, PI, PI * 1.5)
	p.append(Vector2(w, bar))
	var fx := corner.ends_with("r")
	var fy := corner.begins_with("b")
	for i in p.size():   # ...turned to its corner
		p[i] = Vector2(r.position.x + (w - p[i].x if fx else p[i].x), r.position.y + (h - p[i].y if fy else p[i].y))
	return p


static func fill(ci: CanvasItem, pts: PackedVector2Array, col: Color) -> void:
	if pts.size() >= 3:
		ci.draw_colored_polygon(pts, col)


static func outline(ci: CanvasItem, pts: PackedVector2Array, col: Color, width: float) -> void:
	if width <= 0.0 or pts.size() < 2:
		return
	var closed := pts.duplicate()
	closed.append(pts[0])
	ci.draw_polyline(closed, col, width, true)


## Frosted glass in a shape: the blurred background behind it (bg_glass, the build's), the tint at `opacity`, a sheen
## fading down from its top, and an edge.
static func glass(ci: CanvasItem, pts: PackedVector2Array, blurred: Texture2D, tint: Color, opacity: float, sheen: float,
		edge: Color, edge_w: float, screen := Vector2(1280, 720)) -> void:
	if pts.size() < 3:
		return
	if blurred:
		var uvs := PackedVector2Array()
		for q in pts:
			uvs.append(q / screen)
		ci.draw_colored_polygon(pts, Color.WHITE, uvs, blurred)
	ci.draw_colored_polygon(pts, Color(tint, opacity))
	if sheen > 0.0:
		var top := INF
		for q in pts:
			top = minf(top, q.y)
		var cols := PackedColorArray()
		for q in pts:
			cols.append(Color(1, 1, 1, sheen * clampf(1.0 - (q.y - top) / 80.0, 0.0, 1.0)))
		ci.draw_polygon(pts, cols)
	outline(ci, pts, edge, edge_w)


## A readout cell's number: the same until its tick comes round (the mockup's readoutValue matches).
static func readout_value(seed: int, i: int, epoch: int, digits: int) -> String:
	var M := 0xFFFFFFFF
	var h := (((seed + 1) * 73856093) & M) ^ (((i + 1) * 19349663) & M) ^ (((epoch + 1) * 83492791) & M)
	h = ((h ^ (h >> 15)) * 2246822519) & M
	h = ((h ^ (h >> 13)) * 3266489917) & M
	h = (h ^ (h >> 16)) & M
	return str(h % int(pow(10, digits))).pad_zeros(digits)


## The {stardate}, {date}, {time} and {name} tokens in a decor text.
static func tokens(s: String, name: String) -> String:
	var d := Time.get_datetime_dict_from_system()
	var year := int(d.year)
	var y0 := Time.get_unix_time_from_datetime_dict({"year": year, "month": 1, "day": 1})
	var y1 := Time.get_unix_time_from_datetime_dict({"year": year + 1, "month": 1, "day": 1})
	var now := Time.get_unix_time_from_datetime_dict(d)
	var stardate: float = (year - 1976) * 1000.0 + (now - y0) / float(y1 - y0) * 1000.0
	const DAYS := ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"]
	const MONTHS := ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
	return s.replace("{name}", name.to_upper()).replace("{stardate}", "%.1f" % stardate) \
		.replace("{date}", "%s %d %s" % [DAYS[int(d.weekday)], int(d.day), MONTHS[int(d.month) - 1]]) \
		.replace("{time}", "%02d:%02d" % [d.hour, d.minute])
