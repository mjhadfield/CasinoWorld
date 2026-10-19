"""
Game engines -- pure rules, no I/O, no money movement. Ported from Casino v2's
games/*/logic.py with two changes: money is integer pence, and each round
deals N seats plus one dealer hand from a shared deck. TableRooms (tables/)
drive these and move the money.
"""
