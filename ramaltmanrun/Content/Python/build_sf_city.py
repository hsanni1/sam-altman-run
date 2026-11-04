"""Builds the San Francisco street-corner level from the generated 2D art.

Run inside the Unreal Editor (Python + Paper2D plugins enabled):
    Tools > Execute Python Script... > ramaltmanrun/Content/Python/build_sf_city.py
or in the Output Log (Python mode):
    import build_sf_city; build_sf_city.build()

It imports Art/Source/City/**.png as textures, makes a Paper2D sprite per layer,
then creates /Game/Maps/L_SF_CaliforniaStreet with the three corners laid out
left to right (1 px = 1 unit), an orthographic camera and an invisible run floor.
Re-running it rebuilds everything in place.
"""

import os

import unreal

# The art lives at the repo root, one level above the ramaltmanrun project folder.
SRC_DIR = os.path.abspath(os.path.join(unreal.Paths.project_dir(), "..", "Art", "Source", "City"))
TEX_ROOT = "/Game/City/Textures"
SPRITE_ROOT = "/Game/City/Sprites"
LEVEL_PATH = "/Game/Maps/L_SF_CaliforniaStreet"
ACTOR_TAG = "SFCity"

SEGMENT_W = 3840          # width of one corner in px / units
SEGMENT_H = 1080
RUN_PLANE_Z = 150         # sidewalk running height (image y = 930)

CORNERS = ["NobHill_CaliforniaPowell", "Chinatown_CaliforniaGrant", "FiDi_CaliforniaKearny"]

# Layer -> depth (Y). Camera sits at +Y looking toward -Y, so larger Y draws in front.
# The runner character should later be spawned at Y = 50.
LAYER_DEPTH = {
    "Sky": -600.0,
    "BayBridge": -500.0,
    "Skyline": -400.0,
    "Buildings": -200.0,
    "Street": 0.0,
    "Props": 20.0,
}

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
eal = unreal.EditorAssetLibrary
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)


def import_texture(png_path, dest_dir):
    task = unreal.AssetImportTask()
    task.filename = png_path
    task.destination_path = dest_dir
    task.automated = True
    task.replace_existing = True
    task.save = False
    asset_tools.import_asset_tasks([task])
    tex = unreal.load_asset(f"{dest_dir}/{os.path.splitext(os.path.basename(png_path))[0]}")
    tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_EDITOR_ICON)
    tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_PIXELS2D)
    tex.set_editor_property("never_stream", True)
    eal.save_loaded_asset(tex)
    return tex


def make_sprite(tex, dest_dir):
    name = tex.get_name().replace("T_", "SPR_", 1)
    path = f"{dest_dir}/{name}"
    sprite = unreal.load_asset(path) if eal.does_asset_exist(path) else \
        asset_tools.create_asset(name, dest_dir, unreal.PaperSprite, unreal.PaperSpriteFactory())
    size = unreal.Vector2D(tex.blueprint_get_size_x(), tex.blueprint_get_size_y())
    sprite.set_editor_property("source_texture", tex)
    sprite.set_editor_property("source_uv", unreal.Vector2D(0, 0))
    sprite.set_editor_property("source_dimension", size)
    sprite.set_editor_property("pixels_per_unreal_unit", 1.0)
    sprite.set_editor_property("pivot_mode", unreal.SpritePivotMode.BOTTOM_LEFT)
    sprite.set_editor_property("sprite_collision_domain", unreal.SpriteCollisionMode.NONE)
    eal.save_loaded_asset(sprite)
    return sprite


def import_all():
    sprites = {}
    for folder in ["Shared"] + CORNERS:
        src = os.path.join(SRC_DIR, folder)
        for fname in sorted(os.listdir(src)):
            if not fname.endswith(".png"):
                continue
            tex = import_texture(os.path.join(src, fname), f"{TEX_ROOT}/{folder}")
            sprites[os.path.splitext(fname)[0]] = make_sprite(tex, f"{SPRITE_ROOT}/{folder}")
    return sprites


def open_level():
    if eal.does_asset_exist(LEVEL_PATH):
        levels.load_level(LEVEL_PATH)
        for a in actors.get_all_level_actors():
            if a.actor_has_tag(ACTOR_TAG):
                actors.destroy_actor(a)
    else:
        levels.new_level(LEVEL_PATH)


def tag(actor, label, folder):
    actor.tags = [ACTOR_TAG]
    actor.set_actor_label(label)
    actor.set_folder_path(f"SFCity/{folder}")
    return actor


def place_sprite(sprite, x, layer, label, folder, scale_x=1.0):
    actor = actors.spawn_actor_from_class(unreal.PaperSpriteActor, unreal.Vector(x, LAYER_DEPTH[layer], 0))
    actor.get_editor_property("render_component").set_sprite(sprite)
    actor.set_actor_scale3d(unreal.Vector(scale_x, 1.0, 1.0))
    return tag(actor, label, folder)


def build():
    sprites = import_all()
    open_level()
    total_w = SEGMENT_W * len(CORNERS)

    place_sprite(sprites["T_SF_Sky"], 0, "Sky", "Sky", "Background", scale_x=total_w / 1920.0)
    for i, corner in enumerate(CORNERS):
        x = i * SEGMENT_W
        place_sprite(sprites["T_SF_BayBridge"], x, "BayBridge", f"BayBridge_{i}", "Background")
        for layer in ("Skyline", "Buildings", "Street", "Props"):
            place_sprite(sprites[f"T_{corner}_{layer}"], x, layer, f"{corner}_{layer}", corner)

    # invisible run floor along the sidewalk (BasicShapes cube is 100 units)
    floor = actors.spawn_actor_from_class(unreal.StaticMeshActor,
                                          unreal.Vector(total_w / 2, 50, RUN_PLANE_Z - 50))
    mesh = floor.static_mesh_component
    mesh.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Cube"))
    floor.set_actor_scale3d(unreal.Vector(total_w / 100.0, 4.0, 1.0))
    floor.set_actor_hidden_in_game(True)
    tag(floor, "RunFloor", "Gameplay")

    start = actors.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(300, 50, RUN_PLANE_Z + 100))
    tag(start, "PlayerStart", "Gameplay")

    cam = actors.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(960, 2000, SEGMENT_H / 2),
                                        unreal.Rotator(roll=0, pitch=0, yaw=-90))
    comp = cam.camera_component
    comp.set_editor_property("projection_mode", unreal.CameraProjectionMode.ORTHOGRAPHIC)
    comp.set_editor_property("ortho_width", 1920.0)
    comp.set_editor_property("constrain_aspect_ratio", True)
    comp.set_editor_property("aspect_ratio", 16.0 / 9.0)
    cam.set_editor_property("auto_activate_for_player", unreal.AutoReceiveInput.PLAYER0)
    tag(cam, "SideCamera", "Gameplay")

    levels.save_current_level()
    unreal.log(f"SF city built: {len(CORNERS)} corners, {total_w} units wide -> {LEVEL_PATH}")


if __name__ == "__main__":
    build()
