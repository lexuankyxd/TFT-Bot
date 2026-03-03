import cv2
import hashlib
import pytesseract
import numpy as np
import os
import pickle
from dataclasses import dataclass

PICKLE_DIR = "pickle"
BYPRODUCT_DIR = "byproduct"
PICKLE_CACHE_NAME = "scaled_image_cache.pkl"
BYPRODUCT_DIR = "byproduct"


@dataclass(order=True)
class Coordinate:
    x: int
    y: int


def _add_margin(p: list[int], margin: int = -1) -> list[int]:
    assert len(p) == 2, "Only accept list of 2 number."
    if margin == -1:
        size = p[1] - p[0]
        margin = (int)(size * 0.2)
    return [max(p[0] - margin, 0), p[1] + margin]


def match_image(
    main_image: np.ndarray,
    sub_image: np.ndarray,
    p0: list[int],
    p1: list[int],
    create_byproduct: bool = False,
    threshold: float = 0.8,
) -> bool:
    assert len(p1) == 2 and len(p0) == 2, "Coordinates must be 2D points"
    assert p1[0] > p0[0] and p1[1] > p0[1], (
        "Invalid coordinates: p1 must be greater than p0"
    )
    # Load images (main_image: larger image, sub_image: template to find)

    w = p1[0] - p0[0]
    h = p1[1] - p0[1]

    a, b = _add_margin([p0[0], p1[0]]), _add_margin([p0[1], p1[1]])
    cropped_image = main_image[b[0] : b[1], a[0] : a[1]]  # Crop to expected area
    if create_byproduct:
        cv2.imwrite(f"{BYPRODUCT_DIR}/cropped_main_image.jpg", cropped_image)
    # Resize template to expected size
    sub_image = cv2.resize(sub_image, (w, h))
    # Convert to grayscale for matching

    gray_main = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2GRAY)
    gray_sub = cv2.cvtColor(sub_image, cv2.COLOR_BGR2GRAY)
    result = cv2.matchTemplate(gray_main, gray_sub, cv2.TM_CCOEFF_NORMED)

    # Get top-left corner of first/best match
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if create_byproduct:
        if max_val >= threshold:
            top_left = max_loc
            h, w = gray_sub.shape
            bottom_right = (top_left[0] + w, top_left[1] + h)
            top_left = [top_left[0] + a[0], top_left[1] + b[0]]
            bottom_right = [bottom_right[0] + a[0], bottom_right[1] + b[0]]
            cv2.rectangle(main_image, top_left, bottom_right, (0, 255, 0), 3)
        cv2.imwrite(f"{BYPRODUCT_DIR}/matched.jpg", main_image)

    if max_val >= threshold:
        return True
    else:
        return False


def match_image_return_location(
    main_image: np.ndarray,
    sub_image: np.ndarray,
    p0: list[int],
    p1: list[int],
    create_byproduct: bool = False,
    threshold: float = 0.8,
) -> list[int] | None:
    assert len(p1) == 2 and len(p0) == 2, "Coordinates must be 2D points"
    assert p1[0] > p0[0] and p1[1] > p0[1], (
        "Invalid coordinates: p1 must be greater than p0"
    )
    # Load images (main_image: larger image, sub_image: template to find)

    w = p1[0] - p0[0]
    h = p1[1] - p0[1]

    a, b = _add_margin([p0[0], p1[0]]), _add_margin([p0[1], p1[1]])
    cropped_image = main_image[b[0] : b[1], a[0] : a[1]]  # Crop to expected area
    if create_byproduct:
        print("bruh")
        cv2.imwrite(f"{BYPRODUCT_DIR}/cropped_main_image.jpg", cropped_image)
    # Resize template to expected size
    nw = len(sub_image[0])
    nh = len(sub_image)
    if nw > w:
        nh = (int)(nh * nw / w)
        nw = w
    elif nh > h:
        nw = (int)(nw * nh / h)
        nw = h
    # sub_image = cv2.resize(sub_image, (nw, nh))
    # Convert to grayscale for matching

    gray_main = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2GRAY)
    gray_sub = cv2.cvtColor(sub_image, cv2.COLOR_BGR2GRAY)
    if create_byproduct:
        cv2.imwrite(f"{BYPRODUCT_DIR}/sub.png", sub_image)
    result = cv2.matchTemplate(gray_main, gray_sub, cv2.TM_CCOEFF_NORMED)

    # Get top-left corner of first/best match
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if create_byproduct:
        top_left = max_loc
        h, w = gray_sub.shape
        bottom_right = (top_left[0] + w, top_left[1] + h)
        top_left = [top_left[0] + a[0], top_left[1] + b[0]]
        bottom_right = [bottom_right[0] + a[0], bottom_right[1] + b[0]]
        cv2.rectangle(main_image, top_left, bottom_right, (0, 255, 0), 3)
        cv2.imwrite(f"{BYPRODUCT_DIR}/matched.jpg", main_image)

    print(max_val)
    if max_val >= threshold:
        return max_loc
    else:
        return None


ratio_cache: dict[str, list[np.ndarray]] = {}
if os.path.exists(f"{PICKLE_DIR}/{PICKLE_CACHE_NAME}"):
    ratio_cache = pickle.load(open(f"{PICKLE_DIR}/{PICKLE_CACHE_NAME}", "rb"))


def find_subimage(
    main_image: np.ndarray,
    sub_image: np.ndarray,
    min_r: float | None = None,
    max_r: float | None = None,
    threshold: float = 0.7,
    explore: bool = False,
    match_many: bool = False,
    gray_scale: bool = False,
    create_byproduct: bool = False,
) -> list[list[Coordinate]] | None:
    hash_val = hashlib.sha256(
        (str(sub_image.tobytes()) + str(sub_image.shape)).encode("utf-8")
    ).hexdigest()
    main_image = main_image.copy()
    sub_image = sub_image.copy()
    gray_main = (
        cv2.cvtColor(main_image, cv2.COLOR_BGR2GRAY) if gray_scale else main_image
    )
    ratios = []
    scaled = []
    match_locs = []
    val_list = []
    if hash_val in ratio_cache:
        scaled.extend(ratio_cache[hash_val])

    if explore or len(scaled) == 0:
        if min_r is None:
            min_r = 0.3
        if max_r is None:
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
        if create_byproduct:
            cv2.imwrite(f"{BYPRODUCT_DIR}/sub.png", sub_image)
        result = cv2.matchTemplate(gray_main, gray_sub, cv2.TM_CCOEFF_NORMED)
        locs = list(zip(*np.where(result >= threshold)[::-1]))
        if not from_cache and len(locs) > 0:
            if len(match_locs):
                ratio_cache[hash_val].append(curr)
            else:
                ratio_cache[hash_val] = [curr]
            pickle.dump(ratio_cache, open(f"{PICKLE_DIR}/{PICKLE_CACHE_NAME}", "wb"))
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
    filtered_locs = [a for [a, b] in filtered_locs]
    if create_byproduct:
        for p0, p1 in filtered_locs:
            cv2.rectangle(main_image, (p0.x, p0.y), (p1.x, p1.y), (0, 255, 0), 0)
            cv2.imwrite(f"{BYPRODUCT_DIR}/matched.png", main_image)
    if len(filtered_locs):
        return filtered_locs
    return None


def parse_boxed_text(
    main_image: np.ndarray,
    p0: list[int],
    p1: list[int],
    create_byproduct: bool = False,
) -> str | None:
    """
    Designed to parse text within a box. The image need to be no bigger than the background box of the text
    for the cropping to work.
    """
    main_image = main_image[p0[1] : p1[1], p0[0] : p1[0]]
    gray = cv2.cvtColor(main_image, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    #   croping the box with the encounter string
    tmp = np.transpose(gray, [1, 0])
    first, last = -1, -1
    for idx, a in enumerate(tmp):
        if (a == 0).all():
            if first == -1:
                first = idx
            last = idx
    if first == -1 and last == -1:
        return None
    gray = gray[:, first:last]

    if create_byproduct:
        cv2.imwrite(f"{BYPRODUCT_DIR}/cropped_text_box.jpg", gray)

    return pytesseract.image_to_string(gray, config="--psm 6").strip()


def parse_text(
    main_image: np.ndarray,
    p0: list[int],
    p1: list[int],
    create_byproduct: bool = False,
) -> str:
    main_image = main_image[p0[1] : p1[1], p0[0] : p1[0]]
    gray = cv2.cvtColor(main_image, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    if create_byproduct:
        cv2.imwrite(f"{BYPRODUCT_DIR}/cropped_text_box.jpg", gray)

    return pytesseract.image_to_string(gray, config="--psm 6").strip()
