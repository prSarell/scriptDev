import math
import maya.cmds as cmds


class SmoothTool(object):
    def __init__(self):
        self.window_name = "SmoothToolWindow"
        self.original_curves = []
        self.blend_curves = []
        self.smooth_curves = []
        self.selected_obj = None
        self.dummy_rig = None
        self.aim_group = None
        self.up_group = None
        self.target_group = None
        self.bake_group = None
        self.points = []
        self.frame_range = []
        self.original_positions = []
        self.original_rotations = []

    def create_ui(self):
        if cmds.window(self.window_name, exists=True):
            cmds.deleteUI(self.window_name)

        window = cmds.window(self.window_name, title="Smooth Tool",
                             widthHeight=(300, 300))
        cmds.columnLayout(adjustableColumn=True)

        cmds.button(label="Create Curves", command=self.create_curves,
                    backgroundColor=(0.8, 0.2, 0.2))
        cmds.text(label="Smooth Controls")
        self.blend_slider = cmds.floatSliderGrp(
            label="Blend Amount", field=True,
            minValue=0.0, maxValue=1.0, value=0.0,
            changeCommand=self.update_blend)
        self.smooth_slider = cmds.floatSliderGrp(
            label="Smooth Strength", field=True,
            minValue=0.0, maxValue=5.0, value=1.0,
            changeCommand=self.update_smooth)

        self.bake_to_layer_check = cmds.checkBox(label="Bake to Layer",
                                                 value=False)
        cmds.button(label="Build Aim Rig", command=self.build_aim_rig,
                    backgroundColor=(0.2, 0.8, 0.2))
        cmds.button(label="Reset", command=self.reset_interface,
                    backgroundColor=(0.5, 0.5, 0.5))

        cmds.showWindow(window)

    def get_frame_range(self):
        time_control = "timeControl1"
        try:
            if cmds.timeControl(time_control, q=True, rangeVisible=True):
                range_str = cmds.timeControl(time_control, q=True, range=True)
                cleaned_range = range_str.replace('"', '').split(':')
                self.frame_range = [int(float(x)) for x in cleaned_range]
            else:
                raise ValueError("Range not visible")
        except (ValueError, TypeError):
            self.frame_range = [
                int(cmds.playbackOptions(q=True, minTime=True)),
                int(cmds.playbackOptions(q=True, maxTime=True))]

    def distance(self, p1, p2):
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))

    def find_max_distance_points(self, positions):
        if len(positions) < 3:
            return positions + [[0, 0, 0]] * (3 - len(positions))

        p0 = positions[0]
        p1 = max(positions, key=lambda p: self.distance(p0, p))
        p2 = max(positions,
                 key=lambda p: self.distance(p0, p) + self.distance(p1, p))
        return [p0, p1, p2]

    def create_curves(self, *args):
        selection = cmds.ls(selection=True, type="transform")
        if not selection:
            cmds.warning("Please select a transform object (curve).")
            return

        self.selected_obj = selection[0]
        shape_nodes = cmds.listRelatives(self.selected_obj, shapes=True,
                                         fullPath=True)
        if not shape_nodes or cmds.objectType(shape_nodes[0]) != "nurbsCurve":
            cmds.warning("Selected object must be a NURBS curve.")
            return
        curve_shape = shape_nodes[0]
        num_cvs = cmds.getAttr(f"{curve_shape}.controlPoints", size=True)
        if num_cvs < 3:
            cmds.warning("Curve must have at least 3 CVs for triangulation.")
            return

        self.get_frame_range()
        frames = list(range(self.frame_range[0], self.frame_range[1] + 1))

        existing = [c for c in (self.original_curves + self.blend_curves +
                                self.smooth_curves) if cmds.objExists(c)]
        if existing:
            cmds.delete(existing)
        self.original_curves = []
        self.blend_curves = []
        self.smooth_curves = []
        self.original_positions = []
        self.original_rotations = []

        world_curve_positions = [[], [], []]

        cmds.currentTime(frames[0])
        cv_positions = [
            cmds.xform(f"{curve_shape}.cv[{i}]", q=True, t=True, ws=True)
            for i in range(num_cvs)]
        selected_points = self.find_max_distance_points(cv_positions)
        self.points = [cv_positions.index(p) for p in selected_points]

        for frame in frames:
            cmds.currentTime(frame)
            self.original_positions.append(
                cmds.xform(self.selected_obj, q=True, t=True, ws=True))
            self.original_rotations.append(
                cmds.xform(self.selected_obj, q=True, ro=True, ws=True))

            for i, cv_index in enumerate(self.points):
                cv_pos = cmds.xform(f"{curve_shape}.cv[{cv_index}]",
                                    q=True, t=True, ws=True)
                world_curve_positions[i].append(cv_pos)

        for i in range(3):
            positions = world_curve_positions[i]
            name_base = f"{self.selected_obj}_curve{i}"
            orig_curve = cmds.curve(p=positions,
                                    name=f"{name_base}_orig", d=1)
            blend_curve = cmds.curve(p=positions,
                                     name=f"{name_base}_blend", d=1)
            smooth_curve = cmds.curve(p=positions,
                                      name=f"{name_base}_smooth", d=1)
            self.original_curves.append(orig_curve)
            self.blend_curves.append(blend_curve)
            self.smooth_curves.append(smooth_curve)

            cmds.setAttr(f"{orig_curve}.overrideEnabled", 1)
            cmds.setAttr(f"{orig_curve}.overrideRGBColors", 1)
            cmds.setAttr(f"{orig_curve}.overrideColorRGB", 0.5, 0.1, 0.1)
            cmds.setAttr(f"{blend_curve}.overrideEnabled", 1)
            cmds.setAttr(f"{blend_curve}.overrideRGBColors", 1)
            cmds.setAttr(f"{blend_curve}.overrideColorRGB", 0.0, 1.0, 0.0)
            cmds.setAttr(f"{smooth_curve}.overrideEnabled", 1)
            cmds.setAttr(f"{smooth_curve}.overrideRGBColors", 1)
            cmds.setAttr(f"{smooth_curve}.overrideColorRGB", 0.8, 0.8, 0.8)

        self.update_smooth()

    def update_smooth(self, *args):
        strength = cmds.floatSliderGrp(self.smooth_slider, q=True, value=True)
        for i, smooth_curve in enumerate(self.smooth_curves):
            smoothed_pos = self.compute_smooth(self.original_curves[i],
                                               strength)
            for j, pos in enumerate(smoothed_pos):
                cmds.setAttr(f"{smooth_curve}.cp[{j}]", *pos)
        self.update_blend()

    def update_blend(self, *args):
        blend = cmds.floatSliderGrp(self.blend_slider, q=True, value=True)
        for i, blend_curve in enumerate(self.blend_curves):
            orig_pos = cmds.getAttr(f"{self.original_curves[i]}.cp[*]")
            smooth_pos = cmds.getAttr(f"{self.smooth_curves[i]}.cp[*]")
            for j in range(len(orig_pos)):
                blended = tuple((1 - blend) * o + blend * s
                                for o, s in zip(orig_pos[j], smooth_pos[j]))
                cmds.setAttr(f"{blend_curve}.cp[{j}]", *blended)

    def compute_smooth(self, curve, strength):
        cvs = cmds.getAttr(f"{curve}.cp[*]")
        smoothed = []
        window = int(strength * 2) + 1

        for i in range(len(cvs)):
            if i == 0 or i == len(cvs) - 1:
                smoothed.append(cvs[i])
            else:
                max_window = min(window, len(cvs) - 1)
                half_window = max_window // 2
                avg = [0, 0, 0]
                count = 0
                for j in range(-half_window, half_window + 1):
                    idx = i + j
                    if 0 <= idx < len(cvs):
                        for k in range(3):
                            avg[k] += cvs[idx][k]
                        count += 1
                smoothed.append(tuple(a / count for a in avg))
        return smoothed

    def create_dummy_rig(self):
        if not self.selected_obj or not cmds.objExists(self.selected_obj):
            cmds.warning("No valid selected object to base dummy rig on.")
            return None

        rot = cmds.xform(self.selected_obj, q=True, ro=True, ws=True)
        rot_order = cmds.getAttr(f"{self.selected_obj}.rotateOrder")

        base_name = f"{self.selected_obj}_smoothRig"
        rig_name = base_name
        i = 1
        while cmds.objExists(rig_name):
            rig_name = f"{base_name}{i}"
            i += 1

        self.dummy_rig = cmds.group(empty=True, name=rig_name)
        self.aim_group = cmds.group(empty=True, name=f"{rig_name}_aim",
                                    parent=self.dummy_rig)
        self.up_group = cmds.group(empty=True, name=f"{rig_name}_up",
                                   parent=self.dummy_rig)
        self.target_group = cmds.group(empty=True, name=f"{rig_name}_target",
                                       parent=self.dummy_rig)
        self.bake_group = cmds.group(empty=True, name=f"{rig_name}_bake",
                                     parent=self.aim_group)

        cmds.xform(self.bake_group, ro=rot, ws=True)

        for obj in [self.dummy_rig, self.aim_group, self.up_group,
                    self.target_group, self.bake_group]:
            cmds.setAttr(f"{obj}.rotateOrder", rot_order)

        cmds.aimConstraint(self.target_group, self.aim_group,
                           aimVector=[1, 0, 0], upVector=[0, 1, 0],
                           worldUpType="object",
                           worldUpObject=self.up_group)
        return self.dummy_rig

    def reset_interface(self, *args):
        cmds.floatSliderGrp(self.blend_slider, e=True, value=0.0)
        cmds.floatSliderGrp(self.smooth_slider, e=True, value=1.0)
        self.selected_obj = None
        if self.dummy_rig and cmds.objExists(self.dummy_rig):
            cmds.delete(self.dummy_rig)
        self.dummy_rig = None
        self.aim_group = None
        self.up_group = None
        self.target_group = None
        self.bake_group = None

        existing = [c for c in (self.original_curves + self.blend_curves +
                                self.smooth_curves) if cmds.objExists(c)]
        if existing:
            cmds.delete(existing)
        self.original_curves = []
        self.blend_curves = []
        self.smooth_curves = []
        self.points = []
        self.original_positions = []
        self.original_rotations = []

    def build_aim_rig(self, *args):
        if not self.selected_obj or not cmds.objExists(self.selected_obj):
            cmds.warning("No valid object to build rig for.")
            return

        if not self.blend_curves or len(self.blend_curves) != 3:
            cmds.warning("Blend curves missing or incomplete. "
                         "Please create curves first.")
            return

        if self.dummy_rig and cmds.objExists(self.dummy_rig):
            cmds.delete(self.dummy_rig)
            self.dummy_rig = None

        if not self.create_dummy_rig():
            return

        if not self.frame_range:
            self.get_frame_range()

        frames = list(range(self.frame_range[0], self.frame_range[1] + 1))
        bake_to_layer = cmds.checkBox(self.bake_to_layer_check,
                                      q=True, value=True)

        cmds.undoInfo(openChunk=True, chunkName="SmoothTool_BuildAimRig")
        try:
            for i, frame in enumerate(frames):
                cmds.currentTime(frame)
                max_cv = cmds.getAttr(
                    f"{self.blend_curves[0]}.controlPoints", size=True) - 1
                if i > max_cv:
                    continue

                aim_pos = cmds.xform(f"{self.blend_curves[0]}.cv[{i}]",
                                     q=True, t=True, ws=True)
                up_pos = cmds.xform(f"{self.blend_curves[1]}.cv[{i}]",
                                    q=True, t=True, ws=True)
                target_pos = cmds.xform(f"{self.blend_curves[2]}.cv[{i}]",
                                        q=True, t=True, ws=True)

                cmds.xform(self.aim_group, t=aim_pos, ws=True)
                cmds.xform(self.up_group, t=up_pos, ws=True)
                cmds.xform(self.target_group, t=target_pos, ws=True)

                for obj in [self.aim_group, self.up_group, self.target_group]:
                    pos = cmds.xform(obj, q=True, t=True, ws=True)
                    cmds.setKeyframe(obj, t=frame, at="translateX", v=pos[0])
                    cmds.setKeyframe(obj, t=frame, at="translateY", v=pos[1])
                    cmds.setKeyframe(obj, t=frame, at="translateZ", v=pos[2])

            if (cmds.objExists(self.selected_obj)
                    and cmds.objExists(self.bake_group)):
                constraint = cmds.parentConstraint(
                    self.bake_group, self.selected_obj, mo=True, weight=1)

                bake_attrs = ["translateX", "translateY", "translateZ",
                              "rotateX", "rotateY", "rotateZ"]
                bake_time = (self.frame_range[0], self.frame_range[1])

                if bake_to_layer:
                    layer_name = f"{self.selected_obj}_SmoothLayer"
                    if not cmds.animLayer(layer_name, q=True, exists=True):
                        cmds.animLayer(layer_name, override=True)
                    cmds.select(self.selected_obj)
                    cmds.animLayer(layer_name, e=True,
                                  addSelectedObjects=True)
                    cmds.bakeResults(
                        self.selected_obj,
                        animation="layer", layer=layer_name,
                        time=bake_time, simulation=True, sampleBy=1,
                        oversamplingRate=1, disableImplicitControl=True,
                        preserveOutsideKeys=True,
                        sparseAnimCurveBake=False,
                        removeBakedAttributeFromLayer=False,
                        bakeOnOverrideLayer=True,
                        minimizeRotation=True, attribute=bake_attrs)
                else:
                    cmds.bakeResults(
                        self.selected_obj,
                        time=bake_time, simulation=True, sampleBy=1,
                        oversamplingRate=1, disableImplicitControl=True,
                        preserveOutsideKeys=True,
                        sparseAnimCurveBake=False,
                        removeBakedAttributeFromLayer=False,
                        bakeOnOverrideLayer=False,
                        minimizeRotation=True, attribute=bake_attrs)

                cmds.delete(constraint)
                if self.dummy_rig and cmds.objExists(self.dummy_rig):
                    cmds.delete(self.dummy_rig)
                existing = [c for c in (self.original_curves +
                                        self.blend_curves +
                                        self.smooth_curves)
                            if cmds.objExists(c)]
                if existing:
                    cmds.delete(existing)

                self.dummy_rig = None
                self.aim_group = None
                self.up_group = None
                self.target_group = None
                self.bake_group = None
                self.original_curves = []
                self.blend_curves = []
                self.smooth_curves = []

        except Exception as e:
            cmds.warning(f"Building aim rig failed: {e}")
            raise
        finally:
            cmds.undoInfo(closeChunk=True)


def run_smooth_tool():
    tool = SmoothTool()
    tool.create_ui()


run_smooth_tool()
