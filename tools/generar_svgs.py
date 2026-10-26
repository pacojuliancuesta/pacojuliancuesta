"""Perfil de GitHub de Paco como expediente de reconocimiento.

Genera SVGs con fuentes incrustadas (subset woff2 en base64), textura de papel,
sellos de tinta y animaciones que degradan bien: si la animación no se ejecuta,
el estado base es el diseño final visible.

Uso: python3 tools/generar_svgs.py assets <ruta a google/fonts/ofl>
(necesita fonttools y brotli; fuentes: Anton, IBM Plex Mono, Instrument Serif)
"""
import base64
import html
import io
import random
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape as esc

from fontTools import subset
from fontTools.ttLib import TTFont

OUT = Path(sys.argv[1])
FONTS_DIR = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

FONTS = {
    "Anton": FONTS_DIR / "anton/Anton-Regular.ttf",
    "Plex": FONTS_DIR / "ibmplexmono/IBMPlexMono-Regular.ttf",
    "PlexB": FONTS_DIR / "ibmplexmono/IBMPlexMono-SemiBold.ttf",
    "Serif": FONTS_DIR / "instrumentserif/InstrumentSerif-Italic.ttf",
}
_TT = {k: TTFont(v) for k, v in FONTS.items()}

PAPER = "#efe9dc"
PAPER2 = "#e5ddca"
INK = "#16140f"
INK2 = "#4b463b"
MUTED = "#8c8370"
RED = "#c4271d"
YELLOW = "#f3c531"
TERM = "#14130f"
TERM_TXT = "#e9e2d0"


# ───────────────────────────── utilidades ─────────────────────────────
def tw(font, text, size, ls=0):
    """Ancho real del texto según las métricas de la fuente."""
    f = _TT[font]
    cmap = f.getBestCmap()
    hmtx = f["hmtx"]
    upm = f["head"].unitsPerEm
    total = 0
    for ch in text:
        g = cmap.get(ord(ch))
        total += hmtx[g][0] if g else upm * 0.5
    return total * size / upm + ls * len(text)


def font_face(name, chars):
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga"]
    opts.name_IDs = []
    font = TTFont(FONTS[name])
    sub = subset.Subsetter(opts)
    sub.populate(text=chars)
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"@font-face{{font-family:'{name}';src:url(data:font/woff2;base64,{b64}) format('woff2');}}"


def finish(svg, used):
    """Incrusta solo los glifos que aparecen en el SVG."""
    text = html.unescape(" ".join(re.findall(r">([^<>]+)<", svg)))
    chars = "".join(sorted(set(text))) + " "
    faces = "".join(font_face(n, chars) for n in used)
    return svg.replace("/*FONTS*/", faces)


def write(name, svg, used):
    (OUT / name).write_text(finish(svg, used), encoding="utf-8")


def defs_common(seed=7):
    return f'''
  <filter id="grain" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="3" seed="{seed}" stitchTiles="stitch"/>
    <feColorMatrix type="saturate" values="0"/>
    <feComponentTransfer><feFuncA type="table" tableValues="0 .13"/></feComponentTransfer>
  </filter>
  <filter id="stain" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency=".008" numOctaves="2" seed="{seed + 3}"/>
    <feColorMatrix type="matrix" values="0 0 0 0 .45  0 0 0 0 .36  0 0 0 0 .2  0 0 0 -1.4 .62"/>
  </filter>
  <filter id="ink" x="-5%" y="-5%" width="110%" height="110%">
    <feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="{seed + 1}" result="n"/>
    <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  -3.2 0 0 0 2.75" result="m"/>
    <feComposite in="SourceGraphic" in2="m" operator="in" result="c"/>
    <feTurbulence type="turbulence" baseFrequency=".04" numOctaves="1" seed="{seed + 2}" result="w"/>
    <feDisplacementMap in="c" in2="w" scale="2.2"/>
  </filter>
  <filter id="rough" x="-2%" y="-20%" width="104%" height="140%">
    <feTurbulence type="fractalNoise" baseFrequency=".05 .4" numOctaves="2" seed="{seed + 4}" result="w"/>
    <feDisplacementMap in="SourceGraphic" in2="w" scale="5"/>
  </filter>'''


def paper(W, H, rx=6):
    return f'''<rect width="{W}" height="{H}" rx="{rx}" fill="{PAPER}"/>
  <rect width="{W}" height="{H}" rx="{rx}" fill="{PAPER2}" filter="url(#stain)" opacity=".55"/>
  <rect width="{W}" height="{H}" rx="{rx}" filter="url(#grain)"/>'''


def barcode(x, y, w, h, seed, color=INK):
    rnd = random.Random(seed)
    bars, cx = [], x
    while cx < x + w:
        bw = rnd.choice([1.4, 1.4, 2.4, 3.6])
        if rnd.random() > .38:
            bars.append(f'<rect x="{cx:.1f}" y="{y}" width="{bw}" height="{h}"/>')
        cx += bw + rnd.choice([1.2, 1.8, 2.6])
    return f'<g fill="{color}">{"".join(bars)}</g>'


def stamp(cx, cy, lines, angle, color=RED, size=26, pad=18, cls="stamp", delay=0):
    """Sello rectangular de doble borde con textura de tinta."""
    sizes = [size if i == 0 else size * .62 for i in range(len(lines))]
    fonts = ["Anton" if i == 0 else "PlexB" for i in range(len(lines))]
    w = max(tw(f, t, s) for f, t, s in zip(fonts, lines, sizes)) + pad * 2
    h = sum(s * 1.18 for s in sizes) + pad * 1.4
    x0, y0 = -w / 2, -h / 2
    texts, yy = [], y0 + pad * .7
    for t, s, f in zip(lines, sizes, fonts):
        yy += s * 1.02
        fam = "Anton" if f == "Anton" else "PlexB"
        ls = "1.5px" if f == "Anton" else "2px"
        texts.append(f'<text x="0" y="{yy:.1f}" text-anchor="middle" font-family="{fam}" font-size="{s:.1f}" letter-spacing="{ls}" fill="{color}">{esc(t)}</text>')
        yy += s * .16
    style = f' style="animation-delay:{delay}s"' if delay else ""
    return f'''<g transform="translate({cx} {cy}) rotate({angle})"><g class="{cls}"{style}><g filter="url(#ink)" opacity=".9">
    <rect x="{x0:.1f}" y="{y0:.1f}" width="{w:.1f}" height="{h:.1f}" rx="4" fill="none" stroke="{color}" stroke-width="3.2"/>
    <rect x="{x0 + 6:.1f}" y="{y0 + 6:.1f}" width="{w - 12:.1f}" height="{h - 12:.1f}" rx="2" fill="none" stroke="{color}" stroke-width="1.4"/>
    {"".join(texts)}
  </g></g></g>'''


BASE_CSS = f'''
  /*FONTS*/
  .mono {{ font-family: 'Plex', monospace; }}
  .monob {{ font-family: 'PlexB', monospace; }}
  .anton {{ font-family: 'Anton', Impact, sans-serif; }}
  .serif {{ font-family: 'Serif', Georgia, serif; font-style: italic; }}
  /* Sello: el estado base es el visible; la animación solo añade el golpe */
  .stamp {{ transform-box: fill-box; transform-origin: center; animation: thud .5s cubic-bezier(.2,1.6,.4,1) .9s backwards; }}
  @keyframes thud {{ from {{ opacity: 0; transform: scale(1.9) rotate(-6deg); }} to {{ opacity: 1; transform: none; }} }}
  .redact {{ transform-box: fill-box; transform-origin: right center; animation: unredact .7s cubic-bezier(.7,0,.3,1) both; transform: scaleX(0); }}
  @keyframes unredact {{ 0%,35% {{ transform: scaleX(1); }} 100% {{ transform: scaleX(0); }} }}
'''


def section_head(x, y, num, title, note=""):
    s = f'''<text x="{x}" y="{y}" class="anton" font-size="44" fill="{INK}" letter-spacing="1">{esc(num)}</text>
  <text x="{x + tw("Anton", num, 44, 1) + 4}" y="{y}" class="anton" font-size="44" fill="{INK}" letter-spacing="1">{esc(title)}</text>'''
    if note:
        s += f'\n  <text x="{x + tw("Anton", num + title, 44, 1) + 46}" y="{y - 4}" class="serif" font-size="25" fill="{RED}">{esc(note)}</text>'
    return s


def header_strip(W, left, right, y=34):
    return f'''<text x="40" y="{y}" class="mono" font-size="13" fill="{INK2}" letter-spacing="2">{esc(left)}</text>
  <text x="{W - 40}" y="{y}" class="mono" font-size="13" fill="{INK2}" letter-spacing="2" text-anchor="end">{esc(right)}</text>
  <line x1="40" y1="{y + 12}" x2="{W - 40}" y2="{y + 12}" stroke="{INK}" stroke-width="2"/>
  <line x1="40" y1="{y + 17}" x2="{W - 40}" y2="{y + 17}" stroke="{INK}" stroke-width=".8"/>'''


# ─────────────────────────────── PORTADA ───────────────────────────────
def cover():
    W, H = 1200, 520
    fields = [
        ("ALIAS", "paco"),
        ("BASE", "Madrid, España"),
        ("FORMACIÓN", "2º ASIR · Medac"),
        ("FOCO", "pentesting · SOC"),
    ]
    fx, fy = 64, 412
    colw = 268
    fparts = []
    for i, (k, v) in enumerate(fields):
        x = fx + i * colw
        vw = tw("PlexB", v, 19)
        fparts.append(f'''<text x="{x}" y="{fy}" class="mono" font-size="12" fill="{MUTED}" letter-spacing="2.4">{esc(k)}</text>
    <text x="{x}" y="{fy + 30}" class="monob" font-size="19" fill="{INK}">{esc(v)}</text>
    <line x1="{x}" y1="{fy + 41}" x2="{x + colw - 28}" y2="{fy + 41}" stroke="{INK}" stroke-width="1" stroke-dasharray="2 4"/>
    <rect class="redact" x="{x - 3}" y="{fy + 12}" width="{vw + 8}" height="25" fill="{INK}" style="animation-delay:{0.25 + i * 0.18:.2f}s"/>''')
    fields_svg = "\n    ".join(fparts)

    name1, name2 = "FRANCISCO JULIÁN", "CUESTA"
    n1 = 108
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<style>{BASE_CSS}
  .cursor {{ animation: blink 1.05s steps(1) infinite; }}
  @keyframes blink {{ 50% {{ opacity: 0; }} }}
  .scan {{ animation: scan 5.5s ease-in-out infinite; }}
  @keyframes scan {{ 0%,100% {{ transform: translateY(0); opacity: 0; }} 10%,90% {{ opacity: .55; }} 50% {{ transform: translateY(300px); }} }}
</style>
<defs>{defs_common(11)}
  <clipPath id="page"><rect width="{W}" height="{H}" rx="6"/></clipPath>
  <linearGradient id="beam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{RED}" stop-opacity="0"/><stop offset="1" stop-color="{RED}" stop-opacity=".22"/></linearGradient>
</defs>
<g clip-path="url(#page)">
  {paper(W, H)}
  {header_strip(W, "EXP. Nº PJC-2026/ASIR  ·  INFORME DE RECONOCIMIENTO", "HOJA 1 DE 5")}
  <g transform="translate({W - 40 - 190} 66)">
    <rect width="190" height="30" fill="{RED}"/>
    <text x="95" y="21" text-anchor="middle" class="monob" font-size="13" fill="{PAPER}" letter-spacing="3">NIVEL: PÚBLICO</text>
  </g>

  <text x="64" y="132" class="mono" font-size="15" fill="{INK2}" letter-spacing="1.5">OBJETIVO DEL ANÁLISIS ─────</text>
  <text x="64" y="252" class="anton" font-size="{n1}" fill="{INK}" letter-spacing="1">{name1}</text>
  <text x="64" y="370" class="anton" font-size="{n1}" fill="none" stroke="{INK}" stroke-width="2.2" letter-spacing="3">{name2}</text>
  <g class="scan"><rect x="40" y="96" width="{W - 80}" height="34" fill="url(#beam)" opacity=".7"/><line x1="40" y1="130" x2="{W - 40}" y2="130" stroke="{RED}" stroke-width="1.2" opacity=".7"/></g>

  <text x="{64 + tw("Anton", name2, n1, 3) + 40}" y="300" class="mono" font-size="17" fill="{INK}">Estudiante de 2º de ASIR.</text>
  <text x="{64 + tw("Anton", name2, n1, 3) + 40}" y="326" class="mono" font-size="17" fill="{INK}">Me formo en ciberseguridad</text>
  <text x="{64 + tw("Anton", name2, n1, 3) + 40}" y="352" class="mono" font-size="17" fill="{INK}">rompiendo mis propios labs<tspan class="cursor" fill="{RED}">▌</tspan></text>

  {stamp(1012, 232, ["BUSCA FCT", "DESDE MARZO 2027"], -9, size=38, pad=18)}
  <text x="808" y="352" class="serif" font-size="26" fill="{RED}" transform="rotate(-3 808 352)">ciberseguridad, SOC o sistemas</text>

  <line x1="40" y1="388" x2="{W - 40}" y2="388" stroke="{INK}" stroke-width=".8"/>
    {fields_svg}
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="6" fill="none" stroke="{INK}" stroke-opacity=".25"/>
</svg>'''
    return svg


# ────────────────────────────── RECONOCIMIENTO ──────────────────────────────
def recon():
    W = 1200
    P = f'<tspan fill="{YELLOW}">paco@kali</tspan><tspan fill="{MUTED}">:~$ </tspan>'
    rows = [
        P + f'<tspan fill="{TERM_TXT}">nmap -sV -O paco.local</tspan>',
        f'<tspan fill="{MUTED}">Starting Nmap 7.94 at 2026-10-28 10:00 CET</tspan>',
        f'<tspan fill="{TERM_TXT}">Nmap scan report for paco.local (10.20.26.2)</tspan>',
        f'<tspan fill="{TERM_TXT}">Host is up (0.0021s latency).  </tspan><tspan fill="{MUTED}">Not shown: 65529 closed tcp ports</tspan>',
        ("head",),
        ("port", "22/tcp", "ssh", "hardening: OpenSSH reforzado · UFW · Fail2Ban"),
        ("port", "53/tcp", "domain", "redes: TCP/IP · VLANs · DNS · DHCP · subnetting"),
        ("port", "445/tcp", "smb", "Windows Server · Active Directory"),
        ("port", "514/tcp", "syslog", "log-analyzer: 6 patrones de ataque detectados"),
        ("port", "8080/tcp", "http", "web-hacking-lab: DVWA + Burp Suite (en curso)"),
        ("port", "9100/tcp", "scripting", "Python · Bash · Git · Jinja2"),
        f'<tspan fill="{TERM_TXT}">OS details: </tspan><tspan fill="{TERM_TXT}">Linux Mint / Windows (dual boot)</tspan>',
        f'<tspan fill="{TERM_TXT}">Service Info: Host: MADRID; Formación: 2º ASIR; Certs: Cisco Intro to Cybersecurity</tspan>',
        f'<tspan fill="{RED}"># Nmap done: 1 host up · disponible para FCT desde 03/2027</tspan>',
        P + f'<tspan fill="{TERM_TXT}" class="cursor">█</tspan>',
    ]
    top, step = 168, 27
    tx, tyy = 64, 130
    H_term = 40 + step * len(rows) + 10
    H = tyy + H_term + 56
    cols = [96, 196, 296, 418]
    lines = []
    for i, r in enumerate(rows):
        y = top + i * step
        if isinstance(r, tuple) and r[0] == "head":
            lines.append(f'<text y="{y}" class="mono" font-size="15" fill="{MUTED}"><tspan x="{cols[0]}">PORT</tspan><tspan x="{cols[1]}">STATE</tspan><tspan x="{cols[2]}">SERVICE</tspan><tspan x="{cols[3]}">VERSION</tspan></text>')
        elif isinstance(r, tuple):
            _, port, svc, ver = r
            lines.append(f'<text y="{y}" class="mono" font-size="15"><tspan x="{cols[0]}" fill="{TERM_TXT}">{port}</tspan><tspan x="{cols[1]}" fill="{YELLOW}">open</tspan><tspan x="{cols[2]}" fill="{TERM_TXT}">{svc}</tspan><tspan x="{cols[3]}" fill="#b9b19c">{esc(ver)}</tspan></text>')
        else:
            lines.append(f'<text x="{cols[0]}" y="{y}" class="mono" font-size="15" xml:space="preserve">{r}</text>')
    body = "\n    ".join(lines)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<style>{BASE_CSS}
  .cursor {{ animation: blink 1.05s steps(1) infinite; }}
  @keyframes blink {{ 50% {{ opacity: 0; }} }}
  /* Cortina que baja y revela la salida línea a línea; en reposo está fuera de vista */
  .curtain {{ transform: translateY({H_term}px); animation: reveal 3.4s steps({len(rows)}) .2s backwards; }}
  @keyframes reveal {{ from {{ transform: translateY(0); }} to {{ transform: translateY({H_term}px); }} }}
</style>
<defs>{defs_common(21)}
  <clipPath id="page"><rect width="{W}" height="{H}" rx="6"/></clipPath>
  <clipPath id="term"><rect x="{tx}" y="{tyy}" width="{W - 2 * tx}" height="{H_term}" rx="8"/></clipPath>
</defs>
<g clip-path="url(#page)">
  {paper(W, H)}
  {header_strip(W, "EXP. Nº PJC-2026/ASIR  ·  FASE 01", "HOJA 2 DE 5")}
  {section_head(64, 104, "01 ·", " RECONOCIMIENTO", "sí, me he escaneado a mí mismo")}
  <rect x="{tx + 6}" y="{tyy + 8}" width="{W - 2 * tx}" height="{H_term}" rx="8" fill="{INK}" opacity=".18"/>
  <g clip-path="url(#term)">
    <rect x="{tx}" y="{tyy}" width="{W - 2 * tx}" height="{H_term}" fill="{TERM}"/>
    <rect x="{tx}" y="{tyy}" width="{W - 2 * tx}" height="{H_term}" filter="url(#grain)" opacity=".6"/>
    <circle cx="{tx + 20}" cy="{tyy + 18}" r="5" fill="{RED}"/><circle cx="{tx + 38}" cy="{tyy + 18}" r="5" fill="{YELLOW}"/><circle cx="{tx + 56}" cy="{tyy + 18}" r="5" fill="{MUTED}"/>
    <text x="{W / 2}" y="{tyy + 23}" text-anchor="middle" class="mono" font-size="12" fill="{MUTED}" letter-spacing="2">TTY1 · KALI · RECON</text>
    {body}
    <rect class="curtain" x="{tx}" y="{tyy + 36}" width="{W - 2 * tx}" height="{H_term}" fill="{TERM}"/>
  </g>
  <text x="{W - 64}" y="{H - 22}" text-anchor="end" class="mono" font-size="12" fill="{MUTED}" letter-spacing="1.5">ESCANEO AUTORIZADO · SCOPE: YO MISMO</text>
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="6" fill="none" stroke="{INK}" stroke-opacity=".25"/>
</svg>'''


# ───────────────────────────── EVIDENCIAS ─────────────────────────────
def wrap(text, font, size, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if tw(font, t, size) > maxw and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    lines.append(cur)
    return lines


def evidence(num, title, repo, what, result, tools, status, live, seed):
    W, H = 590, 400
    hole_x, hole_y = 52, 52
    desc = wrap(what, "Plex", 14.5, W - 2 * 40)
    desc_svg = "\n    ".join(
        f'<text x="40" y="{196 + i * 22}" class="mono" font-size="14.5" fill="{INK}">{esc(l)}</text>' for i, l in enumerate(desc))
    ry = 196 + len(desc) * 22 + 18
    title_size = 44
    while tw("Anton", title.upper(), title_size, 1) > W - 80:
        title_size -= 1
    st_color = INK if live else RED
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<style>{BASE_CSS}
  .tag {{ transform-origin: {hole_x}px {hole_y}px; animation: sway 6s ease-in-out infinite; }}
  @keyframes sway {{ 0%,100% {{ transform: rotate(0deg); }} 50% {{ transform: rotate(-.9deg); }} }}
</style>
<defs>{defs_common(seed)}
  <clipPath id="shape"><path d="M26 0 H{W - 26} L{W} 26 V{H} H0 V26 Z"/></clipPath>
</defs>
<g class="tag">
  <path d="M26 6 H{W - 26} L{W - 2} 30 V{H - 2} H4 V30 Z" fill="{INK}" opacity=".16" transform="translate(4 6)"/>
  <g clip-path="url(#shape)">
    {paper(W, H, 0)}
    <rect x="0" y="0" width="{W}" height="96" fill="{INK}"/>
    <rect x="0" y="0" width="{W}" height="96" filter="url(#grain)" opacity=".7"/>
    <circle cx="{hole_x}" cy="{hole_y}" r="17" fill="{PAPER}" opacity=".9"/>
    <circle cx="{hole_x}" cy="{hole_y}" r="9" fill="#0d0c09" stroke="{MUTED}" stroke-width="2"/>
    <text x="92" y="44" class="mono" font-size="12" fill="{MUTED}" letter-spacing="3">EVIDENCIA Nº</text>
    <text x="92" y="78" class="anton" font-size="34" fill="{PAPER}" letter-spacing="2">{num}</text>
    <text x="{W - 34}" y="44" text-anchor="end" class="mono" font-size="12" fill="{MUTED}" letter-spacing="2">PRUEBA: {esc(repo)}</text>
    {barcode(W - 34 - 170, 56, 170, 24, seed, PAPER)}
    <text x="40" y="{132 + title_size * .62:.0f}" class="anton" font-size="{title_size}" fill="{INK}" letter-spacing="1">{esc(title.upper())}</text>
    <line x1="40" y1="174" x2="{W - 40}" y2="174" stroke="{INK}" stroke-width=".8" stroke-dasharray="2 4"/>
    {desc_svg}
    <text x="40" y="{ry}" class="monob" font-size="14" fill="{RED}">▸ {esc(result)}</text>
    <text x="40" y="{H - 58}" class="mono" font-size="11" fill="{MUTED}" letter-spacing="2.4">HERRAMIENTAS</text>
    <text x="40" y="{H - 36}" class="monob" font-size="15" fill="{INK}">{esc("  /  ".join(tools))}</text>
    <line x1="0" y1="{H - 16}" x2="{W}" y2="{H - 16}" stroke="{INK}" stroke-width="1" stroke-dasharray="6 5" opacity=".5"/>
    {stamp(W - 108, H - 70, [status], -8, color=st_color, size=24, pad=14)}
  </g>
</g>
</svg>'''


def evidence_head():
    W, H = 1200, 150
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<style>{BASE_CSS}</style>
<defs>{defs_common(71)}
  <clipPath id="page"><rect width="{W}" height="{H}" rx="6"/></clipPath>
</defs>
<g clip-path="url(#page)">
  {paper(W, H)}
  {header_strip(W, "EXP. Nº PJC-2026/ASIR  ·  FASE 02", "HOJA 3 DE 5")}
  {section_head(64, 116, "02 ·", " EVIDENCIAS", "4 pruebas recogidas, todas en GitHub")}
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="6" fill="none" stroke="{INK}" stroke-opacity=".25"/>
</svg>'''


# ───────────────────────────── CRONOLOGÍA ─────────────────────────────
def chronology():
    W = 1200
    rows = [
        ("2023", "SMR", "IES Francisco de Goya", "Redes, sistemas y hardware. Mi base.", "done"),
        ("2025", "FCT", "Diebold Nixdorf", "Cajeros y POS en sucursales bancarias, ~3 incidencias al día.", "done"),
        ("2025", "CERT", "Cisco Intro to Cybersecurity", "Primera certificación de ciberseguridad.", "done"),
        ("2025", "ASIR", "Medac Madrid", "Arranco el grado superior.", "done"),
        ("2026", "AHORA", "2º de ASIR + labs", "Web Hacking Lab y Cisco Cybersecurity Analyst en curso.", "now"),
        ("03/2027", "OBJETIVO", "FCT de ASIR", "En ciberseguridad, SOC o sistemas.", "goal"),
        ("2027", "SIGUIENTE", "eJPT", "Primera certificación ofensiva.", "next"),
    ]
    top, step = 186, 52
    H = top + step * len(rows) + 40
    cx = 220
    parts = []
    for i, (date, tag, what, note, st) in enumerate(rows):
        y = top + i * step
        color = {"done": INK, "now": INK, "goal": RED, "next": MUTED}[st]
        if st == "done":
            mark = f'<path d="M{cx - 7} {y - 6} l5 6 l10 -12" fill="none" stroke="{INK}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>'
        elif st == "now":
            mark = f'<circle cx="{cx}" cy="{y - 6}" r="9" fill="{INK}"/><circle cx="{cx}" cy="{y - 6}" r="9" fill="none" stroke="{INK}" class="ping"/>'
        elif st == "goal":
            mark = f'<circle cx="{cx}" cy="{y - 6}" r="9" fill="{PAPER}" stroke="{RED}" stroke-width="2.4"/><circle cx="{cx}" cy="{y - 6}" r="3.5" fill="{RED}"/>'
        else:
            mark = f'<circle cx="{cx}" cy="{y - 6}" r="8" fill="{PAPER}" stroke="{MUTED}" stroke-width="2" stroke-dasharray="3 3"/>'
        hl = ""
        if st == "now":
            hl = f'<rect class="marker" x="{cx + 30}" y="{y - 24}" width="{tw("Anton", what.upper(), 26, .8) + 22}" height="28" fill="{YELLOW}" opacity=".85" filter="url(#rough)"/>'
        tag_w = tw("PlexB", tag, 11, 1) + 16
        parts.append(f'''{hl}
    <text x="64" y="{y}" class="monob" font-size="17" fill="{color}">{esc(date)}</text>
    {mark}
    <text x="{cx + 40}" y="{y}" class="anton" font-size="26" fill="{color}" letter-spacing=".8">{esc(what.upper())}</text>
    <rect x="{cx + 40 + tw("Anton", what.upper(), 26, .8) + 22}" y="{y - 19}" width="{tag_w}" height="20" fill="none" stroke="{color}" stroke-width="1.2"/>
    <text x="{cx + 40 + tw("Anton", what.upper(), 26, .8) + 22 + tag_w / 2}" y="{y - 5}" text-anchor="middle" class="monob" font-size="11" fill="{color}" letter-spacing="1">{esc(tag)}</text>
    <text x="{W - 64}" y="{y}" text-anchor="end" class="mono" font-size="14" fill="{INK2 if st != "next" else MUTED}">{esc(note)}</text>
    <line x1="64" y1="{y + 18}" x2="{W - 64}" y2="{y + 18}" stroke="{INK}" stroke-width=".6" stroke-dasharray="1 4" opacity=".6"/>''')
    body = "\n    ".join(parts)
    goal_y = top + 5 * step
    goal_x = cx + 40 + tw("Anton", "FCT DE ASIR", 26, .8) + 22 + tw("PlexB", "OBJETIVO", 11, 1) + 16 + 20
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<style>{BASE_CSS}
  .ping {{ transform-box: fill-box; transform-origin: center; animation: ping 2.2s ease-out infinite; }}
  @keyframes ping {{ from {{ opacity: .8; transform: scale(1); }} to {{ opacity: 0; transform: scale(2.6); }} }}
  .marker {{ transform-box: fill-box; transform-origin: left center; animation: mark .9s cubic-bezier(.6,0,.3,1) .4s backwards; }}
  @keyframes mark {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
</style>
<defs>{defs_common(31)}
  <clipPath id="page"><rect width="{W}" height="{H}" rx="6"/></clipPath>
</defs>
<g clip-path="url(#page)">
  {paper(W, H)}
  {header_strip(W, "EXP. Nº PJC-2026/ASIR  ·  FASE 03", "HOJA 4 DE 5")}
  {section_head(64, 104, "03 ·", " CRONOLOGÍA")}
  <text x="64" y="146" class="mono" font-size="11" fill="{MUTED}" letter-spacing="2.4">FECHA</text>
  <text x="{cx + 40}" y="146" class="mono" font-size="11" fill="{MUTED}" letter-spacing="2.4">EVENTO</text>
  <text x="{W - 64}" y="146" text-anchor="end" class="mono" font-size="11" fill="{MUTED}" letter-spacing="2.4">NOTAS DEL ANALISTA</text>
  <line x1="64" y1="156" x2="{W - 64}" y2="156" stroke="{INK}" stroke-width="1.4"/>
  <line x1="{cx}" y1="{top - 6}" x2="{cx}" y2="{top + 4 * step - 6}" stroke="{INK}" stroke-width="2"/>
  <line x1="{cx}" y1="{top + 4 * step - 6}" x2="{cx}" y2="{top + 6 * step - 6}" stroke="{MUTED}" stroke-width="2" stroke-dasharray="4 5"/>
    {body}
  <text x="{goal_x}" y="{goal_y - 1}" class="serif" font-size="26" fill="{RED}">← aquí entras tú</text>
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="6" fill="none" stroke="{INK}" stroke-opacity=".25"/>
</svg>'''


# ────────────────────────────── ARSENAL ──────────────────────────────
def arsenal():
    W, H = 1200, 400
    cols = [
        ("SISTEMAS", ["Linux · Ubuntu · Kali", "Windows Server", "Active Directory", "VirtualBox"]),
        ("REDES", ["TCP/IP · subnetting", "VLANs · 802.1Q", "DNS · DHCP", "Packet Tracer"]),
        ("SEGURIDAD", ["Nmap", "Wireshark", "Burp Suite", "UFW · Fail2Ban"]),
        ("CÓDIGO", ["Python", "Bash", "Git", "Jinja2 · Chart.js"]),
    ]
    x0, cw = 64, (W - 128) / 4
    parts = []
    for i, (head, items) in enumerate(cols):
        x = x0 + i * cw
        if i:
            parts.append(f'<line x1="{x - 14}" y1="158" x2="{x - 14}" y2="{H - 50}" stroke="{INK}" stroke-width=".6" stroke-dasharray="1 4"/>')
        parts.append(f'<text x="{x}" y="176" class="anton" font-size="26" fill="{INK}" letter-spacing="1.5">{head}</text>')
        parts.append(f'<text x="{x + tw("Anton", head, 26, 1.5) + 8}" y="176" class="mono" font-size="12" fill="{MUTED}">/0{i + 1}</text>')
        for j, it in enumerate(items):
            y = 222 + j * 38
            parts.append(f'<rect x="{x}" y="{y - 14}" width="16" height="16" fill="none" stroke="{INK}" stroke-width="1.4"/>'
                         f'<path d="M{x + 3} {y - 6} l4 5 l8 -11" fill="none" stroke="{RED}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" filter="url(#ink)"/>'
                         f'<text x="{x + 28}" y="{y}" class="mono" font-size="16" fill="{INK}">{esc(it)}</text>')
    body = "\n  ".join(parts)
    # círculo "a mano" alrededor de Python
    px, py = x0 + 3 * cw + 28, 222
    pw = tw("Plex", "Python", 16)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<style>{BASE_CSS}
  .draw {{ stroke-dasharray: 260; animation: draw 1.4s ease-out .6s backwards; }}
  @keyframes draw {{ from {{ stroke-dashoffset: 260; }} to {{ stroke-dashoffset: 0; }} }}
</style>
<defs>{defs_common(41)}
  <clipPath id="page"><rect width="{W}" height="{H}" rx="6"/></clipPath>
</defs>
<g clip-path="url(#page)">
  {paper(W, H)}
  {header_strip(W, "EXP. Nº PJC-2026/ASIR  ·  FASE 04", "HOJA 5 DE 5")}
  {section_head(64, 104, "04 ·", " ARSENAL", "lo que uso de verdad")}
  {body}
  <path class="draw" d="M{px - 10} {py - 4} C{px - 12} {py - 26}, {px + pw + 18} {py - 28}, {px + pw + 16} {py - 6} S{px - 2} {py + 16}, {px - 14} {py - 2} l 8 -12" fill="none" stroke="{RED}" stroke-width="2" stroke-linecap="round"/>
  <text x="{px + pw + 26}" y="{py + 2}" class="serif" font-size="22" fill="{RED}">scanner + analyzer</text>
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="6" fill="none" stroke="{INK}" stroke-opacity=".25"/>
</svg>'''


# ─────────────────────────────── CIERRE ───────────────────────────────
def closing():
    W, H = 1200, 300
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<style>{BASE_CSS}</style>
<defs>{defs_common(51)}
  <clipPath id="page"><rect width="{W}" height="{H}" rx="6"/></clipPath>
</defs>
<g clip-path="url(#page)">
  <rect width="{W}" height="{H}" fill="{INK}"/>
  <rect width="{W}" height="{H}" filter="url(#grain)" opacity=".8"/>
  <text x="64" y="52" class="mono" font-size="13" fill="{MUTED}" letter-spacing="2">EXP. Nº PJC-2026/ASIR  ·  CONCLUSIÓN</text>
  <line x1="64" y1="64" x2="{W - 64}" y2="64" stroke="{MUTED}" stroke-width=".8"/>
  <text x="64" y="150" class="anton" font-size="66" fill="{PAPER}" letter-spacing="1">¿TIENES UNA PLAZA DE FCT?</text>
  <text x="64" y="196" class="mono" font-size="18" fill="#cfc7b3">Ciberseguridad, SOC o sistemas · desde marzo de 2027 · Madrid</text>
  <text x="64" y="252" class="monob" font-size="17" fill="{YELLOW}">linkedin.com/in/franciscojuliancuesta</text>
  <text x="64" y="278" class="monob" font-size="17" fill="{YELLOW}">pacojuliancuesta@gmail.com</text>
  <text x="{W - 64}" y="246" text-anchor="end" class="serif" font-size="46" fill="{PAPER}">F. J. Cuesta</text>
  <line x1="{W - 330}" y1="258" x2="{W - 64}" y2="258" stroke="{MUTED}" stroke-width="1"/>
  <text x="{W - 64}" y="278" text-anchor="end" class="mono" font-size="11" fill="{MUTED}" letter-spacing="2.4">FIRMA DEL ANALISTA</text>
  {stamp(W - 210, 140, ["DISPONIBLE"], 8, color=RED, size=38, pad=16)}
</g>
</svg>'''


used_all = ["Anton", "Plex", "PlexB", "Serif"]
write("cover.svg", cover(), used_all)
write("recon.svg", recon(), ["Anton", "Plex", "Serif", "PlexB"])
EV = [
    ("01", "Network Security Scanner", "network-scanner",
     "Automatiza el reconocimiento de mi red: Nmap descubre hosts, puertos, servicios y SO, y el script clasifica cada puerto por riesgo y saca un informe HTML con gráficos.",
     "8 hosts · 19 puertos abiertos · SMB expuesto", ["Python", "Nmap", "Jinja2", "Chart.js"], "PÚBLICO", True),
    ("02", "Log Security Analyzer", "log-analyzer",
     "Lee auth.log y syslog y busca 6 patrones de ataque: fuerza bruta SSH, usuarios inválidos y escalada con sudo/su. Ordena por severidad y te dice qué IPs atacan a qué usuarios.",
     "Informe HTML + JSON, de crítico a info", ["Python", "Regex", "Jinja2", "Chart.js"], "PÚBLICO", True),
    ("03", "Lab de Redes y Seguridad", "lab-red-seguridad",
     "Kali contra Ubuntu Server en una red aislada de VirtualBox. Primero escaneo, luego hardening y vuelta a escanear para ver qué ha cambiado.",
     "SSH reforzado · UFW · Fail2Ban · Nginx sin banners", ["Kali", "Ubuntu Server", "Nmap", "Fail2Ban"], "PÚBLICO", True),
    ("04", "Web Hacking Lab", "web-hacking-lab",
     "DVWA en una VM y los labs de PortSwigger. Rompo cada vulnerabilidad del OWASP Top 10, apunto qué funcionó y por qué, y guardo mis payloads.",
     "SQLi · XSS · CSRF · Command Injection · File Upload", ["Kali", "Burp Suite", "DVWA", "PortSwigger"], "EN CURSO", False),
]
for i, (num, title, repo, what, res, tools, st, live) in enumerate(EV):
    write(f"evidence-{repo}.svg", evidence(num, title, repo, what, res, tools, st, live, 60 + i * 7), used_all)
write("evidence-head.svg", evidence_head(), used_all)
write("chronology.svg", chronology(), used_all)
write("arsenal.svg", arsenal(), used_all)
write("closing.svg", closing(), used_all)
print("ok", sorted(p.name for p in OUT.iterdir()))
