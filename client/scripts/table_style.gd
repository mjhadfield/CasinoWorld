class_name TableStyle
## How each card table looks: the table styles from the server (server/casino_server/table_styles.py, sent in
## the welcome and in `table_styles` when the admin page's Tables tab changes them). A style is a design --
## felt, rail, chip tray, printing, betting spots, Jackpot disc, shuffler, shoe, discard rack, card backs,
## chips -- and every card table uses the default (House) unless the server gives it another. Roulette and
## Craps don't take one (CasinoTable.styled()). Where anything sits never depends on the style.
##
## The pieces that draw it: StyledFelt (the table and its printing), ChipFace (chips), Card2D.draw_back,
## CardShuffler, CardShoe, DiscardRack and the Jackpot lights.

## House, as the server has it (table_styles.HOUSE): what a table shows before the welcome, and in the editor.
const HOUSE := {
	"felt": {"colour": "#93141f", "texture": "velvet", "vignette": 0.55},
	"border": "none", "led": "#9a7bff",
	"rail": {"wood": "mahogany", "armrest": "all", "leather": "#1b1a1a", "bead": "brass"},
	"tray": {"mode": "ledge", "finish": "wood"},
	"shuffler": "black", "shufflerTint": "#3a3e44", "shufflerWood": "match",
	"shoe": "acrylic", "shoeTint": "#141416", "shoeWood": "match",
	"rack": "wood", "rackTint": "#12305e", "rackWood": "match",
	"spots": "double",
	"print": {"font": "cinzel", "ink": "#f1e4c4", "accent": "#c9a24a"},
	"back": "emerald", "jackpot": "gold", "jackpotRim": "thin", "chips": "clay",
}

const WOODS := {
	"mahogany": preload("res://assets/tiles/table/wood_mahogany.jpg"),
	"walnut": preload("res://assets/tiles/table/wood_walnut.jpg"),
	"wenge": preload("res://assets/tiles/table/wood_wenge.jpg"),
	"rosewood": preload("res://assets/tiles/table/wood_rosewood.jpg"),
	"ebony": preload("res://assets/tiles/table/wood_ebony.jpg"),
}
## How many table units one tile of each wood covers.
const WOOD_TILE := {"mahogany": 58.0, "walnut": 52.0, "wenge": 46.0, "rosewood": 64.0, "ebony": 48.0}
## The grain shades: white where the scan is lighter, black where darker (tools/build_table_tiles.py).
const LEATHER := preload("res://assets/tiles/table/leather_shade.png")
const WEAVE := preload("res://assets/tiles/table/weave_shade.png")
const VELVET := preload("res://assets/tiles/table/velvet_shade.png")
const FONTS := {
	"cinzel": preload("res://assets/fonts/Cinzel-SemiBold.ttf"),
	"cormorant": preload("res://assets/fonts/CormorantSC-Bold.ttf"),
	"josefin": preload("res://assets/fonts/JosefinSans-SemiBold.ttf"),
	"montserrat": preload("res://assets/fonts/Montserrat-SemiBold.ttf"),
}
## The rail's bead where it meets the felt (and the metal ring chips): its colour and its highlight.
const BEADS := {"brass": [Color("c9a24a"), Color("f3d78e")], "gold": [Color("d9b453"), Color("fff0b8")],
	"chrome": [Color("aeb7bf"), Color("ffffff")]}
const JADE := Color("7fc8a9")   # the Baccarat Dragon circles, whatever the style

static var styles := {}        # style id -> {name, design, builtin}
static var tables := {}        # table id -> style id, where it isn't the default
static var default_id := "house"


## The table styles from the server: {styles, tables, default}.
static func configure(data: Dictionary) -> void:
	styles = data.get("styles", {})
	tables = data.get("tables", {})
	default_id = str(data.get("default", "house"))


## The design `table_id` is drawn in, everything filled in (a design saved before a choice existed takes House's).
static func design(table_id: String) -> Dictionary:
	var id: String = tables.get(table_id, default_id)
	var style: Dictionary = styles.get(id, styles.get(default_id, {}))
	return fill(style.get("design", {}))


static func fill(given: Dictionary) -> Dictionary:
	var out := HOUSE.duplicate(true)
	for key in given:
		if out.get(key) is Dictionary and given[key] is Dictionary:
			out[key] = (out[key] as Dictionary).merged(given[key], true)
		else:
			out[key] = given[key]
	return out


static func font(d: Dictionary) -> Font:
	return FONTS.get(d.print.font, FONTS.cinzel)


## A wood setting: "match" is the rail's own.
static func wood_of(d: Dictionary, pick: String) -> String:
	return pick if WOODS.has(pick) else str(d.rail.wood)


static func bead(d: Dictionary) -> Array:
	return BEADS.get(d.rail.bead, [])


static func colour(d: Dictionary, path: String) -> Color:
	var node: Variant = d
	for part in path.split("."):
		node = node[part]
	return Color(str(node))
