extends Node
## The floor plan's pictures from the asset library: furniture, decor and floor textures, fetched from the server
## at runtime so new art needs no export.


## A library asset's details and pictures, or {} if it isn't here.
func asset(_id: String) -> Dictionary:
	return {}


## A floor texture by name, or null (drawn as plain colour).
func floor_texture(_name: String) -> Texture2D:
	return null
