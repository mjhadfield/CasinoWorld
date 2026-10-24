extends CanvasLayer
## Screen-space overlay. Top left, walking or seated: Settings, then your name and cash in hand (WalletPill: click
## it to switch character); top right: the minimap (Minimap, with Find and its guide under it).
## Walking: the interact prompt under your feet (Use ATM, Play) and the ATM itself (AtmPanel). Choosing a seat: a hint and Cancel. Seated: the betting bar (BettingBar: the
## table's name and seats, the table's chips, Ready/Repeat Bet, Undo/Clear/Auto rebet/Sit out, the game's decisions
## when you have one, the line saying what's happening), the table's jackpot if it has one, Paytable and Stand up.
## Before you're on the floor, the front door covers it all (FrontDoor: loading, the character select, the designer).
## The floor scene drives it (set_mode / update_seated) and listens to its signals.

signal interact_pressed
signal chip_selected(value: int)
signal rebet_pressed
signal auto_rebet_toggled(on: bool)
signal sit_out_toggled(on: bool)
signal clear_pressed
signal undo_pressed
signal ready_pressed
## One of the table's action buttons (its id, e.g. "play", "hit", "insure").
signal action(id: String)
signal stand_pressed
signal stand_confirmed
signal cancel_choose_pressed
## Your name and cash were clicked: the floor opens the character select to switch.
signal switch_pressed

var _on_yes := Callable()   # what the dialog's first button does when it's asking a question (else: stand up)
var mode := "walking"
var selected_chip := 100
var pending := 0  # your bets on the felt that haven't been taken from your balance yet
var bar: BettingBar        # the seated controls
var sorter: HandSorter    # the Pai Gow hand sorter, over the bottom of the table
var settings_menu: SettingsMenu
var atm: AtmPanel         # the lobby's cash machine, while you're using it
var prompt: BettingBar.BarButton   # walking: what E does here (Use ATM, Play), under your feet
var _prompt_feet := Vector2.ZERO   # where your feet are on screen (place_prompt)
var master: MasterPanel   # a Master Table's game menu, the card asking you to agree, the next game
var settings_button: BettingBar.BarButton
var wallet: WalletPill
var minimap: Minimap
var front_door: FrontDoor  # the loading screen, character select and designer: over the floor till you're on it
var barred: BarredScreen   # banned, timed out or removed by the casino: over everything
var _toast_tween: Tween
var _banner_tween: Tween


func _ready() -> void:
	show()  # always on in the game, even if it was hidden in the editor to see the floor
	# The HUD's text is MSDF, which needs linear filtering to draw crisp edges; the project default is nearest (for the
	# pixel-art floor). Every top-level piece gets it, including ones added later, unless it picked its own filter.
	child_entered_tree.connect(_smooth)
	for n in get_children():
		_smooth(n)
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
	prompt = BettingBar.BarButton.new()
	prompt.zoom = 0.5   # a betting-bar button at half size
	prompt.hide()
	prompt.pressed.connect(interact_pressed.emit)
	add_child(prompt)
	get_viewport().size_changed.connect(_place_prompt)
	atm = AtmPanel.new()
	add_child(atm)
	settings_menu = SettingsMenu.new()
	add_child(settings_menu)
	wallet = WalletPill.new()
	add_child(wallet)
	move_child(wallet, bar.get_index() + 1)
	minimap = Minimap.new()
	add_child(minimap)
	move_child(minimap, wallet.get_index() + 1)
	minimap.corner_changed.connect(_place_corners)
	settings_button = BettingBar.BarButton.new()
	settings_button.setup("Settings", "", "ghost", "settings")
	settings_button.compact = true   # just the cog, in a circle
	settings_button.tooltip_text = "Settings"
	settings_button.toggle_mode = true
	settings_button.pressed.connect(settings_menu.toggle)
	settings_menu.visibility_changed.connect(func():
		settings_button.set_pressed_no_signal(settings_menu.visible)
		settings_button.queue_redraw())
	add_child(settings_button)
	settings_button.resized.connect(_place_settings_button)
	get_viewport().size_changed.connect(_place_settings_button)
	_place_settings_button()
	add_child(PerfOverlay.new())
	move_child(settings_menu, -1)  # the panel opens over everything, its button included
	front_door = FrontDoor.new()
	add_child(front_door)   # over the settings panel (it's the whole screen until you're in)
	wallet.pressed.connect(switch_pressed.emit)
	barred = BarredScreen.new()
	add_child(barred)   # (last: over the front door too)
	for n in [%Toast, %Banner, %ChooseBar, %MyHand, %Paytable, %ConfirmStand]:
		n.hide()
	bar.chip_picked.connect(chip_selected.emit)
	bar.chip_picked.connect(func(v: int): selected_chip = v)
	bar.rebet_pressed.connect(rebet_pressed.emit)
	bar.auto_toggled.connect(auto_rebet_toggled.emit)
	bar.sit_out_toggled.connect(sit_out_toggled.emit)
	bar.clear_pressed.connect(clear_pressed.emit)
	bar.undo_pressed.connect(undo_pressed.emit)
	bar.ready_pressed.connect(ready_pressed.emit)
	bar.action.connect(action.emit)
	bar.stand_pressed.connect(stand_pressed.emit)
	bar.paytable_toggled.connect(func(on):
		if on:   # the rules open under the minimap: fold it out of their way
			Settings.set_value("minimap_collapsed", true)
		%Paytable.visible = on)
	%CancelChooseButton.pressed.connect(cancel_choose_pressed.emit)
	%ConfirmYes.pressed.connect(func():
		%ConfirmStand.hide()
		if _on_yes.is_valid():
			_on_yes.call()
		else:
			stand_confirmed.emit())
	%ConfirmNo.pressed.connect(%ConfirmStand.hide)
	Session.balance_changed.connect(func(_p): _refresh_balance())
	Session.joined.connect(func(p): wallet.set_player_name(p.get("name", "")))
	Net.connected.connect(func(): _set_status(true))
	Net.disconnected.connect(func(): _set_status(false))
	_set_status(Net.is_open())


## Top left, with your wallet to its right.
func _place_settings_button() -> void:
	var w := settings_button.get_combined_minimum_size().x
	settings_button.size = Vector2(w, 40)
	settings_button.position = BettingBar.CORNER_INSET
	wallet.position = BettingBar.CORNER_INSET + Vector2(w + 8.0, 0)


## Round the minimap, top right: the betting bar's Paytable to its left, the paytable itself under it.
func _place_corners() -> void:
	var w: float = minimap.corner_width()
	bar.right_inset = BettingBar.CORNER_INSET.x + (w + 8.0 if w > 0.0 else 0.0)
	%Paytable.offset_top = maxf(64.0, minimap.corner_bottom() + 8.0)


func _smooth(node: Node) -> void:
	if node is CanvasItem and node.get_parent() == self and node.texture_filter == CanvasItem.TEXTURE_FILTER_PARENT_NODE:
		node.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR


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
	wallet.visible = mode != "slot"   # the slot screen has its credit meter...
	settings_button.visible = mode != "slot"   # ...and its own Settings button
	minimap.set_mode(mode)
	if mode != "seated":
		sorter.close()
		master.close_all()
		%MyHand.hide()
		%Paytable.hide()
		bar.close_paytable()
		%ConfirmStand.hide()
		set_pending(0)
	if mode != "walking":
		prompt.hide()
		atm.close_atm()


func show_prompt(text: String) -> void:
	if mode == "walking":
		prompt.setup(text, "E", "primary")
		prompt.show()
		_place_prompt()


func hide_prompt() -> void:
	prompt.hide()


## The prompt centred just under your feet (`feet`, on screen), kept on screen.
func place_prompt(feet: Vector2) -> void:
	if feet != _prompt_feet:
		_prompt_feet = feet
		_place_prompt()


func _place_prompt() -> void:
	var w := prompt.get_combined_minimum_size()
	prompt.size = w
	var vp := get_viewport().get_visible_rect().size
	var at := Vector2(_prompt_feet.x - w.x / 2.0, _prompt_feet.y + 14.0)
	prompt.position = Vector2(round(clampf(at.x, 8.0, vp.x - 8.0 - w.x)), round(clampf(at.y, 8.0, vp.y - 8.0 - w.y)))


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


## True while a panel that takes the keyboard is open (the floor ignores game keys then).
func is_typing() -> bool:
	return front_door.visible or settings_menu.visible or master.menu_open() or atm.visible or barred.visible


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


func auto_rebet_on() -> bool:
	return bar.auto_on()


## The Sit out switch (the floor keeps it: it Readies you with no bets each time betting opens).
func set_sit_out(on: bool) -> void:
	bar.set_sit_out(on)


## A round's result beside the balance, top left.
func flash_result(net: int) -> void:
	wallet.flash_result(net)


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
	wallet.set_balance(Session.shown_balance - pending)


func _set_status(online: bool) -> void:
	wallet.set_online(online)
