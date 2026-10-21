extends Node2D
## The Jackpot lights under each seat's clear plastic Jackpot disc. They flash
## red while a Jackpot bet sits on the disc, and glow solid red once the dealer
## has locked the bets in (the chips are lifted off, the light stays on until
## that player is settled). States live on the table: CasinoTable.jackpot_lights,
## for any game with a Jackpot disc.
## Drawn above the felt and below the chips; this node uses table coordinates.

func _process(_delta: float) -> void:
	var table := get_parent().get_parent() as CasinoTable
	if table and not table.jackpot_lights.is_empty():
		queue_redraw()
	elif get_meta("lit", false):
		queue_redraw()  # one last redraw to clear


func _draw() -> void:
	var table := get_parent().get_parent() as CasinoTable
	if table == null:
		return
	set_meta("lit", not table.jackpot_lights.is_empty())
	var blink_on := fmod(Time.get_ticks_msec() / 1000.0, 0.5) < 0.25
	var look := table.style()
	var inside := StyledFelt.rim_inner(look)   # the light fills the disc inside its rim
	var font := TableStyle.font(look)
	for seat in table.jackpot_lights:
		var state: String = table.jackpot_lights[seat]
		if state == "flash" and not blink_on:
			continue
		var pos := table.spot_pos(int(seat), "jackpot")
		draw_circle(pos, CasinoTable.SPOT_R + 2.5, Color(1, 0.1, 0.1, 0.18))   # glow on the felt
		draw_circle(pos, inside, Color(1, 0.12, 0.15, 0.75))                  # the lit disc
		draw_circle(pos, 3.2, Color(1, 0.55, 0.55, 0.45))                    # brightest in the middle
		if look.jackpot == "led":   # its ring of LEDs goes red too
			for dot in StyledFelt.led_dots(look, pos):
				draw_circle(dot, 0.32, Color("ff5a5a"))
		# The lettering, back on top of the light.
		var w := font.get_string_size("JACKPOT", HORIZONTAL_ALIGNMENT_LEFT, -1, 2).x
		draw_string(font, pos + Vector2(-w / 2, 0.7), "JACKPOT", HORIZONTAL_ALIGNMENT_LEFT, -1, 2, Color.WHITE)
