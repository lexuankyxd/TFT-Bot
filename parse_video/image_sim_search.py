"""
We can do this in 2 ways, first is doing comparision over our image database and select the one with the highest
similarity score.
The second way is to generate a vector embedding representing the image, idealy method of generation is robust
agains distorion in pixel noise, resolution changes and ration.
Depending on how long the first approach takes we will use the 2nd approach. But these type of queries wouldn't
be called too often. So as long as the search takes <= 200ms we should be good.
"""

import numpy as np
import cv2

"""
    Cross checking main_image with every image in image bank, not optimized since image bank is being rescaled
    and gray scaled every time, for each item slot that's 20 time doing the same thing. 
"""

BYPRODUCT_DIR = "byproduct"


def item_bar_sim_search_opencv(
    main_image: np.ndarray,
    image_bank: dict[str, np.ndarray],
    consumable: bool,
    p0: list[int] | None = None,
    p1: list[int] | None = None,
    threshhold: int = 0.8,
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
        result = cv2.matchTemplate(gray, gray_val, cv2.TM_CCOEFF_NORMED)

        # Get top-left corner of first/best match
        _, res_val, _, res_loc = cv2.minMaxLoc(result)
        if res_val > max_val:
            max_val = res_val
            max_loc = res_loc
            max_key = key

    if create_byproduct:
        cv2.imwrite(
            f"{BYPRODUCT_DIR}/image_sim_search_sub_{p0}.png", image_bank[max_key]
        )
    print(max_val)
    return max_key
