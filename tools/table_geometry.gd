extends SceneTree
# Writes the tables' real geometry for the admin page's table designer (server/casino_server/admin_web/tables/)
# and the table styles mockup (docs/table_styles/mockup/): the felt outline and the rail offsets, the chip tray and bay, and for every table its seats'
# spots, cards, dealer cards, equipment and title; and Roulette's and Craps' outlines, layouts and fittings
# ("rou" and "crp"). The designer draws only from this, so it can't drift from the game. Table-local units,
# as layout_audit.gd uses.
#   cd client && CASINO_SERVER_URL=ws://127.0.0.1:1/ws godot --headless --path . -s ../tools/table_geometry.gd
const TABLES := {
	"tcp": "res://scenes/table/tcp_table.tscn", "bj": "res://scenes/table/bj_table.tscn",
	"pgf": "res://scenes/table/pg_table.tscn", "pgu": "res://scenes/table/pg_table.tscn",
	"ms": "res://scenes/table/ms_table.tscn", "uth": "res://scenes/table/uth_table.tscn",
	"lir": "res://scenes/table/lir_table.tscn", "hcf": "res://scenes/table/hcf_table.tscn",
	"bac": "res://scenes/table/bac_table.tscn",
	"mt": "res://scenes/table/master_table.tscn",   # (the Master Table blank: its crest, no spots)
}
const GROWN := [-8.0, -6.5, -6.0, -5.0, -4.0, -3.5, -2.0, -1.2, -0.9, -0.3, 1.2, 1.5, 3.5, 4.0, 5.9, 6.5, 7.0, 7.5, 11.0]
const BORDER := [-2.0, -3.5, -4.0, -4.75, -5.0, -6.0]
const OUT := ["../server/casino_server/admin_web/tables/geometry.json", "../docs/table_styles/mockup/geometry.json"]


func v(p: Vector2) -> Array:
	return [snappedf(p.x, 0.01), snappedf(p.y, 0.01)]


func poly(pts: PackedVector2Array) -> Array:
	var out := []
	for p in pts:
		out.append(v(p))
	return out


func _node_pos(t, path: String) -> Variant:
	var n = t.get_node_or_null(path)
	return v(t.to_local(n.global_position)) if n else null


func _initialize() -> void:
	# Class names and autoloads aren't visible to a -s script, so everything goes through instances.
	var c = load(TABLES.tcp).instantiate()
	root.add_child(c)
	await process_frame
	var data := {
		"outline": poly(c.outline(24)),
		"outline_closed": poly(c.outline(24, false)),
		"grown": {},
		"rail": c.RAIL,
		"bay": {"w": c.BAY_W, "d": c.BAY_D, "r": c.BAY_R, "floor": c.bay_floor()},
		"dealer_y": c.DEALER_Y,
		"spot_r": c.SPOT_R,
		"card": [14, 20],
		"tables": {},
	}
	for g in GROWN:
		data.grown[str(g)] = poly(c.grown(g, 24))
	# The border lines, round the ledge or the sunk tray (StyledFelt.border_edge), keyed "%.2f".
	var felt = c.get_node("Felt")
	data["border"] = {"ledge": {}, "sunk": {}}
	for by in BORDER:
		for mode in data.border:
			data.border[mode]["%.2f" % by] = poly(felt.border_edge(by, mode == "ledge"))
	c.queue_free()
	for key in TABLES:
		var t = load(TABLES[key]).instantiate()
		if key == "pgu":
			t.face_up = true
		root.add_child(t)
		await process_frame
		var n: int = t.seat_count()
		var tab := {
			"label": t.game_label, "seats": n, "tray": [t.tray_rect().position.x, t.tray_rect().position.y, t.tray_rect().size.x, t.tray_rect().size.y],
			"title_y": t.title_y(), "countdown": v(t.countdown_pos()),
			"dealer": _node_pos(t, "Dealer"),
			"shuffler": _node_pos(t, "Felt/Machines/Shuffler"),
			"shoe": _node_pos(t, "Felt/Fixtures/Shoe"),
			"discard": _node_pos(t, "Felt/Fixtures/DiscardRack"),
			"sign": v(t.JACKPOT_SIGN) if t.jackpot_sign else null, "sign_on": "jackpot" in t.bet_spots(),   # (off: no Jackpot bet)
			"chairs": [], "spots": [], "cards": [], "dealer_cards": [], "extra": {},
			"primary": t.primary_spots().filter(func(s): return s in t.bet_spots()),   # (they glow first, the side bets after)
		}
		var names: Array = t.bet_spots().duplicate()
		for extra in ["play", "raise", "blind", "third", "fourth", "fifth", "insurance"]:
			if extra not in names and _has_spot(key, extra):
				names.append(extra)
		for seat in n:
			tab.chairs.append(v(t.chair_pos(seat)))
			var spots := {}
			for s in names:
				spots[s] = {"at": v(t.spot_pos(seat, s)), "r": t.spot_radius(s)}
				if s in t.bet_spots():   # its printed outline, for the designer's spot glow
					var shape: Dictionary = t.spot_shape(seat, s).duplicate()
					shape.at = v(shape.at)
					spots[s]["shape"] = shape
			tab.spots.append(spots)
			var cards := []
			match key:
				"tcp", "lir": for k in 3: cards.append(v(t.card_pos(seat, k)))
				"ms", "uth": for k in 2: cards.append(v(t.card_pos(seat, k)))
				"hcf": for k in 7: cards.append(v(t.card_pos(seat, k)))
				"bj": for k in 2: cards.append(v(t.card_pos(seat, 0, 1, k, 2)))
				"pgf", "pgu":
					cards.append(v(t.box_pos(seat, "low")))
					cards.append(v(t.box_pos(seat, "high")))
			tab.cards.append(cards)
		match key:
			"pgf", "pgu":
				for k in 7: tab.dealer_cards.append(v(t._dealer_row_pos(k)))
				tab.extra = {"ante_r": t.ANTE_R, "low_box": v(t.LOW_BOX), "high_box": v(t.HIGH_BOX), "envy": v(t.ENVY_OFFSET)}
			"bac":
				for side in ["player", "banker"]:
					for k in 3: tab.dealer_cards.append(v(t.coup_pos(side, k)))
				tab.extra = {"box": v(t.BOX), "banker_y": t.BANKER_Y, "player_y": t.PLAYER_Y}
			"uth", "hcf":
				for k in 7: tab.dealer_cards.append(v(t.dealer_card_pos(k)))
			"lir":
				for k in 2: tab.dealer_cards.append(v(t.dealer_card_pos(k)))
			"bj":
				for k in 2: tab.dealer_cards.append(v(t.dealer_card_pos(k)))
				tab.extra = {"bet_r": t.BET_R}
			"ms":
				for k in 3: tab.dealer_cards.append(v(t.dealer_card_pos(k)))
				tab.extra = {"street_r": t.STREET_R}
			_:
				for k in 3: tab.dealer_cards.append(v(t.dealer_card_pos(k)))
		data.tables[key] = tab
		t.queue_free()
		await process_frame
	data["rou"] = await _roulette()
	data["crp"] = await _craps()
	for out in OUT:
		var f := FileAccess.open(out, FileAccess.WRITE)
		f.store_string(JSON.stringify(data, " ", false))
		f.close()
		print("wrote ", out, " (", data.tables.size(), " tables)")
	quit(0)


## The outline grown by everything StyledFelt asks of a 9-wide rail, keyed as the designer asks ("%.2f").
func _grows(t, rw: float, extra: Array) -> Dictionary:
	var out := {}
	for g in [rw + 4.0, rw + 1.5, rw + 0.5, rw / 2, rw * 4.0 / 7.0, 1.2, rw - 1.1] + extra:
		out["%.2f" % g] = poly(t.shape(g))
	return out


func rect(r: Rect2) -> Array:
	return [snappedf(r.position.x, 0.01), snappedf(r.position.y, 0.01), snappedf(r.size.x, 0.01), snappedf(r.size.y, 0.01)]


func _roulette() -> Dictionary:
	var t = load("res://scenes/table/rou_table.tscn").instantiate()
	root.add_child(t)
	await process_frame
	var out := {
		"rail": t.RAIL_W, "felt": poly(t.shape(0.0, true, 12)), "grown": _grows(t, t.RAIL_W, [-5.0, -4.0, -6.0, -3.5, -4.75, -2.0]),
		"tray": rect(t.tray_rect()), "hole": v(t.HOLE_AT), "hole_r": t.HOLE_R, "title": v(t.TITLE_AT), "wheel": v(t.WHEEL_AT),
		"wheel_order": t.wheel.WHEEL, "red": t.RED, "evens": t.EVENS,
		"grid": {"zx": t.ZX, "gx": t.GX, "gy": t.GY, "bw": t.BW, "bh": t.BH, "dy": t.DY, "dh": t.DH, "ey": t.EY, "eh": t.EH},
		"dealer": _node_pos(t, "Dealer"), "chairs": [], "chips": {},
	}
	for seat in t.seat_count():
		out.chairs.append(v(t.chair_pos(seat)))
	for spot in ["n17", "sp_8_11", "co_20_24", "n32", "red", "doz2", "col1", "n0"]:
		out.chips[spot] = v(t.chip_pos(spot))
	t.queue_free()
	await process_frame
	return out


func _craps() -> Dictionary:
	var t = load("res://scenes/table/crp_table.tscn").instantiate()
	root.add_child(t)
	await process_frame
	var felt = load("res://scenes/table/crp_felt.gd").new()
	var out := {
		"rail": t.RAIL_W, "felt": poly(t.shape(0.0, true, 12)), "grown": _grows(t, t.RAIL_W, []),
		"pad": poly(felt._pad_area("dealer")), "tray": rect(t.tray_rect()),
		"rubber_w": t.RUBBER_W, "groove_w": t.GROOVE_W, "rubber": {}, "groove": {}, "zones": {}, "polys": {},
		"props": {}, "prop_box": rect(t.PROP_BOX), "pass": poly(t.pass_line()), "nums": t.NUMS,
		"dice": [v(t.dice.HOME[0]), v(t.dice.HOME[1])], "pips": {}, "mx": {},
		"dealer": _node_pos(t, "Dealer"), "boxman": _node_pos(t, "Boxman"),
	}
	felt.free()
	for h in [1, -1]:
		var rw: float = t.RUBBER_W
		var go: float = t.GROOVE_OUT
		var hw: float = t.GROOVE_W / 2
		out.rubber[str(h)] = {"edge": poly(t.rubber_path(h, 0.0)), "inner": poly(t.rubber_path(h, rw)), "mid": poly(t.rubber_path(h, rw / 2))}
		out.groove[str(h)] = {"mid": poly(t.groove_path(h, go)), "in": poly(t.groove_path(h, go - hw + 0.5)), "out": poly(t.groove_path(h, go + hw + 0.3))}
		var z: Dictionary = t.zones(h)
		out.zones[str(h)] = {}
		out.polys[str(h)] = {}
		for id in z:
			out.zones[str(h)][id] = rect(z[id])
			out.polys[str(h)][id] = poly(t.zone_poly(id, h))
		out.mx[str(h)] = [t.mx(110, h), t.mx(177, h)]
	for id in t.PROPS:
		out.props[id] = rect(t.PROPS[id])
	for n in t.dice.PIPS:
		out.pips[str(n)] = poly(PackedVector2Array(t.dice.PIPS[n]))
	t.queue_free()
	await process_frame
	return out


func _has_spot(key: String, spot: String) -> bool:
	return (key in ["tcp", "uth"] and spot == "play") or (key == "hcf" and spot == "raise") \
		or (key == "ms" and spot in ["third", "fourth", "fifth"]) or (key == "uth" and spot == "blind") \
		or (key == "bj" and spot == "insurance")
