# SEO and discoverability

## Public pages

`/id` and `/en` return translated HTML directly from FastAPI, with localized titles, descriptions, canonical URLs, reciprocal hreflang links, and `Content-Language`. Explicit language URLs override browser preferences; the root page preserves saved/browser language selection. Canonical URLs use the production HTTPS origin, not the incoming Host header. Policy pages have the same metadata system and language alternates.

The interface still requires JavaScript for cleaning; the explanation, source attribution, FAQ answers, and policy text can be read without executing the application.

## Metadata and sharing

- Unique page title and description; index/follow directives for public pages.
- Open Graph and Twitter large-image metadata, localized descriptions, image dimensions, and alternative text.
- A 1200 × 630 English social card at `/static/brand/social-card.png` using the same logo, Avenir Next typography, and cream/mint/peach palette as the site.
- SVG and ICO favicons, Apple touch icon, 192/512px icons, and a browser-mode web manifest. This is not an offline PWA.
- Jakarta, Indonesia as the requested geographic context, using `ID-JK` and a Place in WebSite spatial coverage. This does not claim a physical office, street address, local business listing, or restrict worldwide use. Geographic meta tags do not guarantee ranking.

`npm run brand` renders assets from the outlined SVG masters using Playwright. To reproduce the approved social typography, use a machine with Avenir Next installed; do not regenerate using a different fallback font. The distributed PNG is already rendered and requires no font download by visitors.

## Structured data and clear answers

JSON-LD describes WebSite, WebPage, and WebApplication, plus visible FAQ questions and answers. There are no invented ratings, users, reviews, office details, or awards. Answers explain supported cleaning, local versus server processing, the absence of AI requirements, and the reason the tool exists.

These additions support readable, attributable information for search and answer engines. They do not guarantee rich results, search placement, citations, or AI-answer inclusion. No special AI visibility claims are made.

## Discovery endpoints

| Path | Purpose |
| --- | --- |
| `/robots.txt` | Allow public pages/assets; exclude processing routes, health, and the raw HTML template |
| `/sitemap.xml` | Six canonical localized tool/policy URLs with language alternates |
| `/llms.txt` | Concise public facts and relevant links |
| `/llms-full.txt` | Detailed public facts, bilingual FAQ, and current policy text |

The LLM files are a public documentation convention, not authorization, a prompt for tool execution, or a guarantee that a crawler will use them. They contain no user data. API and health responses carry `X-Robots-Tag: noindex, nofollow`; robots exclusions are not access controls. JavaScript, CSS, and the runtime remain crawlable.

## Maintenance

Update both dictionaries in `static/translations.json`, then regenerate `static/copy.js` with `.venv/bin/python scripts/translations.py`. SEO and SSR read the same dictionary. Policies and full LLM context share the policy source. Update the production origin consistently when changing domains; do not put private previews into the public sitemap.

Restart the application after changing the dictionary so the server reloads its
content too. The Python development watcher does not watch JSON files.

After deployment, inspect actual public HTML and image responses, submit the sitemap through the site's verified search-console account, and use each social platform's preview debugger if cached cards need refreshing. Those external account actions have not been performed by this repository change.

## References

- [Google: localized versions](https://developers.google.com/search/docs/specialty/international/localized-versions)
- [Google: AI features and websites](https://developers.google.com/search/docs/appearance/ai-features)
- [llms.txt proposal](https://llmstxt.org/)
