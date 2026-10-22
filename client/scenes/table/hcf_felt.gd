@tool
extends StyledFelt
## The High Card Flush layout, printed on the table in its style: the title and the dealer's rules, one box for
## the dealer's seven cards, and for each seat the Jackpot disc, the Flush and Straight Flush circles, then the
## Ante and Raise circles.


func _draw_layout(t: CasinoTable) -> void:
	title("HIGH CARD FLUSH", t.title_y())
	for line in [["DEALER NEEDS", -64, -1.5], ["3-CARD 9-HIGH", -64, 3.5], ["RAISE 2X ON 5", 64, -1.5], ["3X ON 6 OR 7", 64, 3.5]]:
		small(line[0], line[1], line[2])
	var left := t.dealer_card_pos(0) - Vector2(8.5, 11)
	var right := t.dealer_card_pos(6) + Vector2(8.5, 11)
	card_box((left + right) / 2, right - left, 0.45)
	for seat in t.seat_count():
		_draw_seat(t, seat)


func _draw_seat(t: CasinoTable, seat: int) -> void:
	jackpot_disc(t.spot_pos(seat, "jackpot"))
	circle(t.spot_pos(seat, "flush"), "side", ["FLUSH"])
	circle(t.spot_pos(seat, "straight_flush"), "side", ["STRAIGHT", "FLUSH"])
	big(t.spot_pos(seat, "ante"), 8.0, ["ANTE"], 3)
	big(t.spot_pos(seat, "raise"), 8.0, ["RAISE"], 3, 0.0, "ink")   # (a follow-up bet)
