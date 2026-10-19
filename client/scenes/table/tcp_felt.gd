@tool
extends TableFelt
## The Three Card Poker layout, printed on the shared Mahogany & Brass table:
## the title and the dealer's rules, and for each seat, top to bottom, the clear
## plastic JACKPOT disc, Pair Plus and Prime circles side by side (all three
## just bigger than a chip), then the Ante diamond and Play box.


func _draw_layout(t: CasinoTable) -> void:
	var cinzel := CINZEL
	_text("THREE CARD POKER", Vector2(0, t.title_y()), 9, CREAM, cinzel)
	var small := Color(CREAM, 0.85)
	for line in [["DEALER QUALIFIES", -62, -1.5], ["WITH QUEEN HIGH", -62, 3.5], ["PLAY MUST", 62, -1.5], ["EQUAL ANTE", 62, 3.5]]:
		_text(line[0], Vector2(line[1], CasinoTable.DEALER_Y + line[2]), 3, small, cinzel)

	for seat in t.seat_count():
		_draw_seat(t, seat)


func _draw_seat(t: CasinoTable, seat: int) -> void:
	var cinzel := CINZEL
	_jackpot_disc(t.spot_pos(seat, "jackpot"))
	_circle_spot(t.spot_pos(seat, "pair_plus"), BRASS, ["PAIR", "PLUS"])
	_circle_spot(t.spot_pos(seat, "prime"), CREAM, ["PRIME"])
	# Ante: a diamond.
	var a := t.spot_pos(seat, "ante")
	var d := PackedVector2Array([a + Vector2(0, -7.5), a + Vector2(9, 0), a + Vector2(0, 7.5), a + Vector2(-9, 0)])
	draw_colored_polygon(d, SPOT_FILL)
	draw_polyline(PackedVector2Array([d[0], d[1], d[2], d[3], d[0]]), CREAM, 0.8, true)
	_text("ANTE", a, 3, CREAM, cinzel)
	# Play: a box with softened corners.
	var p := t.spot_pos(seat, "play")
	var box := _rounded(Rect2(p - Vector2(10.5, 6), Vector2(21, 12)), 1.2)
	draw_colored_polygon(box, SPOT_FILL)
	_loop(box, CREAM, 0.8)
	_text("PLAY", p, 4, CREAM, cinzel)
