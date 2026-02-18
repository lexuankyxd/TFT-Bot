import numpy as np
import cv2
import os


class GameState:
    def __init__(self):
        self.players_name: list[str] = []
        self.main_player: str = ""
        self.encounter: str = ""

    def set_players_name(self, names: list[str]):
        self.players_name = names

    def set_main_player_name(self, name: str):
        self.main_player = name

    def set_encounter(self, encounter: str):
        self.encounter = encounter

    def get_items_image_dict(self) -> dict[str, np.ndarray]:
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
