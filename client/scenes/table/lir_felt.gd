@tool
extends TableFelt
## The Let It Ride layout, printed on the shared Mahogany & Brass table: the
## title, frames for the two community cards, the paying rule, and for each
## seat, top to bottom, the clear plastic JACKPOT disc, the £1 BONUS and the
## 3 CARD BONUS circles, then the three equal bets: 1, 2 and £ (as v2 labels them).


func _draw_layout(t: CasinoTable) -> void:
	var cinzel := CINZEL
	_text("LET IT RIDE", Vector2(0, t.title_y()), 9, CREAM, cinzel)
	var small := Color(CREAM, 0.85)
	for line in [["PAIR OF 10s", -60, -1.5], ["OR BETTER PAYS", -60, 3.5], ["PULL BACK", 60, -1.5], ["1 AND 2", 60, 3.5]]:
		_text(line[0], Vector2(line[1], CasinoTable.DEALER_Y + line[2]), 3, small, cinzel)
	for k in 2:
		var at := t.dealer_card_pos(k)
		var box := _rounded(Rect2(at - Vector2(8, 11), Vector2(16, 22)), 1.5)
		draw_colored_polygon(box, SPOT_FILL)
		_loop(box, Color(CREAM, 0.55), 0.5)
	for seat in t.seat_count():
		_draw_seat(t, seat)


func _draw_seat(t: CasinoTable, seat: int) -> void:
	var cinzel := CINZEL
	_jackpot_disc(t.spot_pos(seat, "jackpot"))
	_circle_spot(t.spot_pos(seat, "bonus"), BRASS, ["BONUS"])
	_circle_spot(t.spot_pos(seat, "three_card"), CREAM, ["3 CARD", "BONUS"])
	for pair in [["bet1", "1"], ["bet2", "2"], ["ante", "£"]]:
		var at := t.spot_pos(seat, pair[0])
		draw_circle(at, 7.0, SPOT_FILL)
		draw_arc(at, 6.6, 0, TAU, 32, CREAM, 0.8, true)
		draw_arc(at, 5.2, 0, TAU, 32, Color(BRASS, 0.7), 0.4, true)
		_text(pair[1], at, 6, CREAM, cinzel if pair[1] != "£" else FONT)  # Cinzel has no £
