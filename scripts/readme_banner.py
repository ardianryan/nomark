"""Generate self-contained README SVGs from the approved outlined wordmark.

Development only: pip install fonttools; pass an Avenir Next TTC path if needed.
"""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from fontTools.ttLib import TTCollection
from fontTools.pens.svgPathPen import SVGPathPen

root = Path(__file__).resolve().parents[1]
fonts = TTCollection(sys.argv[1] if len(sys.argv) > 1 else '/System/Library/Fonts/Avenir Next.ttc')

def lettering(value, x, y, size, index=5, color='var(--ink)'):
    font = fonts.fonts[index]
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    scale = size / font['head'].unitsPerEm
    paths, cursor = [], 0
    for character in value:
        name = cmap[ord(character)]
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(pen)
        paths.append(f'<path transform="translate({cursor},0)" d="{pen.getCommands()}"/>')
        cursor += font['hmtx'][name][0]
    return f'<g fill="{color}" transform="translate({x},{y}) scale({scale},-{scale})">{"".join(paths)}</g>'

logo = ET.parse(root / 'static/brand/logo.svg').getroot()
ET.register_namespace('', 'http://www.w3.org/2000/svg')
logo_inner = ''.join(ET.tostring(child, encoding='unicode') for child in logo)
logo_inner = logo_inner.replace('#233b32', 'var(--ink)').replace('#416e58', 'var(--accent)')
light = '--bg:#f7f5ef;--ink:#233b32;--muted:#4d6258;--mint:#e1eee5;--peach:#f3e4d8;--accent:#416e58;'
dark = '--bg:#16251f;--ink:#edf3ec;--muted:#bacbc0;--mint:#293f33;--peach:#46392f;--accent:#9ec5a9;'
for theme in ('system', 'light', 'dark'):
    css = ':root{' + (dark if theme == 'dark' else light) + '}'
    if theme == 'system':
        css += '@media(prefers-color-scheme:dark){:root{' + dark + '}}'
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 400" role="img" aria-labelledby="title desc">
<title id="title">NoMark — Clean text. Clear traces.</title><desc id="desc">A browser workspace for hidden Unicode and document metadata. No account. No AI API.</desc>
<style>{css}</style><rect width="1200" height="400" rx="28" fill="var(--bg)"/>
<rect x="852" y="32" width="316" height="208" rx="28" fill="var(--mint)"/>
<rect x="852" y="256" width="316" height="112" rx="28" fill="var(--peach)"/>
<g transform="translate(50,27) scale(1.45)">{logo_inner}</g>
{lettering('Clean text.', 52, 191, 53, 2)}
{lettering('Clear traces.', 52, 254, 53, 2)}
{lettering('Hidden Unicode & document metadata.', 54, 307, 25, color='var(--muted)')}
{lettering('No account. No AI API.', 54, 350, 21, color='var(--muted)')}
{lettering('Aa', 887, 156, 94, 2)}
{lettering('Less hidden clutter.', 882, 208, 21, color='var(--muted)')}
{lettering('Made for your browser.', 880, 321, 21)}
</svg>'''
    target = root / 'docs/assets' / ('banner.svg' if theme == 'system' else f'banner-{theme}.svg')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(svg)
    print(target.relative_to(root))
