class_name RouteLine
extends Node2D
## Find's way to a table, drawn on the floor like a runner laid for you: a soft glow between two brass rails, with
## chevrons flowing along it towards where you'd stand, and a beacon there (a brass diamond, like the carpet's, with
## rings rippling out). Over the carpet and under everyone, in World's frame, so it turns with the floor.
##
## It's built once per path (a ribbon mesh whose UV.x is the distance along it) and animated by its shaders, so it
## never redraws while it plays (docs/performance.md). As you walk it, trim_to() fades out the part behind you
## with a shader parameter, not a rebuild.

const HALF_WIDTH := 11.0   # the ribbon's half-width, glow included
const BEACON := 30.0       # the beacon's half-size

const RIBBON_SHADER := """
shader_type canvas_item;
render_mode unshaded;

uniform vec4 brass : source_color = vec4(0.925, 0.827, 0.588, 1.0);
uniform vec4 deep : source_color = vec4(0.70, 0.53, 0.24, 1.0);
uniform float total = 1.0;    // the path's length, px
uniform float start = 0.0;    // how far along you are: it fades out behind you
uniform float half_w = 11.0;

void fragment() {
	float s = UV.x;                 // px along the path
	float y = abs(UV.y) * half_w;   // px out from its middle
	float aa = max(fwidth(y), 0.6);
	// a soft glow under it all, and a darker bed between the rails so it reads on bright carpet too
	float glow = 0.22 * (1.0 - smoothstep(half_w * 0.25, half_w, y));
	float bed = 0.28 * (1.0 - smoothstep(half_w * 0.5 - aa, half_w * 0.5 + aa, y));
	// the rails
	float rail = 1.0 - smoothstep(0.7 - aa, 0.7 + aa, abs(y - half_w * 0.62));
	// chevrons pointing on, every 18px, flowing on at 34px a second
	float d = mod(s - TIME * 34.0 + y * 0.9, 18.0) - 6.0;
	float chev = smoothstep(-aa, aa, d) * (1.0 - smoothstep(3.2 - aa, 3.2 + aa, d));
	chev *= 1.0 - smoothstep(half_w * 0.42 - aa, half_w * 0.42 + aa, y);
	// a glint sweeping from you to the end every couple of seconds
	float sweep = mod(TIME * 260.0, total + 520.0) - 160.0;
	float glint = exp(-pow((s - sweep) / 46.0, 2.0));
	vec3 col = mix(vec3(0.05, 0.04, 0.03), deep.rgb, glow * 2.0);
	float a = max(bed, glow);
	col = mix(col, brass.rgb, rail * (0.75 + 0.25 * glint));
	a = max(a, rail * (0.8 + 0.2 * glint));
	col = mix(col, mix(brass.rgb, vec3(1.0, 0.97, 0.86), glint), chev);
	a = max(a, chev * (0.85 + 0.15 * glint));
	a = max(a, glow * glint * 2.0);
	// in from behind you, out into the beacon
	a *= smoothstep(start, start + 26.0, s) * smoothstep(0.0, 16.0, total - s);
	COLOR = vec4(col, a);
}
"""

const BEACON_SHADER := """
shader_type canvas_item;
render_mode unshaded;

uniform vec4 brass : source_color = vec4(0.925, 0.827, 0.588, 1.0);
uniform vec4 deep : source_color = vec4(0.70, 0.53, 0.24, 1.0);

float ring(float r, float at, float w, float aa) {
	return 1.0 - smoothstep(w - aa, w + aa, abs(r - at));
}

void fragment() {
	vec2 p = UV * 2.0 - 1.0;   // -1..1 across the beacon
	float r = length(p);
	float aa = fwidth(r) * 1.2;
	float a = 0.0;
	vec3 col = brass.rgb;
	// a warm pool on the floor
	float pool = 0.28 * (1.0 - smoothstep(0.0, 0.6, r));
	a = pool;
	col = deep.rgb;
	// two rings rippling out, half a beat apart
	for (int i = 0; i < 2; i++) {
		float t = fract(TIME * 0.55 + float(i) * 0.5);
		float k = ring(r, 0.22 + t * 0.74, 0.035, aa) * (1.0 - t) * 0.9;
		col = mix(col, brass.rgb, k);
		a = max(a, k);
	}
	// a still ring round the spot
	float base = ring(r, 0.36, 0.03, aa) * 0.7;
	col = mix(col, brass.rgb, base);
	a = max(a, base);
	// the diamond, breathing a little, with a dark edge and a lit centre
	float beat = 0.5 + 0.5 * sin(TIME * 3.2);
	float dm = abs(p.x) + abs(p.y);
	float size = 0.25 + 0.02 * beat;
	float aad = fwidth(dm) * 1.2;
	float edge = 1.0 - smoothstep(size + 0.06 - aad, size + 0.06 + aad, dm);
	float fill = 1.0 - smoothstep(size - aad, size + aad, dm);
	float core = 1.0 - smoothstep(size * 0.42 - aad, size * 0.42 + aad, dm);
	col = mix(col, vec3(0.06, 0.05, 0.03), edge);
	a = max(a, edge * 0.9);
	col = mix(col, mix(deep.rgb, brass.rgb, 0.55 + 0.45 * beat), fill);
	col = mix(col, vec3(1.0, 0.97, 0.86), core);
	a = max(a, fill);
	COLOR = vec4(col, a);
}
"""

static var _ribbon_shader: Shader
static var _beacon_shader: Shader

var path := PackedVector2Array():
	set(v):
		path = v
		visible = path.size() >= 2
		_build()
var _mesh: ArrayMesh
var _lengths := PackedFloat32Array()   # the distance along to each point of the path
var _start := 0.0
var _beacon: Node2D


func _ready() -> void:
	z_index = -3   # over the floor, rugs and walls (-10, -6, -5), under the people and tables
	visible = false
	if _ribbon_shader == null:
		_ribbon_shader = Shader.new()
		_ribbon_shader.code = RIBBON_SHADER
		_beacon_shader = Shader.new()
		_beacon_shader.code = BEACON_SHADER
	material = ShaderMaterial.new()
	material.shader = _ribbon_shader
	material.set_shader_parameter("half_w", HALF_WIDTH)
	_beacon = Node2D.new()
	_beacon.material = ShaderMaterial.new()
	_beacon.material.shader = _beacon_shader
	_beacon.draw.connect(func():
		var q := BEACON
		_beacon.draw_primitive(PackedVector2Array([Vector2(-q, -q), Vector2(q, -q), Vector2(q, q), Vector2(-q, q)]),
			PackedColorArray([Color.WHITE]), PackedVector2Array([Vector2(0, 0), Vector2(1, 0), Vector2(1, 1), Vector2(0, 1)])))
	add_child(_beacon)


## You're at `pos`: the ribbon behind you fades out (just a shader parameter, so call it as often as you like).
func trim_to(pos: Vector2) -> void:
	if path.size() < 2:
		return
	var best := INF
	var along := 0.0
	for i in range(1, path.size()):
		var q := Geometry2D.get_closest_point_to_segment(pos, path[i - 1], path[i])
		var d := q.distance_squared_to(pos)
		if d < best:
			best = d
			along = _lengths[i - 1] + path[i - 1].distance_to(q)
	if absf(along - _start) > 0.5:
		_start = along
		(material as ShaderMaterial).set_shader_parameter("start", maxf(_start - 10.0, 0.0))


## The ribbon: a strip along the path, its corners mitred, UV.x the distance along and UV.y -1..1 across.
func _build() -> void:
	_mesh = null
	_start = 0.0
	_lengths = PackedFloat32Array()
	if path.size() < 2:
		queue_redraw()
		return
	var verts := PackedVector2Array()
	var uvs := PackedVector2Array()
	var along := 0.0
	var n := path.size()
	for i in n:
		if i > 0:
			along += path[i - 1].distance_to(path[i])
		_lengths.append(along)
		var into := (path[i] - path[i - 1]).normalized() if i > 0 else (path[1] - path[0]).normalized()
		var on := (path[i + 1] - path[i]).normalized() if i < n - 1 else into
		var side := (into + on).normalized().orthogonal() if not (into + on).is_zero_approx() else into.orthogonal()
		var mitre := clampf(1.0 / maxf(side.dot(into.orthogonal()), 0.01), 1.0, 1.6)
		verts.append(path[i] + side * HALF_WIDTH * mitre)
		verts.append(path[i] - side * HALF_WIDTH * mitre)
		uvs.append(Vector2(along, -1.0))
		uvs.append(Vector2(along, 1.0))
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	_mesh = ArrayMesh.new()
	_mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLE_STRIP, arrays)
	var m := material as ShaderMaterial
	m.set_shader_parameter("total", along)
	m.set_shader_parameter("start", 0.0)
	_beacon.position = path[n - 1]
	queue_redraw()


func _draw() -> void:
	if _mesh:
		draw_mesh(_mesh, null)
