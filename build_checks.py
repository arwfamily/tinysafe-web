#!/usr/bin/env python3
"""build_checks.py — derive the "three things to check" per category from real recalls.

The point of TinySafe is not a recall list. It is what keeps going wrong.
A recall matters only to whoever owns that product; a repeating defect matters to
everyone about to buy one. So for each category we count how often each defect
phrase actually appears in CPSC's own wording, and keep the ones that recur.

Every check here must trace to CPSC text. Nothing is invented, and nothing is ever
phrased as "this product is safe" — we say what to look at, the parent looks.

    python3 build_checks.py /tmp/recalls.json data/checks.json
"""
import json, re, sys, os

# (category, name matcher, [(check line, what CPSC phrase proves it)])
# Check lines are written as something a parent can do in a few seconds.
SPEC = [
 ("Safety gates", r"safety gate|baby gate", [
   ("Kneel down and look at the gap under the gate. A toddler's body can fit through a gap you would call small.",
    r"torso can fit through"),
   ("Check the gap between the gate and the wall, and any pet door opening.",
    r"gate slat and (the )?side wall|secondary opening|pet door"),
   ("Push the gate after it clicks. The lock should hold, not just sound like it did.",
    r"locking mechanism"),
 ]),
 ("Toddler towers & step stools", r"tower stool|toddler tower|step stool|standing tower|learning tower", [
   ("Push it from the side while it is empty. If it rocks or folds, it will do it with your child on it.",
    r"collapse or tip over|can tip over|can collapse"),
   ("Look at the openings on the front, back and sides. A child's body can slip through them.",
    r"torso can fit through"),
   ("Press down hard on the standing platform. It should not shift or loosen.",
    r"platform"),
 ]),
 ("High chairs & boosters", r"high ?chair|booster seat|hook.?on chair", [
   ("Pull on the crotch strap. It should be attached to the chair itself, not lying loose on the seat.",
    r"without the required attached|restraint system is not attached|restraint.*can be removed|attached crotch restraint"),
   ("Look at the gap between the seat and the tray, and beside the seat. A head can fit into it.",
    r"between the seat and"),
   ("A high chair is not a bed. If it reclines and is sold for sleeping, that is the recall pattern.",
    r"incline angle greater than 10"),
   ("Tighten the leg screws before first use, and again every few months.",
    r"legs.*(detach|screws)"),
 ]),
 ("Baby loungers", r"lounger|sleep positioner|baby nest|napper", [
   ("Look at the side height. Low sides are the single most repeated defect in this category.",
    r"sides are (too low|shorter)"),
   ("Press the pad. A thick, soft pad is what CPSC keeps citing.",
    r"thickness exceeds|pad is too thick|padding can obstruct"),
   ("Look at the foot end. An open end is where an infant slides out or gets caught.",
    r"opening at the foot|openings at the foot"),
   ("Never put it on a bed, sofa or counter. These have no stand.",
    r"do not have a stand"),
 ]),
 ("Bassinets & cribs", r"bassinet|\bcrib\b|cradle|play ?yard|playard|pack.?n.?play", [
   ("Look for any incline. Flat on the back is the only sleeping position.",
    r"incline|infant sleep|safe sleep"),
   ("Press the mattress down at the edges. A gap at the side is where an infant wedges.",
    r"gap between|mattress"),
   ("Shake the frame. Rails, legs and folding joints should not shift or detach.",
    r"detach|collapse|rail"),
 ]),
 ("Light-up toys", r"light.?up|led |finger light|glow|balloon light", [
   ("Try to open the battery compartment with your hands. If it opens without a screwdriver, a child can open it too.",
    r"batter"),
   ("Check that the compartment closes flush and the screw is actually there.",
    r"secure|screw|compartment|accessible"),
   ("If a button battery is swallowed it burns internally within hours. Treat a missing battery as an emergency.",
    r"ingest|swallow|burn"),
 ]),
 ("Magnet toys & building sets", r"magnet", [
   ("Twist and pull each piece. Loose magnets are what CPSC cites again and again here.",
    r"magnet.*(detach|loose|come out|separate|dislodge)|detach.*magnet"),
   ("Check the magnet is stronger than a fridge magnet. That strength is what makes swallowing them surgical.",
    r"flux|strength|strong"),
   ("Two swallowed magnets pull together through the gut and need surgery. Count the pieces after play.",
    r"ingest|swallow"),
 ]),
 ("Infant walkers & bouncers", r"walker|bouncer|jumper|activity cent", [
   ("Check the leg openings. Wide openings are what CPSC cites here.", r"leg opening|opening"),
   ("Look for any recline sold as a sleep position.", r"sleep|incline"),
   ("Check the brakes and stair-edge stop if it has wheels.", r"stair|brake|fall"),
 ]),
 ("Strollers & car seat gear", r"stroller|car seat|adapter", [
   ("Pull each buckle after clicking it.", r"restraint|buckle|harness|fail"),
   ("Check the folding joints and hinges near your child's fingers.", r"hinge|fold|amputat|lacerat"),
   ("If it is an adapter, confirm it is made for your exact model.", r"adapter|detach|fall"),
 ]),
 ("Nursing pillows", r"nursing pillow", [
   ("A nursing pillow is for feeding, never for sleeping.", r"suffocat|sleep"),
   ("Never leave a baby resting on it unattended.", r"suffocat|sleep|unattended"),
 ]),
 ("Baby bath seats & tubs", r"bath seat|baby (bath|tub)|toddler tub", [
   ("Set it in the empty tub and push it from the side. Every single recall here is a seat that tips while in use.",
    r"unstable|tip over"),
   ("Look at the leg openings. A baby can slip down until the body is caught.",
    r"leg opening"),
   ("A bath seat is not a reason to step away. Drowning is what CPSC cites at the end of every one of these.",
    r"drown"),
 ]),
 ("Baby carriers & swings", r"carrier|\bswing", [
   ("A swing is not a bed. Recline plus infant sleep is the most repeated defect in this category.",
    r"incline angle greater than 10|marketed for infant sleep|never be used for sleep"),
   ("Check for loose fabric that can form a loop near the head or neck.",
    r"loop|entangle|strangulat"),
   ("For a carrier or sling, pull hard on the seams and buckles before your baby is in it.",
    r"structural integrity|occupant retention|rivet|crack or break"),
 ]),
 ("Crib & playard mattresses", r"mattress", [
   ("Measure the thickness. Failing the thickness test is what both recalls in this category cite.",
    r"thickness"),
   ("Check the warning label is actually on it. Missing labels came up in both.",
    r"warnings and labels|missing the required"),
   ("Press the edges once it is in the crib. No gap should be left at the sides.",
    r"suffocation|mattress"),
 ]),
 ("Pajamas & sleepwear", r"pajama|sleepwear|nightgown|loungewear|\brobe\b|sleepsuit", [
   ("Look for the flame-resistant or snug-fit label. Almost every recall in this category is a sleepwear that failed the flammability standard.",
    r"flammab"),
   ("Loose-fitting cotton sold as sleepwear is the exact thing being recalled. Snug-fit is the rule.",
    r"flammab|sleepwear"),
   ("Pull on the zipper pull and any snap. Detaching hardware is the other pattern here.",
    r"zipper|detach|chok"),
 ]),
 ("Teethers & pacifier clips", r"teether|teething|pacifier|soother clip", [
   ("Pull on every attached part. Small pieces that detach are the pattern here.", r"detach|small part|chok"),
   ("Check the clip cord length. Long cords are a strangulation risk.", r"strangulat|cord"),
 ]),
]

def load(path):
    return json.load(open(path))["recalls"]

# Consumables (formula, food, wipes, medicine) are recalled for contamination,
# bacteria, botulism, undeclared ingredients — none of it visible to a parent.
# Telling someone to "check three things" on a formula tin would be dishonest, so
# these categories get a different, truthful ritual: know your lot number.
CONSUMABLE = {
 "Infant formula": [
   "You cannot see a formula recall. Contamination and dosing errors are what CPSC and FDA cite, and none of it is visible.",
   "Photograph the lot number and best-by date on the bottom of the tin before you open it.",
   "Recalls name specific lots, not brands. That photo is the whole check."],
 "Baby food & purees": [
   "Photograph the lot code on the pouch or jar before it goes in the cupboard.",
   "Recalls here name lots and date ranges, so the code is what matters, not the brand.",
   "Anything already opened and off in smell or colour goes in the bin, not the fridge."],
 "Baby wipes": [
   "Wipe recalls are almost always bacterial or mould contamination, which you may smell before you see.",
   "Keep the pack code until the pack is finished.",
   "An off odour or discoloration is a reason to stop using that pack."],
 "Children's medicine": [
   "Photograph the lot number and expiry on the box, not just the bottle.",
   "Recalls here are usually about dosing, contamination or undeclared ingredients, none of which you can see.",
   "Keep the box until the bottle is finished, because the lot number lives on it."],
 "Vitamins & supplements": [
   "Photograph the lot number on the bottle before first use.",
   "Undeclared ingredients and incorrect levels are the repeated pattern, and neither is visible.",
   "Keep the packaging until the bottle is done."],
 "Lotion, cream & bath": [
   "Photograph the batch code on the tube or bottle.",
   "Contamination is the usual reason, so recalls name batches rather than whole brands.",
   "Stop using anything that changes in smell, colour or texture."],
 "Baby sunscreen": [
   "Photograph the lot number on the tube.",
   "Recalls in this category have been about contamination found in specific batches.",
   "Keep the packaging until the tube is finished."],
}

def build(db):
    cpsc=[r for r in db if (r.get('source','') or '').upper()=='CPSC']
    out=[]
    for label, namepat, checks in SPEC:
        np=re.compile(namepat, re.I)
        hits=[r for r in cpsc if np.search(r.get('display_name','') or '')]
        if not hits: continue
        items=[]
        for line, evidence in checks:
            ev=re.compile(evidence, re.I)
            n=sum(1 for r in hits if ev.search(str(r.get('reason',''))))
            if n==0: continue          # never show a check the data does not support
            items.append({"text": line, "seen_in": n})
        if not items: continue
        items.sort(key=lambda c:-c["seen_in"])
        out.append({
            "category": label,
            "recalls": len(hits),
            "kind": "inspect",
            "checks": items[:3],       # a ritual needs an ending. three, then done.
        })

    # Consumable categories: same ritual shape, honest content.
    others=[r for r in db if r.get('display_category')!='Medical'
            and (r.get('source','') or '').upper()!='CPSC']
    import re as _re
    FDA_PAT={
      "Infant formula": r"formula|similac|enfamil|nutramigen|byheart|alimentum|puramino|elecare",
      "Baby food & purees": r"baby food|puree|pouch|cereal|snack|apple ?sauce|toddler (meal|food)",
      "Children's medicine": r"tylenol|ibuprofen|acetaminophen|motrin|benadryl|nyquil|cough|cold|allergy|syrup|drops|suspension|loratadine|diphenhydramine",
      "Vitamins & supplements": r"vitamin|supplement|multivitamin|probiotic|dha|omega|\biron\b|fluoride",
      "Baby wipes": r"wipe",
      "Lotion, cream & bath": r"lotion|cream|balm|ointment|powder|body wash|shampoo|\boil\b|diaper rash",
      "Baby sunscreen": r"sunscreen|\bspf\b",
    }
    for label, lines in CONSUMABLE.items():
        pat=FDA_PAT.get(label)
        n=len([r for r in others if pat and _re.search(pat, r.get('display_name','') or '', _re.I)]) if pat else 0
        out.append({
            "category": label,
            "recalls": n,
            "kind": "lot",
            "checks": [{"text": l, "seen_in": n} for l in lines[:3]],
        })

    out.sort(key=lambda c:-c["recalls"])
    return {"categories": out}

if __name__=="__main__":
    src=sys.argv[1] if len(sys.argv)>1 else "/tmp/recalls.json"
    dst=sys.argv[2] if len(sys.argv)>2 else "data/checks.json"
    data=build(load(src))
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    json.dump(data, open(dst,"w"), ensure_ascii=False, indent=1)
    print(f"{dst}: {len(data['categories'])} categories\n")
    for c in data["categories"]:
        print(f"  {c['category']}  ({c['recalls']} recalls)")
        for ch in c["checks"]:
            print(f"     [{ch['seen_in']:2d}x] {ch['text'][:78]}")
        print()
