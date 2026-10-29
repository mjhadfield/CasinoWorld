@tool
extends StyledFelt
## The Blackjack layout, printed on the table in its style: the title and the dealer's rules, and for each seat,
## top to bottom, the Jackpot disc beside the Top 3 diamond, Super Pairs beside 21+3 (Top 3 sits over 21+3,
## which it needs), then the Blackjack betting circle with the insurance mark at its side. The cards are dealt
## below the circle.


func _draw_layout(t: CasinoTable) -> void:
	title("BLACKJACK PAYS 3 TO 2", t.title_y())
	small("STANDS ON 17s", -33, -12.5)  # just right of the shuffler, clear of the jackpot sign and the dealer's cards
	small("INSURANCE 2:1", -33, -7.5)   # (left of the shoe is the card count's: count_overlay.gd)
	for seat in t.seat_count():
		_draw_seat(t, seat)


func _draw_seat(t: CasinoTable, seat: int) -> void:
	jackpot_disc(t.spot_pos(seat, "jackpot"))
	spot(t.spot_shape(seat, "top_three").merged({"ring": "side", "lines": ["TOP 3"], "size": 2}))
	circle(t.spot_pos(seat, "super_pairs"), "side", ["SUPER", "PAIRS"])
	circle(t.spot_pos(seat, "twenty_one_plus_three"), "side", ["21+3"])
	var r: float = BlackjackTable.BET_R
	big(t.spot_pos(seat, "bet"), r, [], 0, r - 2.2)
	# Insurance goes on the little mark at the circle's side.
	spot({"shape": "circle", "at": t.spot_pos(seat, "insurance"), "r": 4.6, "ring": "ink", "alpha": 0.55, "width": 0.4,
		"lines": ["INS"], "size": 2, "text_alpha": 0.7})
