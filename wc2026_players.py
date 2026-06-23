"""
FIFA World Cup 2026 — Player Dataset Builder
Source: API-Football (api-sports.io)  •  League ID 1, Season 2026

Usage
-----
1. Set your API key in the API_KEY variable below (or env var APISPORTS_KEY).
2. Run in test mode first to confirm the response schema:
       python wc2026_players.py --test
3. Once confirmed, run the full pull:
       python wc2026_players.py

Outputs
-------
wc2026_players.csv        — main dataset (five columns)
wc2026_missing.csv        — players with one or more missing fields
cache/                    — raw JSON responses (so reruns skip API calls)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("APISPORTS_KEY", "53124f05d916cafb69b4538a179585a1")
BASE_URL = "https://v3.football.api-sports.io"
LEAGUE_ID = 1        # FIFA World Cup in API-Football
SEASON = 2026

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

# Seconds between API calls — free tier allows 10 req/min, so 7 s is safe.
REQUEST_DELAY = 7
MAX_RETRIES = 3

OUTPUT_CSV = "wc2026_players.csv"
MISSING_CSV = "wc2026_missing.csv"

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

HEADERS = {
    "x-apisports-key": "53124f05d916cafb69b4538a179585a1",
    "Accept": "application/json",
}


def _cache_path(endpoint: str, params: dict) -> Path:
    """Deterministic filename for a request so reruns skip the network."""
    safe = "_".join(f"{k}{v}" for k, v in sorted(params.items()))
    name = endpoint.lstrip("/").replace("/", "_") + "__" + safe + ".json"
    return CACHE_DIR / name


def api_get(endpoint: str, params: dict) -> dict:
    """GET with caching, rate-limit delay, and retry on 5xx / network errors."""
    path = _cache_path(endpoint, params)
    if path.exists():
        print(f"  [cache] {path.name}")
        return json.loads(path.read_text(encoding="utf-8"))

    url = BASE_URL + endpoint
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"  [GET]   {url}  params={params}  (attempt {attempt})")
            resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            time.sleep(REQUEST_DELAY)
            return data
        except requests.HTTPError as e:
            if resp.status_code == 429:
                wait = 60
                print(f"  [429] Rate limited — sleeping {wait}s")
                time.sleep(wait)
            elif resp.status_code >= 500:
                print(f"  [5xx] Server error — sleeping 15s")
                time.sleep(15)
            else:
                raise
        except requests.RequestException as e:
            print(f"  [ERR]  {e} — sleeping 15s")
            time.sleep(15)

    raise RuntimeError(f"Failed after {MAX_RETRIES} attempts: {url} {params}")


def get_all_pages(endpoint: str, base_params: dict) -> list:
    """Fetch all pages for a paginated endpoint and return the merged response list."""
    results = []
    page = 1
    while True:
        params = {**base_params, "page": page}
        data = api_get(endpoint, params)

        # API-Football wraps data in {"response": [...], "paging": {...}}
        items = data.get("response", [])
        results.extend(items)

        paging = data.get("paging", {})
        current = paging.get("current", 1)
        total = paging.get("total", 1)
        print(f"    page {current}/{total}  ({len(items)} items)")

        if current >= total:
            break
        page += 1

    return results


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

def extract_player_row(entry: dict, team_name: str) -> dict:
    """
    Pull the five target columns from a single /players response entry.

    API-Football player object shape (relevant fields):
      entry = {
        "player": {
          "name": str,
          "birth": {"country": str, "place": str},
          "nationality": str,         <- country of citizenship / passport
        },
        "statistics": [{"team": {"name": str}, ...}]
      }

    Columns we build:
      team_name          — from the outer loop (what we queried by)
      player_name        — player.name
      birth_country      — player.birth.country
      citizenship        — player.nationality
      representing       — same as team_name (the WC squad they're in)

    Note: birth_country and citizenship are kept separate on purpose — they
    can (and often do) differ, which is the whole point of this dataset.
    """
    player = entry.get("player", {})
    birth = player.get("birth") or {}

    return {
        "team_name":    team_name,
        "player_name":  player.get("name", ""),
        "birth_country": birth.get("country", ""),
        "citizenship":  player.get("nationality", ""),
        "representing": team_name,
    }


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def fetch_teams() -> list[dict]:
    """Return all teams registered for WC 2026 in the API."""
    data = api_get("/teams", {"league": LEAGUE_ID, "season": SEASON})
    teams = data.get("response", [])
    print(f"\nFound {len(teams)} team(s) for league={LEAGUE_ID} season={SEASON}")
    return teams


def fetch_squad(team_id: int, team_name: str) -> list[dict]:
    """Return all player rows for a single team (all pages)."""
    params = {"league": LEAGUE_ID, "season": SEASON, "team": team_id}
    entries = get_all_pages("/players", params)
    return [extract_player_row(e, team_name) for e in entries]


# ---------------------------------------------------------------------------
# Test mode — one team, pretty-printed
# ---------------------------------------------------------------------------

def run_test():
    print("=" * 60)
    print("TEST MODE — fetching one team to verify API response schema")
    print("=" * 60)

    if API_KEY == "YOUR_API_KEY_HERE":
        print("\n[ERROR] Set API_KEY or APISPORTS_KEY env var before running.")
        sys.exit(1)

    teams = fetch_teams()
    if not teams:
        print("[ERROR] No teams returned — check league/season IDs or API key.")
        sys.exit(1)

    # Pick the first team for the test
    first = teams[0]
    team_id = first["team"]["id"]
    team_name = first["team"]["name"]
    print(f"\nTest team: {team_name} (id={team_id})\n")

    # Show raw API structure for the first two players so we can verify
    params = {"league": LEAGUE_ID, "season": SEASON, "team": team_id, "page": 1}
    raw = api_get("/players", params)

    sample = raw.get("response", [])[:2]
    print("--- Raw API sample (first 2 players) ---")
    print(json.dumps(sample, indent=2, ensure_ascii=False))

    rows = [extract_player_row(e, team_name) for e in raw.get("response", [])]
    df = pd.DataFrame(rows)
    print(f"\n--- Extracted rows for {team_name} ---")
    print(df.to_string(index=False))
    print(f"\nColumns: {list(df.columns)}")
    print("\nTest complete. If the schema looks right, run without --test.")


# ---------------------------------------------------------------------------
# Full run — all 48 teams
# ---------------------------------------------------------------------------

def run_full():
    print("=" * 60)
    print("FULL RUN — all WC 2026 teams")
    print("=" * 60)

    if API_KEY == "YOUR_API_KEY_HERE":
        print("\n[ERROR] Set API_KEY or APISPORTS_KEY env var before running.")
        sys.exit(1)

    teams = fetch_teams()
    if not teams:
        print("[ERROR] No teams returned.")
        sys.exit(1)

    all_rows = []
    for i, team_entry in enumerate(teams, 1):
        team_id = team_entry["team"]["id"]
        team_name = team_entry["team"]["name"]
        print(f"\n[{i}/{len(teams)}] {team_name} (id={team_id})")
        rows = fetch_squad(team_id, team_name)
        print(f"  -> {len(rows)} players")
        all_rows.extend(rows)

    df = pd.DataFrame(all_rows)

    # Identify missing-data rows (any of the five core fields is blank)
    core_cols = ["player_name", "birth_country", "citizenship"]
    missing_mask = df[core_cols].apply(lambda c: c.str.strip() == "").any(axis=1)
    missing_df = df[missing_mask].copy()
    clean_df = df.copy()  # keep all rows in main CSV, flag column added

    clean_df["data_complete"] = ~missing_mask

    # Save outputs
    clean_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\nSaved {len(clean_df)} rows -> {OUTPUT_CSV}")

    if len(missing_df):
        missing_df.to_csv(MISSING_CSV, index=False, encoding="utf-8-sig")
        print(f"Flagged {len(missing_df)} players with missing fields -> {MISSING_CSV}")
    else:
        print("No missing-data players found.")

    print("\nSummary:")
    print(f"  Teams processed : {df['team_name'].nunique()}")
    print(f"  Total players   : {len(df)}")
    print(f"  Missing data    : {missing_mask.sum()}")

    return clean_df


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build a FIFA World Cup 2026 player dataset from API-Football."
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Fetch one team only and print the raw API schema.",
    )
    args = parser.parse_args()

    if args.test:
        run_test()
    else:
        run_full()
