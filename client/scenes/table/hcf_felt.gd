@tool
extends TableFelt
## The High Card Flush layout, printed on the shared Mahogany & Brass table:
## the title, the qualifying rule and raise limits, a frame for the dealer's
## seven cards, and for each seat, top to bottom, the clear plastic JACKPOT
## disc, the FLUSH and STRAIGHT FLUSH circles, then ANTE and RAISE.


func _draw_layout(t: CasinoTable) -> void:
	var cinzel := CINZEL
	_text("HIGH CARD FLUSH", Vector2(0, t.title_y()), 9, CREAM, cinzel)
	var small := Color(CREAM, 0.85)
	for line in [["DEALER NEEDS", -64, -1.5], ["3-CARD 9-HIGH", -64, 3.5], ["RAISE 2X ON 5", 64, -1.5], ["3X ON 6 OR 7", 64, 3.5]]:
		_text(line[0], Vector2(line[1], CasinoTable.DEALER_Y + line[2]), 3, small, cinzel)
	var left := t.dealer_card_pos(0) - Vector2(8.5, 11)
	var right := t.dealer_card_pos(6) + Vector2(8.5, 11)
	var box := _rounded(Rect2(left, right - left), 1.5)
	draw_colored_polygon(box, SPOT_FILL)
	_loop(box, Color(CREAM, 0.45), 0.5)
	for seat in t.seat_count():
		_draw_seat(t, seat)


func _draw_seat(t: CasinoTable, seat: int) -> void:
	var cinzel := CINZEL
	_jackpot_disc(t.spot_pos(seat, "jackpot"))
	_circle_spot(t.spot_pos(seat, "flush"), BRASS, ["FLUSH"])
	_circle_spot(t.spot_pos(seat, "straight_flush"), CREAM, ["STRAIGHT", "FLUSH"])
	for spot in ["ante", "raise"]:
		var at := t.spot_pos(seat, spot)
		draw_circle(at, 8.0, SPOT_FILL)
		draw_arc(at, 7.6, 0, TAU, 36, CREAM, 0.8, true)
		_text(spot.to_upper(), at, 3, CREAM, cinzel)
