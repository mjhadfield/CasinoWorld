@tool
extends StyledFelt
## The Blackjack layout, printed on the table in its style: the title and the dealer's rules, and for each seat,
## top to bottom, the Jackpot disc beside the Top 3 diamond, Super Pairs beside 21+3 (Top 3 sits over 21+3,
## which it needs), then the Blackjack betting circle with the insurance mark at its side. The cards are dealt
## below the circle.


func _draw_layout(t: CasinoTable) -> void:
	title("BLACKJACK PAYS 3 TO 2", t.title_y())
	small("STANDS ON 17s", 69, -1.5)  # between the dealer's cards and the shoe
	small("INSURANCE 2:1", 69, 3.5)
	for seat in t.seat_count():
		_draw_seat(t, seat)


func _draw_seat(t: CasinoTable, seat: int) -> void:
	jackpot_disc(t.spot_pos(seat, "jackpot"))
	spot({"shape": "diamond", "at": t.spot_pos(seat, "top_three"), "hw": 8.5, "hh": 7.5, "ring": "accent", "lines": ["TOP 3"], "size": 2})
	circle(t.spot_pos(seat, "super_pairs"), "accent", ["SUPER", "PAIRS"])
	circle(t.spot_pos(seat, "twenty_one_plus_three"), "ink", ["21+3"])
	var r: float = BlackjackTable.BET_R
	big(t.spot_pos(seat, "bet"), r, [], 0, r - 2.2)
	# Insurance goes on the little mark at the circle's side.
	spot({"shape": "circle", "at": t.spot_pos(seat, "insurance"), "r": 4.6, "ring": "ink", "alpha": 0.55, "width": 0.4,
		"lines": ["INS"], "size": 2, "text_alpha": 0.7})
