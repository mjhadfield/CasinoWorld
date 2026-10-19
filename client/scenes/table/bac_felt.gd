@tool
extends TableFelt
## The Baccarat layout, printed on the shared Mahogany & Brass table: the
## title, the PLAYER (cream) and BANKER (brass) areas where the coup is dealt,
## and for each seat, top to bottom, the P DRAGON and B DRAGON circles (jade)
## either side of TIE, then the wide BANKER (brass) and PLAYER (cream) boxes.


const JADE := Color("7fc8a9")  # the Dragon bonus circles: set apart from the Banker's brass


func _draw_layout(t: CasinoTable) -> void:
	var cinzel := CINZEL
	var bt := t as BacTable
	_text("BACCARAT", Vector2(0, t.title_y()), 9, CREAM, cinzel)
	var small := Color(CREAM, 0.85)
	if bt:
		for side in ["player", "banker"]:
			var left := bt.coup_pos(side, 0) - Vector2(8.5, 11)
			var right := bt.coup_pos(side, 2) + Vector2(8.5, 11)
			var box := _rounded(Rect2(left, right - left), 1.5)
			var colour: Color = BRASS if side == "banker" else CREAM  # the same colours as the seats' boxes
			draw_colored_polygon(box, SPOT_FILL)
			_loop(box, Color(colour, 0.8), 0.6)
			_text(side.to_upper(), Vector2((left.x + right.x) / 2, right.y + 3), 3, Color(colour, 0.9), cinzel)  # below: clear of the chip tray
	for seat in t.seat_count():
		_draw_seat(t, seat)


func _draw_seat(t: CasinoTable, seat: int) -> void:
	var cinzel := CINZEL
	_circle_spot(t.spot_pos(seat, "player_dragon"), JADE, ["P", "DRAGON"])
	_circle_spot(t.spot_pos(seat, "tie"), CREAM, ["TIE"])
	_circle_spot(t.spot_pos(seat, "banker_dragon"), JADE, ["B", "DRAGON"])
	for spot in ["banker", "player"]:
		var y: float = BacTable.BANKER_Y if spot == "banker" else BacTable.PLAYER_Y
		var centre := Vector2(t.seat_x(seat), y)
		var box := _rounded(Rect2(centre - BacTable.BOX / 2, BacTable.BOX), 2.0)
		draw_colored_polygon(box, SPOT_FILL)
		_loop(box, CREAM if spot == "player" else BRASS, 0.8)
		_text(spot.to_upper(), centre + Vector2(9, 0), 3, CREAM if spot == "player" else BRASS, cinzel)
