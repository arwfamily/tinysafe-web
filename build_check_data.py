#!/usr/bin/env python3
"""build_check_data.py — generate /data/check.json for the /check landing page.

The /check page asks a parent WHICH BABY GEAR CATEGORIES they use (not brands).
Reason: recalls are spread across 616 mostly-unknown seller entities (507 have a
single recall), so brand selection has no density. Category selection does —
loungers, tower stools, safety gates and sleepwear each carry 9-43 recalls with
a dominant repeating defect. That repeating defect is the payoff we can show.

Usage (from repo root):
    curl -s https://raw.githubusercontent.com/arwfamily/tinysafe-data/main/recalls_unified.json -o /tmp/recalls.json
    python3 build_check_data.py /tmp/recalls.json data/check.json
"""
import json, re, sys, os
from collections import Counter

# Category -> match pattern against display_name. Order matters: first match wins,
# so put the specific ones before the general ones.
CATEGORIES = [
    ("Baby loungers",        r"lounger|sleep positioner|baby nest|napper"),
    ("Toddler towers & step stools", r"tower stool|toddler tower|step stool|standing tower|learning tower"),
    ("Safety gates",         r"safety gate|baby gate"),
    ("High chairs & boosters", r"high ?chair|booster seat|hook.?on chair"),
    ("Bassinets & cribs",    r"bassinet|\bcrib\b|cradle|play ?yard|playard|pack.?n.?play"),
    ("Crib & playard mattresses", r"mattress"),
    ("Infant walkers & bouncers", r"walker|bouncer|jumper|activity cent"),
    ("Baby bath seats & tubs", r"bath seat|baby (bath|tub)|toddler tub"),
    ("Strollers & car seat gear", r"stroller|car seat|adapter"),
    ("Baby carriers & swings", r"carrier|\bswing"),
    ("Nursing pillows",      r"nursing pillow"),
    ("Teethers & pacifier clips", r"teether|teething|pacifier|soother clip"),
    ("Magnet toys & building sets", r"magnet"),
    ("Light-up toys",        r"light.?up|led |finger light|glow|balloon light"),
    ("Pajamas & sleepwear",  r"pajama|sleepwear|nightgown|loungewear|\brobe\b|sleepsuit"),
    ("Dressers & nursery furniture", r"dresser|bookcase|changing table|furniture"),
]

# Human-readable label for the dominant hazard in a category.
HAZARD_LABEL = {
    "suffocation":"suffocation", "entrapment":"entrapment", "strangulation":"strangulation",
    "choking":"choking", "fall":"falls and tip-overs", "battery":"button-battery ingestion",
    "magnet":"magnet ingestion", "flammable":"failing flammability rules",
    "fire":"fire", "lead":"lead", "chemical":"harmful chemicals",
    "laceration":"sharp edges", "contamination":"contamination", "bacteria":"bacteria",
}

def slugify(t):
    t=(t or '').lower(); return re.sub(r'[^a-z0-9]+','-',t).strip('-')
def rid(r): return str(r.get('recall_id','')).lower().replace(' ','').replace('/','-')
def mkslug(r): return slugify(r.get('display_name',''))[:60].rstrip('-')+'-'+rid(r)
def fmt_month(d):
    d=str(d); return f"{d[:4]}-{d[4:6]}"

def build(db):
    recs=[r for r in db if str(r.get('recall_date','')).isdigit() and len(str(r.get('recall_date','')))==8]
    recs.sort(key=lambda r:str(r['recall_date']), reverse=True)
    cpsc=[r for r in recs if (r.get('source','') or '').upper()=='CPSC']

    used=set(); cats=[]
    for label,pat in CATEGORIES:
        p=re.compile(pat, re.I)
        hits=[r for r in cpsc if id(r) not in used and p.search(r.get('display_name','') or '')]
        for r in hits: used.add(id(r))
        if not hits: continue
        hz=Counter(r.get('hazard','') for r in hits if r.get('hazard'))
        top,topn = (hz.most_common(1)[0] if hz else ("",0))
        cats.append({
            "name": label,
            "count": len(hits),
            "top_hazard": HAZARD_LABEL.get(top, top),
            "top_hazard_count": topn,
            "latest": fmt_month(hits[0]["recall_date"]),
        })
    cats.sort(key=lambda c:-c["count"])

    recent=[{"name":r.get('display_name',''), "id":str(r.get('recall_id','')),
             "date":fmt_month(r['recall_date']),
             "hazard":(r.get('hazard') or '').capitalize(),
             "slug":mkslug(r)} for r in cpsc[:3]]

    return {"total": len(recs), "cpsc_total": len(cpsc),
            "updated": max(str(r['recall_date']) for r in recs),
            "recent": recent, "categories": cats}

if __name__=="__main__":
    src = sys.argv[1] if len(sys.argv)>1 else "/tmp/recalls.json"
    out = sys.argv[2] if len(sys.argv)>2 else "data/check.json"
    db=json.load(open(src))["recalls"]
    data=build(db)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(data, open(out,"w"), ensure_ascii=False, indent=1)
    print(f"{out}: {len(data['categories'])} categories, {data['cpsc_total']} CPSC of {data['total']} records")
    for c in data["categories"]:
        print(f"   {c['count']:3d}  {c['name']:32s} {c['top_hazard']} ({c['top_hazard_count']})")
