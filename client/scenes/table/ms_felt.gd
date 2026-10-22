@tool
extends StyledFelt
## The Mississippi Stud layout, printed on the table in its style: the title and the dealer's rules, where the
## three community cards lie, and for each seat the Jackpot disc beside the 3 Card Bonus, the Ante circle, and
## the 3rd, 4th and 5th Street circles.


func _draw_layout(t: CasinoTable) -> void:
	title("MISSISSIPPI STUD", t.title_y())
	for line in [["JACKS OR BETTER", -64, -1.5], ["PAYS EVERY BET", -64, 3.5], ["6s TO 10s", 64, -1.5], ["PUSH", 64, 3.5]]:
		small(line[0], line[1], line[2])
	# Where the three community cards lie, face down until they're turned.
	for k in 3:
		card_box(t.dealer_card_pos(k), Vector2(16, 22), 0.55)
	for seat in t.seat_count():
		_draw_seat(t, seat)


func _draw_seat(t: CasinoTable, seat: int) -> void:
	jackpot_disc(t.spot_pos(seat, "jackpot"))
	circle(t.spot_pos(seat, "bonus"), "side", ["3 CARD", "BONUS"])
	big(t.spot_pos(seat, "ante"), 9.0, ["ANTE"], 3, 7.0)
	for k in 3:
		spot({"shape": "circle", "at": t.spot_pos(seat, MsTable.STREETS[k]), "r": MsTable.STREET_R, "ring": "ink", "alpha": 0.9,
			"width": 0.6, "lines": [MsTable.STREET_LABELS[k]], "size": 2})
