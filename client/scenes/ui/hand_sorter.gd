class_name HandSorter
extends PanelContainer
## The Pai Gow hand sorter: your seven cards, picked up off the felt and shown
## large in a panel over the bottom of the table, where you set them into a
## 2-card LOW hand and a 5-card HIGH hand before they go back down.
##
## The cards arrive in the order you'd pick them up -- unsorted. Tap a card to
## move it between the rows (or press 1-7) and it glides across; Sort (S) puts
## both rows in order.
## The panel names both hands as you go and warns when the High hand doesn't
## beat the Low (a foul), asking the server (pg_check) so it uses the real
## Joker and House Way rules. House Way (H) asks the server for the House Way
## split (pg_suggest); Set hand (Enter) sends it (set_hand); at Face Up Pai Gow
## there's Fold too. The table closes the panel once your hand is set -- by
## you, or by House Way if time runs out.
##
## After a Face Up dealer Ace-high Pai Gow nobody sets a hand: the panel shows
## your seven cards with one button -- Claim bonus if they win a side bet,
## otherwise Fold (open_claim).
##
## Built from UiKit, like the HUD's other popups.

const CARD_SIZE := Vector2(66, 94)
const SLIDE_TIME := 0.22   # a card moving between the rows (or re-sorted) glides this long

var _low: Array = []      # card codes in the Low hand (up to 2)
var _high: Array = []     # the rest
var _order: Array = []    # the seven in their dealt order (for the 1-7 keys)
var _face_up := false
var look := {}            # the table's style, for the cards' fronts (Card2D.paint)
var _sent := false
var _claim_mode := false
var _bonus = null         # claim mode: the side-bet hand you can claim, or null
var _title: Label
var _low_row: HBoxContainer
var _high_row: HBoxContainer
var _low_label: Label
var _high_label: Label
var _warning: Label
var _set_button: BettingBar.BarButton
var _fold_button: BettingBar.BarButton
var _house_button: BettingBar.BarButton
var _sort_button: BettingBar.BarButton
var _claim_button: BettingBar.BarButton


func _ready() -> void:
	hide()
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR  # smooth text and edges on the big cards
	UiKit.make_card(self, Vector4(22, 14, 22, 16))
	get_viewport().size_changed.connect(_place)
	var box := UiKit.column(self, 6)
	_title = UiKit.title()
	box.add_child(_title)
	_low_label = _row_label(box)
	_low_row = _row(box)
	_high_label = _row_label(box)
	_high_row = _row(box)
	_warning = UiKit.text("", 17, UiKit.LOSS)
	_warning.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(_warning)
	var buttons := UiKit.button_row(box)
	_sort_button = _button(buttons, "Sort", "S", "quiet")
	_sort_button.pressed.connect(_sort_rows)
	_house_button = _button(buttons, "House Way", "H", "quiet")
	_house_button.pressed.connect(func(): Net.send("pg_suggest"))
	_set_button = _button(buttons, "Set hand", "Enter", "primary")
	_set_button.pressed.connect(_submit)
	_fold_button = _button(buttons, "Fold", "", "fold")
	_fold_button.pressed.connect(func():
		if not _sent:
			_sent = true
			Net.send("fold"))
	_claim_button = _button(buttons, "Claim bonus", "Enter", "primary")
	_claim_button.pressed.connect(func():
		if not _sent:
			_sent = true
			Net.send("claim"))


func _row_label(parent: Control) -> Label:
	var label := UiKit.caption()
	parent.add_child(label)
	return label


func _row(parent: Control) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 8)
	row.custom_minimum_size = Vector2(5 * (CARD_SIZE.x + 8) + 2 * (CARD_SIZE.x + 8), CARD_SIZE.y)
	parent.add_child(row)
	return row


func _button(parent: Control, words: String, key: String, kind: String) -> BettingBar.BarButton:
	var b := UiKit.button(words, key, kind)
	parent.add_child(b)
	return b


# ------------------------------------------------------------------ open / close
func open(cards: Array, face_up: bool) -> void:
	_order = cards.duplicate()
	_order.shuffle()  # as you'd pick them up: in no particular order
	_low = []
	_high = _order.duplicate()
	_face_up = face_up
	_sent = false
	_claim_mode = false
	_title.text = "Set your hand: two cards Low, five High"
	for b in [_sort_button, _house_button, _set_button]:
		b.visible = true
	_fold_button.setup("Fold", "", "fold")
	_fold_button.visible = face_up
	_claim_button.visible = false
	_low_row.visible = true
	_refresh()
	show()
	_place.call_deferred()


## After a Face Up dealer Ace-high Pai Gow: your seven cards, and one button --
## Claim bonus (it shows them and the side bet's paid) or Fold.
func open_claim(cards: Array, bonus) -> void:
	_order = cards.duplicate()
	_claim_mode = true
	_bonus = bonus
	_sent = false
	_low = []
	_high = _sorted(cards)
	_title.text = "Dealer has an Ace-high Pai Gow -- every Ante pushes"
	for b in [_sort_button, _house_button, _set_button]:
		b.visible = false
	_claim_button.visible = bonus != null
	_fold_button.visible = bonus == null
	_fold_button.setup("Fold", "Enter", "fold")
	_low_row.visible = false
	_low_label.text = ("Your hand makes %s -- claim your bonus." % bonus) if bonus != null else "No bonus in your hand."
	_high_label.text = ""
	_warning.text = ""
	_fill(_high_row, _high, 7)
	show()
	_place.call_deferred()


func close() -> void:
	hide()


## Centred over the bottom of the screen, just above the seated bar.
func _place() -> void:
	if not visible:
		return
	reset_size()
	var screen := get_viewport().get_visible_rect().size
	var hud := get_parent()   # (over the bottom of the table, clear of the betting bar)
	var bar_h: float = screen.y - hud.bar.bar_top if hud and "bar" in hud and hud.bar.bar_top > 0 else 170.0
	position = Vector2((screen.x - size.x) / 2, screen.y - size.y - bar_h - 6)


## The server turned the hand down (it shouldn't happen -- Set is only offered
## for a legal split): let the player try again.
func open_again() -> void:
	if _sent:
		_sent = false
		_set_button.disabled = not (_low.size() == 2 and _high.size() == 5)


func is_open() -> bool:
	return visible


# ------------------------------------------------------------------ the server's answers
func on_suggest(msg: Dictionary) -> void:
	if not visible or _claim_mode:
		return
	_low = _sorted(msg.front)
	_high = _sorted(msg.back)
	_refresh()


func on_check(msg: Dictionary) -> void:
	if not visible or _claim_mode or msg.front != _low or msg.back != _high:
		return  # an answer about a split that's since changed
	_low_label.text = "LOW" + ("  ·  " + msg.front_label if msg.front_label != "" else "")
	_high_label.text = "HIGH" + ("  ·  " + msg.back_label if msg.back_label != "" else "")
	_warning.text = "Foul: your High hand has to beat your Low hand." if msg.foul else ""
	_set_button.disabled = msg.foul or _sent


# ------------------------------------------------------------------ sorting
func _move(code: String) -> void:
	if _sent or _claim_mode:
		return
	if code in _low:
		_low.erase(code)
		_high.append(code)
	elif _low.size() < 2:
		_high.erase(code)
		_low.append(code)
	else:  # Low is full: this card swaps with the last one put there
		var back: String = _low.pop_back()
		_high[_high.find(code)] = back
		_low.append(code)
	_refresh()


## Both rows in order, high to low (the Joker first).
func _sort_rows() -> void:
	if _sent or _claim_mode:
		return
	_low = _sorted(_low)
	_high = _sorted(_high)
	_refresh()


func _refresh() -> void:
	var was := _card_positions()
	_fill(_low_row, _low, 2)
	_fill(_high_row, _high, 5)
	_slide_from.call_deferred(was)  # once the rows have laid the new cards out
	var ready := _low.size() == 2 and _high.size() == 5
	_low_label.text = "LOW  (tap two cards to move them here)" if _low.is_empty() else "LOW"
	_high_label.text = "HIGH"
	_warning.text = ""
	_set_button.disabled = not ready or _sent
	if not _low.is_empty():
		Net.send("pg_check", {"front": _low, "back": _high})


## Where each card is on screen right now (mid-slide included).
func _card_positions() -> Dictionary:
	var at := {}
	for row in [_low_row, _high_row]:
		for card in row.get_children():
			if card.code != "":
				at[card.code] = card.global_position + card.slide
	return at


## Each card that's changed place glides there from where it was, over the others.
func _slide_from(was: Dictionary) -> void:
	for row in [_low_row, _high_row]:
		for card in row.get_children():
			if not was.has(card.code):
				continue
			var offset: Vector2 = was[card.code] - card.global_position
			if offset.length() < 1.0:
				continue
			card.slide = offset
			card.z_index = 2 if row == _low_row else 1  # cards going up pass over the High row
			var tween: Tween = card.create_tween().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
			tween.tween_property(card, "slide", Vector2.ZERO, SLIDE_TIME)
			tween.tween_callback(func(): card.z_index = 0)


func _fill(row: HBoxContainer, codes: Array, slots: int) -> void:
	for child in row.get_children():
		row.remove_child(child)  # out of the row now, so it lays out only the new cards
		child.queue_free()
	for code in codes:
		var card := SortCard.new()
		card.code = code
		card.look = look
		card.custom_minimum_size = CARD_SIZE
		card.key = 0 if _claim_mode else _order.find(code) + 1
		card.pressed.connect(_move.bind(code))
		row.add_child(card)
	for i in maxi(0, slots - codes.size()):  # empty places still to fill
		var empty := SortCard.new()
		empty.custom_minimum_size = CARD_SIZE
		row.add_child(empty)


func _submit() -> void:
	if _sent or _set_button.disabled:
		return
	_sent = true
	_set_button.disabled = true
	Net.send("set_hand", {"front": _low, "back": _high})


func _sorted(codes: Array) -> Array:
	var out := codes.duplicate()
	out.sort_custom(func(a, b): return _rank(a) > _rank(b))
	return out


static func _rank(code: String) -> int:
	return Card2D.rank_value(code)


func _unhandled_input(event: InputEvent) -> void:
	if not visible or not (event is InputEventKey and event.pressed and not event.echo):
		return
	if event.keycode in [KEY_ENTER, KEY_KP_ENTER]:
		if _claim_mode:
			(_claim_button if _bonus != null else _fold_button).pressed.emit()
		else:
			_submit()
		get_viewport().set_input_as_handled()
	elif _claim_mode:
		return
	elif event.keycode == KEY_S:
		_sort_rows()
		get_viewport().set_input_as_handled()
	elif event.keycode == KEY_H and not _sent:
		Net.send("pg_suggest")
		get_viewport().set_input_as_handled()
	elif event.keycode >= KEY_1 and event.keycode <= KEY_7:
		var i: int = event.keycode - KEY_1
		if i < _order.size():
			_move(_order[i])
		get_viewport().set_input_as_handled()


## One big card in the sorter (or an empty place for one).
class SortCard extends Control:
	signal pressed
	var code := ""
	var key := 0
	var look := {}
	var slide := Vector2.ZERO:  # drawn this far from its place while gliding into it
		set(v):
			slide = v
			queue_redraw()
	var _hover := false

	func _ready() -> void:
		mouse_filter = MOUSE_FILTER_STOP if code != "" else MOUSE_FILTER_IGNORE
		mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		mouse_entered.connect(func():
			_hover = true
			queue_redraw())
		mouse_exited.connect(func():
			_hover = false
			queue_redraw())

	func _gui_input(event: InputEvent) -> void:
		if code != "" and event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			pressed.emit()
			accept_event()

	func _draw() -> void:
		if code == "":
			draw_style_box(BettingBar._box(Color(1, 1, 1, 0.03), Color(UiKit.BRASS, 0.35), 6, Vector4.ZERO), Rect2(Vector2.ZERO, size))
			return
		var s := size.x / Card2D.SIZE.x
		var lift := (Vector2(0, -6) if _hover and slide == Vector2.ZERO else Vector2.ZERO) + slide
		Card2D.paint(self, code, Transform2D(0.0, Vector2(s, s), 0.0, size / 2 + lift), look)
		if _hover:
			draw_style_box(BettingBar._box(Color(0, 0, 0, 0), UiKit.BRASS_HI, 6, Vector4.ZERO), Rect2(lift, size).grow(1.0))
