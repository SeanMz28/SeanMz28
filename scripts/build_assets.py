#!/usr/bin/env python3
"""Generate the profile README's banner and project cards as self-contained SVGs.

Each SVG embeds subsets of the portfolio site's fonts (Bricolage Grotesque, Instrument Sans,
JetBrains Mono), because GitHub renders README images without loading web fonts. Every asset
comes in a dark and a light version that the README picks between with <picture>.

    pip install fonttools brotli
    python scripts/build_assets.py

Fonts are downloaded from the google/fonts repository into scripts/.fonts on first run, or read
from $FONT_DIR if it is set.
"""

import base64
import io
import os
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONT_DIR = Path(os.environ.get("FONT_DIR", Path(__file__).resolve().parent / ".fonts"))
GOOGLE_FONTS = "https://github.com/google/fonts/raw/main/ofl/"

# family name -> (file, source path, axis values for the static instance)
FONTS = {
    "SMDisplay": ("BricolageGrotesque.ttf", "bricolagegrotesque/BricolageGrotesque%5Bopsz,wdth,wght%5D.ttf",
                  {"opsz": 96, "wdth": 100, "wght": 800}),
    "SMSans": ("InstrumentSans.ttf", "instrumentsans/InstrumentSans%5Bwdth,wght%5D.ttf",
               {"wdth": 100, "wght": 500}),
    "SMMono": ("JetBrainsMono.ttf", "jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf", {"wght": 500}),
}
FALLBACK = {"SMDisplay": "'Helvetica Neue', Arial, sans-serif",
            "SMSans": "'Helvetica Neue', Arial, sans-serif",
            "SMMono": "ui-monospace, Menlo, monospace"}

# Colours from the portfolio site (src/styles.css).
THEMES = {
    "dark": dict(bg="#0b0c10", surface="#13151b", text="#f2f0eb", muted="#a4a8b3", accent="#ff7a3d",
                 accent_ink="#160a03", ink="#ffffff", line_op=0.09, line_strong_op=0.2, dot_op=0.07,
                 glow_op=0.30),
    "light": dict(bg="#f3f4f6", surface="#ffffff", text="#0e1016", muted="#4f5562", accent="#c2410c",
                  accent_ink="#ffffff", ink="#0c0e14", line_op=0.09, line_strong_op=0.22, dot_op=0.08,
                  glow_op=0.16),
}

ROLES = ["web platforms", "AI products", "mobile apps", "3D games", "cloud backends", "desktop apps"]

PROJECTS = [
    dict(slug="practicelab", label="LIVE APP", title="PracticeLab",
         desc="A learning platform for my tutoring students: shared notes, auto-graded quizzes "
              "and a tutor grading queue.",
         tags=["Next.js", "TypeScript", "Convex", "Better Auth"]),
    dict(slug="saitama", label="LIVE APP", title="Project Saitama",
         desc="Log daily push-ups, keep your streak alive and climb a global leaderboard.",
         tags=["Next.js", "React", "Firebase", "Tailwind"]),
    dict(slug="nitro", label="PLAY IN BROWSER", title="Nitro Assault",
         desc="A 3D time-trial combat racing game, optimized with instanced meshes and frame "
              "profiling.",
         tags=["Three.js", "Cannon.js", "JavaScript"]),
    dict(slug="crafter", label="REINFORCEMENT LEARNING", title="Crafter RL",
         desc="DQN, PPO and QR-DQN agents for the Crafter survival game, tested with LSTMs, frame "
              "stacking and reward shaping.",
         tags=["Python", "Stable-Baselines3", "Gymnasium"]),
    dict(slug="saplg", label="PROCEDURAL GENERATION", title="SAPLG",
         desc="Evolves playable platformer levels with FI-2POP, a two-population genetic "
              "algorithm, seeded from Rainbow Islands maps.",
         tags=["Python", "PyTorch", "NumPy"]),
    dict(slug="cnn", label="COMPUTER VISION", title="Grayscale Image CNN",
         desc="A PyTorch CNN that classifies noisy grayscale images, with a hand-written cleanup "
              "pass before training.",
         tags=["Python", "PyTorch", "NumPy"]),
]


class Fonts:
    """Static font instances used both to measure text and to emit per-SVG subsets."""

    def __init__(self):
        FONT_DIR.mkdir(parents=True, exist_ok=True)
        self.fonts = {}
        for family, (filename, source, axes) in FONTS.items():
            path = FONT_DIR / filename
            if not path.exists():
                urllib.request.urlretrieve(GOOGLE_FONTS + source, path)
            font = instantiateVariableFont(TTFont(path), axes)
            buf = io.BytesIO()
            font.save(buf)
            self.fonts[family] = buf.getvalue()

    def width(self, text, family, size, spacing=0.0):
        font = TTFont(io.BytesIO(self.fonts[family]))
        cmap, hmtx = font.getBestCmap(), font["hmtx"]
        upm = font["head"].unitsPerEm
        adv = sum(hmtx[cmap[ord(ch)]][0] for ch in text if ord(ch) in cmap)
        return adv * size / upm + spacing * max(len(text) - 1, 0)

    def face(self, family, chars):
        font = TTFont(io.BytesIO(self.fonts[family]))
        options = subset.Options()
        options.flavor = "woff2"
        options.layout_features = ["kern", "liga"]
        sub = subset.Subsetter(options)
        sub.populate(text="".join(sorted(set(chars))))
        sub.subset(font)
        buf = io.BytesIO()
        font.save(buf)
        data = base64.b64encode(buf.getvalue()).decode()
        return (f"@font-face{{font-family:{family};"
                f"src:url(data:font/woff2;base64,{data}) format('woff2');}}")


class Svg:
    def __init__(self, fonts, width, height, title):
        self.fonts, self.w, self.h, self.title = fonts, width, height, title
        self.defs, self.body, self.css, self.used = [], [], [], {}

    def text(self, x, y, s, family, size, fill, spacing=0.0, anchor="start", opacity=None, cls=None):
        self.used.setdefault(family, set()).update(s)
        attrs = [f'x="{x:.1f}"', f'y="{y:.1f}"', f'font-family="{family}, {FALLBACK[family]}"',
                 f'font-size="{size}"', f'fill="{fill}"']
        if spacing:
            attrs.append(f'letter-spacing="{spacing}"')
        if anchor != "start":
            attrs.append(f'text-anchor="{anchor}"')
        if opacity is not None:
            attrs.append(f'fill-opacity="{opacity}"')
        if cls:
            attrs.append(f'class="{cls}"')
        return f'<text {" ".join(attrs)}>{escape(s)}</text>'

    def render(self):
        faces = "".join(self.fonts.face(f, chars) for f, chars in self.used.items())
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{escape(self.title)}">'
                f'<title>{escape(self.title)}</title>'
                f'<style>{faces}{"".join(self.css)}</style>'
                f'<defs>{"".join(self.defs)}</defs>{"".join(self.body)}</svg>\n')


REDUCED_MOTION = "@media (prefers-reduced-motion: reduce){.anim{animation:none!important}}"


def pill(svg, x, y, label, t, dot=True):
    """A rounded label like the site's hero badge, with an optional pulsing accent dot."""
    size, pad = 14, 16
    text_w = svg.fonts.width(label, "SMMono", size, 1.4)
    dot_w = 18 if dot else 0
    w, h = pad * 2 + dot_w + text_w, 36
    parts = [f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h}" rx="18" fill="{t["surface"]}" '
             f'stroke="{t["ink"]}" stroke-opacity="{t["line_strong_op"]}"/>']
    if dot:
        parts.append(f'<circle class="anim pulse" cx="{x + pad + 4}" cy="{y + h / 2}" r="4.5" '
                     f'fill="{t["accent"]}"/>')
    parts.append(svg.text(x + pad + dot_w, y + h / 2 + 5, label, "SMMono", size, t["muted"], 1.4))
    return "".join(parts), w


def banner(fonts, theme):
    t = THEMES[theme]
    W, H = 1280, 400
    svg = Svg(fonts, W, H, "Sean Mahlanza, full-stack software engineer")
    cx, cy, r = 1058, 200, 132  # orbit centre and radius

    svg.defs.append(f'<clipPath id="card"><rect width="{W}" height="{H}" rx="28"/></clipPath>')
    svg.defs.append(f'<pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse">'
                    f'<circle cx="2" cy="2" r="1.2" fill="{t["ink"]}" fill-opacity="{t["dot_op"]}"/>'
                    f'</pattern>')
    svg.defs.append(f'<radialGradient id="glow" cx="{cx}" cy="{cy}" r="330" gradientUnits="userSpaceOnUse">'
                    f'<stop offset="0" stop-color="{t["accent"]}" stop-opacity="{t["glow_op"]}"/>'
                    f'<stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/></radialGradient>')

    svg.body.append(f'<g clip-path="url(#card)"><rect width="{W}" height="{H}" fill="{t["bg"]}"/>'
                    f'<rect width="{W}" height="{H}" fill="url(#dots)"/>'
                    f'<rect width="{W}" height="{H}" fill="url(#glow)"/></g>')
    svg.body.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="28" fill="none" '
                    f'stroke="{t["ink"]}" stroke-opacity="{t["line_op"]}"/>')

    badge, _ = pill(svg, 56, 50, "FULL-STACK SOFTWARE ENGINEER · PROKING SOLUTIONS", t)
    svg.body.append(badge)

    # Name, with the site's accent full stop.
    name, size = "Sean Mahlanza", 100
    name_w = fonts.width(name, "SMDisplay", size, -3)
    svg.body.append(svg.text(52, 196, name, "SMDisplay", size, t["text"], -3))
    svg.body.append(f'<circle cx="{52 + name_w + 16:.1f}" cy="182" r="11" fill="{t["accent"]}"/>')

    # "I build <role>" with the role ticking through ROLES like the site's hero.
    lead, rsize, step = "I build ", 46, 58
    lead_w = fonts.width(lead, "SMDisplay", rsize, -1)
    base_y, rx = 270, 56 + lead_w
    svg.body.append(svg.text(56, base_y, lead, "SMDisplay", rsize, t["muted"], -1))
    roles = ROLES + ROLES[:1]
    words = "".join(svg.text(rx, base_y + i * step, w, "SMDisplay", rsize, t["accent"], -1)
                    for i, w in enumerate(roles))
    svg.defs.append(f'<clipPath id="ticker"><rect x="{rx - 4:.1f}" y="{base_y - 46}" width="520" '
                    f'height="{step}"/></clipPath>')
    svg.body.append(f'<g clip-path="url(#ticker)"><g class="anim ticker">{words}</g></g>')
    n, frames = len(ROLES), []
    for i in range(n):
        start, hold = 100 * i / n, 100 * i / n + 100 / n * 0.8
        frames.append(f"{start:.2f}%,{hold:.2f}%{{transform:translateY({-i * step}px)}}")
    frames.append(f"100%{{transform:translateY({-n * step}px)}}")
    svg.css.append(f".ticker{{animation:tick {n * 2.4:.1f}s cubic-bezier(.7,0,.3,1) infinite}}"
                   f"@keyframes tick{{{''.join(frames)}}}")

    stack = "JOHANNESBURG, SOUTH AFRICA  ·  TYPESCRIPT  NEXT.JS  NODE.JS  PYTHON  LLMS"
    svg.body.append(svg.text(56, 344, stack, "SMMono", 14, t["muted"], 1.6))

    # Orbit, monogram and floating chips on the right.
    svg.body.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{t["accent"]}" '
                    f'stroke-opacity="0.45" stroke-dasharray="2 9" stroke-linecap="round"/>')
    svg.body.append(f'<g class="anim orbit"><circle cx="{cx}" cy="{cy}" r="{r}" fill="none"/>'
                    f'<circle cx="{cx}" cy="{cy - r}" r="7" fill="{t["accent"]}"/></g>')
    svg.body.append(f'<rect x="{cx - 62}" y="{cy - 62}" width="124" height="124" rx="32" '
                    f'fill="{t["accent"]}"/>')
    svg.body.append(svg.text(cx, cy + 21, "SM", "SMDisplay", 60, t["accent_ink"], -2, anchor="middle"))
    chip1, w1 = pill(svg, 0, 0, "LLM EVALS", t, dot=False)
    chip2, w2 = pill(svg, 0, 0, "FULL STACK", t, dot=False)
    svg.body.append(f'<g class="anim bob1"><g transform="translate({cx - r - w1 / 2 + 6:.1f},{cy - 112})">'
                    f'{chip1}</g></g>')
    svg.body.append(f'<g class="anim bob2"><g transform="translate({cx + r - w2 / 2 - 10:.1f},{cy + 84})">'
                    f'{chip2}</g></g>')

    svg.css.append(".pulse{animation:pulse 2.4s ease-in-out infinite}"
                   "@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}"
                   ".orbit{transform-box:fill-box;transform-origin:center;animation:spin 18s linear infinite}"
                   "@keyframes spin{to{transform:rotate(360deg)}}"
                   ".bob1{animation:bob 6s ease-in-out infinite}"
                   ".bob2{animation:bob 6s ease-in-out -3s infinite}"
                   "@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-8px)}}")
    svg.css.append(REDUCED_MOTION)
    return svg.render()


def wrap(fonts, text, family, size, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if fonts.width(trial, family, size) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + [line]


def card(fonts, project, theme):
    t = THEMES[theme]
    W, H, pad = 600, 250, 30
    svg = Svg(fonts, W, H, f'{project["title"]}: {project["desc"]}')
    svg.defs.append(f'<radialGradient id="corner" cx="{W}" cy="0" r="320" gradientUnits="userSpaceOnUse">'
                    f'<stop offset="0" stop-color="{t["accent"]}" stop-opacity="{t["glow_op"] * 0.45:.2f}"/>'
                    f'<stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/></radialGradient>')
    svg.defs.append(f'<clipPath id="c"><rect width="{W}" height="{H}" rx="22"/></clipPath>')
    svg.body.append(f'<g clip-path="url(#c)"><rect width="{W}" height="{H}" fill="{t["surface"]}"/>'
                    f'<rect width="{W}" height="{H}" fill="url(#corner)"/></g>')
    svg.body.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="22" fill="none" '
                    f'stroke="{t["ink"]}" stroke-opacity="{t["line_strong_op"]}"/>')

    svg.body.append(svg.text(pad, 50, project["label"], "SMMono", 13, t["accent"], 2))
    ax, ay = W - pad - 18, 44  # arrow icon centre
    svg.body.append(f'<circle cx="{ax}" cy="{ay}" r="18" fill="none" stroke="{t["ink"]}" '
                    f'stroke-opacity="{t["line_strong_op"]}"/>'
                    f'<path d="M{ax - 5} {ay + 5}L{ax + 5} {ay - 5}M{ax - 3} {ay - 5}H{ax + 5}V{ay + 3}" '
                    f'fill="none" stroke="{t["text"]}" stroke-width="2" stroke-linecap="round" '
                    f'stroke-linejoin="round"/>')

    svg.body.append(svg.text(pad - 2, 98, project["title"], "SMDisplay", 34, t["text"], -1))
    for i, line in enumerate(wrap(fonts, project["desc"], "SMSans", 17, W - 2 * pad)[:2]):
        svg.body.append(svg.text(pad, 134 + i * 25, line, "SMSans", 17, t["muted"]))

    x = pad
    for tag in project["tags"]:
        tw = fonts.width(tag, "SMMono", 13) + 26
        svg.body.append(f'<rect x="{x}" y="190" width="{tw:.1f}" height="30" rx="15" fill="none" '
                        f'stroke="{t["ink"]}" stroke-opacity="{t["line_strong_op"]}"/>')
        svg.body.append(svg.text(x + 13, 210, tag, "SMMono", 13, t["text"]))
        x += tw + 8
    return svg.render()


def main():
    fonts = Fonts()
    ASSETS.mkdir(exist_ok=True)
    for theme in THEMES:
        (ASSETS / f"banner-{theme}.svg").write_text(banner(fonts, theme))
        for project in PROJECTS:
            (ASSETS / f'card-{project["slug"]}-{theme}.svg').write_text(card(fonts, project, theme))
    for path in sorted(ASSETS.glob("*.svg")):
        print(f"{path.relative_to(ROOT)}  {path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
