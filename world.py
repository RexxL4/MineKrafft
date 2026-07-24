from collections import deque
from opensimplex import OpenSimplex
import random
import json
import os
import pickle
try:
    import msgpack
except Exception:
    msgpack = None

AIR = 0
GRASS = 1
DIRT = 2
STONE = 3
WOOD = 4
LEAVES = 5
CHUNK_SIZE = 16
WORLD_HEIGHT = 48
RENDER_DISTANCE = 3


class World:
    def __init__(self, seed=12345, save_file="world_save.bin"):
        self.seed = seed
        self.save_file = os.path.join(os.path.dirname(__file__), save_file)
        self.noise = OpenSimplex(seed)
        self.chunks = {}
        self.modified_blocks = {}
        self.player_position = None
        self.load_queue = deque()
        self.loading_chunks = set()
        self.load_world()

    def terrain_height(self, x, z):
        return int(12 + self.noise.noise2(x * 0.06, z * 0.06) * 8)

    def generate_chunk(self, cx, cz):
        chunk_rng = random.Random(f"{self.seed}:{cx}:{cz}")
        blocks = {}
        for x in range(CHUNK_SIZE):
            for z in range(CHUNK_SIZE):
                wx = cx * CHUNK_SIZE + x
                wz = cz * CHUNK_SIZE + z
                h = self.terrain_height(wx, wz)
                for y in range(max(0, h)):
                    if y == h - 1:
                        block = GRASS
                    elif y > h - 5:
                        block = DIRT
                    else:
                        block = STONE
                    blocks[x, y, z] = block

        tree_centers = set()
        for x in range(2, CHUNK_SIZE - 2, 3):
            for z in range(2, CHUNK_SIZE - 2, 3):
                wx = cx * CHUNK_SIZE + x
                wz = cz * CHUNK_SIZE + z
                h = self.terrain_height(wx, wz)
                if (
                    blocks.get((x, h - 1, z)) == GRASS
                    and h + 6 < WORLD_HEIGHT
                    and chunk_rng.random() < 0.03
                ):
                    too_close = any(
                        abs(x - tx) <= 5 and abs(z - tz) <= 5
                        for tx, tz in tree_centers
                    )
                    if too_close:
                        continue

                    tree_centers.add((x, z))
                    for dy in range(0, 4):
                        blocks[x, h + dy, z] = WOOD

                    for dx in range(-2, 3):
                        for dz in range(-2, 3):
                            if abs(dx) + abs(dz) < 4:
                                blocks[x + dx, h + 4, z + dz] = LEAVES

                    for dx in range(-1, 2):
                        for dz in range(-1, 2):
                            blocks[x + dx, h + 5, z + dz] = LEAVES

        if (cx, cz) in self.modified_blocks:
            for (lx, y, lz), block_type in self.modified_blocks[(cx, cz)].items():
                if 0 <= lx < CHUNK_SIZE and 0 <= y < WORLD_HEIGHT and 0 <= lz < CHUNK_SIZE:
                    if block_type == AIR:
                        blocks.pop((lx, y, lz), None)
                    else:
                        blocks[(lx, y, lz)] = block_type

        self.chunks[cx, cz] = blocks

    def get_block(self, x, y, z):
        cx = x // CHUNK_SIZE
        cz = z // CHUNK_SIZE
        if (cx, cz) not in self.chunks:
            return AIR
        return self.chunks[cx, cz].get((x % CHUNK_SIZE, y, z % CHUNK_SIZE), AIR)

    def is_solid(self, x, y, z):
        return self.get_block(x, y, z) not in (AIR, LEAVES)

    def set_block(self, x, y, z, block_type):
        cx = x // CHUNK_SIZE
        cz = z // CHUNK_SIZE
        if (cx, cz) not in self.chunks:
            self.generate_chunk(cx, cz)
        if not (0 <= y < WORLD_HEIGHT):
            return

        lx = x % CHUNK_SIZE
        lz = z % CHUNK_SIZE
        old_block = self.chunks[cx, cz].get((lx, y, lz), AIR)
        if old_block == block_type:
            return

        self.modified_blocks.setdefault((cx, cz), {})[(lx, y, lz)] = block_type
        if block_type == AIR:
            self.chunks[cx, cz].pop((lx, y, lz), None)
        else:
            self.chunks[cx, cz][(lx, y, lz)] = block_type
        self.save_world()

    def schedule_chunk(self, cx, cz):
        if (cx, cz) in self.loading_chunks or (cx, cz) in self.chunks:
            return
        self.loading_chunks.add((cx, cz))
        self.load_queue.append((cx, cz))

    def load_world(self):
        # If no binary save, but a legacy JSON save exists, load from JSON and auto-migrate
        json_path = os.path.join(os.path.dirname(self.save_file), "world_save.json")
        data = None

        # Prefer msgpack if available, then fall back to pickle (legacy), then JSON
        if os.path.exists(self.save_file):
            # try msgpack
            if msgpack is not None:
                try:
                    with open(self.save_file, "rb") as f:
                        data = msgpack.unpackb(f.read(), raw=False)
                except Exception:
                    data = None
            else:
                data = None

            # try pickle if msgpack failed
            if data is None:
                try:
                    with open(self.save_file, "rb") as f:
                        data = pickle.load(f)
                except Exception:
                    data = None

        if data is None and os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as file:
                    data = json.load(file)
            except Exception:
                data = None

        if not data:
            self.modified_blocks = {}
            return

        # Seed
        if "seed" in data:
            self.seed = data["seed"]
            self.noise = OpenSimplex(self.seed)

        # Restore saved player position, if present
        self.player_position = None
        player_pos = data.get("player_position")
        if isinstance(player_pos, (list, tuple)) and len(player_pos) == 3:
            try:
                self.player_position = (
                    float(player_pos[0]),
                    float(player_pos[1]),
                    float(player_pos[2]),
                )
            except Exception:
                self.player_position = None

        # Normalize modified_blocks into internal dict[(cx,cz)] -> {(lx,y,lz): block_type}
        self.modified_blocks = {}
        for chunk_key, blocks_val in data.get("modified_blocks", {}).items():
            # normalize chunk coords
            if isinstance(chunk_key, str):
                try:
                    cx, cz = map(int, chunk_key.split(","))
                except Exception:
                    continue
            elif isinstance(chunk_key, (list, tuple)):
                try:
                    cx, cz = int(chunk_key[0]), int(chunk_key[1])
                except Exception:
                    continue
            else:
                continue

            inner = {}

            # New binary format: list of [lx, y, lz, block_type]
            if isinstance(blocks_val, list):
                for item in blocks_val:
                    if not isinstance(item, (list, tuple)) or len(item) < 4:
                        continue
                    lx, y, lz, block_type = int(item[0]), int(item[1]), int(item[2]), int(item[3])
                    inner[(lx, y, lz)] = block_type

            # Legacy dict form: {"lx,y,lz": block_type} or {(lx, y, lz): block_type}
            elif isinstance(blocks_val, dict):
                for bkey, bval in blocks_val.items():
                    if isinstance(bkey, str):
                        try:
                            lx, y, lz = map(int, bkey.split(","))
                        except Exception:
                            continue
                    elif isinstance(bkey, (list, tuple)):
                        try:
                            lx, y, lz = int(bkey[0]), int(bkey[1]), int(bkey[2])
                        except Exception:
                            continue
                    else:
                        continue
                    inner[(lx, y, lz)] = int(bval)

            if inner:
                self.modified_blocks[(cx, cz)] = inner

        # If we loaded from legacy JSON or pickle, auto-save to msgpack (if available) or pickle
        if os.path.exists(json_path) and (not os.path.exists(self.save_file) or (data and isinstance(data.get("modified_blocks"), dict) and any(isinstance(k, str) for k in data.get("modified_blocks", {})))):
            try:
                self.save_world()
            except Exception:
                pass

    def save_world(self):
        # Create a compact binary representation: modified_blocks -> {(cx,cz): [[lx,y,lz,block_type], ...]}
        data = {
            "seed": self.seed,
            "player_position": list(self.player_position) if self.player_position is not None else None,
            "modified_blocks": {},
        }
        for (cx, cz), blocks in self.modified_blocks.items():
            compact = []
            for (lx, y, lz), block_type in blocks.items():
                compact.append([int(lx), int(y), int(lz), int(block_type)])
            if compact:
                # store chunk keys as strings to be msgpack-friendly and stable
                data["modified_blocks"][f"{int(cx)},{int(cz)}"] = compact

        try:
            # write atomically using msgpack if available
            tmp = self.save_file + ".tmp"
            if msgpack is not None:
                with open(tmp, "wb") as f:
                    f.write(msgpack.packb(data, use_bin_type=True))
            else:
                with open(tmp, "wb") as f:
                    pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp, self.save_file)
        except Exception:
            try:
                if msgpack is not None:
                    with open(self.save_file, "wb") as f:
                        f.write(msgpack.packb(data, use_bin_type=True))
                else:
                    with open(self.save_file, "wb") as f:
                        pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            except Exception:
                pass

    def process_load_queue(self, renderer, max_per_frame=2):
        for _ in range(max_per_frame):
            if not self.load_queue:
                break
            cx, cz = self.load_queue.popleft()
            self.generate_chunk(cx, cz)
            renderer.rebuild_chunk(cx, cz)
            self.loading_chunks.discard((cx, cz))

    def unload_chunk(self, cx, cz):
        self.chunks.pop((cx, cz), None)

    def desired_chunk_coords(self, pcx, pcz):
        return {
            (x, z)
            for x in range(pcx - RENDER_DISTANCE, pcx + RENDER_DISTANCE + 1)
            for z in range(pcz - RENDER_DISTANCE, pcz + RENDER_DISTANCE + 1)
        }
