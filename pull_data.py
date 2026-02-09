import json
import os

from twitch_downloader.download_vod import download_vod
from twitch_downloader.fetchvods import get_vods_list

vod = get_vods_list(1, 12)
assert vod is not None
try:
  os.mkdir("vids")
except Exception as e:
  pass
download_vod(vod[0]["vod_data"]["vod_id"], "vids")
print(vod)
