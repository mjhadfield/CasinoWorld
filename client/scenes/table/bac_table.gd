@tool
class_name BacTable
extends CasinoTable
## A Baccarat (Punto Banco) table: everything shared with the other games
## comes from CasinoTable; this adds the layout (for each seat the Player
## Dragon, Tie and Banker Dragon circles above wide BANKER and PLAYER boxes;
## the coup dealt in the middle, Player's hand on the left, Banker's on the
## right, with their totals) and the round: no decisions -- the coup comes out
## card by card, the dealer calls it, and every seat is settled quickly.

const TOP_Y := -70.5      # Player Dragon, Tie, Banker Dragon -- the three rows evenly spaced
const BANKER_Y := -47.0   # between the title and the front border (there are no player cards)
const PLAYER_Y := -23.5
const SPOTS := ["player", "banker", "tie", "player_dragon", "banker_dragon"]
const BOX := Vector2(40, 13)

var hands := {"player": [], "banker": []}   # Card2Ds of the coup
var totals := {"player": -1, "banker": -1}
var winner := ""


# ------------------------------------------------------------------ layout
func bet_spots() -> Array:
	return SPOTS


func spot_radius(spot: String) -> float:
	return 7.0 if spot in ["tie", "player_dragon", "banker_dragon"] else 7.5


func main_spot() -> String:
	return "player"


func has_main_bet(bets: Dictionary) -> bool:
	return ["player", "banker", "tie"].any(func(s): return int(bets.get(s, 0)) > 0)


func flat_spots() -> Dictionary:
	return {}


func max_cost(b: Dictionary) -> int:
	var total := 0
	for v in b.values():
		total += int(v)
	return total


func spot_pos(seat: int, spot: String) -> Vector2:
	var x := seat_x(seat)
	match spot:
		"player_dragon":
			return Vector2(x - 15, TOP_Y)
		"tie":
			return Vector2(x, TOP_Y)
		"banker_dragon":
			return Vector2(x + 15, TOP_Y)
		"banker":
			return Vector2(x - 9, BANKER_Y)
	return Vector2(x - 9, PLAYER_Y)


## Winnings beside the stake: inside the Banker and Player boxes, to the right;
## a little behind the Tie and Dragon stakes.
func payout_pos(seat: int, spot: String, _bonus := false) -> Vector2:
	if spot in ["banker", "player"]:
		return spot_pos(seat, spot) + Vector2(17, 0)
	return spot_pos(seat, spot) + Vector2(4, -5)


func coup_pos(side: String, index: int) -> Vector2:
	var x0 := -48.0 if side == "player" else 18.0
	return Vector2(x0 + index * 15.0, DEALER_Y)


# ------------------------------------------------------------------ the HUD
func seated_view(ctx: Dictionary) -> Dictionary:
	var info := ""
	match phase:
		"betting":
			info = _betting_info(ctx)
		"dealing":
			info = "The coup's coming out"
		"result", "settling":
			info = winner
	return {"info": info, "actions": [], "my_turn": false}


# ------------------------------------------------------------------ snapshot
func _apply_game_snapshot(state: Dictionary) -> void:
	hands = {"player": [], "banker": []}
	totals = {"player": -1, "banker": -1}
	winner = ""
	for side in ["player", "banker"]:
		var codes: Array = state.get(side, [])
		for k in codes.size():
			var card := _new_card(codes[k], coup_pos(side, k))
			hands[side].append(card)
			_dealer_cards.append(card)
		if not codes.is_empty():
			totals[side] = _total(codes)


static func _total(codes: Array) -> int:
	var sum := 0
	for c in codes:
		var rank: String = c.left(c.length() - 1)
		sum += 1 if rank == "A" else 0 if rank in ["10", "J", "Q", "K"] else int(rank)
	return sum % 10


# ------------------------------------------------------------------ events -> animation
func _note_event(ev: Dictionary) -> void:
	if ev.kind == "betting_open":
		winner = ""


func _animate_game(ev: Dictionary, d: float) -> float:
	match ev.kind:
		"baccarat_card":
			return _card(ev, d)
		"coup_result":
			phase = "result"
			winner = {"player": "Player wins", "banker": "Banker wins"}.get(str(ev.outcome), "Tie")
			return 0.3 * d
		"settle_seat":
			return _settle(ev, d)
	return 0.0


## One card of the coup: out of the shuffler, across to its hand, turned over.
func _card(ev: Dictionary, d: float) -> float:
	phase = "dealing"
	ready_seats.clear()
	_timer_end = 0.0
	var side := str(ev.side)
	var card := _new_card("??", shuffler.slot_point())
	card.visible = false
	hands[side].append(card)
	_dealer_cards.append(card)
	shuffler.deliver()
	_deal_sound(0.15 * d)
	var tw := _tween()
	tw.tween_interval(0.05 * d)
	tw.tween_callback(card.show)
	tw.tween_property(card, "position", shuffler.delivery_point(), 0.15 * d)
	tw.tween_property(card, "position", coup_pos(side, int(ev.index)), 0.25 * d).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tw.tween_callback(card.flip_to.bind(str(ev.card), 0.2 * d))
	tw.tween_callback(func(): totals[side] = int(ev.total))
	return 0.3 * d


## Settle one seat: losing bets swept, winners paid. No cards to turn, so quick.
func _settle(ev: Dictionary, d: float) -> float:
	phase = "settling"
	var seat := int(ev.seat)
	var t := 0.1 * d
	for step in ev.steps:
		_after(t).timeout.connect(_settle_step.bind(seat, step, d))
		t += 0.3 * d
	return t + 0.2 * d


func _after_cards_cleared(d: float) -> void:
	hands = {"player": [], "banker": []}
	totals = {"player": -1, "banker": -1}
	_after(0.6 * d).timeout.connect(func(): _feed_shuffler(d))


# ------------------------------------------------------------------ overlays
func _needs_redraw() -> bool:
	return totals.player >= 0 or totals.banker >= 0


func _draw_game(_now: float, _pulse: float) -> void:
	for side in ["player", "banker"]:  # each hand's total, beside it
		if totals[side] < 0:
			continue
		var at := Vector2(-64.0, DEALER_Y) if side == "player" else Vector2(64.0, DEALER_Y)
		var won := winner.begins_with(side.capitalize())
		draw_circle(at, 6.0, Color("2e9e4f") if won else Color(0.08, 0.04, 0.02, 0.85))
		draw_arc(at, 6.0, 0, TAU, 24, Color("c9a24a"), 0.6, true)
		var text := str(totals[side])
		var w := Card2D.FONT.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 7).x
		draw_string(Card2D.FONT, at + Vector2(-w / 2, 2.6), text, HORIZONTAL_ALIGNMENT_LEFT, -1, 7, Color.WHITE)
