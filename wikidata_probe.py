"""Diagnostic: find WC 2026 in Wikidata and check what's linked."""
import requests, json

SPARQL_URL = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "WC2026Diagnostic/1.0", "Accept": "application/json"}

def sparql(q, label=""):
    r = requests.get(SPARQL_URL, headers=HEADERS,
                     params={"query": q, "format": "json"}, timeout=90)
    rows = r.json()["results"]["bindings"]
    print(f"\n=== {label} ({len(rows)} rows) ===")
    return rows

# 1. All FIFA World Cup editions
rows = sparql("""
SELECT ?item ?itemLabel ?start WHERE {
  ?item wdt:P31 wd:Q3537796 .
  OPTIONAL { ?item wdt:P580 ?start . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
} ORDER BY ?start
""", "FIFA World Cup editions (Q3537796)")

for r in rows:
    qid   = r.get("item",{}).get("value","").split("/")[-1]
    label = r.get("itemLabel",{}).get("value","")
    start = r.get("start",{}).get("value","")[:10]
    print(f"  {qid}: {label!r}  start={start}")

# Grab the 2026 QID from results
wc2026_qid = None
for r in rows:
    label = r.get("itemLabel",{}).get("value","")
    if "2026" in label:
        wc2026_qid = "wd:" + r["item"]["value"].split("/")[-1]
        print(f"\n  -> Found WC 2026 QID: {wc2026_qid}")
        break

if not wc2026_qid:
    # Try searching by start year
    rows2 = sparql("""
    SELECT ?item ?itemLabel WHERE {
      ?item wdt:P31 wd:Q3537796 .
      ?item wdt:P580 ?s . FILTER(YEAR(?s) = 2026)
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    """, "WC editions starting in 2026")
    for r in rows2:
        qid   = r.get("item",{}).get("value","").split("/")[-1]
        label = r.get("itemLabel",{}).get("value","")
        print(f"  {qid}: {label!r}")
    if rows2:
        wc2026_qid = "wd:" + rows2[0]["item"]["value"].split("/")[-1]

if not wc2026_qid:
    print("\n[WARN] Could not find WC 2026 item via Q3537796. Trying broader search...")
    rows3 = sparql("""
    SELECT ?item ?itemLabel WHERE {
      ?item rdfs:label "2026 FIFA World Cup"@en .
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    """, "Direct label search for 2026 FIFA World Cup")
    for r in rows3:
        qid   = r.get("item",{}).get("value","").split("/")[-1]
        label = r.get("itemLabel",{}).get("value","")
        print(f"  {qid}: {label!r}")
    if rows3:
        wc2026_qid = "wd:" + rows3[0]["item"]["value"].split("/")[-1]

if wc2026_qid:
    print(f"\nUsing WC 2026 QID: {wc2026_qid}")

    # 2. Teams linked to WC 2026 via P1344
    rows_teams = sparql(f"""
    SELECT ?team ?teamLabel WHERE {{
      ?team wdt:P1344 {wc2026_qid} .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }} ORDER BY ?teamLabel
    """, f"Teams with P1344 -> {wc2026_qid}")
    for r in rows_teams[:10]:
        print(f"  {r.get('teamLabel',{}).get('value','')}")
    if len(rows_teams) > 10:
        print(f"  ... and {len(rows_teams)-10} more")

    # 3. Players linked to WC 2026 via P1344
    rows_players = sparql(f"""
    SELECT ?player ?playerLabel WHERE {{
      ?player wdt:P1344 {wc2026_qid} .
      ?player wdt:P31 wd:Q5 .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }} LIMIT 5
    """, f"Sample players with P1344 -> {wc2026_qid}")
    for r in rows_players:
        print(f"  {r.get('playerLabel',{}).get('value','')}")
else:
    print("\n[ERROR] Could not determine WC 2026 QID in Wikidata.")
