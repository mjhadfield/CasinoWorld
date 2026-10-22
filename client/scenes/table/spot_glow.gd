class_name SpotGlow
## The light round a betting spot that's waiting for your chips (CasinoTable._draw): it takes the spot's own
## printed shape (CasinoTable.spot_shape), with a soft halo that breathes slowly, a lit edge and a faint wash
## inside, and a glint running round the edge. It fades in when the spot starts to glow. Its colour is the table
## style's `glow`. The admin page's designer draws the same for its preview (tables/render.js spotGlow).

const LAP := 2.8       # seconds for the glint to go once round
const BREATH := 2.4    # seconds for one slow breath
const FADE_IN := 0.4
const BANDS := 4       # the halo: lines stepping out from the edge, each fainter
const BAND_STEP := 0.85
const TAIL := 0.3      # how much of the edge the glint's tail covers


## The outlines a spot's glow needs, worked out once (they never move): the edge, starting at its top so every
## glint sets off from the same place, the halo's bands round it, and how far round the edge each point is.
static func prepare(s: Dictionary) -> Dictionary:
	var edge := StyledFelt.shape(s, 0.0)
	var top := 0
	for i in edge.size():
		if edge[i].y < edge[top].y - 0.01:
			top = i
	edge = edge.slice(top) + edge.slice(0, top)
	var bands := []
	for i in BANDS:
		var grown := Geometry2D.offset_polygon(edge, 0.55 + i * BAND_STEP, Geometry2D.JOIN_ROUND)
		bands.append(_closed(grown[0] if not grown.is_empty() else edge))
	var along := PackedFloat32Array([0.0])
	for i in edge.size():
		along.append(along[i] + edge[i].distance_to(edge[(i + 1) % edge.size()]))
	return {"edge": edge, "closed": _closed(edge), "bands": bands, "along": along}


## Draws a prepared glow on `ci` (in its coordinates) at time `now`, glowing since `since`.
static func draw(ci: CanvasItem, g: Dictionary, colour: Color, now: float, since: float) -> void:
	var fade := clampf((now - since) / FADE_IN, 0.0, 1.0)
	fade = fade * fade * (3.0 - 2.0 * fade)
	var breath := 0.5 + 0.5 * sin(now * TAU / BREATH)
	var k := fade * (0.72 + 0.28 * breath)
	var bright := colour.lerp(Color.WHITE, 0.45)
	# The halo, brighter as it breathes in.
	var bands: Array = g.bands
	for i in bands.size():
		var a := 0.34 * k * pow(1.0 - float(i) / bands.size(), 1.6) * (0.85 + 0.3 * breath)
		ci.draw_polyline(bands[i], Color(colour, a), BAND_STEP + 0.25, true)
	ci.draw_colored_polygon(g.edge, Color(colour, 0.08 * k))
	ci.draw_polyline(g.closed, Color(bright, 0.7 * k), 0.5, true)
	_glint(ci, g, bright, fmod(now / LAP, 1.0), fade)


## The glint: a bright head running clockwise round the edge with a fading tail behind it.
static func _glint(ci: CanvasItem, g: Dictionary, colour: Color, at: float, alpha: float) -> void:
	var edge: PackedVector2Array = g.edge
	var along: PackedFloat32Array = g.along
	var total := along[along.size() - 1]
	var head := at * total
	var tail := TAIL * total
	var pts := PackedVector2Array()
	var cols := PackedColorArray()
	var steps := 18
	for j in steps + 1:
		var d := fposmod(head - tail + tail * j / steps, total)
		pts.append(_point_at(edge, along, d))
		var f := float(j) / steps
		cols.append(Color(colour, alpha * f * f))
	ci.draw_polyline_colors(pts, cols, 0.9, true)
	var tip := pts[pts.size() - 1]
	ci.draw_circle(tip, 1.9, Color(colour, 0.22 * alpha))
	ci.draw_circle(tip, 0.75, Color(Color.WHITE, 0.9 * alpha))


static func _point_at(edge: PackedVector2Array, along: PackedFloat32Array, d: float) -> Vector2:
	var i := along.bsearch(d, true) - 1
	i = clampi(i, 0, edge.size() - 1)
	var span := along[i + 1] - along[i]
	var t := (d - along[i]) / span if span > 0.0 else 0.0
	return edge[i].lerp(edge[(i + 1) % edge.size()], t)


static func _closed(pts: PackedVector2Array) -> PackedVector2Array:
	var out := pts.duplicate()
	out.append(pts[0])
	return out
