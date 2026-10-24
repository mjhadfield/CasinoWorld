class_name AskPanel
extends Control
## A question with two answers on UiKit's card, centred over a dimmed screen: Play second box?, Stand up anyway?,
## a table's question when you sit. Enter picks the first answer, Esc the second; it takes every key while it's
## open, so nothing under it (the Pai Gow sorter, the floor) acts on one. The HUD opens it (HUD.ask).

## The first answer was picked.
signal yes

var _card: PanelContainer
var _text: Label
var _yes: BettingBar.BarButton
var _no: BettingBar.BarButton


func _ready() -> void:
	hide()
	set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	mouse_filter = MOUSE_FILTER_STOP   # (modal: the table under it can't be clicked)
	var scrim := ColorRect.new()
	scrim.color = UiKit.SCRIM
	scrim.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	scrim.mouse_filter = MOUSE_FILTER_IGNORE
	add_child(scrim)
	_card = PanelContainer.new()
	UiKit.make_card(_card)
	add_child(_card)
	var box := UiKit.column(_card, 18)
	_text = UiKit.text()
	_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_text.custom_minimum_size.x = 380
	box.add_child(_text)
	var row := UiKit.button_row(box)
	_yes = UiKit.button("Yes", "Enter", "primary")
	_yes.pressed.connect(func():
		hide()
		yes.emit())
	row.add_child(_yes)
	_no = UiKit.button("Cancel", "Esc", "normal")
	_no.pressed.connect(hide)
	row.add_child(_no)
	resized.connect(_place)


func ask(question: String, yes_words: String, no_words: String) -> void:
	_text.text = question
	_yes.setup(yes_words, "Enter", "primary")
	_no.setup(no_words, "Esc", "normal")
	show()
	_place.call_deferred()


## Centred, a little above the middle (clear of the betting bar).
func _place() -> void:
	_card.size = Vector2.ZERO
	_card.position = Vector2(round((size.x - _card.size.x) / 2.0), round(size.y * 0.42 - _card.size.y / 2.0))


func _unhandled_input(event: InputEvent) -> void:
	if not visible or not (event is InputEventKey and event.pressed):
		return
	if not event.echo:
		if event.keycode in [KEY_ENTER, KEY_KP_ENTER]:
			_yes.pressed.emit()
		elif event.is_action_pressed("cancel"):
			_no.pressed.emit()
	get_viewport().set_input_as_handled()
