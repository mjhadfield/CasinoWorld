import os
import random
import time

from casino_server.dealer import LINES_FILE, DealerLines, hand_phrase
from casino_server.engines import three_card_poker as tcp
from casino_server.engines.cards import Card
from casino_server.engines.hand_evaluator import evaluate_three_card_hand


def cards(*codes):
    return [Card.from_code(c) for c in codes]


def result(player, dealer, folded=False, prime=0):
    return tcp.settle_hand(cards(*player), cards(*dealer), tcp.Bets(ante=100, prime=prime), folded)


def custom(tmp_path, text):
    path = tmp_path / "lines.toml"
    path.write_text(text)
    return DealerLines(path, random.Random(1))


def test_shipped_file_has_every_section():
    lines = DealerLines(LINES_FILE, random.Random(0))
    for section, key in [("table", "place_bets"), ("table", "no_more_bets"), ("dealer", "qualifies"),
                         ("dealer", "no_qualify"), ("announce", "win"), ("announce", "lose"),
                         ("announce", "push"), ("announce", "no_qualify"), ("announce", "prime"),
                         ("win", "ordinary"), ("win", "strong"), ("win", "monster"),
                         ("lose", "ordinary"), ("lose", "strong")]:
        assert lines.say(section, key, hand="Straight", name="Mike", dealer="Queen high", colour="All red"), (section, key)


def test_hand_phrases():
    assert hand_phrase(evaluate_three_card_hand(cards("Qh", "8c", "3d"))) == "Queen high"
    assert hand_phrase(evaluate_three_card_hand(cards("Kh", "Kc", "3d"))) == "Pair of Kings"
    assert hand_phrase(evaluate_three_card_hand(cards("Qs", "Ks", "As"))) == "Royal Flush"


def test_announcements_and_reactions_by_strength(tmp_path):
    lines = custom(tmp_path, """
[announce]
win = ["{hand}, wins."]
lose = ["{hand}, loses."]
no_qualify = ["{hand} -- Ante pays."]
prime = ["{colour} -- Prime pays."]
[win]
ordinary = ["Nice."]
monster = ["Wow, {name}!"]
[lose]
strong = ["Oof, unlucky."]
[chance]
win_ordinary = 0.0
win_monster = 1.0
lose_strong = 1.0
lose_ordinary = 0.0
""")
    assert lines.announce(result(["Kh", "Kc", "3d"], ["Qh", "8c", "4d"]), "Mike", False) == "Pair of Kings, wins."
    assert lines.announce(result(["7h", "7c", "7d"], ["Qh", "8c", "4d"]), "Mike", False) == "Three of a Kind, wins. Wow, Mike!"
    assert lines.announce(result(["Kh", "Kc", "3d"], ["Ah", "Ac", "4d"]), "Mike", False) == "Pair of Kings, loses. Oof, unlucky."
    assert lines.announce(result(["9h", "5c", "2d"], ["Qh", "8c", "4d"]), "Mike", False) == "9 high, loses."
    assert lines.announce(result(["9h", "5c", "2d"], ["Jh", "8c", "4d"]), "Mike", False) == "9 high -- Ante pays."
    held = result(["2h", "7d", "9h"], ["Qh", "8c", "3d"], folded=True, prime=100)
    assert lines.announce(held, "Mike", True) == "All red -- Prime pays."


def test_lines_needing_a_missing_value_are_skipped(tmp_path):
    lines = custom(tmp_path, '[table]\nplace_bets = ["Go, {name}!", "Place your bets."]\n')
    assert {lines.say("table", "place_bets") for _ in range(20)} == {"Place your bets."}
    assert lines.say("table", "nothing_here") == ""


def test_edits_are_picked_up_without_a_restart(tmp_path):
    lines = custom(tmp_path, '[table]\nno_more_bets = ["No more bets."]\n')
    assert lines.say("table", "no_more_bets") == "No more bets."
    path = tmp_path / "lines.toml"
    path.write_text('[table]\nno_more_bets = ["Bets are closed!"]\n')
    later = time.time() + 5
    os.utime(path, (later, later))
    assert lines.say("table", "no_more_bets") == "Bets are closed!"


def test_a_broken_file_keeps_the_last_good_lines(tmp_path):
    lines = custom(tmp_path, '[table]\nno_more_bets = ["No more bets."]\n')
    lines.say("table", "no_more_bets")
    path = tmp_path / "lines.toml"
    path.write_text("this is [not toml")
    later = time.time() + 5
    os.utime(path, (later, later))
    assert lines.say("table", "no_more_bets") == "No more bets."
