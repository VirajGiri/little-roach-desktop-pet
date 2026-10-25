"""Build and render a reference-guided, animated 3D cockroach in Blender.

Run with:
  blender --background --python tools/build_roach_3d.py

The render output is a high-resolution sprite atlas input for the desktop pet;
the .blend file retains the editable 3D model and eight-pose animation rig.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artwork"
ASSETS = ROOT / "assets"
TEXTURE = ART / "roach_abdomen_texture.png"
PRONOTUM_TEXTURE = ART / "roach_pronotum_texture.png"
BLEND = ART / "LittleRoach_3D.blend"
PREVIEW_FRAMES = 8
DIRECTIONS = 32
RENDER_SIZE = 384


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for data in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras,
                 bpy.data.lights, bpy.data.actions):
        for item in list(data):
            if item.users == 0:
                data.remove(item)


def material(name: str, color: tuple[float, float, float, float],
             roughness: float = 0.32, metallic: float = 0.12,
             coat: float = 0.25) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Roughness"].default_value = roughness
    principled.inputs["Metallic"].default_value = metallic
    for socket, value in (("Coat Weight", coat), ("Coat Roughness", 0.2),
                          ("IOR", 1.46), ("Specular IOR Level", 0.36)):
        if socket in principled.inputs:
            principled.inputs[socket].default_value = value
    return mat


def textured_shell_material() -> bpy.types.Material:
    mat = material("Shell - sampled from reference", (0.20, 0.065, 0.018, 1), 0.42, 0.025, 0.20)
    img = bpy.data.images.load(str(TEXTURE), check_existing=True)
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    uv = mat.node_tree.nodes.new("ShaderNodeTexCoord")
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    mat.node_tree.links.new(uv.outputs["UV"], tex.inputs["Vector"])
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    noise = mat.node_tree.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 175
    noise.inputs["Detail"].default_value = 2
    bump = mat.node_tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.10
    bump.inputs["Distance"].default_value = 0.012
    mat.node_tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    mat.node_tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def sampled_plate_material(name: str, image_path: Path) -> bpy.types.Material:
    mat = material(name, (0.22, 0.07, 0.02, 1), 0.40, 0.02, 0.20)
    img = bpy.data.images.load(str(image_path), check_existing=True)
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    uv = mat.node_tree.nodes.new("ShaderNodeTexCoord")
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    mat.node_tree.links.new(uv.outputs["UV"], tex.inputs["Vector"])
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    noise = mat.node_tree.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 150
    bump = mat.node_tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    bump.inputs["Distance"].default_value = 0.009
    mat.node_tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    mat.node_tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def add_sphere(name: str, loc: tuple[float, float, float], scale: tuple[float, float, float],
               mat: bpy.types.Material, root: bpy.types.Object | None = None,
               segments: int = 32, rings: int = 20) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = True
    if root:
        obj.parent = root
    return obj


def add_curve(name: str, points: list[tuple[float, float, float]], radius: float,
              mat: bpy.types.Material, root: bpy.types.Object | None = None,
              resolution: int = 2) -> bpy.types.Object:
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = radius
    curve.bevel_resolution = resolution
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, xyz in zip(spline.points, points):
        point.co = (*xyz, 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    if root:
        obj.parent = root
    return obj


def add_uv_abdomen(mat: bpy.types.Material, root: bpy.types.Object) -> bpy.types.Object:
    longitudinal, around = 112, 64
    verts: list[tuple[float, float, float]] = []
    uv_for_vertex: list[tuple[float, float]] = []
    for i in range(longitudinal + 1):
        u = i / longitudinal
        profile = max(0.001, math.sin(math.pi * u)) ** 0.63
        profile *= 0.91 + 0.13 * (1.0 - u)
        x = -1.56 + 2.67 * u
        ry = 0.67 * profile
        rz = 0.62 * profile
        z_center = 0.98 + 0.075 * math.sin(math.pi * u)
        for j in range(around + 1):
            theta = 2 * math.pi * j / around
            c, s = math.cos(theta), math.sin(theta)
            verts.append((x, ry * s, z_center + rz * c))
            # Blender UV V=1 is the top edge of the source texture.
            uv_for_vertex.append((u, 0.5 + 0.5 * c))
    faces = []
    row = around + 1
    for i in range(longitudinal):
        for j in range(around):
            a = i * row + j
            b = a + row
            faces.append((a, b, b + 1, a + 1))
    mesh = bpy.data.meshes.new("Segmented abdomen UV mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("Abdomen - reference texture mapped", mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = root
    obj.data.materials.append(mat)
    layer = mesh.uv_layers.new(name="Side-view source mapping")
    for poly in mesh.polygons:
        poly.use_smooth = True
        for loop_index in poly.loop_indices:
            vi = mesh.loops[loop_index].vertex_index
            layer.data[loop_index].uv = uv_for_vertex[vi]
    subd = obj.modifiers.new("Soft shell curvature", "SUBSURF")
    subd.levels = 1
    subd.render_levels = 1
    return obj


def add_tapered_segment(name: str, radius: float, mat: bpy.types.Material,
                        root: bpy.types.Object, tip_ratio: float = 0.72,
                        vertices: int = 16) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius,
                                    radius2=radius * tip_ratio, depth=1.0)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = True
    obj.parent = root
    obj.rotation_mode = "QUATERNION"
    return obj


def position_segment(obj: bpy.types.Object, start: Vector, end: Vector,
                     frame: int | None = None) -> None:
    delta = end - start
    obj.location = (start + end) * 0.5
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(delta.normalized())
    obj.scale = (1, 1, max(0.001, delta.length))
    if frame is not None:
        for path in ("location", "rotation_quaternion", "scale"):
            obj.keyframe_insert(data_path=path, frame=frame)


def move_joint(obj: bpy.types.Object, point: Vector, frame: int) -> None:
    obj.location = point
    obj.keyframe_insert(data_path="location", frame=frame)


def antenna_points(side: int, pose: int, high: bool) -> list[Vector]:
    phase = 2 * math.pi * pose / PREVIEW_FRAMES + side * 0.7
    start = Vector((1.57, side * 0.20, 1.02))
    c1 = Vector((2.02, side * 0.30, 1.38 if high else 0.82))
    c2 = Vector((2.55, side * 0.84, 2.45 if high else 1.42))
    end = Vector((3.12 + 0.10 * math.sin(phase),
                  side * (1.22 + 0.16 * math.cos(phase)),
                  (2.10 if high else 0.48) + 0.10 * math.sin(phase + 1.2)))
    points = []
    for i in range(7):
        t = i / 6
        point = ((1-t)**3 * start + 3*(1-t)**2*t*c1 + 3*(1-t)*t*t*c2 + t**3*end)
        points.append(point)
    return points


def leg_pose(pair: int, side: int, pose: int) -> tuple[Vector, Vector, Vector, Vector]:
    hip_x = (0.69, -0.05, -0.82)[pair]
    fore_aft = (0.92, -0.08, -0.86)[pair]
    hip = Vector((hip_x, side * 0.48, 0.78))
    tripod = (pair + (0 if side < 0 else 1)) % 2
    phase = 2 * math.pi * pose / PREVIEW_POSES + tripod * math.pi
    swing = 0.28 * math.cos(phase)
    lift = max(0.0, math.sin(phase)) * 0.19
    knee = Vector((hip_x + fore_aft * 0.34 + swing * 0.22,
                   side * 0.85, 0.55 + lift * 0.3))
    ankle = Vector((hip_x + fore_aft * 0.82 + swing * 0.74,
                    side * 1.16, 0.21 + lift))
    toe = Vector((hip_x + fore_aft * 1.17 + swing,
                  side * 1.22, 0.055 + lift))
    return hip, knee, ankle, toe


PREVIEW_POSES = 8


def create_model() -> tuple[bpy.types.Object, list[tuple[list, list, list]]]:
    clear_scene()
    shell = textured_shell_material()
    dark_shell = sampled_plate_material("Pronotum - sampled from reference", PRONOTUM_TEXTURE)
    amber = material("Amber exoskeleton", (0.24, 0.075, 0.018, 1), 0.40, 0.015, 0.12)
    dark_amber = material("Dark leg joints", (0.095, 0.025, 0.008, 1), 0.44, 0.0, 0.08)
    black = material("Glossy black eyes", (0.009, 0.003, 0.002, 1), 0.1, 0.05, 0.85)

    root = bpy.data.objects.new("Roach_Rig_Root", None)
    bpy.context.collection.objects.link(root)
    root.empty_display_type = "SPHERE"
    root.empty_display_size = 0.18

    add_uv_abdomen(shell, root)
    pronotum = add_sphere("Pronotum shield", (0.82, 0, 1.02), (0.71, 0.74, 0.34), dark_shell, root)
    pronotum.rotation_euler[1] = math.radians(-7)
    # Project the reference crop onto the shield's broad visible face rather
    # than using a spherical UV unwrap that smears its cream stripe at the seam.
    shield_uv = pronotum.data.uv_layers.new(name="Reference side projection")
    for polygon in pronotum.data.polygons:
        for loop_index in polygon.loop_indices:
            vertex = pronotum.data.vertices[pronotum.data.loops[loop_index].vertex_index]
            shield_uv.data[loop_index].uv = ((vertex.co.x + 1) * 0.5,
                                             (vertex.co.z + 1) * 0.5)
    head = add_sphere("Head capsule", (1.43, 0, 0.87), (0.35, 0.39, 0.27), dark_amber, root)
    for side in (-1, 1):
        add_sphere(f"Compound eye {side}", (1.53, side * 0.335, 0.99),
                   (0.17, 0.105, 0.18), black, root, 28, 18)
        # Short paired mouth palps under the head.
        add_curve(f"Mouth palp {side}", [(1.64, side * 0.15, 0.76),
                  (1.78, side * 0.22, 0.61), (1.73, side * 0.30, 0.53)],
                  0.022, amber, root, 3)

    # Tail cerci are short paired tapered feelers, characteristic of a nymph.
    for side in (-1, 1):
        tail = add_tapered_segment(f"Tail cercus {side}", 0.075, amber, root, 0.12, 16)
        position_segment(tail, Vector((-1.48, side * 0.10, 0.86)),
                         Vector((-2.02, side * 0.27, 0.75)))

    # Fine transverse ridges make the individual abdominal plates legible in 3D.
    for index in range(1, 8):
        u = index / 9
        x = -1.56 + 2.67 * u
        profile = max(0.001, math.sin(math.pi * u)) ** 0.63 * (0.91 + 0.13 * (1-u))
        ry, rz = 0.67 * profile + 0.009, 0.62 * profile + 0.009
        zc = 0.98 + 0.075 * math.sin(math.pi*u)
        ring = [(x, ry*math.sin(a), zc + rz*math.cos(a))
                for a in [2*math.pi*j/64 for j in range(65)]]
        add_curve(f"Abdominal segment seam {index}", ring, 0.012, dark_amber, root, 2)

    # Build an alternating tripod gait. Three tapered sections per leg are
    # animated as a small object rig; the rendered sprite views use frames 1-8.
    moving_segments: list[tuple[int, int, bpy.types.Object, str]] = []
    joints: list[tuple[int, int, bpy.types.Object, str]] = []
    spike_segments: list[tuple[int, int, bpy.types.Object, Vector, Vector]] = []
    for pair in range(3):
        for side in (-1, 1):
            hip, knee, ankle, toe = leg_pose(pair, side, 0)
            leg_id = pair * 2 + (0 if side < 0 else 1)
            coxa = add_tapered_segment(f"Leg {leg_id} femur", 0.105, amber, root, 0.72)
            tibia = add_tapered_segment(f"Leg {leg_id} tibia", 0.057, amber, root, 0.54)
            tarsus = add_tapered_segment(f"Leg {leg_id} tarsus", 0.033, dark_amber, root, 0.18)
            moving_segments.extend(((pair, side, coxa, "coxa"),
                                    (pair, side, tibia, "tibia"),
                                    (pair, side, tarsus, "tarsus")))
            for joint_name, point, radius in (("coxa", hip, 0.11), ("knee", knee, 0.075),
                                               ("ankle", ankle, 0.045)):
                joint = add_sphere(f"Leg {leg_id} {joint_name} joint", tuple(point),
                                   (radius, radius, radius), amber if joint_name != "ankle" else dark_amber,
                                   root, 16, 10)
                joints.append((pair, side, joint, joint_name))

    # Long, tapering antennae are articulated in short segments and gently sway.
    antenna_segments: list[tuple[int, bool, int, bpy.types.Object]] = []
    for side in (-1, 1):
        for high in (False, True):
            pts = antenna_points(side, 0, high)
            for index in range(len(pts) - 1):
                r = 0.020 * (1 - index / 8) + 0.003
                seg = add_tapered_segment(f"Antenna {side} {int(high)} segment {index}",
                                          r, amber, root, 0.84, 10)
                antenna_segments.append((side, high, index, seg))

    # Small tibial spines add the bristled profile without obscuring the legs.
    for pair in range(3):
        for side in (-1, 1):
            for n in range(5):
                spike = add_tapered_segment(f"Tibial spine {pair} {side} {n}",
                                            0.029, dark_amber, root, 0.0, 8)
                spike_segments.append((pair, side, spike, Vector((0, 0, 0)), Vector((0, 0, 1))))

    # Animate the leg, spine, and antenna object transforms across one loop.
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = PREVIEW_POSES + 1
    for pose in range(PREVIEW_POSES + 1):
        cyclic_pose = pose % PREVIEW_POSES
        frame = pose + 1
        scene.frame_set(frame)
        root.location.z = 0.035 + 0.025 * math.sin(2 * math.pi * cyclic_pose / PREVIEW_POSES)
        root.keyframe_insert(data_path="location", frame=frame)
        for pair, side, obj, part in moving_segments:
            hip, knee, ankle, toe = leg_pose(pair, side, cyclic_pose)
            if part == "coxa":
                start, end = hip, knee
            elif part == "tibia":
                start, end = knee, ankle
            else:
                start, end = ankle, toe
            position_segment(obj, start, end, frame)
        for pair, side, obj, joint_name in joints:
            hip, knee, ankle, _toe = leg_pose(pair, side, cyclic_pose)
            point = {"coxa": hip, "knee": knee, "ankle": ankle}[joint_name]
            move_joint(obj, point, frame)
        for side, high, index, obj in antenna_segments:
            pts = antenna_points(side, cyclic_pose, high)
            position_segment(obj, pts[index], pts[index+1], frame)
        for pair, side, spike, _a, _b in spike_segments:
            _hip, knee, ankle, _toe = leg_pose(pair, side, cyclic_pose)
            n = int(spike.name.rsplit(" ", 1)[1])
            t = 0.16 + n * 0.16
            base = knee.lerp(ankle, t)
            along = (ankle - knee).normalized()
            outward = Vector((0.35, side * 0.9, 0.26)).normalized()
            tip = base + outward * (0.11 + 0.015 * (n % 2))
            position_segment(spike, base, tip, frame)

    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = RENDER_SIZE
    scene.render.resolution_y = RENDER_SIZE
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = True
    scene.render.fps = 12
    scene.render.filepath = str(ASSETS / "roach_walk_0_dir_0.png")
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "Medium High Contrast"
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_percentage = 100
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.frame_set(1)
    bpy.context.view_layer.update()
    return root, antenna_segments


def add_camera_and_lighting() -> None:
    scene = bpy.context.scene
    target = Vector((0.2, 0, 1.02))
    camera_data = bpy.data.cameras.new("Roach render camera")
    camera = bpy.data.objects.new("Roach render camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = (2.0, -9.2, 4.25)
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 7.25
    scene.camera = camera

    for name, location, energy, size, color in (
        ("Warm key", (2.2, -4.0, 6.0), 420, 4.2, (1.0, 0.74, 0.49)),
        ("Soft fill", (-3.8, -2.5, 3.6), 180, 5.0, (1.0, 0.84, 0.66)),
        ("Amber rim", (0.2, 3.8, 4.8), 440, 3.0, (1.0, 0.53, 0.24)),
    ):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        data.color = color
        light = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(light)
        light.location = location
        light.rotation_euler = (target - light.location).to_track_quat("-Z", "Y").to_euler()

    world = bpy.data.worlds.new("Warm studio world") if not bpy.data.worlds else bpy.data.worlds[0]
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.14, 0.095, 0.06, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.28


def main() -> None:
    ART.mkdir(exist_ok=True)
    ASSETS.mkdir(exist_ok=True)
    preview_only = os.environ.get("ROACH_PREVIEW_ONLY") == "1"
    if not preview_only:
        for old in ASSETS.glob("roach_walk_*_dir_*.png"):
            old.unlink()
    root, _antennae = create_model()
    add_camera_and_lighting()
    # Pack the sampled reference texture so the editable .blend is portable.
    bpy.ops.file.pack_all()
    bpy.context.scene.render.filepath = str(ASSETS / "roach_walk_0_dir_0.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))

    scene = bpy.context.scene
    directions = (0,) if preview_only else range(DIRECTIONS)
    poses = (0,) if preview_only else range(PREVIEW_POSES)
    for direction in directions:
        root.rotation_euler[2] = 2 * math.pi * direction / DIRECTIONS
        for pose in poses:
            scene.frame_set(pose + 1)
            bpy.context.view_layer.update()
            path = ASSETS / f"roach_walk_{pose}_dir_{direction}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
    print(f"Saved editable model {BLEND} and {PREVIEW_POSES * DIRECTIONS} rendered sprite frames.")


if __name__ == "__main__":
    main()
