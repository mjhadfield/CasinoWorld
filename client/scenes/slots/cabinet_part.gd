@tool
extends Node2D
## One drawn part of a SlotCabinet -- the cabinet itself or its stool -- as its own node, so
## the floor's y-sort puts each in front of or behind whoever's sitting there.

@export_enum("cabinet", "stool") var part := "cabinet"


func _draw() -> void:
	var cab := get_parent() as SlotCabinet
	if cab == null:
		return
	if part == "cabinet":
		cab.draw_cabinet(self)
	else:
		cab.draw_stool_node(self)
