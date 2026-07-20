#!/usr/bin/env python3
"""build_hubs.py — regenerate the recall list block + JSON-LD inside hub pages.

Hub pages are hand-written HTML with one machine-generated block (the grouped
recall list) and a matching JSON-LD ItemList. They go stale because nothing
rebuilds them. Run this after the DB changes.

Usage (from repo root):
    curl -s https://raw.githubusercontent.com/arwfamily/tinysafe-data/main/recalls_unified.json -o /tmp/recalls.json
    python3 build_hubs.py all /tmp/recalls.json

    python3 build_hubs.py recent-baby-recalls /tmp/recalls.json

IMPORTANT: slugify here MUST match build_list.py exactly (lowercase, non-alnum
-> hyphen, strip). Do NOT add unicode normalization — "Gigglescape(TM)" would
become "gigglescapetm" and every such link would 404.
"""
import json, re, html as H, sys
from collections import defaultdict
from datetime import date

MON=["January","February","March","April","May","June","July","August","September","October","November","December"]
AB=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

def slugify(t):
    t=(t or '').lower(); return re.sub(r'[^a-z0-9]+','-',t).strip('-')
def rid(r): return str(r.get('recall_id','')).lower().replace(' ','').replace('/','-')
def mkslug(r): return slugify(r.get('display_name',''))[:60].rstrip('-')+'-'+rid(r)
def fmt(d):
    d=str(d); return f"{AB[int(d[4:6])-1]} {int(d[6:8])}, {d[:4]}"
def blob(r): return f"{r.get('product_name','')} {r.get('reason','')} {r.get('display_name','')}".lower()
def is_cpsc(r): return (r.get('source','') or '').upper()=='CPSC'

TOY_WORDS=re.compile(r"toy|doll|playset|play set|game|puzzle|block|teether|teething|rattle|"
                     r"busy board|activity|plush|figure|ball|light[- ]up|balloon|chess|"
                     r"building|stacker|tile|magnet|bath toy|water toy|tent|swing", re.I)

HUBS={
 "recent-baby-recalls": dict(mode="month", months=6, flt=lambda r: True),
 "baby-toy-safety": dict(mode="group", months=12,
   flt=lambda r: is_cpsc(r) and bool(TOY_WORDS.search(r.get('display_name','') or '')),
   groups=[("Choking hazards",{"choking"}),("Magnet ingestion",{"magnet"}),
           ("Button batteries",{"battery"}),("Lead &amp; chemicals",{"lead","chemical","asbestos"}),
           ("Other safety recalls",None)]),
 "amazon-baby-products-safety": dict(mode="group", months=18,
   flt=lambda r: is_cpsc(r) and 'amazon' in blob(r),
   groups=[("Suffocation &amp; strangulation",{"suffocation","strangulation","entrapment"}),
           ("Button batteries",{"battery"}),("Choking hazards",{"choking"}),
           ("Magnet ingestion",{"magnet"}),("Fall &amp; tip-over",{"fall"}),
           ("Fire &amp; flammability",{"fire","flammable"}),
           ("Lead &amp; chemicals",{"lead","chemical","asbestos"}),
           ("Other safety recalls",None)]),
 "button-battery-recalls": dict(mode="group", months=18,
   flt=lambda r: r.get('hazard')=='battery' and is_cpsc(r),
   groups=[("Light-up toys &amp; novelties", re.compile(r"light|led|glow|lamp|beam|balloon|ring|headband|wand|novelt", re.I)),
           ("Toys &amp; games", re.compile(r"toy|game|doll|playset|play set|puzzle|block|book|figure|cube|kit", re.I)),
           ("Other products", None)]),
}

def item_html(r):
    nm=H.escape(r.get('display_name',''), quote=True)
    cat=H.escape(r.get('display_category') or 'Other')
    src=H.escape((r.get('source') or '').upper())
    hz=(r.get('hazard') or '').capitalize()
    tag=f'<span class="tag tag-hz">{H.escape(hz)}</span>' if hz else ''
    return (f'<a class="ritem" href="/recalls/{mkslug(r)}"><div class="rtop">'
            f'<span class="tag tag-src">{cat} &middot; {src}</span>{tag}</div>'
            f'<div class="rname">{nm}</div><div class="rdate">Recalled {fmt(r["recall_date"])}</div></a>')

def window(db, months, flt):
    recs=[r for r in db if str(r.get('recall_date','')).isdigit() and len(str(r.get('recall_date','')))==8]
    recs.sort(key=lambda r:str(r['recall_date']), reverse=True)
    newest=str(recs[0]['recall_date']); cut=(int(newest[:4])*12+int(newest[4:6]))-months
    return [r for r in recs if flt(r) and (int(str(r['recall_date'])[:4])*12+int(str(r['recall_date'])[4:6]))>cut]

def build(db, cfg):
    pool=window(db, cfg['months'], cfg['flt'])
    out=[]; ordered=[]
    if cfg['mode']=="month":
        g=defaultdict(list)
        for r in pool: d=str(r['recall_date']); g[(int(d[:4]),int(d[4:6]))].append(r)
        for (y,m) in sorted(g, reverse=True):
            items=g[(y,m)]; ordered.extend(items)
            out.append(f'<div class="gtitle">{MON[m-1]} {y} <span class="gcount">{len(items)}</span></div><div class="rlist">')
            out += [item_html(r) for r in items]; out.append('</div>')
    else:
        used=set()
        for title,rule in cfg['groups']:
            if rule is None: items=[r for r in pool if id(r) not in used]
            elif isinstance(rule,set): items=[r for r in pool if r.get('hazard') in rule and id(r) not in used]
            else: items=[r for r in pool if rule.search(r.get('display_name','') or '') and id(r) not in used]
            for r in items: used.add(id(r))
            if not items: continue
            ordered.extend(items)
            out.append(f'<div class="gtitle">{title} <span class="gcount">{len(items)}</span></div><div class="rlist">')
            out += [item_html(r) for r in items]; out.append('</div>')
    return ''.join(out), ordered

def update(key, db):
    cfg=HUBS[key]; page=f"recalls/{key}.html"
    h=open(page,encoding='utf-8').read()
    block,ordered=build(db,cfg)
    i=h.index('<div class="gtitle">'); j=h.index('</section>', i)
    h=h[:i]+block+h[j:]
    n=len(ordered)
    h=re.sub(r'<div class="section-sub">\d+ recalls grouped by reason\.',
             f'<div class="section-sub">{n} recalls grouped by reason.', h)
    h=re.sub(r'"numberOfItems":\s*\d+', f'"numberOfItems": {n}', h)
    m=re.search(r'"itemListElement":\s*\[.*?\]', h, re.S)
    if m:
        items=['{"@type": "ListItem", "position": %d, "url": "https://tinysafe.app/recalls/%s", "name": %s}'
               % (k, mkslug(r), json.dumps(r.get('display_name',''))) for k,r in enumerate(ordered,1)]
        h=h[:m.start()]+'"itemListElement": ['+", ".join(items)+']'+h[m.end():]
    h=re.sub(r'"dateModified": "[\d-]+"', f'"dateModified": "{date.today().isoformat()}"', h)
    open(page,'w',encoding='utf-8').write(h)
    return n

if __name__=="__main__":
    if len(sys.argv)<3:
        print(__doc__); sys.exit(1)
    target, dbp = sys.argv[1], sys.argv[2]
    db=json.load(open(dbp))['recalls']
    keys=list(HUBS) if target=="all" else [target]
    for k in keys:
        print(f"{k}: {update(k, db)} recalls")
