@tool
extends TableFelt
## The Blackjack layout, printed on the shared Mahogany & Brass table: the
## title and the dealer's rules, and for each seat, top to bottom, the clear
## plastic JACKPOT disc beside the Top 3 diamond, Super Pairs beside 21+3 (Top 3
## sits over 21+3, which it needs), then the Blackjack betting circle with the
## insurance mark at its side. The cards are dealt below the circle.


func _draw_layout(t: CasinoTable) -> void:
	var cinzel := CINZEL
	_text("BLACKJACK PAYS 3 TO 2", Vector2(0, t.title_y()), 9, CREAM, cinzel)
	var small := Color(CREAM, 0.85)
	_text("STANDS ON 17s", Vector2(69, CasinoTable.DEALER_Y - 1.5), 3, small, cinzel)  # between the dealer's cards and the shoe
	_text("INSURANCE 2:1", Vector2(69, CasinoTable.DEALER_Y + 3.5), 3, small, cinzel)
	for seat in t.seat_count():
		_draw_seat(t, seat)


func _draw_seat(t: CasinoTable, seat: int) -> void:
	var cinzel := CINZEL
	_jackpot_disc(t.spot_pos(seat, "jackpot"))
	# Top 3: a brass diamond.
	var top := t.spot_pos(seat, "top_three")
	var d := PackedVector2Array([top + Vector2(0, -7.5), top + Vector2(8.5, 0), top + Vector2(0, 7.5), top + Vector2(-8.5, 0)])
	draw_colored_polygon(d, SPOT_FILL)
	draw_polyline(PackedVector2Array([d[0], d[1], d[2], d[3], d[0]]), BRASS, 0.8, true)
	_text("TOP 3", top, 2, BRASS, cinzel)
	_circle_spot(t.spot_pos(seat, "super_pairs"), BRASS, ["SUPER", "PAIRS"])
	_circle_spot(t.spot_pos(seat, "twenty_one_plus_three"), CREAM, ["21+3"])
	# The betting circle: a cream ring with a brass ring inside it.
	var bet := t.spot_pos(seat, "bet")
	var r: float = BlackjackTable.BET_R
	draw_circle(bet, r, SPOT_FILL)
	draw_arc(bet, r - 0.4, 0, TAU, 40, CREAM, 0.8, true)
	draw_arc(bet, r - 2.2, 0, TAU, 40, Color(BRASS, 0.8), 0.4, true)
	# Insurance goes on the little mark at the circle's side.
	var ins := t.spot_pos(seat, "insurance")
	draw_arc(ins, 4.6, 0, TAU, 24, Color(CREAM, 0.55), 0.4, true)
	_text("INS", ins, 2, Color(CREAM, 0.7), cinzel)
