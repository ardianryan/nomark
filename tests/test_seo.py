from html.parser import HTMLParser
import json
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

from fastapi.testclient import TestClient
import pytest

from nomark.app import create_app
from nomark.seo import COPY, SITE


class Head(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.meta = {}
        self.links = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            self.meta[attrs.get("name", attrs.get("property"))] = attrs.get("content")
        if tag == "link":
            self.links.append(attrs)


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as session:
        yield session


@pytest.mark.parametrize("path", ["/id", "/en", "/id/privacy", "/en/privacy", "/id/terms", "/en/terms"])
def test_public_pages_have_localized_discovery_without_javascript(client, path):
    response = client.get(path)
    assert response.status_code == 200
    lang = path.split("/")[1]
    html = response.text
    head = Head(html)
    assert f'<html lang="{lang}">' in html
    assert head.meta["description"]
    assert head.meta["geo.placename"] == "Jakarta, Indonesia"
    assert head.meta["og:url"] == SITE + path
    assert head.meta["og:image"] == SITE + "/static/brand/social-card.png"
    assert head.meta["twitter:card"] == "summary_large_image"
    assert next(link for link in head.links if link["rel"] == "canonical")["href"] == SITE + path
    alternates = {link["hreflang"]: link["href"] for link in head.links if "hreflang" in link}
    assert {"id", "en", "x-default"} == set(alternates)
    other = "en" if lang == "id" else "id"
    assert alternates[other] == SITE + path.replace("/" + lang, "/" + other, 1)
    schema = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)[1])
    assert any(item["@type"] == "WebPage" and item["inLanguage"] == lang for item in schema["@graph"])
    if path in ("/id", "/en"):
        assert response.headers["content-language"] == lang
        assert COPY[lang]["title"] in html
        assert COPY[lang]["sourcePurpose"] in html
        faq = next(item for item in schema["@graph"] if item["@type"] == "FAQPage")
        for item in faq["mainEntity"]:
            assert item["name"] in html
            assert item["acceptedAnswer"]["text"] in html


def test_sitemap_robots_and_public_context(client):
    sitemap = client.get("/sitemap.xml")
    assert sitemap.headers["content-type"].startswith("application/xml")
    root = ET.fromstring(sitemap.text)
    locations = [entry.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc").text for entry in root]
    assert len(locations) == 6
    for url in locations:
        assert client.get(url.removeprefix(SITE)).status_code == 200
    robots = client.get("/robots.txt")
    assert "Disallow: /api/" in robots.text
    assert "Disallow: /static/\n" not in robots.text
    assert SITE + "/sitemap.xml" in robots.text
    for path in ("/llms.txt", "/llms-full.txt"):
        response = client.get(path)
        assert response.headers["content-type"].startswith("text/plain")
        assert "watermarks-remover" in response.text
        assert "me@ardianryan.com" in response.text
    assert "Privacy policy (en)" in client.get("/llms-full.txt").text
    assert client.get("/health").headers["x-robots-tag"] == "noindex, nofollow"


def test_brand_files_are_real_images_and_manifest_icons_resolve(client):
    image = client.get("/static/brand/social-card.png")
    assert image.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", image.content[16:24]) == (1200, 630)
    ico = client.get("/favicon.ico")
    assert ico.content[:6] == b"\x00\x00\x01\x00\x03\x00"
    manifest = client.get("/site.webmanifest")
    assert manifest.headers["content-type"].startswith("application/manifest+json")
    for icon in manifest.json()["icons"]:
        assert client.get(icon["src"]).status_code == 200


def test_browser_dictionary_matches_server_source():
    root = Path(__file__).resolve().parents[1]
    script = (root / "static/copy.js").read_text()
    assert json.loads(script.removeprefix("window.NoMarkCopy = ").removesuffix(";\n")) == COPY
