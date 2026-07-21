#!/usr/bin/env python3
"""build_check_data.py — generate /data/check.json for the /check landing page.

WHY THIS SHAPE
--------------
/check asks a parent WHICH THINGS THEY USE, not which brands. Brand selection has
no density in our data: 616 distinct brand values, 507 with a single recall, and
the largest are medical-device makers. Category selection does have density.

Two groups, two different time windows, on purpose:

  GEAR (CPSC)          — every record we hold. Cribs, high chairs and loungers get
                         handed down, resold and reused for years, so an older
                         recall is still sitting in somebody's nursery today.
  FEEDING & CARE (FDA) — last 3 years only. Formula, food and wipes are consumed.
                         A 2015 formula lot does not exist anymore, and listing it
                         would inflate the count with records no parent can act on.

MEDICAL RECORDS ARE EXCLUDED. Neonatal resuscitators, ventilators and hospital
convenience kits are not things a parent owns. They stay in the database (a NICU
parent may search for them) but must never appear as a /check option.

Defect patterns ("9 of 15 were recalled for suffocation") are GEAR-ONLY. FDA
recall text does not name a mechanism, so those records carry hazard "general"
and any pattern claim would be invented.

Usage (from repo root):
    curl -s https://raw.githubusercontent.com/arwfamily/tinysafe-data/main/recalls_unified.json -o /tmp/recalls.json
    python3 build_check_data.py /tmp/recalls.json data/check.json
"""
import json, re, sys, os, datetime
from collections import Counter

CONSUMABLE_YEARS = 3   # window for FDA feeding & care records

# Order is deliberate: what a parent worries about at night comes first, not what
# has the biggest count. Sleepwear carries the most recalls but they are almost
# all US flammability-standard violations rather than injuries, so it sits last.
GEAR = [
    ("Baby loungers",               r"lounger|sleep positioner|baby nest|napper"),
    ("Bassinets & cribs",           r"bassinet|\bcrib\b|cradle|play ?yard|playard|pack.?n.?play"),
    ("Crib & playard mattresses",   r"mattress"),
    ("High chairs & boosters",      r"high ?chair|booster seat|hook.?on chair"),
    ("Safety gates",                r"safety gate|baby gate"),
    ("Toddler towers & step stools",r"tower stool|toddler tower|step stool|standing tower|learning tower"),
    ("Infant walkers & bouncers",   r"walker|bouncer|jumper|activity cent"),
    ("Baby bath seats & tubs",      r"bath seat|baby (bath|tub)|toddler tub"),
    ("Strollers & car seat gear",   r"stroller|car seat|adapter"),
    ("Baby carriers & swings",      r"carrier|\bswing"),
    ("Nursing pillows",             r"nursing pillow"),
    ("Teethers & pacifier clips",   r"teether|teething|pacifier|soother clip"),
    ("Magnet toys & building sets", r"magnet"),
    ("Light-up toys",               r"light.?up|led |finger light|glow|balloon light"),
    ("Pajamas & sleepwear",         r"pajama|sleepwear|nightgown|loungewear|\brobe\b|sleepsuit"),
]

FEEDING = [
    ("Infant formula",        r"formula|similac|enfamil|nutramigen|byheart|alimentum|puramino|elecare"),
    ("Baby food & purees",    r"baby food|puree|pouch|cereal|snack|apple ?sauce|toddler (meal|food)"),
    ("Children's medicine",   r"tylenol|ibuprofen|acetaminophen|motrin|benadryl|nyquil|cough|cold|"
                              r"allergy|syrup|drops|suspension|loratadine|diphenhydramine"),
    ("Vitamins & supplements",r"vitamin|supplement|multivitamin|probiotic|dha|omega|\biron\b|fluoride"),
    ("Baby wipes",            r"wipe"),
    ("Lotion, cream & bath",  r"lotion|cream|balm|ointment|powder|body wash|shampoo|\boil\b|diaper rash"),
    ("Baby sunscreen",        r"sunscreen|\bspf\b"),
]

HAZARD_LABEL = {
    "suffocation":"suffocation", "entrapment":"entrapment", "strangulation":"strangulation",
    "choking":"choking", "fall":"falls and tip-overs", "battery":"button-battery ingestion",
    "magnet":"magnet ingestion", "flammable":"failing flammability rules", "fire":"fire",
    "lead":"lead", "chemical":"harmful chemicals", "laceration":"sharp edges",
    "contamination":"contamination", "bacteria":"bacteria", "botulism":"botulism",
}

def slugify(t):
    t=(t or '').lower(); return re.sub(r'[^a-z0-9]+','-',t).strip('-')
def rid(r): return str(r.get('recall_id','')).lower().replace(' ','').replace('/','-')
def mkslug(r): return slugify(r.get('display_name',''))[:60].rstrip('-')+'-'+rid(r)
def rdate(r):
    s=str(r.get('recall_date',''))
    if not (s.isdigit() and len(s)==8): return None
    try: return datetime.date(int(s[:4]),int(s[4:6]),int(s[6:8]))
    except ValueError: return None
def is_cpsc(r): return (r.get('source','') or '').upper()=='CPSC'

def group(pool, spec, with_pattern):
    used=set(); out=[]
    for label,pat in spec:
        p=re.compile(pat, re.I)
        hits=[r for r in pool if id(r) not in used and p.search(r.get('display_name','') or '')]
        for r in hits: used.add(id(r))
        if not hits: continue
        item={"name":label, "count":len(hits)}
        if with_pattern:
            hz=Counter(r.get('hazard','') for r in hits
                       if r.get('hazard') and r.get('hazard')!='general')
            if hz:
                top,n = hz.most_common(1)[0]
                item["top_hazard"]=HAZARD_LABEL.get(top, top)
                item["top_hazard_count"]=n
        out.append(item)
    return out

def build(db):
    recs=[r for r in db if rdate(r)]
    newest=max(rdate(r) for r in recs)

    # Hospital / clinical records never become a parent-facing option.
    consumer=[r for r in recs if r.get('display_category')!='Medical']
    gear_pool=[r for r in consumer if is_cpsc(r)]
    cut=newest-datetime.timedelta(days=365*CONSUMABLE_YEARS)
    feed_pool=[r for r in consumer if not is_cpsc(r) and rdate(r)>=cut]

    scope=gear_pool+feed_pool
    yr=newest-datetime.timedelta(days=365)

    recent=[{"name":r.get('display_name',''), "id":str(r.get('recall_id','')),
             "date":rdate(r).strftime("%Y-%m"),
             "hazard":(r.get('hazard') or '').capitalize(),
             "slug":mkslug(r)}
            for r in sorted(gear_pool, key=rdate, reverse=True)[:3]]

    return {
        "total": len(scope),
        "last12": sum(1 for r in scope if rdate(r)>=yr),
        "gear_total": len(gear_pool),
        "feeding_total": len(feed_pool),
        "updated": newest.isoformat(),
        "gear_from": min(rdate(r) for r in gear_pool).year,
        "feeding_years": CONSUMABLE_YEARS,
        "recent": recent,
        "groups": [
            {"key":"gear",    "label":"Gear",           "items": group(gear_pool, GEAR, True)},
            {"key":"feeding", "label":"Feeding & care", "items": group(feed_pool, FEEDING, False)},
        ],
    }

if __name__=="__main__":
    src = sys.argv[1] if len(sys.argv)>1 else "/tmp/recalls.json"
    out = sys.argv[2] if len(sys.argv)>2 else "data/check.json"
    data=build(json.load(open(src))["recalls"])
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    json.dump(data, open(out,"w"), ensure_ascii=False, indent=1)
    print(f"{out}: {data['total']} in scope "
          f"(gear {data['gear_total']} since {data['gear_from']}, "
          f"feeding {data['feeding_total']} last {CONSUMABLE_YEARS}y), "
          f"{data['last12']} in the last 12 months")
    for g in data["groups"]:
        print(f"\n  {g['label']}")
        for c in g["items"]:
            pat=f"   [{c['top_hazard_count']} {c['top_hazard']}]" if c.get('top_hazard') else ""
            print(f"    {c['count']:3d}  {c['name']}{pat}")
