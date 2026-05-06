"""Pull Novikov Beverly Hills menu into data/menu.json.

Pipeline:
1. Paginate /wp-json/wp/v2/menus for names + categories.
2. Fetch each dish detail page concurrently to scrape `menu_pos-item-price`
   and `menu_pos-item-description` (price + ingredient/dietary line).

Run: .venv/bin/python scripts/scrape_menu.py
"""

from __future__ import annotations

import asyncio
import html as _html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "menu.json"
BASE = "https://novikovbeverly.com"


def _clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return _html.unescape(text).replace(" ", " ").strip()


def fetch_categories(client: httpx.Client) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for page in range(1, 5):
        r = client.get(
            f"{BASE}/wp-json/wp/v2/menu-category",
            params={"per_page": 100, "page": page},
        )
        if r.status_code != 200:
            break
        items = r.json()
        for c in items:
            out[c["id"]] = {
                "id": c["id"],
                "name": _clean_html(c["name"]),
                "slug": c["slug"],
                "count": c.get("count", 0),
            }
        if len(items) < 100:
            break
    return out


def fetch_items(client: httpx.Client) -> list[dict]:
    out: list[dict] = []
    for page in range(1, 8):
        r = client.get(
            f"{BASE}/wp-json/wp/v2/menus",
            params={
                "per_page": 100,
                "page": page,
                "_fields": "id,slug,title,link,menu-category",
            },
        )
        if r.status_code != 200:
            break
        items = r.json()
        out.extend(items)
        if len(items) < 100:
            break
    return out


_PRICE_RE = re.compile(
    r'menu_pos-item-price">\s*([^<]{1,40})\s*<', re.IGNORECASE
)
_DESC_RE = re.compile(
    r'menu_pos-item-description">\s*([^<]{1,500})\s*<', re.IGNORECASE
)


def _normalize_price(raw: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", _html.unescape(raw or "")).strip()
    if not cleaned:
        return None
    if cleaned.upper().startswith("MP"):
        return "market price"
    # Site uses both '$71' and '71$' — normalize to '$71'.
    money = re.search(r"(\d{1,4}(?:\.\d{1,2})?)\s*\$|\$\s*(\d{1,4}(?:\.\d{1,2})?)", cleaned)
    if money:
        amount = money.group(1) or money.group(2)
        return f"${amount}"
    return cleaned


async def _fetch_detail(client: httpx.AsyncClient, link: str) -> tuple[str | None, str | None]:
    try:
        r = await client.get(link)
    except httpx.HTTPError:
        return None, None
    if r.status_code != 200:
        return None, None
    text = r.text
    price = None
    desc = None
    pm = _PRICE_RE.search(text)
    if pm:
        price = _normalize_price(pm.group(1))
    dm = _DESC_RE.search(text)
    if dm:
        desc = _clean_html(dm.group(1)) or None
    return price, desc


async def _enrich_details(items: list[dict], concurrency: int = 8) -> None:
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(20.0), follow_redirects=True
    ) as client:
        async def worker(item: dict, idx: int) -> None:
            async with sem:
                price, desc = await _fetch_detail(client, item["url"])
            if price:
                item["price"] = price
            if desc:
                item["description"] = desc
            if (idx + 1) % 25 == 0:
                print(f"  detail {idx + 1}/{len(items)}")

        await asyncio.gather(*(worker(it, i) for i, it in enumerate(items)))


def main() -> int:
    DATA.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        print("fetching categories...")
        categories = fetch_categories(client)
        print(f"  {len(categories)} categories")

        print("fetching items...")
        raw_items = fetch_items(client)
        print(f"  {len(raw_items)} items raw")

    items_out: list[dict] = []
    seen: set[str] = set()
    for it in raw_items:
        link = it.get("link") or ""
        if "/es/" in link:
            continue
        slug = it.get("slug") or ""
        if slug in seen:
            continue
        seen.add(slug)
        name = _clean_html(it["title"]["rendered"])
        cat_ids = it.get("menu-category") or []
        cat_names = sorted(
            {
                categories[cid]["name"]
                for cid in cat_ids
                if cid in categories
                and not categories[cid]["slug"].endswith("-es")
            }
        )
        items_out.append(
            {
                "slug": slug,
                "name": name,
                "url": link,
                "categories": cat_names,
            }
        )

    print(f"fetching detail pages for {len(items_out)} items (price + description)...")
    asyncio.run(_enrich_details(items_out))
    with_price = sum(1 for it in items_out if it.get("price"))
    with_desc = sum(1 for it in items_out if it.get("description"))
    print(f"  prices: {with_price}/{len(items_out)}")
    print(f"  descriptions: {with_desc}/{len(items_out)}")

    items_out.sort(
        key=lambda x: (x["categories"][0] if x["categories"] else "ZZZ", x["name"])
    )

    cats_with_items = sorted(
        (
            {"name": c["name"], "slug": c["slug"], "count": c["count"]}
            for c in categories.values()
            if c["count"] > 0 and not c["slug"].endswith("-es")
        ),
        key=lambda c: -c["count"],
    )

    out_doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": BASE,
        "items_total": len(items_out),
        "categories": cats_with_items,
        "items": items_out,
    }

    DATA.write_text(json.dumps(out_doc, indent=2, ensure_ascii=False))
    print(f"\nwrote {DATA}  ({DATA.stat().st_size} bytes, {len(items_out)} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
