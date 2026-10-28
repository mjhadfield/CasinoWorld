class_name RoundSummary
extends PanelContainer
## Top left, under your wallet, while you're seated: the whole table's results for the last round (the round_end's
## `summary`; at Craps the come-out's after a seven-out, for the shooter's hand). Each player's net (a second box in
## with its player's), best first and yours in brass. At a card table, a player whose side bet, bonus or jackpot won
## gets their net bet by bet in small print under it, adding up; at Roulette and Craps the inside hits, hardways and
## props that won are listed there instead. It stays up while the next round's bets go down and fades as they close.
## Settings › Round summary turns it off.

const WIDTH := 290.0
const PAD := Vector4(18, 12, 18, 14)
const LINE_INDENT := 14.0
const LINE_SIZE := 13   # (a breakdown, smaller than the player's row above it)

var _column: VBoxContainer
var _tween: Tween


func _ready() -> void:
	UiKit.make_card(self, PAD)
	mouse_filter = MOUSE_FILTER_IGNORE   # (it's not a dialog: clicks go through to the table)
	custom_minimum_size.x = WIDTH
	_column = UiKit.column(self, 7.0)   # (between players; a player's lines sit close under them)
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
	for r in summary.rows:   # (one a player: a second box is in its player's)
		var player := UiKit.column(_column, 1.0)
		var me := int(r.seat) in mine
		_row(player, str(r.name), BettingBar.BRASS_HI if me else UiKit.INK, _net(int(r.net)), 18, 0.0)
		for b in r.get("lines", []):   # their breakdown (or wins), indented under them
			var amount := _net(int(b.amount))
			if b.get("jackpot", false):
				amount[1] = BettingBar.BRASS_HI
			_row(player, str(b.text), BettingBar.BRASS_HI if b.get("jackpot", false) else UiKit.MUTED, amount,
				LINE_SIZE, LINE_INDENT)
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


func _row(parent: Control, words: String, colour: Color, amount: Array, size: int, indent: float) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	row.mouse_filter = MOUSE_FILTER_IGNORE
	if indent > 0.0:
		var gap := Control.new()
		gap.custom_minimum_size.x = indent - 12.0   # (less the row's own separation)
		gap.mouse_filter = MOUSE_FILTER_IGNORE
		row.add_child(gap)
	var left := UiKit.text(words, size, colour)
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	left.custom_minimum_size.x = WIDTH - PAD.x - PAD.z - 80.0 - indent
	row.add_child(left)
	var right := UiKit.text(amount[0], size, amount[1])
	right.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	right.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	row.add_child(right)
	parent.add_child(row)
