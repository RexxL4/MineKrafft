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
            color_templates = [
                (30, 100, 30),
                (120, 75, 35),
                (120, 120, 120),
                (110, 65, 20),
                (50, 120, 40),
            ]
            for tile, base_color in enumerate(color_templates):
                for y in range(size):
                    for x in range(size):
                        n = random.randint(-20, 20)
                        if tile == 2:
                            gray = base_color[0] + n // 2
                            color = (gray, gray, gray, 255)
                        else:
                            color = (
                                base_color[0] + (n // 3 if tile in (0, 1, 3) else n // 2),
                                base_color[1] + (n if tile in (0, 1, 4) else n // 2),
                                base_color[2] + (n // 4 if tile in (0, 4) else n // 3),
                                255,
                            )
                        px[x + tile * size, y] = color
            img.save(path)
        return Texture(path)

    def _get_neighbor(self, cx, cz, x, y, z, chunk):
        if y < 0 or y >= WORLD_HEIGHT:
            return AIR
        if 0 <= x < CHUNK_SIZE and 0 <= z < CHUNK_SIZE:
            return chunk.get((x, y, z), AIR)

        nx = cx + (1 if x == CHUNK_SIZE else -1 if x == -1 else 0)
        nz = cz + (1 if z == CHUNK_SIZE else -1 if z == -1 else 0)
        neighbor_chunk = self.world.chunks.get((nx, nz))
        if not neighbor_chunk:
            return AIR
        return neighbor_chunk.get((x % CHUNK_SIZE, y, z % CHUNK_SIZE), AIR)

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
        colors = []
        coll_verts = []
        coll_tris = []
        coll_normals = []

        for (x, y, z), block in chunk.items():
            face_uvs = self.block_texture_uvs[block]
            is_leaf = block == LEAVES
            for normal, quad in self.faces:
                neighbor = self._get_neighbor(
                    cx,
                    cz,
                    x + normal[0],
                    y + normal[1],
                    z + normal[2],
                    chunk,
                )
                if neighbor != AIR:
                    continue

                brightness = self.face_brightness.get(normal, 0.8)
                start = len(verts)
                for (vx, vy, vz), uv in zip(quad, face_uvs):
                    verts.append((x + vx, y + vy, z + vz))
                    uvs.append((uv[0], 1 - uv[1]))
                    normals.append(normal)
                    colors.append((brightness, brightness, brightness, 1))
                tris += [start, start + 2, start + 1, start, start + 3, start + 2]

                if is_leaf:
                    continue
                cstart = len(coll_verts)
                for vx, vy, vz in quad:
                    coll_verts.append((x + vx, y + vy, z + vz))
                    coll_normals.append(normal)
                coll_tris += [cstart, cstart + 2, cstart + 1, cstart, cstart + 3, cstart + 2]

        if verts:
            mesh = Mesh(
                vertices=verts,
                triangles=tris,
                uvs=uvs,
                normals=normals,
                colors=colors,
                mode="triangle",
            )
            parent = Entity(position=(cx * CHUNK_SIZE, 0, cz * CHUNK_SIZE))
            Entity(
                parent=parent,
                model=mesh,
                texture=self.block_texture,
            )

            if coll_verts:
                coll_mesh = Mesh(
                    vertices=coll_verts,
                    triangles=coll_tris,
                    normals=coll_normals,
                    mode="triangle",
                )
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
