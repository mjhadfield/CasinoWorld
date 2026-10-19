@tool
extends TableFelt
## The Mississippi Stud layout, printed on the shared Mahogany & Brass table:
## the title, the paytable's key lines, a frame for the three community cards
## in front of the dealer, and for each seat, top to bottom, the clear plastic
## JACKPOT disc beside the 3 CARD BONUS circle, the Ante circle, then the row
## of 3rd, 4th and 5th Street circles.


func _draw_layout(t: CasinoTable) -> void:
	var cinzel := CINZEL
	_text("MISSISSIPPI STUD", Vector2(0, t.title_y()), 9, CREAM, cinzel)
	var small := Color(CREAM, 0.85)
	for line in [["JACKS OR BETTER", -64, -1.5], ["PAYS EVERY BET", -64, 3.5], ["6s TO 10s", 64, -1.5], ["PUSH", 64, 3.5]]:
		_text(line[0], Vector2(line[1], CasinoTable.DEALER_Y + line[2]), 3, small, cinzel)
	# Where the three community cards lie, face down until they're turned.
	for k in 3:
		var at := t.dealer_card_pos(k)
		var box := _rounded(Rect2(at - Vector2(8, 11), Vector2(16, 22)), 1.5)
		draw_colored_polygon(box, SPOT_FILL)
		_loop(box, Color(CREAM, 0.55), 0.5)
	for seat in t.seat_count():
		_draw_seat(t, seat)


func _draw_seat(t: CasinoTable, seat: int) -> void:
	var cinzel := CINZEL
	_jackpot_disc(t.spot_pos(seat, "jackpot"))
	_circle_spot(t.spot_pos(seat, "bonus"), BRASS, ["3 CARD", "BONUS"])
	var ante := t.spot_pos(seat, "ante")
	draw_circle(ante, 9.0, SPOT_FILL)
	draw_arc(ante, 8.6, 0, TAU, 40, CREAM, 0.8, true)
	draw_arc(ante, 7.0, 0, TAU, 40, Color(BRASS, 0.8), 0.4, true)
	_text("ANTE", ante, 3, CREAM, cinzel)
	for k in 3:
		var at := t.spot_pos(seat, MsTable.STREETS[k])
		draw_circle(at, MsTable.STREET_R, SPOT_FILL)
		draw_arc(at, MsTable.STREET_R - 0.3, 0, TAU, 32, Color(CREAM, 0.9), 0.6, true)
		_text(MsTable.STREET_LABELS[k], at, 2, CREAM, cinzel)
