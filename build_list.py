#!/usr/bin/env python3
# TinySafe recall list builder
# ----------------------------
# Regenerates the DATA array + recall counts + updated date in recalls/index.html
# from the recalls_unified.json data file.
#
# USAGE (run from the tinysafe-web repo root):
#   1) Download the latest data:
#        curl -s https://raw.githubusercontent.com/arwfamily/tinysafe-data/main/recalls_unified.json -o /tmp/recalls.json
#   2) Update the list page:
#        python3 build_list.py update recalls/index.html /tmp/recalls.json
#   3) git add -A && git commit -m "Rebuild recall list" && git push
#
# This builder reproduces the original site exactly (slug rule, hazard labels,
# urgent flag, date format) and only adds/updates records from the JSON.

import json, re, sys
from datetime import datetime

HAZARD_MAP = {
 '': 'Safety Recall', 'asbestos':'Asbestos','bacteria':'Bacteria','battery':'Battery hazard',
 'botulism':'Contamination','chemical':'Chemical hazard','choking':'Choking risk',
 'contamination':'Contamination','fall':'Fall hazard','fire':'Fire hazard','flammable':'Fire hazard',
 'general':'Safety recall','labeling':'Labeling issue','laceration':'Laceration hazard','lead':'Lead',
 'magnet':'Magnet hazard','mold':'Mold','quality':'Quality issue','strangulation':'Strangulation risk',
 'subpotent':'Quality issue','suffocation':'Suffocation risk',
}

SEVERE={'suffocation','choking','contamination','flammable','battery','bacteria','lead','magnet','fall','strangulation','fire','botulism','chemical','asbestos'}

def slugify(t):
    t = (t or '').lower()
    t = re.sub(r'[^a-z0-9]+','-',t)
    return t.strip('-')

def rid_norm(r):
    return str(r.get('recall_id','')).lower().replace(' ','').replace('/','-')

def make_slug(r):
    name = slugify(r.get('display_name',''))[:60].rstrip('-')
    return f"{name}-{rid_norm(r)}"

def fmt_date(yyyymmdd):
    s=str(yyyymmdd)
    if len(s)==8 and s.isdigit():
        try: return datetime.strptime(s,'%Y%m%d').strftime('%b %d, %Y')
        except: return ''
    return ''

def build_items(records):
    items=[]
    for r in records:
        raw_h=(r.get('hazard') or '').lower()
        items.append({
            's': make_slug(r),
            'n': r.get('display_name',''),
            'b': r.get('brand',''),
            'h': HAZARD_MAP.get(raw_h, 'Safety recall'),
            'c': r.get('display_category') or r.get('category',''),
            "src": ('CPSC' if str(r.get('source','')).upper().startswith('CPSC') else 'FDA' if str(r.get('source','')).upper().startswith('FDA') else r.get('source','')),
            'd': fmt_date(r.get('recall_date','')),
            'u': 1 if (r.get('is_urgent') or raw_h in SEVERE) else 0,
        })
    return items

if __name__=='__main__':
    data=json.load(open('latest.json'))['recalls']
    items=build_items(data)
    print('built items:', len(items))
    json.dump(items, open('built_items.json','w'))
    print('sample:', json.dumps(items[0]))


def update_index_html(index_path, json_path):
    """Rewrite the DATA array + counts + updated date in recalls/index.html from the JSON."""
    import re as _re
    records = json.load(open(json_path))['recalls']
    items = build_items(records)
    n = len(items)
    html = open(index_path, encoding='utf-8').read()

    # 1) replace DATA array
    start = html.find('const DATA =')
    arr_start = html.find('[', start)
    depth=0; instr=False; esc=False; arr_end=-1
    for j in range(arr_start, len(html)):
        ch=html[j]
        if esc: esc=False; continue
        if ch=='\\': esc=True; continue
        if ch=='"': instr=not instr; continue
        if instr: continue
        if ch=='[': depth+=1
        elif ch==']':
            depth-=1
            if depth==0: arr_end=j; break
    new_arr = json.dumps(items, ensure_ascii=False, separators=(', ', ': '))
    html = html[:arr_start] + new_arr + html[arr_end+1:]

    # 2) replace counts: 852 -> n  (covers "852+" and "852")
    # find the OLD count by scanning the title pattern "Search NNN+ Official"
    m = _re.search(r'Search (\d+)\+ Official', html)
    old = m.group(1) if m else None
    if old:
        html = html.replace(f'{old}+', f'{n}+').replace(f'{old} official', f'{n} official').replace(f'{old} recalls', f'{n} recalls')

    # 3) update the "updated YYYY-MM-DD" date if present
    upd = json.load(open(json_path)).get('updated','')[:10]
    if upd:
        html = _re.sub(r'updated \d{4}-\d{2}-\d{2}', f'updated {upd}', html)

    open(index_path,'w',encoding='utf-8').write(html)
    return n, old, upd

if __name__=='__main__' and len(sys.argv)>1 and sys.argv[1]=='update':
    # usage: python3 build_list.py update <index.html> <recalls_unified.json>
    idx = sys.argv[2] if len(sys.argv)>2 else 'recalls/index.html'
    jsn = sys.argv[3] if len(sys.argv)>3 else 'latest.json'
    n, old, upd = update_index_html(idx, jsn)
    print(f'updated {idx}: {old} -> {n} recalls, date {upd}')
