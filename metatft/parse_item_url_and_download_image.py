import json
import requests
import tqdm

reqs = json.load(open("metatft/www.metatft.com_Archive [26-02-17 16-00-36].har"))[
    "log"
]["entries"]
urls = [
    a["request"]["url"]
    for a in reqs
    if a["request"]["url"].split("/")[-1].startswith("tft")
]
print(urls[0])
# def convert_avif_to_png(avif_path, save_path: str):
#     try:

for url in tqdm.tqdm(urls):
    while True:
        req = requests.get(url)
        if req.status_code != 200:
            continue
        name = url.split("/")[-1]
        if "?" in name:
            name = name.split("?")[0]
        f = open(
            f"game/component_images/items/{name}",
            "wb",
        )
        f.write(req.content)
        f.close()
        break
