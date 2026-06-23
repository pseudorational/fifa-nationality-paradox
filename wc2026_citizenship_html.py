"""
Generates wc2026_citizenship.html — interactive bipartite chart of
citizenship vs. represented nation for FIFA World Cup 2026 players.

Reads wc2026_players.csv, normalises Wikidata formal country names to
match team short-names, then injects FLOWS and COLS as JSON into the
HTML template. No manual data entry required.

Run: python wc2026_citizenship_html.py
Output: wc2026_citizenship.html  (open in any browser)
"""

import json
import sys
import os

if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd

MIN_PLAYERS = 2
OUTPUT_HTML = "wc2026_citizenship.html"

# Wikidata formal names → team short-names used in the representing column
NORM = {
    "Kingdom of the Netherlands": "Netherlands",
    "Democratic Republic of the Congo": "DR Congo",
}

# Long names → display abbreviations (applied to both columns)
ABBR = {
    "Bosnia and Herzegovina": "Bosnia & Herz.",
}

# Colors from the birth-country chart (wc2026_migration_html.py), in the same
# order.  Countries present in both charts keep the same color; citizenship-only
# countries (United Kingdom, Italy, Croatia, Brazil) inherit the spare slots
# left by birth-only countries (England, Bosnia & Herz., DRC, Austria).
BIRTH_COLS = {
    "France":        "#378ADD",
    "Netherlands":   "#1D9E75",
    "England":       "#D4537E",   # spare → United Kingdom
    "Germany":       "#BA7517",
    "Spain":         "#7F77DD",
    "Belgium":       "#639922",
    "Sweden":        "#E24B4A",
    "United States": "#D85A30",
    "Bosnia & Herz.":"#888780",   # spare → Italy
    "Portugal":      "#185FA5",
    "DRC":           "#534AB7",   # spare → Croatia
    "Canada":        "#85B7EB",
    "Austria":       "#ED93B1",   # spare → Brazil
    "Argentina":     "#F0997B",
    "Slovenia":      "#EF9F27",
}

# ── 1. Load & compute flows ───────────────────────────────────────────────────

df = pd.read_csv("wc2026_players.csv")
complete = df[df["data_complete"] == True].copy()
complete = complete[complete["citizenship"].fillna("").str.strip() != ""]

# Explode players with multiple citizenships (separated by "; ")
exploded = (
    complete
    .assign(citizenship=complete["citizenship"].str.split("; "))
    .explode("citizenship")
)
exploded = exploded[exploded["citizenship"].str.strip() != ""].copy()

# Normalise citizenship formal names for the cross-border comparison
exploded["cit_norm"] = exploded["citizenship"].map(lambda c: NORM.get(c, c))

# Display names for both columns
exploded["cit_disp"] = exploded["cit_norm"].map(lambda c: ABBR.get(c, c))
exploded["rep_disp"] = exploded["representing"].map(lambda c: ABBR.get(c, c))

# Keep only cross-citizenship rows (normalised name ≠ team name)
cross = exploded[exploded["cit_norm"] != exploded["representing"]]

flows_df = (
    cross
    .groupby(["cit_disp", "rep_disp"])
    .size()
    .reset_index(name="n")
    .query("n >= @MIN_PLAYERS")
    .sort_values("n", ascending=False)
)

# Assign colors: known countries keep their birth-chart color; new countries
# cycle through the spare slots in birth-chart order.
cit_totals = flows_df.groupby("cit_disp")["n"].sum().sort_values(ascending=False)
spares = [v for k, v in BIRTH_COLS.items() if k not in cit_totals.index]
spare_iter = iter(spares)
cols = {
    c: BIRTH_COLS[c] if c in BIRTH_COLS else next(spare_iter)
    for c in cit_totals.index
}

flows = [
    {"b": r.cit_disp, "r": r.rep_disp, "n": int(r.n)}
    for r in flows_df.itertuples()
]

n_cross    = len(cross)
n_complete = len(complete)
n_cross_pct = (n_cross/n_complete)*100
n_flows    = len(flows)
n_covered  = int(flows_df["n"].sum())

print(f"Players with citizenship data  : {n_complete}")
print(f"Cross-citizenship players      : {n_cross} ({100*n_cross/n_complete:.0f}%)")
print(f"Flows shown (>= {MIN_PLAYERS} players)  : {n_flows}  covering {n_covered} players")
print(f"Top citizenship sources        : "
      + ", ".join(f"{c} ({n})" for c, n in cit_totals.head(6).items()))

# ── 2. HTML template ──────────────────────────────────────────────────────────

TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FIFA World Cup 2026 — Citizenship vs Representation</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; padding: 20px;
         background: #fff; color: #111; }
  @media (prefers-color-scheme: dark) {
    body { background: #0d1117; color: #e6edf3; }
    .footer { color: #6e7681; }
  }
  .hint   { font-size: 13px; text-align: center; margin: 0 0 10px; color: #555; }
  .footer { font-size: 11px; text-align: center; margin: 6px 0 0; color: #888; }
  .fp,.nb,.nr,.nl { transition: opacity .22s ease; }
  .ng { cursor: pointer; }
</style>
</head>
<body>
<p class="hint">Click any bubble to highlight its connections · click again to reset</p>
<svg id="fv" viewBox="0 0 1000 960" xmlns="http://www.w3.org/2000/svg"
     style="width:100%;display:block"></svg>
<p class="footer">__FOOTER__</p>
<script>
const FLOWS=__FLOWS__;
const COLS=__COLS__;

const LX=290,RX=710,CX=500,TY=90,BY=905;
const TT={},BT={};
FLOWS.forEach(f=>{TT[f.r]=(TT[f.r]||0)+f.n;BT[f.b]=(BT[f.b]||0)+f.n;});
const LC=Object.entries(TT).sort((a,b)=>b[1]-a[1]).map(([c])=>c);
const RC=Object.entries(BT).sort((a,b)=>b[1]-a[1]).map(([c])=>c);
function ypos(arr){
  return Object.fromEntries(
    arr.map((c,i)=>[c,arr.length<2?(TY+BY)/2:TY+i*(BY-TY)/(arr.length-1)])
  );
}
const LY=ypos(LC),RY=ypos(RC);
const MAXL=Math.max(...Object.values(TT));
const MAXR=Math.max(...Object.values(BT));
const MAXN=Math.max(...FLOWS.map(f=>f.n));
const bR=(v,m)=>8+14*Math.pow(v/m,.62);
const lW=n=>1.5+14.5*Math.pow(n/MAXN,.55);
const NS="http://www.w3.org/2000/svg";
const sv=document.getElementById("fv");
function mk(t,a,s){
  const e=document.createElementNS(NS,t);
  for(const[k,v]of Object.entries(a||{}))e.setAttribute(k,v);
  if(s)Object.assign(e.style,s);
  return e;
}
const gf=mk("g");
FLOWS.forEach(f=>{
  if(RY[f.b]==null||LY[f.r]==null)return;
  gf.appendChild(mk("path",{
    d:`M${RX} ${RY[f.b]} C${CX} ${RY[f.b]} ${CX} ${LY[f.r]} ${LX} ${LY[f.r]}`,
    fill:"none",stroke:COLS[f.b]||"#888","stroke-width":lW(f.n),
    "stroke-linecap":"round","data-b":f.b,"data-r":f.r,class:"fp"
  },{opacity:".32"}));
});
sv.appendChild(gf);
function mkNodes(arr,x,side,tot,maxV){
  const g=mk("g");
  arr.forEach(c=>{
    const y=side==="l"?LY[c]:RY[c];
    if(y==null)return;
    const r=bR(tot[c],maxV),col=side==="r"?(COLS[c]||"#888"):"#378ADD";
    const ng=mk("g",{"data-c":c,"data-s":side,class:"ng"});
    ng.appendChild(mk("circle",{cx:x,cy:y,r:r+7,fill:"none",stroke:"white",
      "stroke-width":2.5,class:"nr"},{opacity:"0"}));
    ng.appendChild(mk("circle",{cx:x,cy:y,r,fill:col,
      stroke:"rgba(255,255,255,.3)","stroke-width":1.5,class:"nb"},{opacity:".92"}));
    const ta=side==="l"?"end":"start",dx=side==="l"?-r-9:r+9;
    const t1=mk("text",{x:x+dx,y:y-2,"text-anchor":ta,"font-size":"10.5",
      "font-weight":"500","font-family":"system-ui,sans-serif",class:"nl"});
    t1.style.fill="inherit";t1.textContent=c;ng.appendChild(t1);
    const t2=mk("text",{x:x+dx,y:y+10,"text-anchor":ta,"font-size":"8.5",
      "font-family":"system-ui,sans-serif",class:"nl"});
    t2.style.fill="gray";
    t2.textContent=side==="l"?`${tot[c]} dual-nationality`:`${tot[c]} players`;
    ng.appendChild(t2);
    ng.addEventListener("click",e=>{e.stopPropagation();hc(c,side);});
    g.appendChild(ng);
  });
  sv.appendChild(g);
}
mkNodes(LC,LX,"l",TT,MAXL);
mkNodes(RC,RX,"r",BT,MAXR);
[["Representing","#378ADD",LX],["Citizenship","#BA7517",RX]].forEach(([t,col,x])=>{
  const e=mk("text",{x,y:52,"text-anchor":"middle","font-size":"12",
    "font-weight":"500","font-family":"system-ui,sans-serif","letter-spacing":".5"});
  e.style.fill=col;e.textContent=t;sv.appendChild(e);
});
sv.appendChild(mk("line",{x1:CX,y1:20,x2:CX,y2:950,
  stroke:"#ccc","stroke-width":1,"stroke-dasharray":"5 5"}));
let SC=null,SS=null;
function hc(c,s){
  if(SC===c&&SS===s){ra();return;}
  SC=c;SS=s;
  const cb=new Set(),cr=new Set();
  FLOWS.forEach(f=>{
    if((s==="r"&&f.b===c)||(s==="l"&&f.r===c)){cb.add(f.b);cr.add(f.r);}
  });
  sv.querySelectorAll(".fp").forEach(p=>{
    p.style.opacity=((s==="r"&&p.dataset.b===c)||(s==="l"&&p.dataset.r===c))?".88":".04";
  });
  sv.querySelectorAll(".ng").forEach(ng=>{
    const nc=ng.dataset.c,ns=ng.dataset.s;
    const isSel=nc===c&&ns===s;
    const isConn=(ns==="l"&&cr.has(nc))||(ns==="r"&&cb.has(nc));
    const on=isSel||isConn;
    ng.querySelectorAll(".nb").forEach(b=>b.style.opacity=on?".92":".12");
    ng.querySelectorAll(".nl").forEach(t=>t.style.opacity=on?"1":".1");
    ng.querySelectorAll(".nr").forEach(r=>r.style.opacity=isSel?".85":"0");
  });
}
function ra(){
  SC=null;SS=null;
  sv.querySelectorAll(".fp").forEach(p=>p.style.opacity=".32");
  sv.querySelectorAll(".nb").forEach(b=>b.style.opacity=".92");
  sv.querySelectorAll(".nl").forEach(t=>t.style.opacity="1");
  sv.querySelectorAll(".nr").forEach(r=>r.style.opacity="0");
}
sv.addEventListener("click",ra);
</script>
</body>
</html>
"""

footer = (
    f"{n_cross} ({n_cross_pct:.1f}%) of {n_complete} players hold citizenship outside their represented nation "
    f"· Only flows of 2 or more players shown · Data Source: Football API (https://www.api-football.com) and Wikipedia"
  
)


html = (
    TEMPLATE
    .replace("__FLOWS__", json.dumps(flows, ensure_ascii=False))
    .replace("__COLS__",  json.dumps(cols,  ensure_ascii=False))
    .replace("__FOOTER__", footer)
)

with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\nSaved: {OUTPUT_HTML}")
