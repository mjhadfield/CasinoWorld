@tool
extends TableFelt
## The Pai Gow layout (Fortune or Face Up), printed on the shared Mahogany &
## Brass table: the title and the dealer's rules, and for each seat, top to
## bottom, the clear plastic JACKPOT disc beside the Fortune circle, the Ante
## circle, then the LOW box (upright, for the 2-card hand) with the HIGH box
## (sideways, for the 5-card hand) below it, where a set hand goes down.


func _draw_layout(t: CasinoTable) -> void:
	var cinzel := CINZEL
	var pg := t as PaiGowTable
	_text(t.game_label.to_upper(), Vector2(0, t.title_y()), 9, CREAM, cinzel)
	var small := Color(CREAM, 0.85)
	var last := "NO COMMISSION" if pg and pg.face_up else "5% COMMISSION"
	for line in [["DEALER SETS", -6.5], ["BY HOUSE WAY", -1.5], [last, 3.5]]:
		_text(line[0], Vector2(-62, CasinoTable.DEALER_Y + line[1]), 3, small, cinzel)
	for seat in t.seat_count():
		_draw_seat(t, seat)


func _draw_seat(t: CasinoTable, seat: int) -> void:
	var cinzel := CINZEL
	_jackpot_disc(t.spot_pos(seat, "jackpot"))
	_circle_spot(t.spot_pos(seat, "fortune"), BRASS, ["FORTUNE"])
	# The Ante: a cream circle with a brass ring inside it.
	var ante := t.spot_pos(seat, "ante")
	var r: float = PaiGowTable.ANTE_R
	draw_circle(ante, r, SPOT_FILL)
	draw_arc(ante, r - 0.4, 0, TAU, 40, CREAM, 0.8, true)
	draw_arc(ante, r - 2.0, 0, TAU, 40, Color(BRASS, 0.8), 0.4, true)
	_text("ANTE", ante, 3, CREAM, cinzel)
	# The LOW box, upright, with the HIGH box lying sideways below it.
	var pg := t as PaiGowTable
	if pg == null:
		return
	for which in ["low", "high"]:
		var at := pg.box_pos(seat, which)
		var size: Vector2 = PaiGowTable.HIGH_BOX if which == "high" else PaiGowTable.LOW_BOX
		var box := _rounded(Rect2(at - size / 2, size), 1.5)
		draw_colored_polygon(box, SPOT_FILL)
		_loop(box, Color(CREAM, 0.8), 0.6)
		_text(which.to_upper(), at + Vector2(0, size.y / 2 - 3.0), 2, Color(CREAM, 0.8), cinzel)
