"""
wc2026_fix_uk.py
Resolve "United Kingdom" birth country to the specific constituent home nation
(England, Scotland, Wales, Northern Ireland) via Wikidata's P131 property chain.

P131 = "located in the administrative territorial entity"
P3336843 = "constituent country of the United Kingdom" (class)

The chain for a city like Leeds goes:
  Leeds -> West Yorkshire -> England  (where England wdt:P31 wd:Q3336843)

Run: python wc2026_fix_uk.py
Updates wc2026_players.csv in place.
"""
import sys, os, json, time
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from collections import Counter
import pandas as pd
import requests
from bs4 import BeautifulSoup

CACHE_DIR   = Path("cache_wiki")
SPARQL_URL  = "https://query.wikidata.org/sparql"
HEADERS     = {"User-Agent": "WC2026PlayerDataset/1.0", "Accept": "application/json"}
CACHE_UK    = CACHE_DIR / "uk_constituent_countries.json"

# ── 1. Load CSV ───────────────────────────────────────────────────────────────
df = pd.read_csv("wc2026_players.csv")
uk_rows = df[df["birth_country"] == "United Kingdom"]
print(f"Players labelled 'United Kingdom': {len(uk_rows)}")

# ── 2. Rebuild title → QID from cache files ───────────────────────────────────
title_to_qid: dict[str, str] = {}
for cache_file in sorted(CACHE_DIR.glob("qids_batch_*.json")):
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    for page in data.get("query", {}).get("pages", {}).values():
        title = page.get("title", "")
        qid   = page.get("pageprops", {}).get("wikibase_item", "")
        if title and qid:
            title_to_qid[title] = qid
print(f"QIDs loaded from cache: {len(title_to_qid)}")

# ── 3. Re-parse Wikipedia HTML to get player_name → wiki_title ────────────────
wiki_cache = CACHE_DIR / "wikipedia_wc2026_squads.json"
html = json.loads(wiki_cache.read_text(encoding="utf-8"))["parse"]["text"]["*"]
soup = BeautifulSoup(html, "html.parser")

_SKIP = {"See also", "Notes", "References", "External links",
         "Notes and references", "Contents"}

player_to_title: dict[str, str] = {}
current_team = None
for tag in soup.find_all(["h2", "h3", "table"]):
    if tag.name == "h2":
        continue
    elif tag.name == "h3":
        t = tag.get_text(strip=True)
        if t and t not in _SKIP:
            current_team = t
    elif tag.name == "table" and current_team:
        for row in tag.find_all("tr", class_="nat-fs-player"):
            th = row.find("th", attrs={"scope": "row"})
            if not th:
                continue
            link = th.find("a")
            if link:
                name  = link.get_text(strip=True)
                title = link.get("title") or ""
                if name and title:
                    player_to_title[name] = title

print(f"Players with wiki titles: {len(player_to_title)}")

# ── 4. Get QIDs for UK-born players ──────────────────────────────────────────
uk_qid: dict[str, str] = {}   # QID → player_name
for player_name in uk_rows["player_name"]:
    wiki_title = player_to_title.get(player_name)
    if wiki_title:
        qid = title_to_qid.get(wiki_title)
        if qid:
            uk_qid[qid] = player_name

print(f"UK-born players with QIDs: {len(uk_qid)}  "
      f"(no QID: {len(uk_rows) - len(uk_qid)})")

# ── 5. SPARQL: traverse P131+ to find England / Scotland / Wales / N.Ireland ──
def _sparql_uk_batch(qids: list[str], label: str) -> list[dict]:
    """
    For a batch of player QIDs, walk the P131 chain (up to 4 levels deep)
    to find which UK home nation their birth place sits in.

    Instead of P131+ (transitive, times out on Wikidata), we write an explicit
    UNION for depths 1-4 and pin the target to the four home-nation QIDs:
      Q21 = England, Q22 = Scotland, Q25 = Wales, Q26 = Northern Ireland
    This is orders of magnitude faster because Wikidata doesn't scan P31 instances.
    """
    cache = CACHE_DIR / f"uk_{label}.json"
    if cache.exists():
        print(f"  [cache] {cache.name}")
        return json.loads(cache.read_text(encoding="utf-8"))

    values = " ".join(f"wd:{q}" for q in qids)
    # Hardcode the four home-nation QIDs to avoid scanning P31 = Q3336843
    query = f"""
SELECT DISTINCT ?player ?ukCountryLabel
WHERE {{
  VALUES ?player {{ {values} }}
  VALUES ?ukCountry {{ wd:Q21 wd:Q22 wd:Q25 wd:Q26 }}

  ?player wdt:P19 ?bp .

  {{  ?bp wdt:P131 ?ukCountry . }}
  UNION
  {{  ?bp wdt:P131/wdt:P131 ?ukCountry . }}
  UNION
  {{  ?bp wdt:P131/wdt:P131/wdt:P131 ?ukCountry . }}
  UNION
  {{  ?bp wdt:P131/wdt:P131/wdt:P131/wdt:P131 ?ukCountry . }}

  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
"""
    print(f"  [SPARQL] {label} ({len(qids)} players) …")
    r = requests.get(SPARQL_URL, headers=HEADERS,
                     params={"query": query, "format": "json"}, timeout=90)
    r.raise_for_status()
    rows = r.json()["results"]["bindings"]
    cache.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"    -> {len(rows)} rows")
    time.sleep(2)
    return rows


if CACHE_UK.exists():
    print(f"[cache] {CACHE_UK.name}")
    bindings = json.loads(CACHE_UK.read_text(encoding="utf-8"))
else:
    # Process in batches of 20 to keep queries small and fast
    BATCH = 20
    all_qids = list(uk_qid.keys())
    bindings = []
    for i in range(0, len(all_qids), BATCH):
        batch = all_qids[i : i + BATCH]
        bindings.extend(_sparql_uk_batch(batch, f"batch{i}"))
    CACHE_UK.write_text(json.dumps(bindings, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"Total rows: {len(bindings)}")

# ── 6. Build QID → constituent country ───────────────────────────────────────
qid_to_home: dict[str, str] = {}
for b in bindings:
    qid  = b.get("player",       {}).get("value", "").split("/")[-1]
    name = b.get("ukCountryLabel", {}).get("value", "")
    if qid and name:
        qid_to_home[qid] = name   # keep first match (should be unique per player)

# ── 7. Map back to player_name → home nation ─────────────────────────────────
name_to_home: dict[str, str] = {}
for qid, player_name in uk_qid.items():
    if qid in qid_to_home:
        name_to_home[player_name] = qid_to_home[qid]

print(f"\nResolved {len(name_to_home)} of {len(uk_qid)} UK-born players")
print("Breakdown:")
for country, count in sorted(Counter(name_to_home.values()).items()):
    print(f"  {country}: {count}")

# ── 8. Show interesting cross-border cases after resolution ───────────────────
print("\nCross-border cases (birth home-nation ≠ representing team):")
for _, row in uk_rows.iterrows():
    name    = row["player_name"]
    rep     = row["representing"]
    home    = name_to_home.get(name)
    if home and home != rep:
        print(f"  {name:30s}  born in {home:20s}  → representing {rep}")

# ── 9. Update CSV ─────────────────────────────────────────────────────────────
updated = 0
for idx, row in df.iterrows():
    if row["birth_country"] == "United Kingdom":
        home = name_to_home.get(row["player_name"])
        if home:
            df.at[idx, "birth_country"] = home
            updated += 1

# Recompute data_complete with updated birth_country
core_cols = ["player_name", "birth_country", "citizenship"]
df["data_complete"] = df[core_cols].apply(
    lambda c: c.fillna("").str.strip() != ""
).all(axis=1)

still_uk = (df["birth_country"] == "United Kingdom").sum()
print(f"\nUpdated {updated} rows  |  Still 'United Kingdom': {still_uk} (no P131 data)")
df.to_csv("wc2026_players.csv", index=False, encoding="utf-8-sig")
print("Saved: wc2026_players.csv")
