extends SceneTree
# Table layout audit: for every table scene, checks the shuffler/shoe/discard rack sit inside the felt's
# cream border, the dealer's cards clear the chip tray, and lists one seat's rows (side bets, main bets,
# cards) with the gap above each and the gap from the cards to the front border. Table-local units.
# Roulette (LAYOUT_ONLY=rou) has its own check: the wheel, float, chip hole, title and layout sit inside the
# felt (clear of the bay and the rail), and the results sign stands clear of the table.
#   cd client && godot --headless --path . -s ../tools/layout_audit.gd      (LAYOUT_ONLY=uth for one table)
const CARD := Vector2(14, 20)
const TABLES := {
	"tcp": "res://scenes/table/tcp_table.tscn", "bj": "res://scenes/table/bj_table.tscn",
	"pg": "res://scenes/table/pg_table.tscn", "ms": "res://scenes/table/ms_table.tscn",
	"uth": "res://scenes/table/uth_table.tscn", "lir": "res://scenes/table/lir_table.tscn",
	"hcf": "res://scenes/table/hcf_table.tscn", "bac": "res://scenes/table/bac_table.tscn",
}

func crect(c: Vector2, size: Vector2) -> Rect2:
	return Rect2(c - size / 2, size)

func inside(poly: PackedVector2Array, r: Rect2) -> bool:
	for p in [r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)]:
		if not Geometry2D.is_point_in_polygon(p, poly):
			return false
	return true

func fmt(r: Rect2) -> String:
	return "y %.1f..%.1f x %.1f..%.1f" % [r.position.y, r.end.y, r.position.x, r.end.x]

func _initialize() -> void:
	var only := OS.get_environment("LAYOUT_ONLY")
	var border := PackedVector2Array()
	for key in TABLES:
		if only != "" and key != only:
			continue
		var t = load(TABLES[key]).instantiate()
		root.add_child(t)
		await process_frame
		if border.is_empty():   # the 5-in border line, round the sunk tray (the tighter of the two)
			border = t.get_node("Felt").border_edge(-5.0, false)
		print("\n=== ", key, "  seats ", t.seat_count())
		var tray: Rect2 = t.tray_rect()
		print("  chip tray      ", fmt(tray))
		var eq := {}
		var shuf = t.get_node_or_null("Felt/Machines/Shuffler")
		if shuf: eq["shuffler"] = crect(t.shoe_pos(), Vector2(24, 18))
		var shoe = t.get_node_or_null("Felt/Machines/Shoe")
		if shoe: eq["shoe"] = crect(shoe.position, Vector2(26, 20))
		var rack = t.get_node_or_null("Felt/Fixtures/DiscardRack")
		if rack: eq["discard"] = crect(rack.position, Vector2(24, 18))
		for name in eq:
			print("  %-14s %s  inside border: %s" % [name, fmt(eq[name]), inside(border, eq[name])])
		# Dealer cards
		var dealer := []
		match key:
			"pg":
				for k in 7: dealer.append(crect(t._dealer_row_pos(k), CARD))
			"bac":
				for side in ["player", "banker"]:
					for k in 3: dealer.append(crect(t.coup_pos(side, k), CARD))
			"uth", "hcf":
				for k in 7: dealer.append(crect(t.dealer_card_pos(k), CARD))
			"lir":
				for k in 2: dealer.append(crect(t.dealer_card_pos(k), CARD))
			"bj":
				for k in 5: dealer.append(crect(t.dealer_card_pos(k), CARD))
			_:
				for k in 3: dealer.append(crect(t.dealer_card_pos(k), CARD))
		var d := dealer[0] as Rect2
		for r in dealer: d = d.merge(r)
		print("  dealer cards   ", fmt(d), "   gap below tray: %.1f" % (d.position.y - tray.end.y))
		for name in eq:
			var e: Rect2 = eq[name]
			var gap: float = minf(absf(e.position.x - d.end.x), absf(d.position.x - e.end.x))
			print("    %s clear of dealer cards: %s (x gap %.1f)" % [name, not e.intersects(d), gap])
		# One seat's column (the middle seat)
		var seat: int = t.seat_count() / 2
		var rows := []
		for spot in t.bet_spots() + ["play", "raise", "blind", "third", "fourth", "fifth"]:
			if spot in rows.map(func(x): return x[0]): continue
			var p: Vector2 = t.spot_pos(seat, spot)
			if spot == "play" and key in ["tcp", "uth"]:
				rows.append([spot, crect(p, Vector2(21, 12))])
			elif spot in ["play", "raise", "third", "fourth", "fifth", "blind"] and not (spot in t.bet_spots()):
				if (key == "hcf" and spot == "raise") or (key == "ms" and spot in ["third", "fourth", "fifth"]) or (key == "uth" and spot == "blind"):
					var rr: float = t.spot_radius(spot)
					rows.append([spot, crect(p, Vector2(rr, rr) * 2)])
			else:
				var r: float = t.spot_radius(spot)
				rows.append([spot, crect(p, Vector2(r, r) * 2)])
		if key == "bac":
			rows = rows.filter(func(x): return not x[0] in ["banker", "player"])
			for spot in ["banker", "player"]:
				rows.append([spot, crect(Vector2(t.seat_x(seat), t.BANKER_Y if spot == "banker" else t.PLAYER_Y), t.BOX)])
		var cards := []
		match key:
			"tcp": for k in 3: cards.append(crect(t.card_pos(seat, k), CARD))
			"ms", "uth": for k in 2: cards.append(crect(t.card_pos(seat, k), CARD))
			"lir": for k in 3: cards.append(crect(t.card_pos(seat, k), CARD))
			"hcf": for k in 7: cards.append(crect(t.card_pos(seat, k), CARD))
			"bj": for k in 2: cards.append(crect(t.card_pos(seat, 0, 1, k, 2), CARD))
			"pg":
				rows.append(["low box", crect(t.box_pos(seat, "low"), t.LOW_BOX)])
				rows.append(["high box", crect(t.box_pos(seat, "high"), t.HIGH_BOX)])
		if not cards.is_empty():
			var c := cards[0] as Rect2
			for r in cards: c = c.merge(r)
			rows.append(["CARDS", c])
		rows.sort_custom(func(a, b): return a[1].position.y < b[1].position.y)
		var title_y: float = t.TITLE_Y - 3.15
		print("  title centre y %.1f (approx %.1f..%.1f)" % [title_y, title_y - 3.4, title_y + 3.4])
		var last_end := title_y + 3.4
		for r in rows:
			var rect: Rect2 = r[1]
			print("    %-14s %s   gap above: %.1f   inside border: %s" % [r[0], fmt(rect), rect.position.y - last_end, inside(border, rect)])
			last_end = maxf(last_end, rect.end.y)
		print("  front border at y -5.0: last row gap to it %.1f" % (-5.0 - last_end))
		t.queue_free()
	if only == "" or only == "rou":
		await _audit_roulette()
	quit(0)


func _audit_roulette() -> void:
	var t = load("res://scenes/table/rou_table.tscn").instantiate()
	root.add_child(t)
	await process_frame
	var felt: PackedVector2Array = t.shape(-2.0, true, 24)   # 2 px in from the brass bead
	print("\n=== rou  seats ", t.seat_count())
	var wheel_r := 46.0
	var parts := {
		"wheel": crect(t.WHEEL_AT, Vector2(wheel_r, wheel_r) * 2),
		"float": t.tray_rect(),
		"chip hole": crect(t.HOLE_AT, Vector2(t.HOLE_R, t.HOLE_R) * 2),
		"title": crect(t.TITLE_AT + Vector2(0, 3), Vector2(80, 16)),
		"countdown": crect(t.countdown_pos(), Vector2(60, 6)),
		"layout": Rect2(Vector2(t.ZX, t.GY), Vector2(t.GX + 13 * t.BW - t.ZX, t.EY + t.EH - t.GY)),
	}
	for name in parts:
		var r: Rect2 = parts[name]
		var ok := inside(felt, r)
		if name in ["wheel", "chip hole"]:   # circles, not their boxes: every point of the rim on the felt
			var c: Vector2 = r.get_center()
			ok = true
			for k in 48:
				ok = ok and Geometry2D.is_point_in_polygon(c + Vector2.from_angle(k * TAU / 48) * r.size.x / 2, felt)
		print("  %-10s %s  on the felt: %s" % [name, fmt(r), ok])
	var names := parts.keys()
	for i in names.size():
		for j in range(i + 1, names.size()):
			if (parts[names[i]] as Rect2).intersects(parts[names[j]]) and not (names[i] == "wheel" and names[j] == "float"):
				print("  OVERLAP: %s and %s" % [names[i], names[j]])
	var sign_box := Rect2(t.get_node("Sign").position + Vector2(-17.6, -157.6), Vector2(35.2, 160))
	print("  sign       %s  clear of the table: %s" % [fmt(sign_box), not Geometry2D.intersect_polygons(t.shape(t.RAIL_W), PackedVector2Array([sign_box.position, Vector2(sign_box.end.x, sign_box.position.y), sign_box.end, Vector2(sign_box.position.x, sign_box.end.y)])).size() > 0])
	t.queue_free()
