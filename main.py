from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
from world import World, AIR, CHUNK_SIZE
from renderer import Renderer
from inventory import Inventory
import math

app = Ursina()
window.title = "Voxel Engine"
window.color = color.rgb(120, 180, 255)
AmbientLight(color=color.rgb(100, 110, 130))
DirectionalLight().look_at(Vec3(1, -1, -1))

# game state (populated when starting)
world = None
renderer = None
inventory = None
player = None
last_player_chunk = None

# menu UI handles
menu_title = None
start_button = None
quit_button = None


def get_player_chunk():
    if not player:
        return 0, 0
    cx = int(math.floor(player.x)) // CHUNK_SIZE
    cz = int(math.floor(player.z)) // CHUNK_SIZE
    return cx, cz


def voxel_raycast():
    origin = camera.world_position
    direction = camera.forward
    last = None
    for i in range(1, 120):
        pos = origin + direction * (i * 0.1)
        x = int(math.floor(pos.x))
        y = int(math.floor(pos.y))
        z = int(math.floor(pos.z))
        if world and world.is_solid(x, y, z):
            return x, y, z, last
        last = x, y, z
    return None


def rebuild_at(x, z):
    if not renderer:
        return
    cx = x // CHUNK_SIZE
    cz = z // CHUNK_SIZE
    renderer.rebuild_chunk(cx, cz)


def update():
    global last_player_chunk
    if not world or not renderer:
        return
    pcx, pcz = get_player_chunk()
    if last_player_chunk != (pcx, pcz):
        desired = world.desired_chunk_coords(pcx, pcz)
        for coord in desired:
            if coord not in world.chunks and coord not in world.loading_chunks:
                world.schedule_chunk(coord[0], coord[1])
        for coord in list(world.chunks.keys()):
            if coord not in desired:
                renderer.unload_chunk(coord[0], coord[1])
                world.unload_chunk(coord[0], coord[1])
        last_player_chunk = pcx, pcz
    renderer.process_load_queue()


def input(key):
    # when menu is active, start with Enter or Space
    if not world:
        if key == 'enter' or key == 'space':
            start_game()
        return

    if key == "1":
        inventory.select(1)
    if key == "2":
        inventory.select(2)
    if key == "3":
        inventory.select(3)
    if key == "4":
        inventory.select(4)
    if key == "5":
        inventory.select(5)

    if key == "left mouse down":
        hit = voxel_raycast()
        if hit:
            x, y, z, _ = hit
            old = world.get_block(x, y, z)
            if old != AIR:
                inventory.add(old)
                world.set_block(x, y, z, AIR)
                rebuild_at(x, z)

    if key == "right mouse down":
        hit = voxel_raycast()
        if hit:
            x, y, z, last = hit
            if last and inventory.can_place():
                px, py, pz = last
                if (
                    abs(px - player.x) > 1
                    or abs(py - player.y) > 2
                    or abs(pz - player.z) > 1
                ):
                    world.set_block(px, py, pz, inventory.selected)
                    rebuild_at(px, pz)
                    inventory.remove(inventory.selected)


def start_game(seed=None):
    global world, renderer, inventory, player, last_player_chunk
    # remove menu UI
    try:
        destroy(menu_title)
    except Exception:
        pass
    try:
        destroy(start_button)
    except Exception:
        pass
    try:
        destroy(quit_button)
    except Exception:
        pass

    world = World(seed=seed if seed is not None else 12345)
    renderer = Renderer(world)
    inventory = Inventory()
    player = FirstPersonController(y=30, speed=6, jump_height=2, gravity=1)
    last_player_chunk = None

    for coord in world.desired_chunk_coords(0, 0):
        world.schedule_chunk(coord[0], coord[1])

    Sky()


def create_menu():
    global menu_title, start_button, quit_button
    menu_title = Text('Voxel Engine', origin=(0, 0), scale=2, color=color.black, parent=camera.ui, position=(0, 0.25))
    start_button = Button('Start', parent=camera.ui, position=(0, 0), scale=0.12)
    start_button.on_click = lambda: start_game()
    quit_button = Button('Quit', parent=camera.ui, position=(0, -0.15), scale=0.12)
    quit_button.on_click = application.quit


create_menu()

app.run()
