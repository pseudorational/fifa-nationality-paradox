"""
FIFA World Cup 2026 — Player Dataset (Wikipedia + Wikidata, free)

Data sources
------------
1. Wikipedia "2026 FIFA World Cup squads" page
     -> team assignments (which country each player represents)
     -> player Wikipedia article links (used to look up Wikidata QIDs)

2. Wikidata SPARQL
     -> P19 place of birth -> P17 country (birth_country)
     -> P27 country of citizenship          (citizenship)

These two sources are joined on the player's Wikidata QID.

Why this hybrid? Wikidata's P54 (team membership) is incomplete for WC 2026
players, so team assignments come from Wikipedia's squad tables instead. Birth
and citizenship data are structured properties in Wikidata, so SPARQL is the
right tool for those.

Usage
-----
    python wc2026_wikidata.py --test     # process first country only
    python wc2026_wikidata.py            # full run -> wc2026_players.csv

Outputs
-------
wc2026_players.csv   — main five-column dataset
wc2026_missing.csv   — players missing birth_country or citizenship
cache_wiki/          — cached Wikipedia HTML and Wikidata responses
"""

import argparse
import json
import sys
import time
import re
from pathlib import Path
from urllib.parse import quote

# Force UTF-8 on Windows consoles so non-ASCII player names print correctly.
if sys.platform == "win32":
    import os
    os.environ.setdefault("PYTHONUTF8", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WIKI_SQUADS_URL = (
    "https://en.wikipedia.org/w/api.php?"
    "action=parse&page=2026_FIFA_World_Cup_squads"
    "&prop=text&format=json&disableeditsection=1"
)
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
MEDIAWIKI_API   = "https://en.wikipedia.org/w/api.php"

CACHE_DIR = Path("cache_wiki")
CACHE_DIR.mkdir(exist_ok=True)

OUTPUT_CSV  = "wc2026_players.csv"
MISSING_CSV = "wc2026_missing.csv"

HEADERS_WIKI = {
    "User-Agent": "WC2026PlayerDataset/1.0 (research)",
    "Accept": "application/json",
}
HEADERS_SPARQL = {
    "User-Agent": "WC2026PlayerDataset/1.0 (research)",
    "Accept":     "application/json",
}

# Wikidata batch size for QID lookup and SPARQL queries
BATCH_SIZE = 50

# ---------------------------------------------------------------------------
# Caching helpers
# ---------------------------------------------------------------------------

def _cache(name: str) -> Path:
    return CACHE_DIR / (name.replace("/", "_").replace(":", "_") + ".json")


def cached_get(url: str, params: dict, cache_name: str,
               delay: float = 2.0, max_retries: int = 4) -> dict:
    path = _cache(cache_name)
    if path.exists():
        print(f"  [cache] {path.name}")
        return json.loads(path.read_text(encoding="utf-8"))

    print(f"  [GET]   {cache_name}")
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, headers=HEADERS_WIKI, params=params, timeout=60)
            if r.status_code == 429:
                wait = 60 * attempt
                print(f"  [429]  Rate limited — sleeping {wait}s (attempt {attempt})")
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            time.sleep(delay)
            return data
        except requests.RequestException as e:
            if attempt == max_retries:
                raise
            print(f"  [ERR]  {e} — sleeping 15s")
            time.sleep(15)

    raise RuntimeError(f"All retries exhausted for {cache_name}")


def cached_sparql(query: str, cache_name: str, timeout: int = 120) -> list[dict]:
    path = _cache(cache_name)
    if path.exists():
        print(f"  [cache] {path.name}")
        return json.loads(path.read_text(encoding="utf-8"))
    print(f"  [SPARQL] {cache_name} ...")
    r = requests.get(
        WIKIDATA_SPARQL,
        headers=HEADERS_SPARQL,
        params={"query": query, "format": "json"},
        timeout=timeout,
    )
    r.raise_for_status()
    bindings = r.json()["results"]["bindings"]
    path.write_text(json.dumps(bindings, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> {len(bindings)} rows")
    time.sleep(1)
    return bindings


# ---------------------------------------------------------------------------
# Step 1: Scrape Wikipedia squad tables
# ---------------------------------------------------------------------------

def fetch_squad_html() -> str:
    """Return the rendered HTML of the WC 2026 squads Wikipedia article."""
    data = cached_get(WIKI_SQUADS_URL, {}, "wikipedia_wc2026_squads")
    return data["parse"]["text"]["*"]


def parse_squads(html: str) -> list[dict]:
    """
    Parse the squad tables from the rendered Wikipedia HTML.

    The 2026 WC squads article uses:
      <h2 id="Group_A">Group A</h2>           <- group, skip
      <h3 id="Czech_Republic">Czech Republic</h3>  <- country
      <tr class="nat-fs-player">               <- one player per row
        <th scope="row"><a title="Matej Kovar">Matej Kovar</a></th>

    Returns a list of dicts with:
        team        - country name  (e.g. "Czech Republic")
        player_name - player display name
        wiki_title  - Wikipedia article title for the player (may be None)
    """
    soup = BeautifulSoup(html, "html.parser")
    players = []
    current_team = None

    _SKIP_HEADINGS = {
        "See also", "Notes", "References", "External links",
        "Notes and references", "Contents",
    }

    for tag in soup.find_all(["h2", "h3", "table"]):
        if tag.name == "h2":
            # Group headings (Group A, Group B, …) — skip
            continue

        elif tag.name == "h3":
            text = tag.get_text(strip=True)
            if text and text not in _SKIP_HEADINGS:
                current_team = text

        elif tag.name == "table" and current_team:
            # Player rows have class "nat-fs-player"
            for row in tag.find_all("tr", class_="nat-fs-player"):
                # Player name is in <th scope="row"> (not <td>)
                th = row.find("th", attrs={"scope": "row"})
                if not th:
                    continue

                link = th.find("a")
                if link:
                    # Use link text for the display name (clean, no disambiguation).
                    # Use the 'title' attribute for wiki_title (needed for QID lookup).
                    player_name = link.get_text(strip=True)
                    wiki_title  = link.get("title") or None
                else:
                    player_name = th.get_text(strip=True)
                    wiki_title  = None

                # Drop empty or very short strings (artifacts)
                if player_name and len(player_name) > 1:
                    players.append({
                        "team":        current_team,
                        "player_name": player_name,
                        "wiki_title":  wiki_title,
                    })

    return players


# ---------------------------------------------------------------------------
# Step 2: Convert Wikipedia article titles -> Wikidata QIDs
# ---------------------------------------------------------------------------

def get_wikidata_qids(titles: list[str]) -> dict[str, str]:
    """
    Use the MediaWiki API to resolve Wikipedia article titles to Wikidata QIDs.
    Returns {title: QID} for titles that have a linked Wikidata item.
    Processes in batches of BATCH_SIZE.
    """
    result = {}
    titles = [t for t in titles if t]  # drop None

    for i in range(0, len(titles), BATCH_SIZE):
        batch = titles[i : i + BATCH_SIZE]
        cache_name = f"qids_batch_{i}"
        joined = "|".join(batch)

        data = cached_get(
            MEDIAWIKI_API,
            {
                "action": "query",
                "titles": joined,
                "prop":   "pageprops",
                "ppprop": "wikibase_item",
                "format": "json",
            },
            cache_name,
        )

        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            title = page.get("title", "")
            qid   = page.get("pageprops", {}).get("wikibase_item", "")
            if qid:
                result[title] = qid

    return result


# ---------------------------------------------------------------------------
# Step 3: Batch-query Wikidata for birth country + citizenship
# ---------------------------------------------------------------------------

def build_sparql_for_qids(qids: list[str]) -> str:
    values_block = " ".join(f"wd:{q}" for q in qids)
    return f"""
SELECT DISTINCT ?player ?birthCountryLabel ?citizenshipLabel
WHERE {{
  VALUES ?player {{ {values_block} }}

  OPTIONAL {{
    ?player wdt:P19 ?birthPlace .
    ?birthPlace wdt:P17 ?birthCountry .
  }}
  OPTIONAL {{ ?player wdt:P27 ?citizenship . }}

  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
"""


def fetch_wikidata_for_players(qids: list[str]) -> dict[str, dict]:
    """
    Query Wikidata for birth country and citizenship for a list of QIDs.
    Returns {QID: {"birth_country": str, "citizenship": str}}.
    Multiple citizenships are joined with "; ".
    """
    result: dict[str, dict] = {}
    qids = list(set(qids))  # deduplicate

    for i in range(0, len(qids), BATCH_SIZE):
        batch = qids[i : i + BATCH_SIZE]
        cache_name = f"wikidata_players_{i}"
        query = build_sparql_for_qids(batch)
        bindings = cached_sparql(query, cache_name)

        # Aggregate rows per player (multiple rows if multiple citizenships)
        for b in bindings:
            qid   = b.get("player", {}).get("value", "").split("/")[-1]
            bc    = b.get("birthCountryLabel", {}).get("value", "")
            cit   = b.get("citizenshipLabel", {}).get("value", "")

            if qid not in result:
                result[qid] = {"birth_country": bc, "citizenships": set()}
            if not result[qid]["birth_country"] and bc:
                result[qid]["birth_country"] = bc
            if cit:
                result[qid]["citizenships"].add(cit)

    # Flatten citizenships set to a sorted string
    for qid, data in result.items():
        data["citizenship"] = "; ".join(sorted(data["citizenships"]))
        del data["citizenships"]

    return result


# ---------------------------------------------------------------------------
# Build final DataFrame
# ---------------------------------------------------------------------------

def build_dataset(players: list[dict], wikidata: dict[str, dict],
                  title_to_qid: dict[str, str]) -> pd.DataFrame:
    rows = []
    for p in players:
        qid = title_to_qid.get(p["wiki_title"], "") if p["wiki_title"] else ""
        wd  = wikidata.get(qid, {})
        rows.append({
            "team_name":    p["team"],
            "player_name":  p["player_name"],
            "birth_country": wd.get("birth_country", ""),
            "citizenship":  wd.get("citizenship", ""),
            "representing": p["team"],
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main flows
# ---------------------------------------------------------------------------

def run(test_mode: bool = False):
    mode = "TEST MODE (first country only)" if test_mode else "FULL RUN"
    print("=" * 60)
    print(f"WC 2026 Players — {mode}")
    print("=" * 60)

    # Step 1: scrape Wikipedia
    print("\n[1] Fetching Wikipedia squad article...")
    html = fetch_squad_html()
    players = parse_squads(html)
    print(f"  Parsed {len(players)} player rows across "
          f"{len(set(p['team'] for p in players))} teams")

    if test_mode:
        first_team = players[0]["team"] if players else None
        players = [p for p in players if p["team"] == first_team]
        print(f"  Test mode: keeping only '{first_team}' ({len(players)} players)")

    if not players:
        print("[ERROR] No players parsed from Wikipedia. Check the article name.")
        sys.exit(1)

    # Step 2: Wikipedia title -> Wikidata QID
    print("\n[2] Resolving Wikipedia titles -> Wikidata QIDs...")
    titles = list({p["wiki_title"] for p in players if p["wiki_title"]})
    title_to_qid = get_wikidata_qids(titles)
    matched = sum(1 for p in players if title_to_qid.get(p.get("wiki_title")))
    print(f"  Resolved {len(title_to_qid)}/{len(titles)} titles to QIDs")
    print(f"  Players with a QID: {matched}/{len(players)}")

    # Step 3: Wikidata lookup for birth country + citizenship
    print("\n[3] Querying Wikidata for birth country + citizenship...")
    qids = list(set(title_to_qid.values()))
    wikidata = fetch_wikidata_for_players(qids)
    print(f"  Wikidata records fetched: {len(wikidata)}")

    # Step 4: Build DataFrame
    print("\n[4] Building dataset...")
    df = build_dataset(players, wikidata, title_to_qid)

    # Flag incomplete rows
    missing_mask = (df["birth_country"].str.strip() == "") | \
                   (df["citizenship"].str.strip() == "")
    df["data_complete"] = ~missing_mask

    print(f"\n  Teams:    {df['team_name'].nunique()}")
    print(f"  Players:  {len(df)}")
    print(f"  Missing:  {missing_mask.sum()}")

    if test_mode:
        print("\nFirst 10 rows:")
        print(df.head(10).to_string(index=False))
        return df

    # Save
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\nSaved -> {OUTPUT_CSV}")

    missing_df = df[missing_mask]
    if len(missing_df):
        missing_df.to_csv(MISSING_CSV, index=False, encoding="utf-8-sig")
        print(f"Missing -> {MISSING_CSV} ({len(missing_df)} players)")

    return df


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="WC 2026 player dataset — Wikipedia squads + Wikidata birth/citizenship."
    )
    parser.add_argument("--test", action="store_true",
                        help="Process the first country only and print results.")
    args = parser.parse_args()
    run(test_mode=args.test)
