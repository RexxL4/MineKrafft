import os
from ursina import Text, Entity, color, Texture, camera
from PIL import Image
from world import GRASS, DIRT, STONE, WOOD, LEAVES

block_order = [GRASS, DIRT, STONE, WOOD, LEAVES]
block_names = {
    GRASS: "Grass",
    DIRT: "Dirt",
    STONE: "Stone",
    WOOD: "Wood",
    LEAVES: "Leaves",
}


class Inventory:
    def __init__(self):
        self.max_inventory = 99
        self.items = {GRASS: 10, DIRT: 10, STONE: 10, WOOD: 0, LEAVES: 0}
        self.selected = GRASS
        self.block_icons = self._load_block_icons()
        self.hotbar_slots = []
        self.hotbar_counts = []
        self._create_hotbar_ui()
        self.update_ui()

    def _load_block_icons(self):
        path = os.path.join(os.path.dirname(__file__), "blocks.png")
        atlas = Image.open(path).convert("RGBA")
        size = 16
        icons = {}
        for index, block_type in enumerate(block_order):
            icon_image = atlas.crop((index * size, 0, (index + 1) * size, size))
            icons[block_type] = Texture(icon_image)
        return icons

    def _create_hotbar_ui(self):
        spacing = 0.13
        start_x = -spacing
        for index, block_type in enumerate(block_order):
            x = start_x + index * spacing
            slot = Entity(
                parent=camera.ui,
                model="quad",
                color=color.rgb(30, 30, 30),
                scale=(0.12, 0.12),
                position=(x, -0.42, 0),
                always_on_top=True,
                double_sided=True,
            )
            Entity(
                parent=slot,
                model="quad",
                texture=self.block_icons[block_type],
                scale=0.75,
                color=color.white,
                always_on_top=True,
                double_sided=True,
            )
            count_text = Text(
                parent=camera.ui,
                text="0",
                position=(x + 0.06, -0.47),
                origin=(0.5, 0.5),
                scale=0.7,
                color=color.white,
                always_on_top=True,
            )
            self.hotbar_slots.append((slot, block_type))
            self.hotbar_counts.append(count_text)

    def select(self, block_type):
        self.selected = block_type
        self.update_ui()

    def add(self, block_type, amount=1):
        self.items[block_type] = min(
            self.max_inventory,
            self.items.get(block_type, 0) + amount,
        )
        self.update_ui()

    def remove(self, block_type, amount=1):
        if self.items.get(block_type, 0) < amount:
            return False
        self.items[block_type] -= amount
        self.update_ui()
        return True

    def can_place(self):
        return self.items.get(self.selected, 0) > 0

    def update_ui(self):
        for index, (slot, block_type) in enumerate(self.hotbar_slots):
            slot.color = color.rgb(70, 70, 70) if block_type == self.selected else color.rgb(25, 25, 25)
            self.hotbar_counts[index].text = str(self.items.get(block_type, 0))
            self.hotbar_counts[index].color = color.white if block_type == self.selected else color.light_gray
