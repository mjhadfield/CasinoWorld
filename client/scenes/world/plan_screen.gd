class_name PlanScreen
extends Node2D
## A live display on a piece of furniture (an asset's "screen" in the plan library): for now the progressive jackpot,
## drawn on the Modern lobby's LED board in the same 3×5 pixel font the board's picture uses, as big as the screen
## takes (twice its size on that board), in the screen's colour, and kept up to date from Session.jackpot_now().

const LED := Color("ff5a3c")
const GLYPHS := {
	"0": "111101101101111", "1": "010110010010111", "2": "111001111100111", "3": "111001111001111",
	"4": "101101111001001", "5": "111100111001111", "6": "111100111101111", "7": "111001001010010",
	"8": "111101111101111", "9": "111101111001111", "£": "011010111010111", ",": "000000000010100",
	".": "000000000000010", "-": "000000111000000",
}

var kind := "jackpot"
var colour := LED
var rect := Rect2()     # on the furniture's picture, from its top-left corner
var _text := ""
var _check := 0.0


func _process(delta: float) -> void:
	_check -= delta
	if _check > 0.0:
		return
	_check = 0.25
	var amount := Session.jackpot_now() if kind == "jackpot" else 0.0
	var t := Money.format(int(amount)) if amount > 0 else "----"
	if t != _text:
		_text = t
		queue_redraw()


func _draw() -> void:
	var k := clampf(floorf(minf(rect.size.x / maxf(1.0, _text.length() * 4 - 1), rect.size.y / 7.0)), 1.0, 8.0)
	var w := (_text.length() * 4 - 1) * k
	var origin := (rect.position + Vector2((rect.size.x - w) / 2.0, (rect.size.y - 5.0 * k) / 2.0)).round()
	for i in _text.length():
		var g: String = GLYPHS.get(_text[i], "")
		for j in g.length():
			if g[j] == "1":
				draw_rect(Rect2(origin + Vector2((i * 4 + j % 3) * k, floorf(j / 3.0) * k), Vector2(k, k)), colour)
	for y in range(int(rect.position.y), int(rect.end.y), 2):   # the LED rows, as the board's picture has them
		draw_rect(Rect2(rect.position.x, y, rect.size.x, 1), Color(0, 0, 0, 0.28))
