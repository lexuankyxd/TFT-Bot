import os
import json
import numpy as np
from cv2 import imwrite
from time import time

EDGE_CASE_DIR = "parse_video/edge_cases"
EDGE_CASE_JSON_PATH = "parse_video/edge_cases/edge_cases.json"
EDGE_CASE_IMAGE_PATH = "parse_video/edge_cases/images"

if not os.path.exists(EDGE_CASE_JSON_PATH):
    f = open(EDGE_CASE_JSON_PATH, "rw")
    f.write("[]")
    f.close()

data = json.load(open(EDGE_CASE_JSON_PATH, "rw"))


def report_edge_case(incedent: str, image: np.ndarray):
    image_path = f"{EDGE_CASE_IMAGE_PATH}/{time()}.png"
    imwrite(image_path, image)
    data.append({"incedent": incedent, "image_path": image_path})
