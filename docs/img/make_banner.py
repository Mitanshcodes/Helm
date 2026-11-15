# OWNER: P4 (written by P2 at the user's request, 2026-11-15)
"""Generate the two README banner SVGs in Helm's own riso-zine palette.

    python docs/img/make_banner.py

Palette tracks ui/src/styles.css. Keep them in step.

Fonts cannot load inside an SVG that GitHub serves through its image proxy, so every
glyph here is geometry: the wordmark is monoline strokes, nothing is <text>.
"""
import math
from pathlib import Path

W, H = 1200, 400

LIGHT = dict(bg="#f3eee2", ink="#141414", blue="#0067a6", pink="#ff48b0",
             soft="#ffc9e5", yellow="#ffe800", dash="#141414")
DARK = dict(bg="#141414", ink="#f3eee2", blue="#3ba4f5", pink="#ff48b0",
            soft="#5e2342", yellow="#ffe800", dash="#f3eee2")

SW = 28          # wordmark stroke weight


def wordmark(x, y, h, color, sw=SW, opacity=1.0):
    """HELM as monoline strokes. (x, y) is the top-left of the cap box.

    The M is one continuous path so its apex gets a mitre join; square caps on a
    diagonal would leave spikes sticking out of the vertex.
    """
    b = y + h
    bars = []
    def seg(x1, y1, x2, y2):
        bars.append(f"M{x1:.0f} {y1:.0f}L{x2:.0f} {y2:.0f}")

    seg(x, y, x, b); seg(x + 104, y, x + 104, b); seg(x, y + h / 2, x + 104, y + h / 2)
    e = x + 170
    seg(e, y, e, b); seg(e, y, e + 86, y); seg(e, y + h / 2, e + 72, y + h / 2); seg(e, b, e + 86, b)
    l = x + 312
    seg(l, y, l, b); seg(l, b, l + 86, b)

    m = x + 454
    mpath = (f"M{m} {b}L{m} {y}L{m + 62} {y + h * 0.60:.0f}L{m + 124} {y}L{m + 124} {b}")

    return (f'<g fill="none" stroke="{color}" stroke-width="{sw}" opacity="{opacity}">'
            f'<path d="{"".join(bars)}" stroke-linecap="square"/>'
            f'<path d="{mpath}" stroke-linecap="square" stroke-linejoin="round"/>'
            f'</g>')


def wheel(cx, cy, r, color, accent):
    """A ship's wheel: rim, hub, eight spokes with handle nubs."""
    out = [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="15"/>',
           f'<circle cx="{cx}" cy="{cy}" r="{r - 30}" fill="none" stroke="{color}" stroke-width="4" opacity="0.5"/>']
    for i in range(8):
        a = math.radians(i * 45 + 22.5)
        ca, sa = math.cos(a), math.sin(a)
        x1, y1 = cx + ca * 22, cy + sa * 22
        x2, y2 = cx + ca * (r + 28), cy + sa * (r + 28)
        out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                   f'stroke="{color}" stroke-width="12" stroke-linecap="round"/>')
        out.append(f'<circle cx="{x2:.1f}" cy="{y2:.1f}" r="10" fill="{color}"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="24" fill="{accent}"/>')          # hub = tracking reticle
    out.append(f'<circle cx="{cx}" cy="{cy}" r="8" fill="none" stroke="{color}" stroke-width="5"/>')
    return "\n".join(out)


def halftone(x0, y0, x1, y1, color, step=19):
    """Riso halftone: dots that fade out to the right."""
    d = []
    for gy in range(y0, y1, step):
        for gx in range(x0, x1, step):
            t = 1.0 - (gx - x0) / max(1, (x1 - x0))
            r = 1.2 + 3.2 * t * t
            if r > 1.35:
                d.append(f'<circle cx="{gx}" cy="{gy}" r="{r:.1f}"/>')
    return f'<g fill="{color}" opacity="0.95">{"".join(d)}</g>'


def trace(x0, x1, y, amp, color, fire, dash):
    """The signal crossing its threshold, and the notch where it commits to a button."""
    pts, n = [], 160
    for i in range(n + 1):
        t = i / n
        x = x0 + t * (x1 - x0)
        v = (math.sin(t * 7.1) * 0.40 + math.sin(t * 17.3 + 1.1) * 0.12
             + math.sin(t * 3.0 + 0.4) * 0.26)
        if 0.70 < t < 0.82:                      # the one deliberate gesture
            v += 1.50 * math.sin((t - 0.70) / 0.12 * math.pi)
        pts.append(f"{x:.1f},{y - v * amp:.1f}")
    on = y - 0.62 * amp
    fx = x0 + 0.706 * (x1 - x0)
    return (f'<line x1="{x0}" y1="{on:.1f}" x2="{x1 + 40}" y2="{on:.1f}" stroke="{dash}" stroke-width="2" '
            f'stroke-dasharray="9 8" opacity="0.45"/>'
            f'<rect x="{fx:.0f}" y="{on - 34:.0f}" width="86" height="34" fill="{fire}" opacity="0.9"/>'
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="4" '
            f'stroke-linejoin="round" stroke-linecap="round"/>')


def build(c):
    reg = "".join(
        f'<rect x="{70 + i * 30}" y="348" width="17" height="17" fill="{col}"/>'
        for i, col in enumerate(("#5dc21e", "#ff4f45", "#3ba4f5", "#ffc83d")))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Helm: a game controller you steer with your face">
<rect width="{W}" height="{H}" fill="{c['bg']}"/>
{halftone(72, 66, 548, 224, c['soft'])}
{wheel(988, 196, 104, c['blue'], c['pink'])}
{wordmark(76, 76, 140, c['pink'], opacity=0.9)}
{wordmark(70, 70, 140, c['ink'])}
{trace(70, 846, 306, 38, c['pink'], c['yellow'], c['dash'])}
{reg}
<rect x="0" y="{H - 9}" width="{W}" height="9" fill="{c['blue']}"/>
</svg>'''


root = Path(__file__).resolve().parent
root.mkdir(parents=True, exist_ok=True)
for name, c in (("banner-light.svg", LIGHT), ("banner-dark.svg", DARK)):
    (root / name).write_text(build(c))
    print("wrote", root / name, (root / name).stat().st_size, "bytes")
