class_name RoundSummary
extends PanelContainer
## Top left, under your wallet, while you're seated: the whole table's results for the last round (the round_end's
## `summary`; at Craps the come-out's after a seven-out, for the shooter's hand). Each player's net, best first and
## yours in brass, then the side bets, bonuses and jackpots that paid (Roulette: the inside bets that hit). It stays up
## while the next round's bets go down and fades as they close. Settings › Round summary turns it off.

const WIDTH := 290.0
const PAD := Vector4(18, 12, 18, 14)

var _column: VBoxContainer
var _tween: Tween


func _ready() -> void:
	UiKit.make_card(self, PAD)
	mouse_filter = MOUSE_FILTER_IGNORE   # (it's not a dialog: clicks go through to the table)
	custom_minimum_size.x = WIDTH
	_column = UiKit.column(self, 5.0)
	hide()
	Settings.changed.connect(func(key: String, on):
		if key == "show_round_summary" and not on:
			clear())


## Shows a round's summary; `mine` are your seats (yours and a second box), whose rows are picked out.
func show_summary(summary: Dictionary, mine: Array) -> void:
	if not Settings.value("show_round_summary") or summary.get("rows", []).is_empty():
		return
	for c in _column.get_children():
		_column.remove_child(c)
		c.queue_free()
	_column.add_child(UiKit.caption(str(summary.get("title", "")).to_upper()))
	for r in summary.rows:
		var me := int(r.seat) in mine
		var who := str(r.name) + (" · box 2" if r.get("box", false) else "")
		_row(who, BettingBar.BRASS_HI if me else UiKit.INK, _net(int(r.net)), 18)
	var lights: Array = summary.get("highlights", [])
	if not lights.is_empty():
		var rule := ColorRect.new()
		rule.color = Color(UiKit.BRASS, 0.3)
		rule.custom_minimum_size.y = 1
		rule.mouse_filter = MOUSE_FILTER_IGNORE
		_column.add_child(rule)
		for h in lights:
			var colour := BettingBar.BRASS_HI if h.get("jackpot", false) else UiKit.INK
			_row("%s — %s" % [h.name, h.text], colour, ["+" + Money.format(int(h.amount), true), colour if h.get("jackpot", false) else BettingBar.WIN], 16)
	reset_size()
	if _tween:
		_tween.kill()
	modulate.a = 0.0
	show()
	_tween = create_tween()
	_tween.tween_property(self, "modulate:a", 1.0, 0.25)


## The next round's bets have closed: it fades away.
func fade() -> void:
	if not visible:
		return
	if _tween:
		_tween.kill()
	_tween = create_tween()
	_tween.tween_property(self, "modulate:a", 0.0, 0.4)
	_tween.tween_callback(hide)


## Gone at once (you've left the table).
func clear() -> void:
	if _tween:
		_tween.kill()
	hide()


## A net as the wallet flashes it: green for a win, red for a loss; "Even" for neither.
func _net(net: int) -> Array:
	if net == 0:
		return ["Even", UiKit.MUTED]
	return [("+" if net > 0 else "−") + Money.format(absi(net), true), BettingBar.WIN if net > 0 else BettingBar.LOSS]


func _row(words: String, colour: Color, amount: Array, size: int) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	row.mouse_filter = MOUSE_FILTER_IGNORE
	var left := UiKit.text(words, size, colour)
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	left.custom_minimum_size.x = WIDTH - PAD.x - PAD.z - 80.0
	row.add_child(left)
	var right := UiKit.text(amount[0], size, amount[1])
	right.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	right.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	row.add_child(right)
	_column.add_child(row)
