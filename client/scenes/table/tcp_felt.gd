@tool
extends StyledFelt
## The Three Card Poker layout, printed on the table in its style: the title and the dealer's rules, and for
## each seat, top to bottom, the Jackpot disc, Pair Plus and Prime circles side by side (all three just bigger
## than a chip), then the Ante diamond and Play box.


func _draw_layout(t: CasinoTable) -> void:
	title("THREE CARD POKER", t.title_y())
	for line in [["DEALER QUALIFIES", -62, -1.5], ["WITH QUEEN HIGH", -62, 3.5], ["PLAY MUST", 62, -1.5], ["EQUAL ANTE", 62, 3.5]]:
		small(line[0], line[1], line[2])
	for seat in t.seat_count():
		_draw_seat(t, seat)


func _draw_seat(t: CasinoTable, seat: int) -> void:
	jackpot_disc(t.spot_pos(seat, "jackpot"))
	circle(t.spot_pos(seat, "pair_plus"), "accent", ["PAIR", "PLUS"])
	circle(t.spot_pos(seat, "prime"), "ink", ["PRIME"])
	spot({"shape": "diamond", "at": t.spot_pos(seat, "ante"), "hw": 9.0, "hh": 7.5, "ring": "ink", "lines": ["ANTE"], "size": 3})
	spot({"shape": "box", "at": t.spot_pos(seat, "play"), "w": 21.0, "h": 12.0, "rad": 1.2, "ring": "ink", "lines": ["PLAY"], "size": 4})
