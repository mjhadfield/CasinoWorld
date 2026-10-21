extends SceneTree
# Writes the card tables' real geometry to docs/table_styles/mockup/geometry.json for the table styles
# mockup: the felt outline and the rail offsets, the chip tray and bay, and for every table its seats'
# spots, cards, dealer cards, equipment and title. The mockup draws only from this, so it can't drift
# from the game. Table-local units, as layout_audit.gd uses.
#   cd client && godot --headless --path . -s ../tools/table_geometry.gd
const TABLES := {
	"tcp": "res://scenes/table/tcp_table.tscn", "bj": "res://scenes/table/bj_table.tscn",
	"pgf": "res://scenes/table/pg_table.tscn", "pgu": "res://scenes/table/pg_table.tscn",
	"ms": "res://scenes/table/ms_table.tscn", "uth": "res://scenes/table/uth_table.tscn",
	"lir": "res://scenes/table/lir_table.tscn", "hcf": "res://scenes/table/hcf_table.tscn",
	"bac": "res://scenes/table/bac_table.tscn",
}
const GROWN := [-8.0, -6.5, -6.0, -5.0, -4.0, -3.5, -2.0, -1.2, -0.9, -0.3, 1.2, 1.5, 3.5, 4.0, 5.9, 6.5, 7.0, 7.5, 11.0]
const OUT := "../docs/table_styles/mockup/geometry.json"


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
			"chairs": [], "spots": [], "cards": [], "dealer_cards": [], "extra": {},
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
	var f := FileAccess.open(OUT, FileAccess.WRITE)
	f.store_string(JSON.stringify(data, " ", false))
	f.close()
	print("wrote ", OUT, " (", data.tables.size(), " tables)")
	quit(0)


func _has_spot(key: String, spot: String) -> bool:
	return (key in ["tcp", "uth"] and spot == "play") or (key == "hcf" and spot == "raise") \
		or (key == "ms" and spot in ["third", "fourth", "fifth"]) or (key == "uth" and spot == "blind") \
		or (key == "bj" and spot == "insurance")
