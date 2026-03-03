import json
from time import perf_counter_ns

import cv2
import numpy as np
import tqdm
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from video import Video
from game.game_state import GameState
from parse_video.parse_funcs import parse_boxed_text, parse_text, match_image

BYPRODUCT_DIR = "byproduct"

coords = json.load(open("parse_video/coords_1080_desktop.json"))


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
    threshhold: int = 0.7,
    create_byproduct: bool = False,
) -> list[str | None]:
    lp0 = [a[0] for a in coords["components"]]
    lp1 = [a[1] for a in coords["components"]]
    assert len(lp0) == len(lp1) and len(lp0) == 10, (
        "List of items coords must be of length 10, check the coords json file"
    )
    assert len(image_bank.keys()) > 0, "Image bank must contain atleast 1 image"
    result_keys = ["empty"] * 20

    for idx, p0, p1 in enumerate(zip(lp0, lp1)):
        curr = main_image[p0[1] : p1[1], p0[0] : p1[0]]
        w, h = p1[0] - p0[0], p1[1] - p0[1]
        for key in image_bank.keys():
            image_bank[key] = cv2.resize(image_bank[key], (w, h))
        gray = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)
        if (gray == 0).sum() > 0.7 * len(gray) * len(gray[0]):
            # print((gray == 0).sum() / (len(gray) * len(gray[0])))
            result_keys[idx] = "empty"
            return result_keys
        max_val, max_key = -1, None
        if create_byproduct:
            cv2.imwrite(f"{BYPRODUCT_DIR}/image_sim_search_{p0}.png", curr)
        for key, val in image_bank.items():
            # gray_val = cv2.cvtColor(val, cv2.COLOR_BGR2GRAY)
            if "stackable" in key:
                val = val[(int)(len(val) * 0.35) :, :]
                if create_byproduct:
                    cv2.imwrite(f"{BYPRODUCT_DIR}/val_sim_search{p0}.png", val)
            result = cv2.matchTemplate(curr, val, cv2.TM_CCOEFF_NORMED)
            # Get top-left corner of first/best match
            _, res_val, _, res_loc = cv2.minMaxLoc(result)
            if res_val >= threshhold and res_val > max_val:
                max_val = res_val
                # max_loc = res_loc
                max_key = key
        if max_val == -1:
            result_keys[idx] = None
            continue
        if create_byproduct:
            cv2.imwrite(
                f"{BYPRODUCT_DIR}/image_sim_search_sub_{p0}.png", image_bank[max_key]
            )
        if "stackable" in max_key:
            curr = curr[: (int)(len(curr) * 0.35), :]
            curr = 255 - curr
            stack = parse_boxed_text(
                curr,
                (0, 0),
                (len(curr[0]), len(curr) - 1),
                create_byproduct=create_byproduct,
            )
            if stack is None or len(stack) == 0:
                stack = 1
            else:
                try:
                    stack = int(stack)
                except Exception as e:
                    stack = f"parse error {e}"

            max_key = f"{max_key}_{stack}"
        result_keys[idx] = max_key
    return result_keys


def parse_encounter(
    main_image: np.ndarray,
    create_byproduct: bool = False,
) -> str | None:

    return None


if __name__ == "__main__":
    game = GameState()
    # Load video
    step = 60
    cap = Video("vids/a.mp4")

    cap.setFrameIndex(312022)
    # cap.setFrameIndex(13000)
    frame = cap.getNextFrame(1)
    # text = parse_text(
    #     frame,
    #     coords["encounter_string"][0],
    #     coords["encounter_string"][1],
    #     create_byproduct=True,
    # )
    items = game.get_items_image_dict()
    text = item_bar_sim_search_opencv(frame, items, create_byproduct=True)
    print(text)
