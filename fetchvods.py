import json

import requests


def get_vod_url(limit: int, offset: int) -> str:
  """
    Returns the URL for fetching TFT vods from the API.
  """
  assert limit > 0 and limit <= 100, "Invalid limit"
  assert offset >= 0, "Invalid offset"
  return f"https://api.metatft.com/tft-vods/latest?limit={limit}&offset={offset}"

if __name__ == "__main__":
  res = requests.get(get_vod_url(1, 1))
  if(res.status_code == 200):
    objs = json.loads(res.text)
    for obj in objs:
      for key, val in obj.items():
        if(isinstance(val, str) and "{" in val):
          obj[key] = json.loads(val)
    print(json.dumps(objs, indent=2, ensure_ascii=False))
  else:
    print(f"Error: {res.status_code}")
