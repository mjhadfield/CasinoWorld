class_name TableStyle
## How each table looks: the table styles from the server (server/casino_server/table_styles.py, sent in
## the welcome and in `table_styles` when the admin page's Tables tab changes them). There are three kinds,
## each with its own styles and default (House): "cards" (felt, rail, chip tray, printing, betting spots,
## Jackpot disc, shuffler, shoe, discard rack, card backs, chips), "roulette" (felt, rail, printing, number
## colours, float, wheel) and "craps" (felt, rail, printing, rubber, chip rack, dice). A table uses its kind's
## default unless the server gives it another (CasinoTable.style_kind()). Where anything sits never depends on
## the style.
##
## The pieces that draw it: StyledFelt (the table and its printing, Roulette's and Craps' too), ChipFace
## (chips), Card2D.draw_back, CardShuffler, CardShoe, DiscardRack, the Jackpot lights, RouletteWheel and CrapsDice.

## House, as the server has it (table_styles.HOUSE): what a table shows before the welcome, and in the editor.
const HOUSE := {
	"felt": {"colour": "#93141f", "texture": "weave", "vignette": 0.95},
	"border": "led", "led": "#ffd28a",
	"rail": {"wood": "rosewood", "armrest": "all", "leather": "#1b1a1a", "bead": "gold"},
	"tray": {"mode": "ledge", "finish": "wood"},
	"shuffler": "black", "shufflerTint": "#cfccc4", "shufflerWood": "match",
	"shoe": "wood", "shoeTint": "#141416", "shoeWood": "match",
	"rack": "wood", "rackTint": "#12305e", "rackWood": "match",
	"spots": "deco",
	"print": {"font": "cinzel", "ink": "#f1e4c4", "primary": "#f1e4c4", "side": "#c9a24a", "accent": "#c9a24a"},
	"back": "lattice", "jackpot": "led", "jackpotRim": "thin", "chips": "clay",
}
## Roulette's and Craps' House (table_styles.ROULETTE_HOUSE, CRAPS_HOUSE): how they looked before they took styles.
const ROULETTE_HOUSE := {
	"felt": {"colour": "#93141f", "texture": "grain", "vignette": 0.3},
	"border": "none", "led": "#ffd28a",
	"rail": {"wood": "mahogany", "armrest": "none", "leather": "#2a140a", "bead": "brass"},
	"print": {"font": "cinzel", "ink": "#f1e4c4", "accent": "#c9a24a"},
	"numbers": {"red": "#e0453d", "black": "#1a0d0b", "zero": "#1f8a52"},
	"float": "wood",
	"wheel": {"wood": "match", "metal": "brass"},
}
const CRAPS_HOUSE := {
	"felt": {"colour": "#93141f", "texture": "grain", "vignette": 0.3},
	"rail": {"wood": "mahogany", "armrest": "dealer", "leather": "#2a140a", "bead": "brass"},
	"print": {"font": "cinzel", "ink": "#f1e4c4", "accent": "#f2cf6a", "red": "#e0453d"},
	"rubber": "#1b1413",
	"rack": "wood",
	"dice": "red",
}
const HOUSES := {"cards": HOUSE, "roulette": ROULETTE_HOUSE, "craps": CRAPS_HOUSE}

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
## The roulette wheel's bowl in each wood (its track, floor and cone are shades of it).
const WHEEL_WOODS := {"mahogany": Color("4e2814"), "walnut": Color("4a3222"), "wenge": Color("302520"),
	"rosewood": Color("4c1f17"), "ebony": Color("1c1917")}
## The craps dice: their lit and shaded sides.
const DICE := {"red": [Color("f04a4f"), Color("a5101a")], "green": [Color("3fcf7a"), Color("0d6b34")],
	"blue": [Color("4a8ff0"), Color("0f3c9a")], "smoke": [Color("8a8f96"), Color("2c3036")],
	"amber": [Color("f2b04a"), Color("9a5a0c")], "violet": [Color("a77bf0"), Color("4a1f9a")]}

static var kinds := {}         # kind -> {styles: {style id -> {name, design, builtin}}, tables: {table id -> style id}, default}


## The table styles from the server: {kind: {styles, tables, default}}.
static func configure(data: Dictionary) -> void:
	kinds = data


## The design `table_id` is drawn in, everything filled in (a design saved before a choice existed takes House's).
static func design(table_id: String, kind := "cards") -> Dictionary:
	var k: Dictionary = kinds.get(kind, {})
	var styles: Dictionary = k.get("styles", {})
	var default_id := str(k.get("default", "house"))
	var id: String = k.get("tables", {}).get(table_id, default_id)
	var style: Dictionary = styles.get(id, styles.get(default_id, {}))
	return fill(style.get("design", {}), kind)


static func fill(given: Dictionary, kind := "cards") -> Dictionary:
	var out: Dictionary = HOUSES.get(kind, HOUSE).duplicate(true)
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
