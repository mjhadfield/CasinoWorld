"""The hand-authored vector art set for Armadillo Goes West: one SVG per symbol and trail item,
all on a 256x256 board with the same outline, palette and drop shadow.
usage: python3 gen_svg.py <out_dir>"""
import math
import sys
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "art/svg")
INK = "#2b1608"           # every outline
SW = 7                    # outline width

GRADS = {
    "gold": ["#fff6c2", "#f4c94f", "#c58a1f", "#734710"],
    "leather": ["#e2a46a", "#b06a34", "#7a4219", "#45230b"],
    "red": ["#ff9a86", "#e2402f", "#a51c12", "#5e0d07"],
    "teal": ["#a6f2e6", "#2bb5ac", "#137377", "#0a4245"],
    "purple": ["#d8baff", "#8f57de", "#5a2aa0", "#2f1460"],
    "orange": ["#ffd59a", "#f59a32", "#c3600c", "#6e3203"],
    "wood": ["#d29a62", "#9a6034", "#6b3d1d", "#3c200d"],
    "steel": ["#ffffff", "#c9d1d8", "#7f8a95", "#3d454e"],
    "ivory": ["#fffaf0", "#f0e0bf", "#c8ad7f", "#8a7048"],
    "amber": ["#ffd27a", "#e9951f", "#a8540a", "#5a2a03"],
    "canvas": ["#fffdf6", "#efe4cc", "#cdb994", "#8f7a55"],
    "tan": ["#f3d3a2", "#d6a46a", "#a87239", "#6a4219"],
    "pink": ["#ffd6c9", "#f0a690", "#c47160", "#7d4033"],
    "yellow": ["#fffbd0", "#ffe14a", "#f0a90c", "#8f5a00"],
    "green": ["#d7f5a6", "#7ec440", "#3f8a1c", "#1e4a0b"],
}


def defs(*names):
    out = ['<filter id="ds" x="-25%" y="-25%" width="150%" height="150%">'
           '<feDropShadow dx="0" dy="7" stdDeviation="6" flood-color="#160802" flood-opacity="0.55"/></filter>',
           '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9"/></filter>']
    for n in names:
        c = GRADS[n]
        out.append(f'<linearGradient id="{n}" x1="0" y1="0" x2="0.35" y2="1">'
                   f'<stop offset="0" stop-color="{c[0]}"/><stop offset="0.35" stop-color="{c[1]}"/>'
                   f'<stop offset="0.75" stop-color="{c[2]}"/><stop offset="1" stop-color="{c[3]}"/></linearGradient>')
        out.append(f'<radialGradient id="{n}R" cx="0.38" cy="0.32" r="0.75">'
                   f'<stop offset="0" stop-color="{c[0]}"/><stop offset="0.4" stop-color="{c[1]}"/>'
                   f'<stop offset="0.85" stop-color="{c[2]}"/><stop offset="1" stop-color="{c[3]}"/></radialGradient>')
    out.append('<linearGradient id="shine" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0.75"/>'
               '<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>')
    return "<defs>" + "".join(out) + "</defs>"


def svg(name, body, grads):
    OUT.mkdir(parents=True, exist_ok=True)
    doc = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="512" height="512">'
           f'{defs(*grads)}<g filter="url(#ds)" stroke="{INK}" stroke-width="{SW}" stroke-linejoin="round" '
           f'stroke-linecap="round">{body}</g></svg>')
    (OUT / f"{name}.svg").write_text(doc)


def pts(points):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def star(cx, cy, n, r_out, r_in, rot=-90):
    p = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(rot + i * 180 / n)
        p.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return p


# ------------------------------------------------------------------ W: the sheriff's star
def wild():
    tips = star(128, 132, 6, 104, 58)
    balls = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="15" fill="url(#goldR)"/>' for x, y in tips[::2])
    inner = star(128, 132, 6, 78, 46)
    body = (f'<polygon points="{pts(tips)}" fill="url(#gold)"/>{balls}'
            f'<polygon points="{pts(inner)}" fill="url(#goldR)" stroke-width="3" stroke="#8a5a12"/>'
            f'<circle cx="128" cy="132" r="40" fill="url(#gold)" stroke-width="5"/>'
            f'<circle cx="128" cy="132" r="31" fill="none" stroke="#9a6614" stroke-width="3" stroke-dasharray="4 5"/>'
            f'<path d="M84 90 Q128 60 172 90" fill="none" stroke="#fff" stroke-opacity="0.55" stroke-width="6"/>')
    svg("W", body, ["gold"])


# ------------------------------------------------------------------ H1: the armadillo outlaw
def hat_shape(cx, top, w, color="leather"):
    """A cowboy hat: crown with a pinch, a curled brim, a band. Returns svg."""
    s = w / 200
    def P(x, y):
        return f"{cx + x * s:.1f} {top + y * s:.1f}"
    crown = (f'<path d="M{P(-58, 70)} C{P(-62, 20)} {P(-40, 0)} {P(-20, 6)} C{P(-8, 12)} {P(8, 12)} {P(20, 6)} '
             f'C{P(40, 0)} {P(62, 20)} {P(58, 70)} Z" fill="url(#{color})"/>')
    dent = f'<path d="M{P(-6, 14)} Q{P(0, 40)} {P(6, 14)}" fill="none" stroke-width="4"/>'
    band = f'<path d="M{P(-58, 58)} Q{P(0, 72)} {P(58, 58)} L{P(58, 72)} Q{P(0, 86)} {P(-58, 72)} Z" fill="#2a1408" stroke-width="4"/>'
    brim = (f'<path d="M{P(-100, 58)} C{P(-92, 78)} {P(-60, 90)} {P(0, 92)} C{P(60, 90)} {P(92, 78)} {P(100, 58)} '
            f'C{P(104, 76)} {P(84, 108)} {P(0, 110)} C{P(-84, 108)} {P(-104, 76)} {P(-100, 58)} Z" fill="url(#{color})"/>')
    sheen = f'<path d="M{P(-40, 20)} Q{P(-30, 8)} {P(-16, 12)}" fill="none" stroke="#fff" stroke-opacity="0.5" stroke-width="5"/>'
    return crown + dent + band + brim + sheen


def armadillo_head():
    ears = ('<ellipse cx="66" cy="104" rx="22" ry="30" fill="url(#pink)" transform="rotate(-28 66 104)"/>'
            '<ellipse cx="190" cy="104" rx="22" ry="30" fill="url(#pink)" transform="rotate(28 190 104)"/>')
    bandana = '<path d="M62 196 Q128 222 194 196 L172 244 Q128 236 128 252 Q128 236 84 244 Z" fill="url(#red)"/>'
    head = ('<path d="M70 120 C70 82 186 82 186 120 C188 160 160 176 150 198 C142 226 114 226 106 198 '
            'C96 176 68 160 70 120 Z" fill="url(#tanR)"/>')
    bands = "".join(f'<path d="M{80 + i * 2} {116 + i * 14} Q128 {104 + i * 14} {176 - i * 2} {116 + i * 14}" '
                    f'fill="none" stroke="#8a5a2a" stroke-width="4"/>' for i in range(3))
    snout = ('<path d="M108 168 Q128 160 148 168 L140 210 Q128 222 116 210 Z" fill="url(#tan)" stroke-width="5"/>'
             '<ellipse cx="128" cy="212" rx="13" ry="9" fill="#3a1d0e" stroke-width="4"/>'
             '<ellipse cx="124" cy="209" rx="4" ry="2.5" fill="#fff" stroke="none" opacity="0.7"/>')
    eyes = ("".join(f'<ellipse cx="{x}" cy="150" rx="12" ry="14" fill="#fff" stroke-width="4"/>'
                    f'<circle cx="{x + 3}" cy="153" r="7" fill="#1b0d05" stroke="none"/>'
                    f'<circle cx="{x + 5}" cy="150" r="2.4" fill="#fff" stroke="none"/>' for x in (104, 152))
            + '<path d="M88 132 L118 140" stroke-width="6"/><path d="M168 132 L138 140" stroke-width="6"/>')
    smirk = '<path d="M134 196 Q146 196 152 186" fill="none" stroke-width="4"/>'
    hat = hat_shape(128, 18, 196)
    svg("H1", ears + bandana + head + bands + snout + eyes + smirk + hat, ["tan", "pink", "red", "leather"])


# ------------------------------------------------------------------ H2: the rattler
def snake():
    coils = ""
    for i, (cy, rx, ry) in enumerate([(206, 92, 30), (176, 74, 26), (150, 54, 22)]):
        coils += (f'<ellipse cx="128" cy="{cy}" rx="{rx}" ry="{ry}" fill="none" stroke="{INK}" stroke-width="34"/>'
                  f'<ellipse cx="128" cy="{cy}" rx="{rx}" ry="{ry}" fill="none" stroke="url(#tan)" stroke-width="22"/>'
                  f'<ellipse cx="128" cy="{cy}" rx="{rx}" ry="{ry}" fill="none" stroke="#6a3c16" stroke-width="10" '
                  f'stroke-dasharray="10 14" stroke-linecap="butt"/>')
    neck = ('<path d="M150 150 C176 120 166 92 140 80" fill="none" stroke="#2b1608" stroke-width="32"/>'
            '<path d="M150 150 C176 120 166 92 140 80" fill="none" stroke="url(#tan)" stroke-width="20"/>')
    head = ('<path d="M106 76 C106 50 160 44 170 66 C178 84 150 100 128 98 C114 96 106 88 106 76 Z" fill="url(#tanR)"/>'
            '<path d="M108 82 C88 92 76 94 68 92" fill="none" stroke="#c4271a" stroke-width="4"/>'
            '<path d="M68 92 L58 86 M68 92 L58 98" stroke="#c4271a" stroke-width="3"/>'
            '<ellipse cx="140" cy="68" rx="8" ry="6" fill="#ffe14a" stroke-width="3"/>'
            '<ellipse cx="141" cy="68" rx="2" ry="5" fill="#1b0d05" stroke="none"/>'
            '<path d="M132 58 L150 62" stroke-width="4"/>')
    rattle = ('<g transform="rotate(-25 214 214)">' + "".join(
        f'<ellipse cx="{214 + i * 9}" cy="214" rx="7" ry="10" fill="url(#ivory)" stroke-width="3"/>' for i in range(3)) + "</g>")
    svg("H2", coils + rattle + neck + head, ["tan", "ivory"])


def hat():
    svg("M1", hat_shape(128, 62, 236) +
        '<polygon points="' + pts(star(128, 140, 5, 16, 7)) + '" fill="url(#steel)" stroke-width="3"/>', ["leather", "steel"])


def horseshoe():
    path = "M70 70 C40 150 70 226 128 226 C186 226 216 150 186 70"
    holes = "".join(f'<circle cx="{x}" cy="{y}" r="5" fill="#5a3708" stroke="none"/>'
                    for x, y in [(66, 104), (68, 146), (84, 186), (190, 104), (188, 146), (172, 186)])
    body = (f'<path d="{path}" fill="none" stroke="{INK}" stroke-width="52"/>'
            f'<path d="{path}" fill="none" stroke="url(#gold)" stroke-width="38"/>'
            f'<path d="{path}" fill="none" stroke="#fff" stroke-opacity="0.35" stroke-width="8" transform="translate(-6 -4)"/>'
            f'{holes}'
            '<rect x="52" y="56" width="36" height="18" rx="5" fill="url(#gold)" stroke-width="5"/>'
            '<rect x="168" y="56" width="36" height="18" rx="5" fill="url(#gold)" stroke-width="5"/>')
    svg("M2", body, ["gold"])


def whiskey():
    body = ('<path d="M108 24 L148 24 L148 40 L144 44 L144 84 C176 98 184 114 184 140 L184 226 C184 238 176 242 164 242 '
            'L92 242 C80 242 72 238 72 226 L72 140 C72 114 80 98 112 84 L112 44 L108 40 Z" fill="url(#amber)"/>'
            '<path d="M76 150 L180 150 L180 226 C180 234 174 238 164 238 L92 238 C82 238 76 234 76 226 Z" '
            'fill="#7a3a06" stroke="none" opacity="0.45"/>'
            '<rect x="104" y="10" width="48" height="26" rx="6" fill="url(#wood)" stroke-width="5"/>'
            '<rect x="84" y="152" width="88" height="64" rx="6" fill="url(#canvas)" stroke-width="5"/>'
            '<text x="128" y="194" text-anchor="middle" font-family="Georgia,serif" font-weight="700" font-size="30" '
            'fill="#5a2a06" stroke="none">XXX</text>'
            '<path d="M92 160 L164 160 M92 208 L164 208" stroke="#a8540a" stroke-width="2"/>'
            '<path d="M86 108 C80 130 82 200 86 226" fill="none" stroke="#fff" stroke-opacity="0.55" stroke-width="8"/>')
    svg("M3", body, ["amber", "wood", "canvas"])


def boot():
    body = ('<path d="M92 20 L172 20 L176 120 C178 150 186 166 214 178 C238 188 244 204 236 214 L236 222 '
            'L130 222 L126 236 L92 236 L90 200 C86 160 84 90 92 20 Z" fill="url(#leather)"/>'
            '<path d="M90 222 L130 222 L126 240 L92 240 Z" fill="#2a1408" stroke-width="5"/>'
            '<path d="M86 20 L178 20 L176 40 L88 40 Z" fill="url(#wood)" stroke-width="5"/>'
            '<path d="M108 56 C130 70 150 70 160 56 M108 84 C124 120 150 110 160 84 M114 130 C128 150 150 146 156 126" '
            'fill="none" stroke="#f2c36b" stroke-width="4"/>'
            '<path d="M150 182 C176 176 196 184 212 196" fill="none" stroke="#f2c36b" stroke-width="4"/>'
            '<path d="M86 196 L60 202" stroke-width="6"/>'
            f'<polygon points="{pts(star(48, 204, 6, 22, 9))}" fill="url(#steel)" stroke-width="4"/>'
            '<circle cx="48" cy="204" r="5" fill="#59636d" stroke-width="2"/>'
            '<path d="M104 36 C100 100 102 160 106 210" fill="none" stroke="#fff" stroke-opacity="0.35" stroke-width="7"/>')
    svg("M4", body, ["leather", "wood", "steel"])


# ------------------------------------------------------------------ L1-L4: suits carved in wood
SUITS = {
    "spade": "M128 22 C150 70 226 104 226 156 C226 194 186 210 150 186 C152 206 160 222 176 234 L80 234 "
             "C96 222 104 206 106 186 C70 210 30 194 30 156 C30 104 106 70 128 22 Z",
    "club": "M128 28 C162 28 176 60 164 90 C196 78 232 98 232 136 C232 176 186 188 154 164 C156 196 164 218 180 234 "
            "L76 234 C92 218 100 196 102 164 C70 188 24 176 24 136 C24 98 60 78 92 90 C80 60 94 28 128 28 Z",
    "diamond": "M128 18 C150 60 184 98 222 128 C184 158 150 196 128 238 C106 196 72 158 34 128 C72 98 106 60 128 18 Z",
    "heart": "M128 228 C88 196 26 156 26 98 C26 58 56 34 86 34 C106 34 120 46 128 62 C136 46 150 34 170 34 "
             "C200 34 230 58 230 98 C230 156 168 196 128 228 Z",
}


def suit(name, key, ink):
    d = SUITS[key]
    body = (f'<path d="{d}" fill="url(#wood)"/>'
            f'<path d="{d}" fill="url(#{ink})" stroke="#3c200d" stroke-width="4" transform="translate(128 132) scale(0.72) translate(-128 -132)"/>'
            f'<path d="{d}" fill="none" stroke="#e0b07a" stroke-opacity="0.5" stroke-width="3" '
            f'transform="translate(128 132) scale(0.86) translate(-128 -132)" stroke-dasharray="2 9"/>'
            f'<path d="{d}" fill="url(#shine)" stroke="none" opacity="0.35" transform="translate(128 100) scale(0.55 0.4) translate(-128 -100)"/>')
    svg(name, body, ["wood", ink])


# ------------------------------------------------------------------ scatters and the barrel
def wheel(cx, cy, r):
    spokes = "".join(f'<line x1="{cx}" y1="{cy}" x2="{cx + r * math.cos(math.radians(a)):.1f}" '
                     f'y2="{cy + r * math.sin(math.radians(a)):.1f}" stroke-width="5"/>' for a in range(0, 360, 30))
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{INK}" stroke-width="16"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="url(#wood)" stroke-width="9"/>'
            f'{spokes}<circle cx="{cx}" cy="{cy}" r="9" fill="url(#steel)" stroke-width="4"/>')


def wagon():
    bonnet = ('<path d="M52 140 C40 70 66 40 128 40 C190 40 220 70 208 140 Z" fill="url(#canvas)"/>'
              '<path d="M86 140 C80 80 96 52 112 46 M170 140 C176 80 160 52 144 46" fill="none" stroke="#a89064" stroke-width="5"/>'
              '<path d="M60 90 C80 70 100 62 116 60" fill="none" stroke="#fff" stroke-width="6" stroke-opacity="0.8"/>'
              '<ellipse cx="128" cy="92" rx="22" ry="30" fill="#3d2410" stroke-width="5"/>')
    bed = ('<path d="M34 136 L222 136 L212 176 L44 176 Z" fill="url(#wood)"/>'
           '<path d="M44 150 L214 150 M48 164 L210 164" stroke="#3c200d" stroke-width="3"/>'
           '<path d="M222 150 L246 128" stroke-width="7"/>')
    svg("BS", bonnet + bed + wheel(74, 194, 38) + wheel(186, 194, 38), ["canvas", "wood", "steel"])


def revolver():
    return ('<path d="M-104 -14 L18 -14 L24 -22 L44 -22 L48 -10 L48 18 L30 22 L36 34 C44 62 50 76 46 88 '
            'L18 92 C12 70 6 50 -2 36 L-10 26 L-30 26 L-36 10 L-104 6 Z" fill="url(#steel)"/>'
            '<path d="M-2 36 C6 50 12 70 18 92 L46 88 C50 76 44 62 36 34 Z" fill="url(#ivory)" stroke-width="5"/>'
            '<rect x="-16" y="-20" width="40" height="34" rx="8" fill="url(#steel)" stroke-width="5"/>'
            '<path d="M-10 -12 L18 -12 M-10 -3 L18 -3 M-10 6 L18 6" stroke="#59636d" stroke-width="3"/>'
            '<path d="M-24 26 C-20 42 -6 44 -2 30" fill="none" stroke-width="5"/>'
            '<path d="M-100 -6 L14 -6" stroke="#fff" stroke-opacity="0.7" stroke-width="4"/>'
            '<path d="M-104 -14 L-104 6" stroke="#c58a1f" stroke-width="7"/>')


def pistols():
    body = (f'<g transform="translate(134 128) rotate(-38) scale(1.18)">{revolver()}</g>'
            f'<g transform="translate(122 128) scale(-1 1) rotate(-38) scale(1.18)">{revolver()}</g>')
    svg("FS", body, ["steel", "ivory", "gold"])


def coin_heap(cx, cy, n, r=16, seed=3):
    import random
    rnd = random.Random(seed)
    out = ""
    for i in range(n):
        x = cx + rnd.uniform(-60, 60) * (1 - i / n)
        y = cy - i * 3 + rnd.uniform(-6, 6)
        out += (f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{r}" ry="{r * 0.45:.1f}" fill="url(#gold)" stroke-width="4"/>')
    return out


def barrel():
    body = ('<path d="M58 88 C46 130 46 180 58 236 L198 236 C210 180 210 130 198 88 Z" fill="url(#wood)"/>'
            '<path d="M92 88 C86 140 86 190 92 236 M128 88 L128 236 M164 88 C170 140 170 190 164 236" stroke="#3c200d" stroke-width="3"/>'
            '<path d="M52 118 C100 128 156 128 204 118 M52 206 C100 216 156 216 204 206" fill="none" stroke="#59636d" stroke-width="12"/>'
            '<ellipse cx="128" cy="88" rx="72" ry="20" fill="#3c200d"/>'
            + coin_heap(128, 80, 16, 18) +
            '<ellipse cx="96" cy="44" rx="18" ry="18" fill="url(#goldR)" stroke-width="4"/>'
            '<ellipse cx="164" cy="52" rx="16" ry="16" fill="url(#goldR)" stroke-width="4"/>'
            '<path d="M66 120 C60 160 62 200 68 226" fill="none" stroke="#fff" stroke-opacity="0.3" stroke-width="8"/>')
    svg("barrel", body, ["wood", "gold", "steel"])


# ------------------------------------------------------------------ trail items
def t_coin():
    body = ('<circle cx="128" cy="128" r="96" fill="url(#goldR)"/>'
            '<circle cx="128" cy="128" r="76" fill="none" stroke="#9a6614" stroke-width="5"/>'
            f'<polygon points="{pts(star(128, 132, 5, 52, 22))}" fill="url(#gold)" stroke-width="5"/>'
            '<path d="M62 92 Q86 52 132 44" fill="none" stroke="#fff" stroke-opacity="0.7" stroke-width="8"/>')
    svg("t_coin", body, ["gold"])


def t_double():
    body = ('<path d="M128 14 L242 128 L128 242 L14 128 Z" fill="url(#gold)"/>'
            '<path d="M128 38 L218 128 L128 218 L38 128 Z" fill="url(#red)" stroke-width="5"/>'
            '<path d="M60 112 L128 44 L150 66" fill="none" stroke="#fff" stroke-opacity="0.55" stroke-width="7"/>')
    svg("t_double", body, ["gold", "red"])


def signpost(board):
    return ('<rect x="116" y="120" width="24" height="124" rx="4" fill="url(#wood)"/>' + board +
            '<path d="M120 240 L136 240" stroke="#3c200d" stroke-width="3"/>')


def t_forward():
    board = ('<path d="M30 54 L188 54 L238 98 L188 142 L30 142 Z" fill="url(#wood)"/>'
             '<path d="M44 78 L180 78 M44 118 L180 118" stroke="#3c200d" stroke-width="3"/>'
             '<circle cx="48" cy="98" r="6" fill="url(#steel)" stroke-width="3"/>')
    svg("t_forward", signpost(board), ["wood", "steel"])


def t_heart():
    d = SUITS["heart"]
    body = (f'<path d="{d}" fill="url(#redR)" transform="translate(128 132) scale(0.92) translate(-128 -132)"/>'
            '<path d="M58 82 C64 58 92 52 104 66" fill="none" stroke="#fff" stroke-opacity="0.85" stroke-width="10"/>')
    svg("t_heart", body, ["red"])


def t_lightning():
    d = "M152 14 L64 142 L118 142 L92 242 L196 100 L138 100 L168 14 Z"
    body = (f'<path d="{d}" fill="#ffe14a" stroke="none" filter="url(#glow)" opacity="0.8"/>'
            f'<path d="{d}" fill="url(#yellow)"/>'
            '<path d="M148 32 L90 128" stroke="#fff" stroke-opacity="0.8" stroke-width="6"/>')
    svg("t_lightning", body, ["yellow"])


def t_crate():
    body = ('<path d="M40 112 L58 40 L222 52 L216 112 Z" fill="url(#wood)" stroke-width="6"/>'
            '<path d="M54 64 L214 74 M48 90 L216 98" stroke="#3c200d" stroke-width="3"/>'
            + coin_heap(128, 112, 16, 20, seed=8) +
            '<ellipse cx="96" cy="78" rx="18" ry="18" fill="url(#goldR)" stroke-width="4"/>'
            '<ellipse cx="160" cy="86" rx="16" ry="16" fill="url(#goldR)" stroke-width="4"/>'
            '<path d="M30 116 L226 116 L216 236 L40 236 Z" fill="url(#wood)"/>'
            '<path d="M36 156 L220 156 M38 196 L218 196" stroke="#3c200d" stroke-width="4"/>'
            '<path d="M44 120 L212 232 M212 120 L44 232" stroke="#3c200d" stroke-width="6" opacity="0.55"/>')
    svg("t_crate", body, ["wood", "gold"])


def t_upgrade():
    chevrons = "".join(f'<path d="M{50 + i * 48} 66 L{78 + i * 48} 98 L{50 + i * 48} 130 L{70 + i * 48} 130 L{98 + i * 48} 98 '
                       f'L{70 + i * 48} 66 Z" fill="#1d1208" stroke="none"/>' for i in range(3))
    board = ('<rect x="28" y="54" width="200" height="88" rx="8" fill="url(#yellow)"/>' + chevrons)
    svg("t_upgrade", signpost(board), ["wood", "yellow"])


def t_gold():
    bar = lambda x, y: (f'<path d="M{x} {y} L{x + 70} {y} L{x + 84} {y + 34} L{x - 14} {y + 34} Z" fill="url(#gold)"/>'
                        f'<path d="M{x + 6} {y + 6} L{x + 62} {y + 6}" stroke="#fff" stroke-opacity="0.7" stroke-width="5"/>')
    body = (bar(46, 190) + bar(136, 190) + bar(92, 154) + bar(92, 118) + bar(46, 154) + bar(136, 154)
            + '<path d="M60 70 L70 92 L80 70 L70 48 Z M190 84 L196 98 L202 84 L196 70 Z" fill="#fff" stroke="none"/>')
    svg("t_gold", body, ["gold"])


def t_snake():
    body = ('<path d="M40 240 C30 180 90 170 110 150 C130 128 116 96 140 80" fill="none" stroke="#2b1608" stroke-width="40"/>'
            '<path d="M40 240 C30 180 90 170 110 150 C130 128 116 96 140 80" fill="none" stroke="url(#tan)" stroke-width="28"/>'
            '<path d="M40 240 C30 180 90 170 110 150 C130 128 116 96 140 80" fill="none" stroke="#6a3c16" stroke-width="12" stroke-dasharray="10 14" stroke-linecap="butt"/>'
            '<path d="M112 70 C120 30 190 24 214 50 L236 84 L196 82 L232 108 L186 112 C160 118 120 110 112 70 Z" fill="url(#tanR)"/>'
            '<path d="M196 82 L236 84 L232 108 Z" fill="#7d130c" stroke-width="4"/>'
            '<path d="M206 84 L210 100 M222 85 L222 102" stroke="#fff" stroke-width="4"/>'
            '<ellipse cx="170" cy="56" rx="10" ry="8" fill="#ffe14a" stroke-width="4"/>'
            '<ellipse cx="171" cy="56" rx="2.5" ry="7" fill="#1b0d05" stroke="none"/>'
            '<path d="M154 44 L184 48" stroke-width="5"/>')
    svg("t_snake", body, ["tan"])


def armadillo_body():
    shell = ('<path d="M34 170 C30 100 80 62 140 66 C196 70 226 110 222 170 Z" fill="url(#tanR)"/>'
             + "".join(f'<path d="M{70 + i * 26} {80 - (2 - abs(i - 2)) * 4} C{64 + i * 26} 120 {66 + i * 26} 150 {72 + i * 26} 170" '
                       f'fill="none" stroke="#8a5a2a" stroke-width="5"/>' for i in range(5)))
    legs = ('<rect x="60" y="164" width="26" height="54" rx="10" fill="url(#tan)"/>'
            '<rect x="170" y="164" width="26" height="54" rx="10" fill="url(#tan)"/>'
            '<path d="M54 216 L92 216 M164 216 L202 216" stroke-width="10"/>')
    tail = '<path d="M38 160 C14 168 8 190 18 206" fill="none" stroke="#2b1608" stroke-width="18"/><path d="M38 160 C14 168 8 190 18 206" fill="none" stroke="url(#tan)" stroke-width="8"/>'
    head = ('<path d="M196 96 C230 90 248 128 244 150 C238 160 222 158 214 148 C204 136 192 122 196 96 Z" fill="url(#tanR)"/>'
            '<ellipse cx="200" cy="90" rx="12" ry="20" fill="url(#pink)" transform="rotate(20 200 90)"/>'
            '<circle cx="222" cy="116" r="6" fill="#1b0d05" stroke="none"/><circle cx="224" cy="114" r="2" fill="#fff" stroke="none"/>'
            '<ellipse cx="242" cy="148" rx="7" ry="6" fill="#3a1d0e" stroke-width="3"/>')
    neckerchief = '<path d="M196 130 L222 158 L190 166 Z" fill="url(#red)" stroke-width="5"/>'
    hat = f'<g transform="rotate(14 214 70)">{hat_shape(214, 34, 92)}</g>'
    svg("armadillo", '<g transform="translate(-4 10) scale(0.94)">' + tail + legs + shell + head + neckerchief + hat + '</g>',
        ["tan", "pink", "red", "leather"])


def cylinder():
    holes = "".join(f'<circle cx="{128 + 58 * math.cos(math.radians(a)):.1f}" cy="{128 + 58 * math.sin(math.radians(a)):.1f}" '
                    f'r="24" fill="#1d2329" stroke-width="5"/>' for a in range(-90, 270, 60))
    flutes = "".join(f'<path d="M{128 + 108 * math.cos(math.radians(a)):.1f} {128 + 108 * math.sin(math.radians(a)):.1f} '
                     f'L{128 + 90 * math.cos(math.radians(a)):.1f} {128 + 90 * math.sin(math.radians(a)):.1f}" stroke-width="5"/>'
                     for a in range(-60, 300, 60))
    body = ('<circle cx="128" cy="128" r="112" fill="url(#steelR)"/>' + flutes + holes +
            '<circle cx="128" cy="128" r="16" fill="url(#steel)" stroke-width="5"/>'
            '<path d="M44 92 Q70 36 132 28" fill="none" stroke="#fff" stroke-opacity="0.8" stroke-width="8"/>')
    svg("cylinder", body, ["steel"])


if __name__ == "__main__":
    wild(); armadillo_head(); snake(); hat(); horseshoe(); whiskey(); boot()
    suit("L1", "spade", "purple"); suit("L2", "club", "teal"); suit("L3", "diamond", "orange"); suit("L4", "heart", "red")
    wagon(); pistols(); barrel()
    t_coin(); t_double(); t_forward(); t_heart(); t_lightning(); t_crate(); t_upgrade(); t_gold(); t_snake()
    armadillo_body(); cylinder()
    print("\n".join(sorted(p.name for p in OUT.glob("*.svg"))))
