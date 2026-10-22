@tool
extends StyledFelt
## The Ultimate Texas Hold'em layout, printed on the table in its style: the title and the dealer's rules, the
## dealer's two cards and the five community cards' places, and for each seat the Jackpot disc beside Trips,
## Ante = Blind, and the Play box.


func _draw_layout(t: CasinoTable) -> void:
	title("ULTIMATE TEXAS HOLD'EM", t.title_y(), 8)
	small("DEALER QUALIFIES", 64, -1.5)
	small("WITH A PAIR", 64, 3.5)
	for k in 7:
		card_box(t.dealer_card_pos(k), Vector2(15, 21), 0.5 if k >= 2 else 0.35)
	for seat in t.seat_count():
		_draw_seat(t, seat)


func _draw_seat(t: CasinoTable, seat: int) -> void:
	jackpot_disc(t.spot_pos(seat, "jackpot"))
	circle(t.spot_pos(seat, "trips"), "side", ["TRIPS"])
	for spot_name in ["ante", "blind"]:
		big(t.spot_pos(seat, spot_name), 8.0, [spot_name.to_upper()], 3)
	var mid := (t.spot_pos(seat, "ante") + t.spot_pos(seat, "blind")) / 2
	print_text("=", mid, 4, Color(ink(), 0.8))
	spot({"shape": "box", "at": t.spot_pos(seat, "play"), "w": 21.0, "h": 12.0, "rad": 1.2, "ring": "ink", "lines": ["PLAY"], "size": 4})
