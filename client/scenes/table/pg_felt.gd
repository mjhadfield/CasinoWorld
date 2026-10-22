@tool
extends StyledFelt
## The Pai Gow layout (Fortune or Face Up), printed on the table in its style: the title and the dealer's rules,
## and for each seat, top to bottom, the Jackpot disc beside the Fortune circle, the Ante circle, then the LOW box
## (upright, for the 2-card hand) with the HIGH box (sideways, for the 5-card hand) below it, where a set hand
## goes down.


func _draw_layout(t: CasinoTable) -> void:
	var pg := t as PaiGowTable
	title(t.game_label.to_upper(), t.title_y())
	var last := "NO COMMISSION" if pg and pg.face_up else "5% COMMISSION"
	for line in [["DEALER SETS", -6.5], ["BY HOUSE WAY", -1.5], [last, 3.5]]:
		small(line[0], -62, line[1])
	for seat in t.seat_count():
		_draw_seat(t, seat)


func _draw_seat(t: CasinoTable, seat: int) -> void:
	jackpot_disc(t.spot_pos(seat, "jackpot"))
	circle(t.spot_pos(seat, "fortune"), "side", ["FORTUNE"])
	var r: float = PaiGowTable.ANTE_R
	big(t.spot_pos(seat, "ante"), r, ["ANTE"], 3, r - 2.0)
	# The LOW box, upright, with the HIGH box lying sideways below it.
	var pg := t as PaiGowTable
	if pg == null:
		return
	for which in ["low", "high"]:
		var size: Vector2 = PaiGowTable.HIGH_BOX if which == "high" else PaiGowTable.LOW_BOX
		spot({"shape": "box", "at": pg.box_pos(seat, which), "w": size.x, "h": size.y, "rad": 1.5, "ring": "ink", "alpha": 0.8,
			"width": 0.6, "lines": [which.to_upper()], "size": 2, "dy": size.y / 2 - 3.0, "text_alpha": 0.8})
