class_name Furniture
extends Node2D
## A piece of furniture or decor from the asset library (the floor plan's "a:<id>" items): its picture for the
## way it faces (PlanArt), standing on its base point so it Y-sorts with the people, and a body where it blocks
## walking. Rugs lie flat under everyone; pictures hang on the back wall.

var asset_id := ""
var facing := "down"


## Set it up from its plan item. False if the library doesn't have it (yet): nothing is placed.
func setup(item: Dictionary) -> bool:
	asset_id = str(item.asset).substr(2)
	facing = str(item.get("facing", "down"))
	return not PlanArt.asset(asset_id).is_empty()
