import json
from time import perf_counter_ns

import cv2
import numpy as np
import tqdm
import pytesseract
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from video import Video
from game.game_state import GameState

BYPRODUCT_DIR = "byproduct"


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


def parse_boxed_text(
    main_image: np.ndarray,
    p0: list[int],
    p1: list[int],
    create_byproduct: bool = False,
) -> str:
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
    gray = gray[:, first:last]

    if create_byproduct:
        cv2.imwrite(f"{BYPRODUCT_DIR}/cropped_text_box.jpg", gray)

    return pytesseract.image_to_string(gray, config="--psm 6")


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

    return pytesseract.image_to_string(gray, config="--psm 6")


def _test_loop():
    coords = json.load(open("parse_video/coords_1080_desktop.json"))

    # Load video
    step = 60
    cap = Video("vids/a.mp4")
    sub_image = cv2.imread("parse_video/component_images/encounter_icon.png")
    assert sub_image is not None, "Sub image can't be None"
    matches = []
    is_game = False
    start, end = 0, 0
    bar = tqdm.tqdm(total=cap.total_frames / step, desc="Parsing video")
    while True:
        t0 = perf_counter_ns()
        main_image = cap.getNextFrame(step)
        if main_image is None:
            break
        t1 = perf_counter_ns() - t0
        t2 = perf_counter_ns()
        contains = match_image(
            main_image,
            sub_image,
            coords["stage_bar_encounter_icon"][0],
            coords["stage_bar_encounter_icon"][1],
            create_byproduct=False,
        )
        t2 = perf_counter_ns() - t2
        if contains:
            text = parse_text(
                main_image,
                coords["encounter_string"][0],
                coords["encounter_string"][1],
                create_byproduct=True,
            )
            print(text)
            if is_game:
                end = cap.current_frame
            else:
                start = cap.current_frame
                is_game = True
        else:
            if is_game:
                is_game = False
                matches.append((start, end))
                print(matches[-1])
        t0 = perf_counter_ns() - t0
        bar.set_description_str(
            f"Parsing video (current frame: {cap.current_frame}/{
                cap.total_frames
            }, decode + forward/total%: {t1 / t0 * 100:.2f}%, ocr/total%: {
                t2 / t0 * 100:.2f}%)"
        )
        bar.update(1)
    if is_game:
        matches.append((start, end))
    bar.close()


"""
    Cross checking main_image with every image in image bank, not optimized since image bank is being rescaled
    and gray scaled every time, for each item slot that's 20 time doing the same thing. 
"""


def item_bar_sim_search_opencv(
    main_image: np.ndarray,
    image_bank: dict[str, np.ndarray],
    p0: list[int] | None = None,
    p1: list[int] | None = None,
    threshhold: int = 0.7,
    create_byproduct: bool = False,
) -> str:
    assert len(image_bank.keys()) > 0, "Image bank must contain atleast 1 image"
    if p0 is None or p1 is None:
        assert p0 is None and p1 is None, (
            "You must either provide both coordinate or none, can't provide just 1"
        )
    else:
        assert len(p0) == 2, "p0 must be a list of 2 integer"
        assert len(p1) == 2, "p1 must be a list of 2 integer"
        main_image = main_image[p0[1] : p1[1], p0[0] : p1[0]]
        w, h = p1[0] - p0[0], p1[1] - p0[1]
        for key in image_bank.keys():
            image_bank[key] = cv2.resize(image_bank[key], (w, h))
    gray = cv2.cvtColor(main_image, cv2.COLOR_BGR2GRAY)
    if (gray == 0).sum() > 0.7 * len(gray) * len(gray[0]):
        return "empty"

    max_val, max_loc, max_key = -1, None, None
    if create_byproduct:
        cv2.imwrite(f"{BYPRODUCT_DIR}/image_sim_search_{p0}.png", main_image)
    for key, val in image_bank.items():
        gray_val = cv2.cvtColor(val, cv2.COLOR_BGR2GRAY)
        if "stackable" in key:
            val = val[(int)(len(val) * 0.35) :, :]
        result = cv2.matchTemplate(main_image, val, cv2.TM_CCOEFF_NORMED)
        # Get top-left corner of first/best match
        _, res_val, _, res_loc = cv2.minMaxLoc(result)
        if res_val >= threshhold and res_val > max_val:
            max_val = res_val
            max_loc = res_loc
            max_key = key

    if create_byproduct:
        cv2.imwrite(
            f"{BYPRODUCT_DIR}/image_sim_search_sub_{p0}.png", image_bank[max_key]
        )
    if "stackable" in max_key:
        stack = parse_text(
            main_image,
            (0, 0),
            (len(main_image[0]) - 1, len(main_image) - 1),
            create_byproduct=True,
        )
        print(stack, len(stack))
    print(max_val)
    return max_key


if __name__ == "__main__":
    coords = json.load(open("parse_video/coords_1080_desktop.json"))
    game = GameState()
    # Load video
    step = 60
    cap = Video("vids/a.mp4")

    # cap.setFrameIndex(312022)
    cap.setFrameIndex(13000)
    frame = cap.getNextFrame(1)
    # text = parse_text(
    #     frame,
    #     coords["encounter_string"][0],
    #     coords["encounter_string"][1],
    #     create_byproduct=True,
    # )
    items = game.get_items_image_dict()
    for p0, p1 in coords["components"]:
        text = item_bar_sim_search_opencv(
            frame, items, p0=p0, p1=p1, create_byproduct=True
        )
        print(text)
