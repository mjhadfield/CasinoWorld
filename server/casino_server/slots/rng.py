"""The mockup's generator (mulberry32) and its helpers, so a seed replays exactly as in JS.
Anything that returns floats in [0, 1) works as an rng; these helpers only call it."""
import os

_M32 = 0xFFFFFFFF


def _imul(a: int, b: int) -> int:
    return (a * b) & _M32


def mulberry32(seed: int):
    a = seed & _M32

    def rng() -> float:
        nonlocal a
        a = (a + 0x6D2B79F5) & _M32
        t = a
        t = _imul(t ^ (t >> 15), t | 1)
        t ^= (t + _imul(t ^ (t >> 7), t | 61)) & _M32
        return ((t ^ (t >> 14)) & _M32) / 4294967296
    return rng


def fresh() -> "callable":
    """An unpredictable generator for real play."""
    return mulberry32(int.from_bytes(os.urandom(4), "little"))


def randint(rng, n: int) -> int:
    """0 <= x < n (Math.floor(rng() * n))."""
    return int(rng() * n)


def weighted(rng, table):
    """table: [(value, weight), ...] -> one value, in proportion to its weight."""
    total = 0.0
    for _, w in table:
        total += w
    r = rng() * total
    for v, w in table:
        r -= w
        if r < 0:
            return v
    return table[-1][0]


def shuffle(rng, items: list) -> list:
    for i in range(len(items) - 1, 0, -1):
        j = randint(rng, i + 1)
        items[i], items[j] = items[j], items[i]
    return items


def sample(rng, items, n: int) -> list:
    return shuffle(rng, list(items))[:n]
