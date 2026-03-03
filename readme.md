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

    The problem with using twitch vods is that screen resolution and ratio varies(I know most people use 1080p as their resolution but fuck me if i'm going to manually record the coordinates for every UI component.), which using a fixed set of coordinates might be problematic. Instead we can find the coordianates for each game incase changes occur.
what about champion positions? how can i even do this dynamically 
