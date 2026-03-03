import numpy as np
import cv2
import os


def _recursive_glob(dir: str) -> list[str]:
    res = []
    files = os.listdir(dir)
    for file in files:
        if os.path.isdir(f"{dir}/{file}"):
            tmp = _recursive_glob(f"{dir}/{file}")
            res += tmp
        else:
            res.append(f"{dir}/{file}")
    return res


def get_items_image_dict() -> dict[str, np.ndarray]:
    items: dict[str, np.ndarray] = {}

    equipables = os.listdir("game/component_images/items")
    for equipable in equipables:
        items[f"{equipable.split('.')[0]}"] = cv2.imread(
            f"game/component_images/items/{equipable}"
        )

    consumables = os.listdir("game/component_images/consumables")
    for consumable in consumables:
        items[f"{consumable.split('.')[0]}"] = cv2.imread(
            f"game/component_images/consumables/{consumable}"
        )
    return items


class GameState:
    def __init__(self):
        self.players_name: list[str] = []
        self.main_player: str = ""
        self.encounter: str = ""
        self.image_bank: dict[str, np.ndarray] = {}
        tmp = _recursive_glob("game/component_images")
        for f in tmp:
            self.image_bank[f.split("/")[-1]] = cv2.imread(f)
        self.item_image_bank: dict[str, np.ndarray] = get_items_image_dict()

    def set_players_name(self, names: list[str]):
        self.players_name = names

    def set_main_player_name(self, name: str):
        self.main_player = name

    def set_encounter(self, encounter: str):
        self.encounter = encounter
