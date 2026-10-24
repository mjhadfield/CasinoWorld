@tool
class_name MasterTable
extends CasinoTable
## A Master Table with no game chosen yet (server/casino_server/tables/master.py): the crest and no spots
## (master_felt.gd). Sit down and the dealer asks what you'd like to play; once there's a game, the floor swaps this
## for that game's own table (MasterSwap). While a game is set, that table plays the part: `master` says so.


func bet_spots() -> Array:
	return []


func flat_spots() -> Dictionary:
	return {}


func accepting_bets() -> bool:
	return false


func can_ready() -> bool:
	return false


func queues_bets() -> bool:
	return false


func seated_view(_ctx: Dictionary) -> Dictionary:
	return {"info": "Click the dealer to choose a game", "actions": [], "my_turn": false, "quiet_betting": true, "prompt": true}


func _countdown_text(_left: float) -> String:
	return ""
