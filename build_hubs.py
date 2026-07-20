#!/usr/bin/env python3
"""Regenerate the hub pages (recalls/baby-toy-safety.html, recalls/recent-baby-recalls.html)
from recalls_unified.json.

The hubs are curated landing pages: intro copy, official-guidance blocks and FAQ are
hand-written and left untouched. Only the machine-generated parts are rebuilt:

  * the "Recalled products to check" card grid
  * the group counts and the total in the section sub-heading
  * the stat strip numbers
  * the visible "updated" date and the JSON-LD dateModified

Usage (from repo root):
    python3 build_hubs.py /tmp/recalls.json

Slug rule mirrors build_list.py: slugify(display_name)[:60].rstrip('-') + '-' + recall_id
"""
import json
import re
import sys
import unicodedata
from datetime import date, datetime

TOY_HUB = "recalls/baby-toy-safety.html"
RECENT_HUB = "recalls/recent-baby-recalls.html"

# Hazard tag shown on each card, keyed by the DB hazard field.
HAZARD_LABEL = {
    "choking": "Choking risk",
    "magnet": "Magnet hazard",
    "battery": "Battery hazard",
    "lead": "Lead",
    "chemical": "Chemical hazard",
    "suffocation": "Suffocation risk",
    "fall": "Fall hazard",
    "entrapment": "Entrapment risk",
    "fire": "Fire hazard",
    "burn": "Burn hazard",
    "laceration": "Laceration risk",
    "asbestos": "Asbestos",
    "drowning": "Drowning risk",
    "strangulation": "Strangulation risk",
}

# Toy-hub groups, in display order: (heading, set of DB hazard values)
TOY_GROUPS = [
    ("Choking hazards", {"choking"}),
    ("Magnet ingestion", {"magnet"}),
    ("Button batteries", {"battery"}),
    ("Lead & chemicals", {"lead", "chemical", "asbestos"}),
    ("Other safety recalls", None),  # None = everything else
]


def slugify(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def page_slug(rec):
    name = rec.get("display_name") or rec.get("product_name") or ""
    rid = str(rec.get("recall_id", "")).strip()
    return slugify(name)[:60].rstrip("-") + "-" + rid


def esc(text):
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def parse_date(rec):
    raw = str(rec.get("recall_date", ""))
    if len(raw) == 8 and raw.isdigit():
        try:
            return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
        except ValueError:
            return None
    return None


def hazard_label(rec):
    return HAZARD_LABEL.get((rec.get("hazard") or "").lower(), "Safety recall")


def card(rec):
    d = parse_date(rec)
    when = d.strftime("%b %d, %Y") if d else ""
    name = rec.get("display_name") or rec.get("product_name") or ""
    return (
        f'<a class="ritem" href="/recalls/{page_slug(rec)}">'
        f'<div class="rtop"><span class="tag tag-hz">{esc(hazard_label(rec))}</span>'
        f'<span class="tag tag-src">{esc(rec.get("source", ""))}</span></div>'
        f'<div class="rname">{esc(name)}</div>'
        f'<div class="rdate">Recalled {when}</div></a>'
    )


def group_block(title, records):
    cards = "".join(card(r) for r in records)
    return (
        f'<div class="gtitle">{title} <span class="gcount">{len(records)}</span></div>'
        f'<div class="rlist">{cards}</div>'
    )


def replace_grid(html, blocks, total, sub_note):
    """Swap everything between the "Recalled products to check" sub-heading and the FAQ."""
    start = html.index('<div class="section-sub">', html.index("Recalled products to check"))
    end = html.index('<section class="faq"', start)
    new_sub = f'<div class="section-sub">{total} {sub_note}</div>\n'
    return html[:start] + new_sub + "\n".join(blocks) + "\n\n" + html[end:]


def bump_dates(html, today):
    html = re.sub(r'"dateModified": "\d{4}-\d{2}-\d{2}"',
                  f'"dateModified": "{today}"', html)
    html = re.sub(r"updated \d{4}-\d{2}-\d{2}", f"updated {today}", html)
    return html


def build_toy_hub(records, today):
    toys = [r for r in records
            if (r.get("display_category") or "") == "Toys & Gear"
            or "toy" in (r.get("display_name") or "").lower()]
    toys.sort(key=lambda r: str(r.get("recall_date", "")), reverse=True)

    blocks, used = [], set()
    for title, hazards in TOY_GROUPS:
        if hazards is None:
            bucket = [r for r in toys if id(r) not in used]
        else:
            bucket = [r for r in toys if (r.get("hazard") or "").lower() in hazards]
        used.update(id(r) for r in bucket)
        if bucket:
            blocks.append(group_block(title, bucket))

    html = open(TOY_HUB, encoding="utf-8").read()
    html = replace_grid(html, blocks, len(toys),
                        "recalls grouped by reason. Each links to its official recall record.")
    # top stat strip: leading number is the recall count
    html = re.sub(r'(<div class="stat"><b>)\d+(</b>)', rf"\g<1>{len(toys)}\g<2>", html, count=1)
    html = bump_dates(html, today)
    open(TOY_HUB, "w", encoding="utf-8").write(html)
    return len(toys)


def build_recent_hub(records, today, months=7):
    dated = [(parse_date(r), r) for r in records]
    dated = [(d, r) for d, r in dated if d]
    dated.sort(key=lambda pair: pair[0], reverse=True)

    buckets, order = {}, []
    for d, r in dated:
        key = (d.year, d.month)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(r)

    blocks, total = [], 0
    for key in order[:months]:
        label = date(key[0], key[1], 1).strftime("%B %Y")
        blocks.append(group_block(label, buckets[key]))
        total += len(buckets[key])

    html = open(RECENT_HUB, encoding="utf-8").read()
    html = replace_grid(html, blocks, total,
                        "recalls from the last %d months, newest first." % months)
    html = re.sub(r'(<div class="stat"><b>)\d+(</b>)', rf"\g<1>{total}\g<2>", html, count=1)
    html = bump_dates(html, today)
    open(RECENT_HUB, "w", encoding="utf-8").write(html)
    return total


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/recalls.json"
    records = json.load(open(src, encoding="utf-8"))["recalls"]
    today = datetime.now().strftime("%Y-%m-%d")
    n_toys = build_toy_hub(records, today)
    n_recent = build_recent_hub(records, today)
    print(f"baby-toy-safety.html   : {n_toys} recalls")
    print(f"recent-baby-recalls.html: {n_recent} recalls")
    print(f"updated date            : {today}")


if __name__ == "__main__":
    main()
