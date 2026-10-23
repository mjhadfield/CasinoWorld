extends CanvasLayer
## Screen-space overlay. Walking: balance, jackpot, the "take a seat" prompt.
## Choosing a seat: a hint and Cancel. Seated: the betting bar (BettingBar: your balance,
## the table's chips, Ready, Undo/Rebet/Clear/Auto rebet, the game's decisions when you
## have one, the line saying what's happening), the table's name and jackpot, Paytable and Stand up.
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
var bar: BettingBar        # the seated controls
var sorter: HandSorter    # the Pai Gow hand sorter, over the bottom of the table
var settings_menu: SettingsMenu
var master: MasterPanel   # a Master Table's game menu, the card asking you to agree, the next game
var settings_button: Button
var _toast_tween: Tween
var _banner_tween: Tween


func _ready() -> void:
	show()  # always on in the game, even if it was hidden in the editor to see the floor
	# Every button in the HUD clicks, including ones built later (actions, the sorter's).
	get_tree().node_added.connect(_click_if_button)
	_click_all(self)
	bar = BettingBar.new()
	bar.hide()
	add_child(bar)
	move_child(bar, %MyHand.get_index())   # under the panels and dialogs, over the floor's prompts
	sorter = HandSorter.new()
	add_child(sorter)
	master = MasterPanel.new()
	add_child(master)
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
	add_child(PerfOverlay.new())
	move_child(settings_menu, -1)  # the panel opens over everything, its button included
	for n in [%InteractButton, %Toast, %Banner, %ChooseBar, %MyHand, %Paytable, %NamePrompt, %ConfirmStand, %TopUpButton]:
		n.hide()
	%InteractButton.pressed.connect(interact_pressed.emit)
	bar.chip_picked.connect(chip_selected.emit)
	bar.chip_picked.connect(func(v: int): selected_chip = v)
	bar.rebet_pressed.connect(rebet_pressed.emit)
	bar.auto_toggled.connect(auto_rebet_toggled.emit)
	bar.clear_pressed.connect(clear_pressed.emit)
	bar.undo_pressed.connect(undo_pressed.emit)
	bar.ready_pressed.connect(ready_pressed.emit)
	bar.action.connect(action.emit)
	bar.stand_pressed.connect(stand_pressed.emit)
	bar.paytable_toggled.connect(func(on): %Paytable.visible = on)
	%CancelChooseButton.pressed.connect(cancel_choose_pressed.emit)
	%TopUpButton.pressed.connect(func(): Net.send("top_up"))
	%ConfirmYes.pressed.connect(func():
		%ConfirmStand.hide()
		if _on_yes.is_valid():
			_on_yes.call()
		else:
			stand_confirmed.emit())
	%ConfirmNo.pressed.connect(%ConfirmStand.hide)
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
	bar.visible = mode == "seated"
	$TopBar.visible = mode != "slot" and mode != "seated"   # the bar has your balance; the slot screen its credit meter...
	settings_button.visible = mode != "slot"   # ...and its own Settings button
	if mode != "seated":
		sorter.close()
		master.close_all()
		%MyHand.hide()
		%Paytable.hide()
		bar.close_paytable()
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
	return %NamePrompt.visible or settings_menu.visible or master.menu_open()


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
## Called once when you sit: the bar's chips (in `design`, the table's chip style; {}: the game's own) and the
## paytable, from the server's rules.
func setup_table(rules: Dictionary, design := {}) -> void:
	var chips: Array = rules.get("chips", [100])
	selected_chip = int(chips[0])
	for value in chips:   # the smallest chip that covers the table minimum (Craps: £5)
		if int(value) >= int(rules.get("min_ante", 0)):
			selected_chip = int(value)
			break
	bar.set_chips(chips, selected_chip, design)
	var text := ""
	for section in rules.get("sections", []):
		text += "[b][color=#ecd396]%s[/color][/b]\n" % str(section.title).to_upper()
		for row in section.rows:
			text += "%s  [color=#cfe8d5]%s[/color]\n" % [row[0], row[1]]
		text += "\n"
	for note in rules.get("notes", []):
		text += "[i]%s[/i]\n" % note
	%Text.text = text


## Picks the bar's nth chip (keys 1-5); false if there isn't one.
func pick_chip(n: int) -> bool:
	var values: Array = bar.chip_values()
	if n < 0 or n >= values.size():
		return false
	bar.pick(int(values[n]))
	return true


## What the seated bar should offer right now (BettingBar.update_view).
func update_seated(s: Dictionary) -> void:
	bar.update_view(s)


## The Auto rebet switch as the server has it (flicking it asks the server; this echoes back).
func set_auto_rebet(on: bool) -> void:
	bar.set_auto(on)


## A round's result beside the balance in the bar.
func flash_result(net: int) -> void:
	bar.flash_result(net)


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
	bar.set_balance(Session.shown_balance - pending)
	%TopUpButton.visible = mode == "walking" and Session.balance < 200 and Session.balance > -1 and Session.player.size() > 0


func _set_status(online: bool) -> void:
	%Status.text = "Online" if online else "Connecting..."
	%Status.modulate = Color("7fd17f") if online else Color("e0a040")
	bar.set_online(online)
