import os
import random
from ursina import Entity, Mesh, destroy
from ursina.texture import Texture
from PIL import Image
from world import AIR, CHUNK_SIZE, WORLD_HEIGHT, WOOD, LEAVES


class Renderer:
    def __init__(self, world):
        self.world = world
        self.chunk_entities = {}
        self.block_texture = self._get_block_texture()
        self.block_texture_uvs = {
            1: [(0, 0), (1 / 5, 0), (1 / 5, 1), (0, 1)],
            2: [(1 / 5, 0), (2 / 5, 0), (2 / 5, 1), (1 / 5, 1)],
            3: [(2 / 5, 0), (3 / 5, 0), (3 / 5, 1), (2 / 5, 1)],
            4: [(3 / 5, 0), (4 / 5, 0), (4 / 5, 1), (3 / 5, 1)],
            5: [(4 / 5, 0), (1, 0), (1, 1), (4 / 5, 1)],
        }
        self.face_brightness = {
            (0, 1, 0): 1.0,
            (0, -1, 0): 0.6,
            (1, 0, 0): 0.8,
            (-1, 0, 0): 0.8,
            (0, 0, 1): 0.7,
            (0, 0, -1): 0.7,
        }
        self.faces = [
            ((1, 0, 0), [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]),
            ((-1, 0, 0), [(0, 0, 1), (0, 1, 1), (0, 1, 0), (0, 0, 0)]),
            ((0, 1, 0), [(0, 1, 1), (1, 1, 1), (1, 1, 0), (0, 1, 0)]),
            ((0, -1, 0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]),
            ((0, 0, 1), [(1, 0, 1), (1, 1, 1), (0, 1, 1), (0, 0, 1)]),
            ((0, 0, -1), [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)]),
        ]

    def _get_block_texture(self):
        path = os.path.join(os.path.dirname(__file__), "blocks.png")
        if not os.path.exists(path):
            regenerate = True
        else:
            try:
                existing = Image.open(path)
                regenerate = existing.width < 16 * 5
            except Exception:
                regenerate = True

        if regenerate:
            size = 16
            img = Image.new("RGBA", (size * 5, size))
            px = img.load()
            for tile in range(5):
                for y in range(size):
                    for x in range(size):
                        n = random.randint(-20, 20)
                        if tile == 0:
                            px[x + tile * size, y] = (
                                30 + n // 3,
                                100 + n,
                                30 + n // 4,
                                255,
                            )
                        elif tile == 1:
                            px[x + tile * size, y] = (
                                120 + n,
                                75 + n // 2,
                                35 + n // 3,
                                255,
                            )
                        elif tile == 2:
                            gray = 120 + n // 2
                            px[x + tile * size, y] = (gray, gray, gray, 255)
                        elif tile == 3:
                            px[x + tile * size, y] = (
                                110 + n // 2,
                                65 + n // 2,
                                20 + n // 3,
                                255,
                            )
                        else:
                            px[x + tile * size, y] = (
                                50 + n // 2,
                                120 + n,
                                40 + n // 4,
                                255,
                            )
            img.save(path)
        return Texture(path)

    def is_solid(self, x, y, z):
        return self.world.is_solid(x, y, z)

    def rebuild_chunk(self, cx, cz):
        old = self.chunk_entities.pop((cx, cz), None)
        if old:
            destroy(old)
        if (cx, cz) not in self.world.chunks:
            self.world.generate_chunk(cx, cz)
        chunk = self.world.chunks[(cx, cz)]
        verts = []
        tris = []
        uvs = []
        normals = []
        for ((x, y, z), block) in chunk.items():
            for normal, quad in self.faces:
                nx = x + normal[0]
                ny = y + normal[1]
                nz = z + normal[2]
                if ny < 0 or ny >= WORLD_HEIGHT:
                    neighbor = AIR
                elif 0 <= nx < CHUNK_SIZE and 0 <= nz < CHUNK_SIZE:
                    neighbor = chunk.get((nx, ny, nz), AIR)
                else:
                    ncx = cx + (1 if nx == CHUNK_SIZE else -1 if nx == -1 else 0)
                    ncz = cz + (1 if nz == CHUNK_SIZE else -1 if nz == -1 else 0)
                    neighbor_chunk = self.world.chunks.get((ncx, ncz))
                    neighbor = (
                        neighbor_chunk.get((nx % CHUNK_SIZE, ny, nz % CHUNK_SIZE), AIR)
                        if neighbor_chunk
                        else AIR
                    )
                if neighbor == AIR:
                    start = len(verts)
                    face_uvs = self.block_texture_uvs[block]
                    for (vx, vy, vz), uv in zip(quad, face_uvs):
                        verts.append((x + vx, y + vy, z + vz))
                        uvs.append((uv[0], 1 - uv[1]))
                        normals.append(normal)
                    tris += [start, start + 2, start + 1, start, start + 3, start + 2]
        if verts:
            colors = []
            for normal in normals:
                brightness = self.face_brightness.get(normal, 0.8)
                colors.append((brightness, brightness, brightness, 1))

            mesh = Mesh(vertices=verts, triangles=tris, uvs=uvs, normals=normals, colors=colors, mode="triangle")
            parent = Entity(position=(cx * CHUNK_SIZE, 0, cz * CHUNK_SIZE))
            Entity(
                parent=parent,
                model=mesh,
                texture=self.block_texture,
            )

            coll_verts = []
            coll_tris = []
            coll_normals = []
            for ((x, y, z), block) in chunk.items():
                if block == LEAVES:
                    continue
                for normal, quad in self.faces:
                    nx = x + normal[0]
                    ny = y + normal[1]
                    nz = z + normal[2]
                    if ny < 0 or ny >= WORLD_HEIGHT:
                        neighbor = AIR
                    elif 0 <= nx < CHUNK_SIZE and 0 <= nz < CHUNK_SIZE:
                        neighbor = chunk.get((nx, ny, nz), AIR)
                    else:
                        ncx = cx + (1 if nx == CHUNK_SIZE else -1 if nx == -1 else 0)
                        ncz = cz + (1 if nz == CHUNK_SIZE else -1 if nz == -1 else 0)
                        neighbor_chunk = self.world.chunks.get((ncx, ncz))
                        neighbor = (
                            neighbor_chunk.get((nx % CHUNK_SIZE, ny, nz % CHUNK_SIZE), AIR)
                            if neighbor_chunk
                            else AIR
                        )
                    if neighbor == AIR:
                        start = len(coll_verts)
                        for (vx, vy, vz) in quad:
                            coll_verts.append((x + vx, y + vy, z + vz))
                            coll_normals.append(normal)
                        coll_tris += [start, start + 2, start + 1, start, start + 3, start + 2]
            if coll_verts:
                coll_mesh = Mesh(vertices=coll_verts, triangles=coll_tris, normals=coll_normals, mode="triangle")
                Entity(
                    parent=parent,
                    model=coll_mesh,
                    collider="mesh",
                    visible=False,
                )

            self.chunk_entities[(cx, cz)] = parent

    def unload_chunk(self, cx, cz):
        ent = self.chunk_entities.pop((cx, cz), None)
        if ent:
            destroy(ent)

    def process_load_queue(self, max_per_frame=2):
        self.world.process_load_queue(self, max_per_frame)
