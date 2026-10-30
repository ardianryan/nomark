"""Localized public pages and discovery documents; never include user content."""
from html import escape
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://nomark.ardianryan.com"
SOURCE = "https://github.com/guillaumemeyer/watermarks-remover"
COPY = json.loads((ROOT / "static/translations.json").read_text())


def public_head(lang, path, title, description, *, tool=False):
    url = SITE + path
    suffix = "" if tool else "/" + path.rsplit("/", 1)[-1]
    alternates = "".join(f'<link rel="alternate" hreflang="{code}" href="{SITE}/{code}{suffix}">' for code in ("id", "en"))
    default_path = "/" if tool else "/en" + suffix
    alternates += f'<link rel="alternate" hreflang="x-default" href="{SITE}{default_path}">'
    graph = [
        {"@type": "WebSite", "@id": SITE + "/#website", "name": "NoMark", "url": SITE + "/", "inLanguage": ["id", "en"], "spatialCoverage": {"@type": "Place", "name": "Jakarta, Indonesia"}},
        {"@type": "WebPage", "@id": url + "#page", "url": url, "name": title, "description": description, "inLanguage": lang, "isPartOf": {"@id": SITE + "/#website"}},
    ]
    if tool:
        graph += [
            {"@type": "WebApplication", "@id": SITE + "/#application", "name": "NoMark", "url": url, "description": description, "applicationCategory": "UtilitiesApplication", "operatingSystem": "Any", "browserRequirements": "JavaScript, WebAssembly and Web Workers", "isAccessibleForFree": True, "inLanguage": ["id", "en"], "featureList": ["Hidden Unicode character cleaning", "Document metadata cleaning", "Browser-local history"], "isBasedOn": SOURCE},
            {"@type": "FAQPage", "@id": url + "#faq", "inLanguage": lang, "mainEntity": [{"@type": "Question", "name": COPY[lang][f"faq{i}Q"], "acceptedAnswer": {"@type": "Answer", "text": COPY[lang][f"faq{i}A"]}} for i in range(1, 5)]},
        ]
    data = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False).replace("<", "\\u003c")
    title, description = escape(title, quote=True), escape(description, quote=True)
    locale, other_locale = ("id_ID", "en_US") if lang == "id" else ("en_US", "id_ID")
    return f'''<title>{title}</title>
<meta name="description" content="{description}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="application-name" content="NoMark">
<meta name="geo.region" content="ID-JK"><meta name="geo.placename" content="Jakarta, Indonesia">
<link rel="canonical" href="{url}">{alternates}
<link rel="icon" href="/static/brand/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" sizes="16x16 32x32 48x48">
<link rel="apple-touch-icon" href="/static/brand/apple-touch-icon.png" sizes="180x180">
<link rel="manifest" href="/site.webmanifest">
<link rel="describedby" href="/llms.txt" type="text/plain">
<meta property="og:type" content="website"><meta property="og:site_name" content="NoMark">
<meta property="og:title" content="{title}"><meta property="og:description" content="{description}">
<meta property="og:url" content="{url}"><meta property="og:locale" content="{locale}">
<meta property="og:locale:alternate" content="{other_locale}">
<meta property="og:image" content="{SITE}/static/brand/social-card.png">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:image:alt" content="NoMark — hidden character and document metadata cleaner">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}"><meta name="twitter:image" content="{SITE}/static/brand/social-card.png">
<meta name="twitter:image:alt" content="NoMark — hidden character and document metadata cleaner">
<script type="application/ld+json">{data}</script>'''


def render_index(lang="en"):
    text = (ROOT / "static/index.html").read_text()
    text = text.replace('<html lang="id">', f'<html lang="{lang}">')
    text = text.replace("<!-- NOMARK_HEAD -->", public_head(lang, "/" + lang, COPY[lang]["seoTitle"], COPY[lang]["seoDescription"], tool=True))
    # Only literal dictionary bindings on leaf elements are substituted.
    pattern = r'''(<[\w-]+\b[^>]*\bx-text="t\('([^']+)'\)"[^>]*>)[^<]*(</[\w-]+>)'''
    text = re.sub(pattern, lambda match: match[1] + escape(COPY[lang].get(match[2], COPY["en"].get(match[2], ""))) + match[3], text)
    text = text.replace('href="/id/terms"', f'href="/{lang}/terms"').replace('href="/id/privacy"', f'href="/{lang}/privacy"')
    text = text.replace('placeholder="Tempel teks Anda di sini…"', 'placeholder="' + escape(COPY[lang]["placeholder"], quote=True) + '"')
    return text


def sitemap():
    paths = ["/id", "/en", "/id/privacy", "/en/privacy", "/id/terms", "/en/terms"]
    entries = []
    for path in paths:
        suffix = path[3:]
        links = "".join(f'<xhtml:link rel="alternate" hreflang="{lang}" href="{SITE}/{lang}{suffix}"/>' for lang in ("id", "en"))
        entries.append(f"<url><loc>{SITE}{path}</loc>{links}</url>")
    return '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">' + "".join(entries) + "</urlset>"


def llms_index():
    return f'''# NoMark

> Public, account-free browser tool for cleaning supported hidden Unicode characters and document metadata. No AI model or API key is required.

Text and non-PDF documents are processed locally in a browser Web Worker. PDFs require explicit upload permission and a server slot. Findings do not establish AI authorship, and statistical AI watermark removal is not guaranteed. Public site context: Jakarta, Indonesia. Available worldwide in Indonesian and English.

## Pages
- [English tool]({SITE}/en): Workspace, supported formats, processing locations, attribution, and frequently asked questions.
- [Indonesian tool]({SITE}/id): The same tool and information in Indonesian.
- [Privacy policy]({SITE}/en/privacy): Browser storage, PDF uploads, retention, and privacy choices.
- [Terms of service]({SITE}/en/terms): Scope, permitted use, limitations, and contact.
- [Full public context]({SITE}/llms-full.txt): Detailed tool facts, bilingual questions and answers, and current public policies.

## Source
- [watermarks-remover]({SOURCE}): The pinned upstream Python cleaning engine used by NoMark.

Contact: me@ardianryan.com
'''


def llms_full():
    from nomark.policies import POLICIES, UPDATED
    sections = [llms_index(), "## Processing and limits\n\nSupported files: TXT, MD/Markdown, HTML/HTM, PDF, DOCX, XLSX, PPTX, ODT, EPUB. Images, audio, and video are unsupported. Text and every supported non-PDF format run locally through Pyodide. PDF metadata cleaning runs on the server with ExifTool, qpdf, and Ghostscript; no OCR or text rewriting.\n\nLimits: 200,000 pasted characters; 20 MiB per file; five sequential files in the browser queue. Server: two simultaneous jobs, eight waiting tickets, 120-second waiting expiry, 20-second ready expiry, 30-second upload timeout, 60-second processing timeout. Waiting files stay on the device. Temporary files are removed after jobs; interrupted-job remnants older than five minutes are swept while running.\n\nIndexedDB history: 20 entries or 100 MiB, including originals and results. Oldest entries are evicted. Language and theme preferences use localStorage. No account, server history database, analytics, S3 bucket, external CDN, MCP, or AI provider is configured. Compatibility API calls send their contents to the server even for non-PDF input.\n"]
    for lang in ("en", "id"):
        sections.append(f"## Questions and answers ({lang})\n")
        for i in range(1, 5):
            sections.append(f"### {COPY[lang][f'faq{i}Q']}\n\n{COPY[lang][f'faq{i}A']}\n")
        for kind in ("privacy", "terms"):
            policy = POLICIES[lang][kind]
            sections.append(f"## {policy['title']} ({lang})\n\nUpdated: {UPDATED}\n\n{policy['lead']}\n")
            for heading, paragraphs in policy["sections"]:
                sections.append("### " + heading + "\n\n" + "\n\n".join(paragraphs) + "\n")
    return "\n".join(sections)
