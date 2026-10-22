class_name SpotGlow
## The light round a betting spot that's waiting for your chips (CasinoTable._draw): it takes the spot's own
## printed shape (CasinoTable.spot_shape), with a soft halo that breathes slowly, a lit edge and a faint wash
## inside. It fades in when the spot starts to glow. Its colour is the table style's `glow`. The admin page's
## designer draws the same for its preview (tables/render.js drawGlow).

const BREATH := 2.4    # seconds for one slow breath
const FADE_IN := 0.4
const BANDS := 4       # the halo: lines stepping out from the edge, each fainter
const BAND_STEP := 0.85


## The outlines a spot's glow needs, worked out once (they never move): its edge and the halo's bands round it.
static func prepare(s: Dictionary) -> Dictionary:
	var edge := StyledFelt.shape(s, 0.0)
	var bands := []
	for i in BANDS:
		var grown := Geometry2D.offset_polygon(edge, 0.55 + i * BAND_STEP, Geometry2D.JOIN_ROUND)
		bands.append(_closed(grown[0] if not grown.is_empty() else edge))
	return {"edge": edge, "closed": _closed(edge), "bands": bands}


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


static func _closed(pts: PackedVector2Array) -> PackedVector2Array:
	var out := pts.duplicate()
	out.append(pts[0])
	return out
