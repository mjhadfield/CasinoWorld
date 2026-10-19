extends CanvasLayer
## Screen-space overlay. Walking: balance, jackpot, the "take a seat" prompt.
## Choosing a seat: a hint and Cancel. Seated: chip tray, Rebet/Auto rebet/Clear/Ready,
## the game's own action buttons when you have a decision (Play/Fold at Three
## Card Poker; Hit/Stand/Double/Split and Insurance at Blackjack), the
## countdown, paytable and Stand up.
## The floor scene drives it (set_mode / update_seated) and listens to its signals.

signal interact_pressed
signal chip_selected(value: int)
signal rebet_pressed
signal auto_rebet_toggled(on: bool)
signal clear_pressed
signal undo_pressed
signal ready_pressed
## One of the table's action buttons (its id, e.g. "play", "hit", "insure").
signal action(id: String)
signal stand_pressed
signal stand_confirmed
signal cancel_choose_pressed
signal name_entered(name: String)

var _on_yes := Callable()   # what the dialog's first button does when it's asking a question (else: stand up)
var mode := "walking"
var selected_chip := 100
var pending := 0  # your bets on the felt that haven't been taken from your balance yet
var _actions_shown := []  # the action list the buttons were built from
var sorter: HandSorter    # the Pai Gow hand sorter, over the bottom of the table
var settings_menu: SettingsMenu
var settings_button: Button
var _toast_tween: Tween
var _banner_tween: Tween


func _ready() -> void:
	show()  # always on in the game, even if it was hidden in the editor to see the floor
	# Every button in the HUD clicks, including ones built later (actions, the sorter's).
	get_tree().node_added.connect(_click_if_button)
	_click_all(self)
	sorter = HandSorter.new()
	add_child(sorter)
	settings_menu = SettingsMenu.new()
	add_child(settings_menu)
	settings_button = Button.new()
	settings_button.text = "Settings"
	settings_button.focus_mode = Control.FOCUS_NONE
	settings_button.add_theme_font_size_override("font_size", 16)
	settings_button.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	settings_button.offset_left = -112
	settings_button.offset_right = -12
	settings_button.offset_top = 12
	settings_button.offset_bottom = 52
	settings_button.pressed.connect(settings_menu.toggle)
	add_child(settings_button)
	move_child(settings_menu, -1)  # the panel opens over everything, its button included
	for n in [%InteractButton, %Toast, %Banner, %ChooseBar, %SeatedBar, %MyHand, %Paytable, %NamePrompt, %ConfirmStand, %TopUpButton]:
		n.hide()
	%InteractButton.pressed.connect(interact_pressed.emit)
	%RebetButton.pressed.connect(rebet_pressed.emit)
	%AutoRebetCheck.toggled.connect(auto_rebet_toggled.emit)
	%ClearButton.pressed.connect(clear_pressed.emit)
	%UndoButton.pressed.connect(undo_pressed.emit)
	%ReadyButton.pressed.connect(ready_pressed.emit)
	%StandButton.pressed.connect(stand_pressed.emit)
	%CancelChooseButton.pressed.connect(cancel_choose_pressed.emit)
	%PaytableButton.toggled.connect(func(on): %Paytable.visible = on)
	%TopUpButton.pressed.connect(func(): Net.send("top_up"))
	%ConfirmYes.pressed.connect(func():
		%ConfirmStand.hide()
		if _on_yes.is_valid():
			_on_yes.call()
		else:
			stand_confirmed.emit())
	%ConfirmNo.pressed.connect(%ConfirmStand.hide)
	%Info.max_lines_visible = 2           # with a lot of buttons it wraps; it mustn't grow the bar
	%Info.custom_minimum_size.x = 180
	%NameOk.pressed.connect(_submit_name)
	%NameEdit.text_submitted.connect(func(_t): _submit_name())
	Session.balance_changed.connect(func(_p): _refresh_balance())
	Session.joined.connect(func(p): %PlayerName.text = p.get("name", ""))
	Net.connected.connect(func(): _set_status(true))
	Net.disconnected.connect(func(): _set_status(false))
	_set_status(Net.is_open())


func _process(_delta: float) -> void:
	var amount := Session.jackpot_now()
	%Jackpot.text = ("Jackpot " + Money.format(int(amount))) if amount > 0 else ""


func _click_if_button(node: Node) -> void:
	if node is BaseButton and is_ancestor_of(node) and not node.has_meta("clicks"):
		node.set_meta("clicks", true)
		node.pressed.connect(Sfx.play.bind("click"))


func _click_all(node: Node) -> void:
	for child in node.get_children():
		_click_if_button(child)
		_click_all(child)


## The slot machines' full-screen game: over the floor and the HUD's bars, under the
## toasts, the banner and the Settings panel.
func add_slot_screen(screen: Control) -> void:
	add_child(screen)
	move_child(screen, sorter.get_index() + 1)
	for n in [%Toast, %Banner]:
		move_child(n, screen.get_index() + 1)


# ------------------------------------------------------------------ modes
func set_mode(new_mode: String) -> void:
	mode = new_mode
	%ChooseBar.visible = mode == "choosing"
	%SeatedBar.visible = mode == "seated"
	$TopBar.visible = mode != "slot"   # the slot screen has its own credit meter...
	settings_button.visible = mode != "slot"   # ...and its own Settings button
	if mode != "seated":
		sorter.close()
		%MyHand.hide()
		%Paytable.hide()
		%PaytableButton.button_pressed = false
		%ConfirmStand.hide()
		set_pending(0)
	if mode != "walking":
		%InteractButton.hide()


func show_prompt(text: String) -> void:
	if mode == "walking":
		%InteractButton.text = text
		%InteractButton.show()


func hide_prompt() -> void:
	%InteractButton.hide()


func show_toast(text: String, seconds := 2.8) -> void:
	%Toast.text = text
	%Toast.modulate.a = 1.0
	%Toast.show()
	if _toast_tween:
		_toast_tween.kill()
	_toast_tween = create_tween()
	_toast_tween.tween_interval(seconds)
	_toast_tween.tween_property(%Toast, "modulate:a", 0.0, 0.6)
	_toast_tween.tween_callback(%Toast.hide)


func show_banner(text: String) -> void:
	%Banner.text = text
	%Banner.show()
	%Banner.modulate.a = 1.0
	%Banner.scale = Vector2.ONE
	if _banner_tween:
		_banner_tween.kill()
	_banner_tween = create_tween()
	_banner_tween.tween_interval(3.5)
	_banner_tween.tween_property(%Banner, "modulate:a", 0.0, 0.8)
	_banner_tween.tween_callback(%Banner.hide)


func show_name_prompt(current := "") -> void:
	if %NamePrompt.visible:
		return  # (a resync's welcome: keep what's being typed)
	%NameEdit.text = "" if current.begins_with("Guest") else current
	%NamePrompt.show()
	%NameEdit.grab_focus()


## True while a panel that takes the keyboard is open (the floor ignores game keys then).
func is_typing() -> bool:
	return %NamePrompt.visible or settings_menu.visible


func confirm_stand(text := "You're in this hand -- standing up folds it. Stand up anyway?") -> void:
	_on_yes = Callable()
	%ConfirmText.text = text
	%ConfirmYes.text = "Stand up"
	%ConfirmNo.text = "Stay"
	%ConfirmStand.show()


## A question with two answers in the same panel: `on_yes` runs if they pick the first.
func ask(text: String, yes: String, no: String, on_yes: Callable) -> void:
	_on_yes = on_yes
	%ConfirmText.text = text
	%ConfirmYes.text = yes
	%ConfirmNo.text = no
	%ConfirmStand.show()


func _submit_name() -> void:
	var text: String = %NameEdit.text.strip_edges()
	if text == "":
		return
	%NamePrompt.hide()
	name_entered.emit(text)


# ------------------------------------------------------------------ seated
## Called once when you sit: builds the chip tray and paytable from the server's rules.
func setup_table(rules: Dictionary) -> void:
	for child in %ChipTray.get_children():
		child.queue_free()
	for value in rules.get("chips", [100]):
		var chip := ChipButton.new()
		chip.value = int(value)
		chip.custom_minimum_size = Vector2(54, 54)
		chip.pressed.connect(_on_chip.bind(int(value)))
		%ChipTray.add_child(chip)
	selected_chip = int(rules.get("chips", [100])[0])
	for value in rules.get("chips", []):   # the smallest chip that covers the table minimum (Craps: £5)
		if int(value) >= int(rules.get("min_ante", 0)):
			selected_chip = int(value)
			break
	_mark_chips()
	var text := ""
	for section in rules.get("sections", []):
		text += "[b][color=#ffd54a]%s[/color][/b]\n" % str(section.title).to_upper()
		for row in section.rows:
			text += "%s  [color=#cfe8d5]%s[/color]\n" % [row[0], row[1]]
		text += "\n"
	for note in rules.get("notes", []):
		text += "[i]%s[/i]\n" % note
	%Text.text = text


func _on_chip(value: int) -> void:
	selected_chip = value
	_mark_chips()
	chip_selected.emit(value)


func _mark_chips() -> void:
	for chip in %ChipTray.get_children():
		chip.selected = chip.value == selected_chip


## What the seated bar should offer right now. Keys: can_bet, has_bets,
## can_rebet, is_ready, my_turn, actions ([{id, label, key}]), info.
func update_seated(s: Dictionary) -> void:
	var can_bet: bool = s.get("can_bet", false)
	var my_turn: bool = s.get("my_turn", false)
	for chip in %ChipTray.get_children():
		chip.disabled = not can_bet
	%RebetButton.visible = not my_turn
	%AutoRebetCheck.visible = not my_turn
	%ClearButton.visible = not my_turn
	%UndoButton.visible = not my_turn
	%ReadyButton.visible = not my_turn
	_show_actions(s.get("actions", []))
	%RebetButton.disabled = not (can_bet and s.get("can_rebet", false) and not s.get("has_bets", false))
	%ClearButton.disabled = not (can_bet and s.get("has_bets", false))
	%UndoButton.disabled = not s.get("can_undo", false)
	%ReadyButton.disabled = not s.get("can_ready", can_bet)
	%ReadyButton.text = "Ready  [Space]" if s.get("has_bets", false) else "Sit out"
	%Info.text = s.get("info", "")
	var hide: Array = s.get("hide", [])   # buttons this table doesn't use (Craps: no Ready or Rebet)
	%ReadyButton.visible = %ReadyButton.visible and not "ready" in hide
	%RebetButton.visible = %RebetButton.visible and not "rebet" in hide
	%AutoRebetCheck.visible = %AutoRebetCheck.visible and not "auto_rebet" in hide


## The Auto rebet box as the server has it (ticking it asks the server; this echoes back).
func set_auto_rebet(on: bool) -> void:
	%AutoRebetCheck.set_pressed_no_signal(on)


## Rebuilds the action buttons only when what's on offer changes.
func _show_actions(actions: Array) -> void:
	if actions == _actions_shown:
		return
	_actions_shown = actions.duplicate(true)
	for child in %Actions.get_children():
		child.queue_free()
	for a in actions:
		var button := Button.new()
		button.text = a.label
		button.custom_minimum_size = Vector2(110, 50)
		button.focus_mode = Control.FOCUS_NONE
		button.add_theme_font_size_override("font_size", 18)
		if a.has("pressed"):   # an on/off setting (Craps: Working)
			button.toggle_mode = true
			button.set_pressed_no_signal(bool(a.pressed))
		button.pressed.connect(action.emit.bind(str(a.id)))
		%Actions.add_child(button)


func show_my_hand(cards: Array, hand: String) -> void:
	var views: Array = %Cards.get_children()
	for i in views.size():
		views[i].code = ""
		views[i].show_card(cards[i] if i < cards.size() else "", i * 0.1)
	%HandName.text = hand
	%MyHand.show()


func clear_my_hand() -> void:
	%MyHand.hide()
	for view in %Cards.get_children():
		view.show_card("")


func set_pending(pence: int) -> void:
	pending = pence
	_refresh_balance()


func _refresh_balance() -> void:
	%Balance.text = Money.format(Session.shown_balance - pending)
	%TopUpButton.visible = mode == "walking" and Session.balance < 200 and Session.balance > -1 and Session.player.size() > 0


func _set_status(online: bool) -> void:
	%Status.text = "Online" if online else "Connecting..."
	%Status.modulate = Color("7fd17f") if online else Color("e0a040")
