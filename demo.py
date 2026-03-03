import numpy as np
from dataclasses import dataclass
import cv2
from time import perf_counter
import hashlib
import pickle
import os

PICKLE_DIR = "pickle"
BYPRODUCT_DIR = "byproduct"
PICKLE_CACHE_NAME = "scaled_image_cache.pkl"


@dataclass(order=True)
class Coordinate:
    x: int
    y: int


ratio_cache: dict[str, list[np.ndarray]] = {}
if os.path.exists(f"{PICKLE_DIR}/{PICKLE_CACHE_NAME}"):
    ratio_cache = pickle.load(open(f"{PICKLE_DIR}/{PICKLE_CACHE_NAME}", "rb"))


def find_subimage(
    main_image: np.ndarray,
    sub_image: np.ndarray,
    threshold: float = 0.7,
    explore: bool = False,
    match_many: bool = False,
    gray_scale: bool = False,
    create_byproduct: bool = False,
) -> list[list[Coordinate]] | None:
    hash_val = hashlib.sha256(
        (str(sub_image.tobytes()) + str(sub_image.shape)).encode("utf-8")
    ).hexdigest()
    gray_main = (
        cv2.cvtColor(main_image, cv2.COLOR_BGR2GRAY)
        if gray_scale
        else main_image.copy()
    )
    ratios = []
    scaled = []
    match_locs = []
    val_list = []
    if hash_val in ratio_cache:
        scaled.extend(ratio_cache[hash_val])
    if explore or len(scaled) == 0:
        min_r = 0.3
        max_r = (
            min(
                main_image.shape[0] / sub_image.shape[0],
                main_image.shape[1] / sub_image.shape[1],
            )
            / 4
        )
        ratios.extend([float(a) for a in np.arange(min_r, max_r + 0.01, 0.1)])

    while True:
        from_cache = False
        if len(scaled) == 0 and len(ratios) == 0:
            break
        elif len(scaled) != 0:
            from_cache = True
            curr = scaled.pop(0)
        elif len(ratios) != 0:
            ratio = ratios.pop(0)
            curr = cv2.resize(sub_image, (0, 0), fx=ratio, fy=ratio)
        gray_sub = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY) if gray_scale else curr
        result = cv2.matchTemplate(gray_main, gray_sub, cv2.TM_CCOEFF_NORMED)
        locs = list(zip(*np.where(result >= threshold)[::-1]))
        # usually, there's a bunch of locations that match the subimage but they are matching the same location, only differing by a couple pixel in coordiante
        # this is removing them
        h, w = gray_sub.shape if gray_scale else gray_sub.shape[:2]
        filtered_locs = []
        for loc in locs:
            if len(filtered_locs) == 0:
                filtered_locs.append(loc)
                continue
            if (
                abs(filtered_locs[-1][1] - loc[1]) < h * 0.2
                and abs(filtered_locs[-1][0] - loc[0]) < w * 0.2
            ):
                v1 = result[filtered_locs[-1][1], filtered_locs[-1][0]]
                v2 = result[loc[1], loc[0]]
                if v2 > v1:
                    filtered_locs[-1] = loc
            else:
                filtered_locs.append(loc)
        if not from_cache and len(locs) > 0:
            if len(match_locs):
                ratio_cache[hash_val].append(curr)
            else:
                ratio_cache[hash_val] = [curr]
            pickle.dump(ratio_cache, open(f"{PICKLE_DIR}/{PICKLE_CACHE_NAME}", "wb"))
        for loc in filtered_locs:
            val = result[loc[1], loc[0]]
            # print(loc, val)
            top_left = loc
            bottom_right = (top_left[0] + w, top_left[1] + h)
            if match_many:
                match_locs.append(
                    [
                        Coordinate(top_left[0], top_left[1]),
                        Coordinate(bottom_right[0], bottom_right[1]),
                    ]
                )
                val_list.append(val)
            else:
                if create_byproduct:
                    cv2.rect(main_image, top_left, bottom_right, (0, 255, 0), 1)
                    cv2.imwrite(f"{BYPRODUCT_DIR}/matched.png", main_image)
                return [
                    [
                        Coordinate(top_left[0], top_left[1]),
                        Coordinate(bottom_right[0], bottom_right[1]),
                    ]
                ]

    # filtering images with different ratios that might be matching the same thing
    del filtered_locs
    a = sorted(zip(match_locs, val_list), key=lambda x: x[0])
    filtered_locs = []
    for b in a:
        if len(filtered_locs) == 0:
            filtered_locs.append(b[:2])
        else:
            [pa0, pa1], va = filtered_locs[-1]
            [pb0, pb1], vb = b
            wa, ha = pa1.x - pa0.x, pa1.y - pa0.y
            wb, hb = pb1.x - pb0.x, pb1.y - pb0.y
            if (
                abs(pa0.x - pb0.x) < min(wa, wb) * 0.2
                and abs(pa0.y - pb0.y) < min(ha, hb) * 0.2
            ):
                if vb > va:
                    filtered_locs[-1] = b
            else:
                filtered_locs.append(b)
    for f in filtered_locs:
        print(f)
    filtered_locs = [a for [a, b] in filtered_locs]
    if create_byproduct:
        for p0, p1 in filtered_locs:
            cv2.rectangle(gray_main, (p0.x, p0.y), (p1.x, p1.y), (0, 255, 0), 0)
            cv2.imwrite(f"{BYPRODUCT_DIR}/matched.png", gray_main)

        cv2.imwrite(f"{BYPRODUCT_DIR}/sub.png", sub_image)
    if len(filtered_locs):
        return filtered_locs
    return None


if __name__ == "__main__":
    from parse_video.video import Video

    cap = Video("vids/a.mp4")

    cap.setFrameIndex(14600)
    frame = cap.getNextFrame(1)
    sub = cv2.imread("game/component_images/reroll_augment.png")

    from tqdm import tqdm

    cv2.imwrite("a.png", frame)
    s = perf_counter()
    res = find_subimage(
        frame,
        sub,
        match_many=True,
        gray_scale=True,
        create_byproduct=True,
    )
    print(perf_counter() - s)
    # for r in res:
    #     print(r)
