@tool
extends TableFelt
## The Ultimate Texas Hold'em layout, printed on the shared Mahogany & Brass
## table: the title, frames for the dealer's two cards and the five community
## cards, the qualifying rule, and for each seat, top to bottom, the clear
## plastic JACKPOT disc beside the TRIPS circle, the ANTE and BLIND circles
## side by side (with an = between them), then the PLAY box.


func _draw_layout(t: CasinoTable) -> void:
	var cinzel := CINZEL
	_text("ULTIMATE TEXAS HOLD'EM", Vector2(0, t.title_y()), 8, CREAM, cinzel)
	var small := Color(CREAM, 0.85)
	for line in [["DEALER QUALIFIES", 64, -1.5], ["WITH A PAIR", 64, 3.5]]:
		_text(line[0], Vector2(line[1], CasinoTable.DEALER_Y + line[2]), 3, small, cinzel)
	for k in 7:
		var at := t.dealer_card_pos(k)
		var box := _rounded(Rect2(at - Vector2(7.5, 10.5), Vector2(15, 21)), 1.5)
		draw_colored_polygon(box, SPOT_FILL)
		_loop(box, Color(CREAM, 0.5 if k >= 2 else 0.35), 0.5)
	for seat in t.seat_count():
		_draw_seat(t, seat)


func _draw_seat(t: CasinoTable, seat: int) -> void:
	var cinzel := CINZEL
	_jackpot_disc(t.spot_pos(seat, "jackpot"))
	_circle_spot(t.spot_pos(seat, "trips"), BRASS, ["TRIPS"])
	for spot in ["ante", "blind"]:
		var at := t.spot_pos(seat, spot)
		draw_circle(at, 8.0, SPOT_FILL)
		draw_arc(at, 7.6, 0, TAU, 36, CREAM, 0.8, true)
		_text(spot.to_upper(), at, 3, CREAM, cinzel)
	var mid := (t.spot_pos(seat, "ante") + t.spot_pos(seat, "blind")) / 2
	_text("=", mid, 4, Color(CREAM, 0.8), cinzel)
	var p := t.spot_pos(seat, "play")
	var box := _rounded(Rect2(p - Vector2(10.5, 6), Vector2(21, 12)), 1.2)
	draw_colored_polygon(box, SPOT_FILL)
	_loop(box, CREAM, 0.8)
	_text("PLAY", p, 4, CREAM, cinzel)
