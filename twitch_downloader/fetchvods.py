import json
import os
import re
from typing import Dict, List, Optional

import requests


def get_vod_url(limit: int, offset: int) -> str:
  """
    Returns the URL for fetching TFT vods from the API.
  """
  assert limit > 0 and limit <= 100, "Invalid limit"
  assert offset >= 0, "Invalid offset"
  return f"https://api.metatft.com/tft-vods/latest?limit={limit}&offset={offset}"

def _normalize_embedded_json(obj: dict) -> None:
  """
  Mutates obj in-place: if any value is a JSON-like string, attempt to parse it.
  """
  for key, val in list(obj.items()):
    if isinstance(val, str) and "{" in val:
      try:
        obj[key] = json.loads(val)
      except Exception:
        # leave the original string if parsing fails
        pass


def _simplify_obj(obj: dict) -> dict:
  """
  Return a simplified object with only the requested structure:
  {
    "vod_data": {
      "twitch": {"name": ..., "id": ...},
      "vod_id": ...,
      "league": {"riot_id": ..., "rating_numeric": ..., "region": ..., "games_played": ...},
      "game_version": ...
    },
    "data_extracted": {"actions": [], "states": []}
  }
  """
  # ensure any embedded json strings are parsed first
  _normalize_embedded_json(obj)

  # Twitch info
  twitch_account = obj.get("twitch_account_info") or {}
  twitch_name = twitch_account.get("name") or obj.get("twitch_login")
  twitch_id = twitch_account.get("id") or None

  # VOD id
  vod_id = None
  if isinstance(obj.get("vod_info"), dict):
    vod_id = obj["vod_info"].get("id")
  if not vod_id:
    # try to extract from twitch_vod url (fallback)
    twitch_vod_url = obj.get("twitch_vod", "")
    m = re.search(r"/videos/(\d+)", twitch_vod_url)
    if m:
      vod_id = m.group(1)

  # League info
  league = {"riot_id": None, "rating_numeric": None, "region": None, "games_played": None}
  la = obj.get("league_account_info")
  if isinstance(la, dict):
    league["riot_id"] = la.get("riot_id")
    league["rating_numeric"] = la.get("rating_numeric")
    league["region"] = la.get("region")
    # user asked for "games played"
    league["games_played"] = la.get("num_played")
  else:
    # fallback to match_data._metatft.participant_info (use first participant if present)
    md_participants = obj.get("match_data", {}).get("_metatft", {}).get("participant_info")
    if isinstance(md_participants, list) and len(md_participants) > 0:
      p = md_participants[0]
      league["riot_id"] = p.get("riot_id")
      ranked = p.get("ranked") or {}
      league["rating_numeric"] = ranked.get("rating_numeric")
      league["region"] = p.get("summoner_region")
      league["games_played"] = ranked.get("num_games")

  # Game version (try match_data.info.game_version)
  game_version = obj.get("match_data", {}).get("info", {}).get("game_version")

  return {
    "vod_data": {
      "twitch": {"name": twitch_name, "id": twitch_id},
      "vod_id": vod_id,
      "league": league,
      "game_version": game_version,
    },
    # leave data_extracted empty as requested
    "data_extracted": {"actions": [], "states": []},
  }


def get_vods_list(limit: int, offset: int) -> List[Dict] | Optional[None]:
  """
  Return a list of simplified VOD objects. Prefer a local data.json (project root) when present.
  Falls back to the remote API if local file is not found or cannot be parsed.
  """
  # Fallback to remote API
  res = requests.get(get_vod_url(limit, offset))
  if res.status_code == 200:
    objs = json.loads(res.text)
    simplified = []
    if isinstance(objs, dict):
      objs = [objs]
    for obj in objs:
      if isinstance(obj, dict):
        _normalize_embedded_json(obj)
        simplified.append(_simplify_obj(obj))
    return simplified
  else:
    return None
