@tool
extends StyledFelt
## The Let It Ride layout, printed on the table in its style: the title and the dealer's rules, the two
## community cards' places, and for each seat the Jackpot disc, the Bonus and 3 Card Bonus circles, then the
## three bets: 1, 2 and £.


func _draw_layout(t: CasinoTable) -> void:
	title("LET IT RIDE", t.title_y())
	for line in [["PAIR OF 10s", -60, -1.5], ["OR BETTER PAYS", -60, 3.5], ["PULL BACK", 60, -1.5], ["1 AND 2", 60, 3.5]]:
		small(line[0], line[1], line[2])
	for k in 2:
		card_box(t.dealer_card_pos(k), Vector2(16, 22), 0.55)
	for seat in t.seat_count():
		_draw_seat(t, seat)


func _draw_seat(t: CasinoTable, seat: int) -> void:
	jackpot_disc(t.spot_pos(seat, "jackpot"))
	circle(t.spot_pos(seat, "bonus"), "side", ["BONUS"])
	circle(t.spot_pos(seat, "three_card"), "side", ["3 CARD", "BONUS"])
	for pair in [["bet1", "1"], ["bet2", "2"], ["ante", "£"]]:
		var s := {"shape": "circle", "at": t.spot_pos(seat, pair[0]), "r": 7.0, "ring": "primary", "lines": [pair[1]], "size": 6,
			"inner": {"r": 5.2, "ring": "primary", "alpha": 0.7, "width": 0.4}}
		spot(s)
