class_name UiKit
## The HUD's popups in one place: the card they sit on, their title and text, and their buttons. Every popup (the
## Ask card, the Pai Gow sorter, the choose-a-seat bar, the paytable, the Master Table's cards) builds from these, so
## a restyle starts here. They're in the betting bar's look: its palette, Barlow Condensed and its BarButtons (the
## bar owns those; this is the one place popups reach for them).

const FONT := BettingBar.FONT
const INK := BettingBar.INK
const MUTED := BettingBar.MUTED
const BRASS := BettingBar.BRASS
const BRASS_HI := BettingBar.BRASS_HI
const WARN := BettingBar.WARN
const LOSS := BettingBar.LOSS
const CARD_BG := Color(0.04, 0.047, 0.05, 0.87)   # the Settings panel's colour, 10% more see-through
const CARD_EDGE := Color(BettingBar.BRASS, 0.55)
const CARD_RADIUS := 14
const CARD_PAD := Vector4(24, 16, 24, 18)
const SCRIM := Color(0.016, 0.02, 0.024, 0.45)   # over the screen behind a card that must be answered (as the ATM's)
const GAP := 14.0          # between a card's rows
const BUTTON_GAP := 10.0   # between a card's buttons
const TITLE_SIZE := 24
const TEXT_SIZE := 19


## A popup's card: near solid, a thin brass edge, lifted off the table by a soft shadow. `pad` overrides its margins.
static func card_style(pad := CARD_PAD) -> StyleBoxFlat:
	var s := BettingBar._box(CARD_BG, CARD_EDGE, CARD_RADIUS, pad)
	s.shadow_color = Color(0, 0, 0, 0.5)
	s.shadow_size = 18
	s.shadow_offset = Vector2(0, 6)
	return s


## A slimmer card for a bar or pill (the choose-a-seat bar, the Master Table's next game).
static func strip_style(radius := 12) -> StyleBoxFlat:
	return BettingBar._lifted(BettingBar._box(BettingBar.CORNER_BG, Color(BRASS, 0.45), radius, Vector4(16, 8, 10, 8)))


## Styles `panel` as a popup card and stops clicks going through it to the table.
static func make_card(panel: PanelContainer, pad := CARD_PAD) -> void:
	panel.add_theme_stylebox_override("panel", card_style(pad))
	panel.mouse_filter = Control.MOUSE_FILTER_STOP


## A card's column of rows.
static func column(parent: Control, gap := GAP) -> VBoxContainer:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", int(gap))
	parent.add_child(box)
	return box


## A centred row of buttons.
static func button_row(parent: Control) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", int(BUTTON_GAP))
	parent.add_child(row)
	return row


## A card's heading: brass, centred.
static func title(words := "", size := TITLE_SIZE) -> Label:
	var l := text(words, size, BRASS_HI)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	return l


## Small spaced capitals naming a part of a card (LOW, HIGH).
static func caption(words := "") -> Label:
	var l := text(words, 15, MUTED)
	var f := FontVariation.new()
	f.base_font = FONT
	f.spacing_glyph = 1
	l.add_theme_font_override("font", f)
	return l


## A line of popup text.
static func text(words := "", size := TEXT_SIZE, colour := INK) -> Label:
	var l := Label.new()
	l.text = words
	l.add_theme_font_override("font", FONT)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", colour)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


## A popup's button: the betting bar's, so they match (every button is the one "Lip" style: a raised face on a
## darker lip). `kind` is a BarButton kind: "primary" (the brass one, the answer most will pick), "normal", "quiet"
## (flat, no lip), "fold" (red: losing or deleting something), "ghost" (a smaller one). `key` is the key it answers
## to, shown in its box.
static func button(words: String, key := "", kind := "normal", glyph := "") -> BettingBar.BarButton:
	var b := BettingBar.BarButton.new()
	b.setup(words, key, kind, glyph)
	return b
