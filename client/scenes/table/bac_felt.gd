@tool
extends StyledFelt
## The Baccarat layout, printed on the table in its style: the title, the Player and Banker boxes for the coup's
## cards, and for each seat the Player Dragon, Tie and Banker Dragon circles (side bets), then the Banker and
## Player boxes. Banker's box and hand take the primary colour, Player's the ink.


func _draw_layout(t: CasinoTable) -> void:
	var bt := t as BacTable
	title("BACCARAT", t.title_y())
	if bt:
		for side in ["player", "banker"]:
			var left := bt.coup_pos(side, 0) - Vector2(8.5, 11)
			var right := bt.coup_pos(side, 2) + Vector2(8.5, 11)
			var ring := "primary" if side == "banker" else "ink"   # the same colours as the seats' boxes
			spot({"shape": "box", "at": (left + right) / 2, "w": right.x - left.x, "h": right.y - left.y, "rad": 1.5, "ring": ring,
				"alpha": 0.8, "width": 0.6})
			print_text(side.to_upper(), Vector2((left.x + right.x) / 2, right.y + 3), 3, Color(role_colour(ring), 0.9))  # below: clear of the chip tray
	for seat in t.seat_count():
		_draw_seat(t, seat)


func _draw_seat(t: CasinoTable, seat: int) -> void:
	circle(t.spot_pos(seat, "player_dragon"), "side", ["P", "DRAGON"])
	circle(t.spot_pos(seat, "tie"), "side", ["TIE"])
	circle(t.spot_pos(seat, "banker_dragon"), "side", ["B", "DRAGON"])
	for spot_name in ["banker", "player"]:
		spot(t.spot_shape(seat, spot_name).merged({"ring": "ink" if spot_name == "player" else "primary",
			"lines": [spot_name.to_upper()], "size": 3, "dx": 9.0}))
