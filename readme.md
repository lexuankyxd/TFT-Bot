# TFT Bot

Le Xuan Ky - HUST

---

# Data collection

Query twitch vods
curl https://api.metatft.com/tft-vods/latest\?limit\=100\&offset\=12500
limit <= 100, should write script that query every twitch vods based on offset. Seems like it's sorting by newest so offset changes overtime as new vods are added in

- some vods require to be a subcribber on twitch
- we have a ocr budget of 100ms ?
- for stats: GET https://data.metatft.com/lookups/latest_TFTSet16_tables.json
---

# OCR module
