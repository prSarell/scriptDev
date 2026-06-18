# Metahuman API (Maya 2025 port — maya.cmds, no PyMEL)
# Collection of classes and functions to extract data from Metahuman face rig for
# retargeting the FBX animation from the root joint back onto the face rig controls

from functools import wraps
import logging
import time

import maya.cmds as cmds
from maya import mel

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Excluded from zeroing out
ZERO_OUT_EXCLUDED_CONTROLS = ['CTRL_eyesAimFollowHead',
                              'CTRL_faceGUIfollowHead'
                              'CTRL_lookAtSwitch',
                              'CTRL_rigLogicSwitch',
                              'CTRL_neckCorrectivesMultiplyerU',
                              'CTRL_neckCorrectivesMultiplyerM',
                              'CTRL_neckCorrectivesMultiplyerD',
                              'CTRL_faceGUI',
                              'CTRL_GUIswitch',
                              'CTRL_L_mouth_lipsPressD',
                              'CTRL_R_mouth_lipsPressD',
                              'CTRL_expressions',
                              'CTRL_rigLogic'
                              ]

EXCLUDED_RETARGET_CONTROLS = ['CTRL_C_eye',
                              'CTRL_C_eyesAim',
                              'CTRL_L_eyeAim',
                              'CTRL_R_eyeAim',
                              'CTRL_lookAtSwitch',
                              'CTRL_convergenceSwitch',
                              'CTRL_faceTweakersGUI']

EXCLUDED_RETARGET_CONTROLS.extend(ZERO_OUT_EXCLUDED_CONTROLS)
DEFAULT_NAMESPACE = ':'


class ControllerError(Exception):
	pass

class SelectionError(Exception):
	pass

class MetahumanError(Exception):
	pass


def strip_namespace(node_name):
	'''
	Args:
		node_name (str): node name, possibly with a DAG path and/or namespace
	Returns:
		str: node's short name with any namespace removed
	'''
	short_name = node_name.split('|')[-1]
	return short_name.rsplit(':', 1)[-1]

def get_namespace(node_name):
	'''
	Args:
		node_name (str): node name, possibly with a DAG path and/or namespace
	Returns:
		str: namespace including trailing colon, or '' if node is in the root namespace
	'''
	short_name = node_name.split('|')[-1]
	if ':' in short_name:
		return short_name.rsplit(':', 1)[0] + ':'
	return ''

def _fbx_set(option, value):
	''' Run an FBX option/setter command through mel, e.g. FBXImportShapes -v false '''
	if isinstance(value, bool):
		value = 'true' if value else 'false'
	mel.eval('{} -v {}'.format(option, value))


class Controller:

	def __init__(self, control, ctrl_expressions_node):
		'''
		Class to hold and train facial expressions to control channel attributes
		Args:
			control (str): control transform node name
			ctrl_expressions_node (str): transform node that holds facial expressions
		'''
		if cmds.nodeType(control) != 'transform':
			raise ControllerError('{} is not a control transform'.format(control))
		if cmds.nodeType(ctrl_expressions_node) != 'transform':
			raise ControllerError('{} is not the CTRL_expressions node!'.format(ctrl_expressions_node))

		if strip_namespace(ctrl_expressions_node) != 'CTRL_expressions':
			raise ControllerError('{} is not the CTRL_expressions node!'.format(ctrl_expressions_node))

		expression_list = cmds.listAttr(ctrl_expressions_node, userDefined=True, scalar=True) or []

		if not expression_list:
			raise ControllerError('Missing expressions on the {}! Unable to process!'.format(ctrl_expressions_node))

		self.control = control
		self._ctrl_expressions_node = ctrl_expressions_node
		self._expression_list = expression_list
		self._control_mapping = {}
		self.train_control_expressions()

	def train_control_expressions(self):
		''' Trains controls to expression by determining the control limits and what's keyable
			and creates a mapping between the controls attribute and driven expression

			While the controls are driven with a similar animCurve name that the incoming FBX data will have,
			there's a few animCurves that don't follow this convention so will train the data. Takes longer
			to build but more reliable.
		'''
		control_limits = {}
		self._control_mapping = {}
		mapping = {}

		for channel_name, limit_flag in (('tx', 'translationX'), ('ty', 'translationY')):
			control_attr = '{}.{}'.format(self.control, channel_name)
			if cmds.getAttr(control_attr, settable=True) and cmds.getAttr(control_attr, keyable=True):
				control_limits[control_attr] = [cmds.transformLimits(self.control, query=True, **{limit_flag: True}),
				                                 channel_name]
		if control_limits:
			for control_attr, (ctrl_limits, channel_name) in control_limits.items():
				for value in ctrl_limits:
					# Set the control value which will drive the expression
					cmds.setAttr(control_attr, value)

					# Loop through expressions to determine what is active
					for exp in self._expression_list:
						cur_value = cmds.getAttr('{}.{}'.format(self._ctrl_expressions_node, exp))
						if cur_value > 0 or cur_value < 0:
							# The expression name matches the keyframed attribute name from incoming FBX file
							# This will make it easier to connect the keyframe data to a control
							driven_anim_name = 'CTRL_expressions_{}'.format(exp)
							mapping[driven_anim_name] = [control_attr, value]
				# Reset the control
				cmds.setAttr(control_attr, 0.0)

		for key, (attr, value) in mapping.items():
			if attr not in self._control_mapping:
				self._control_mapping[attr] = []
			self._control_mapping[attr].append([key, value])

	@property
	def control_mapping(self):
		return self._control_mapping

	def is_valid(self):
		if self.control_mapping:
			return True
		else:
			return False

def show_wait_cursor(func):
	''' Decorator for waitCursor'''
	@wraps(func)
	def wrapper(*args, **kwargs):
		cmds.waitCursor(state=True)
		try:
			result = func(*args, **kwargs)
		finally:
			cmds.waitCursor(state=False)
		return result
	return wrapper

def load_plugin(plugin_name='fbxmaya'):
	'''
	Load the plugin if not already loaded
	Args:
		plugin_name (str): name of plugin
	'''
	loaded_plugins = cmds.pluginInfo(query=True, listPlugins=True)
	if plugin_name not in loaded_plugins:
		cmds.loadPlugin(plugin_name, quiet=True)

def get_face_controls(namespace=DEFAULT_NAMESPACE):
	'''
	Get a list of metahuman face controls
	Args:
		namespace (str): namespace
	Returns:
		(list of str): list of face control transform names
	'''
	control_set = 'FacialControls'
	face_control_set = '{}{}'.format(namespace, control_set)
	if cmds.objExists(face_control_set):
		cmds.select(face_control_set, replace=True)
		controls = cmds.ls(selection=True) or []
	else:
		# If we're missing the FacialControls set, will look by CTRL_ convention naming
		controls = cmds.ls('{}{}'.format(namespace, 'CTRL_*'), type='transform') or []

	face_controls = []
	# Some controls are shapes so make sure the list is just transforms
	for control in controls:
		node_type = cmds.nodeType(control)
		if node_type == 'transform':
			face_controls.append(control)
		elif node_type == 'mesh':
			parents = cmds.listRelatives(control, parent=True)
			if parents:
				face_controls.append(parents[0])
	cmds.select(clear=True)
	return face_controls

def select_face_controls(namespace=DEFAULT_NAMESPACE):
	'''
	Select face controls
	Args:
		namespace (str): namespace
	Returns:
		bool: True if controls present, otherwise False
	'''
	result = False
	controls = get_face_controls(namespace)
	if controls:
		cmds.select(controls, replace=True)
		result = True
	return result

def zero_out_face_controls(namespace=DEFAULT_NAMESPACE):
	'''
	Zeroes out all controls
	Args:
		namespace (str): namespace
	Returns:
		bool: True if controls present, otherwise False
	'''
	result = False
	selection = cmds.ls(selection=True)
	controls = get_face_controls(namespace)
	if controls:
		result = True
	for control in controls:
		if strip_namespace(control) not in ZERO_OUT_EXCLUDED_CONTROLS:
			cmds.setAttr('{}.translateY'.format(control), 0.0)
			if not cmds.getAttr('{}.translateX'.format(control), lock=True):
				cmds.setAttr('{}.translateX'.format(control), 0.0)
	if selection:
		cmds.select(selection, replace=True)
	return result

def get_controllers(namespace=DEFAULT_NAMESPACE):
	'''
	Get all controller objects
	Args:
		namespace (str): rig namespace, so we can gather all the controls

	Returns:
		tuple(list of Controller, error message): list of Controller objects, error message
	'''
	error_msg = ''
	face_controls = get_face_controls(namespace)
	if not face_controls:
		error_msg = 'Unable to find face controls! Either not a Metahuman or controls are missing!'
		return [], error_msg

	expression_node = '{}{}'.format(namespace, 'CTRL_expressions')
	if not cmds.objExists(expression_node):
		error_msg = 'Unable to find CTRL_expressions! Unable to process!'
		return [], error_msg
	# Zero out controls so we get the proper control mapping
	zero_out_face_controls(namespace)
	controllers = []
	for face_control in face_controls:
		if strip_namespace(face_control) not in EXCLUDED_RETARGET_CONTROLS:
			controller = Controller(face_control, expression_node)
			if controller.is_valid():
				controllers.append(controller)
	return controllers, error_msg

def import_fbx_animation(fbx_path):
	'''
	Import fbx animation data
	Args:
		fbx_path (str): absolute path to fbx animation
	Returns:
		(set of str): names of imported nodes
	'''
	# Import animation
	_fbx_set('FBXImportShapes', False)
	_fbx_set('FBXImportSkins', False)
	_fbx_set('FBXImportMode', 'add')
	_fbx_set('FBXImportMergeAnimationLayers', False)
	_fbx_set('FBXImportProtectDrivenKeys', True)
	_fbx_set('FBXImportSetMayaFrameRate', False)

	cur_nodes = cmds.ls()
	mel.eval('FBXImport -file "{}" -take 1'.format(fbx_path.replace('\\', '/')))
	return set(cmds.ls()) - set(cur_nodes)

def export_fbx_animation(fbx_path, namespace=DEFAULT_NAMESPACE):
	'''
	Export fbx animation
	Args:
		fbx_path (str): absolute path to fbx animation
		namespace (str): rig namespace
	Returns:
		(list of str): list of exported control names
	'''
	face_controls = get_face_controls(namespace)
	if not face_controls:
		return []

	start_frame, end_frame = get_key_frame_ranges(face_controls)
	cmds.bakeResults(face_controls,
	                 time=(int(start_frame), int(end_frame)),
	                 preserveOutsideKeys=True,
	                 minimizeRotation=False,
	                 sparseAnimCurveBake=False,
	                 sampleBy=1,
	                 oversamplingRate=1,
	                 bakeOnOverrideLayer=False,
	                 removeBakedAttributeFromLayer=False,
	                 removeBakedAnimFromLayer=False,
	                 shape=False,
	                 controlPoints=False,
	                 disableImplicitControl=True)

	cmds.select(face_controls, replace=True)
	current_namespace = get_namespace(face_controls[0])
	controls = []
	# Handle exporting control animation if in namespace
	if current_namespace:
		# Set to root namespace
		cmds.namespace(setNamespace=':')
		for control in face_controls:
			control_name = strip_namespace(control)
			dup_control = cmds.duplicate(control, returnRootsOnly=True, inputConnections=True)[0]
			new_control = cmds.rename(dup_control, control_name)
			controls.append(new_control)
		cmds.select(controls, replace=True)
	# Set it back to current namespace
	cmds.namespace(setNamespace=current_namespace if current_namespace else ':')
	mel.eval('FBXResetExport')
	_fbx_set('FBXExportAnimationOnly', True)
	_fbx_set('FBXExportBakeComplexAnimation', False)
	_fbx_set('FBXExportLights', False)
	_fbx_set('FBXExportCameras', False)
	_fbx_set('FBXExportConstraints', False)
	_fbx_set('FBXExportSkins', False)
	_fbx_set('FBXExportApplyConstantKeyReducer', False)
	_fbx_set('FBXExportSmoothMesh', False)
	_fbx_set('FBXExportShapes', False)
	_fbx_set('FBXExportEmbeddedTextures', False)
	_fbx_set('FBXExportInputConnections', False)
	_fbx_set('FBXExportFileVersion', 'FBX202000')
	mel_path = fbx_path.replace('\\', '/')
	mel.eval('FBXExport -file "{}" -s'.format(mel_path))
	# Original tool issues the export command twice (once with -file, once with -f) — preserved to match its behavior
	mel.eval('FBXExport -f "{}" -s'.format(mel_path))
	if controls:
		cmds.delete(controls)
	return face_controls

def get_root_joint(joint_list):
	'''
	Get the root joint from joint list
	Args:
		joint_list (list of str): list of joint node names

	Returns:
		str or None: root joint name or None
	'''
	root_joints = [joint for joint in joint_list if not cmds.listRelatives(joint, parent=True)]
	if len(root_joints) == 0:
		return None
	return root_joints[0]

def get_key_frame_range(node):
	'''
	Get the min, max range of keyframes for this node
	Args:
		node (str): node with keys

	Returns:
		tuple(float, float): start, end of keyframes
	'''
	return float(cmds.findKeyframe(node, which='first')), float(cmds.findKeyframe(node, which='last'))

def get_key_frame_ranges(nodes):
	'''
	Get the min, max of start and end frames
	Args:
        nodes (list of str): list of node names with keys
    Returns:
    	tuple(float, float): start, end of keyframes
	'''
	start_frames = [get_key_frame_range(node)[0] for node in nodes]
	end_frames = [get_key_frame_range(node)[1] for node in nodes]
	return min(start_frames), max(end_frames)

@show_wait_cursor
def retarget_metahuman_animation_sequence(fbx_path, namespace=DEFAULT_NAMESPACE, timeunit='ntsc'):
	'''
	Imports the fbx animation into the scene and connects the curve data to the control rig.
	Then will bake the animation on the controls and clean up the scene

	To keep the file size small and still bring in the animation, here are suggested settings
	Unreal FBX Export Options:
		* FBX Export Compatibility: 2020
		* Set ONLY these check-box's to True
			* Export Morph Targets: True
			* Export Preview Mesh: True
			* Map Skeletal Motion to Root: True
			* Export Local Time: True

	Args:
		fbx_path (str): absolute path to fbx animation
		namespace (str): rig namespace, so we can gather all the controls
  		timeunit (str): time unit to set the scene to. Default is 'ntsc' for 30fps

	Returns:
		tuple(str, str): elapsed time to complete, error message
	'''
	start_time = time.time()
	load_plugin()

	error_msg = ''
	elapsed_time = ''

	# Build control mapping
	controllers, error = get_controllers(namespace)
	if error:
		return elapsed_time, error

	new_nodes = list(import_fbx_animation(fbx_path))

	cmds.currentUnit(time=timeunit)

	# Check if animCurves came in
	anim_curves = cmds.ls(new_nodes, type='animCurve')
	if not anim_curves:
		error_msg = "No animation curves present!\n\n" \
		            "Ensure the exported animation is from an animation sequence!"
		cmds.delete(new_nodes)
		return elapsed_time, error_msg

	new_joints = cmds.ls(new_nodes, type='joint')
	root_joint = get_root_joint(new_joints)
	if not root_joint:
		cmds.delete(new_nodes)
		error_msg = 'Did not find the root joint from: {}.\n' \
		            'Ensure the exported animation is from an animation sequence!'.format(fbx_path)
		return elapsed_time, error_msg

	# Get the range of keys
	start_frame, end_frame = get_key_frame_range(root_joint)

	# Take the mapping data and copy animation keys over to the proper control.channel
	blend_weighted_nodes = []
	controls_attrs_to_bake = []
	for controller in controllers:
		for control_attr, expression_data in controller.control_mapping.items():

			# Connect control channel that has more than one anim curve driving it
			if len(expression_data) > 1:
				anim_curves_for_attr = []
				for index, (expression, driver_value) in enumerate(expression_data):
					if cmds.attributeQuery(expression, node=root_joint, exists=True):
						driver_attr = '{}.{}'.format(root_joint, expression)
						anim_curve = cmds.listConnections(driver_attr, source=True, destination=False, type='animCurve')
						if anim_curve:
							# Control moves in the negative
							if driver_value == -1.0:
								# Get the anim curve and scale it by -1
								cmds.scaleKey(anim_curve[0], valueScale=-1.0)
						else:
							logger.error('No animation curve for {}'.format(driver_attr))

						anim_curves_for_attr.append(anim_curve[0])
					else:
						logger.warning('{} does not have {} in the name. This will be skipped!'.format(root_joint, expression))

				# Connect anim curves
				bw_node = cmds.createNode('blendWeighted')
				for i, anim_curve in enumerate(anim_curves_for_attr):
					cmds.connectAttr('{}.output'.format(anim_curve), '{}.input[{}]'.format(bw_node, i))
				cmds.connectAttr('{}.output'.format(bw_node), control_attr)
				controls_attrs_to_bake.append(control_attr)
				blend_weighted_nodes.append(bw_node)
			else:
				for index, (expression, driver_value) in enumerate(expression_data):
					if cmds.attributeQuery(expression, node=root_joint, exists=True):
						driver_attr = '{}.{}'.format(root_joint, expression)
						anim_curve = cmds.listConnections(driver_attr, source=True, destination=False, type='animCurve')
						if anim_curve:
							copied = cmds.copyKey(driver_attr)
							if copied:
								try:
									cmds.pasteKey(control_attr)
								except RuntimeError:
									logger.error('Failed to paste keys to {}'.format(control_attr))
					else:
						logger.warning('{} does not have {} in the name. This will be skipped!'.format(root_joint, expression))

	# Bake controls
	cmds.bakeResults(controls_attrs_to_bake,
	                 time=(int(start_frame), int(end_frame)),
	                 preserveOutsideKeys=True,
	                 sparseAnimCurveBake=False,
	                 sampleBy=1,
	                 oversamplingRate=1,
	                 removeBakedAttributeFromLayer=False,
	                 removeBakedAnimFromLayer=False,
	                 shape=False,
	                 controlPoints=False,
	                 disableImplicitControl=True)

	# Clean up
	cmds.delete(blend_weighted_nodes)
	cmds.delete(new_nodes)

	cmds.playbackOptions(animationStartTime=int(start_frame), animationEndTime=int(end_frame))

	delta_time = time.gmtime(time.time() - start_time)
	elapsed_time = str(time.strftime("%H:%M:%S", delta_time))
	logger.info("Transfer completed in: {}".format(elapsed_time))
	return elapsed_time, error_msg


def retarget_metahuman_level_sequence(fbx_path, namespace=DEFAULT_NAMESPACE, timeunit='film'):
	'''
	This currently is only supported in Maya 2022.4, 2022.5 and 2023.3

	This only supports FBX data exported from a Level Sequence exported from
	the face track in Unreal. The data is hit or miss due to FBX incompatibility issues with Maya.
	It's recommended to use	'retarget_metahuman_animation_sequence' instead for broader compatibility

	References in FBX file and copies the keys from the attributes over to the face controls
	Args:
		fbx_path (str): path to exported FBX file from Unreal
		namespace (str): current namespace
  		timeunit (str): time unit to set the scene to. Default is 'film' for 24fps
	Returns:
		tuple(str, str): elapsed time to complete, error message
	'''
	start_time = time.time()
	load_plugin()

	error_msg = ''
	elapsed_time = ''

	supported_versions = [20200400, 20220400, 20220500, 20230300]
	current_version = cmds.about(apiVersion=True)
	if current_version not in supported_versions:
		error_msg = 'This version (year.cut) of Maya is not currently supported: {}'.format(current_version)
		return elapsed_time, error_msg

	cmds.currentUnit(time=timeunit)

	nodes = cmds.file(fbx_path, reference=True, namespace=':', returnNewNodes=True) or []
	reference_nodes = cmds.ls(nodes, type='reference')
	reference_node = reference_nodes[0] if reference_nodes else None

	if not nodes:
		error_msg = '{} is an empty file!'.format(fbx_path)
		if reference_node:
			cmds.file(referenceNode=reference_node, removeReference=True)
		return elapsed_time, error_msg

	# Check if animCurves came in
	anim_curves = cmds.ls(nodes, type='animCurve')
	if not anim_curves:
		error_msg = "No animation curves present!\n\n" \
		            "Export Facial animation from Animation Sequence \n" \
		            "Then use 'Import FBX Animation Sequence File'"
		if reference_node:
			cmds.file(referenceNode=reference_node, removeReference=True)
		return elapsed_time, error_msg

	control_board = None
	for node in cmds.ls(nodes):
		if strip_namespace(node) == 'Face_ControlBoard_CtrlRig':
			control_board = node
			break
	if control_board is None:
		error_msg = "Missing Face_ControlBoard_CtrlRig node!\nUnable to import animation!"
		if reference_node:
			cmds.file(referenceNode=reference_node, removeReference=True)
		return elapsed_time, error_msg

	keyed_attributes = {}
	for attr_name in cmds.listAttr(control_board, keyable=True) or []:
		if 'CTRL_' in attr_name:
			index = attr_name.find("FBX")
			if index != -1:
				channel_name = attr_name[-1]
				if channel_name == 'X':
					driven_channel = 'translateX'
				elif channel_name == 'Y':
					driven_channel = 'translateY'
				elif channel_name == 'Z':
					driven_channel = 'translateZ'
				else:
					driven_channel = 'translateY'
				control_name = attr_name[:index]
				if control_name not in EXCLUDED_RETARGET_CONTROLS:
					control_name = '{}{}'.format(namespace, control_name)
					result = (control_name, driven_channel)
					keyed_attributes[attr_name] = result
			else:
				if attr_name not in EXCLUDED_RETARGET_CONTROLS:
					control_name = '{}{}'.format(namespace, attr_name)
					result = (control_name, 'translateY')
					keyed_attributes[attr_name] = result

	copied_keys = []
	for driver_attr, (control_name, channel) in keyed_attributes.items():
		if cmds.objExists(control_name):
			driven_attr = '{}.{}'.format(control_name, channel)
			if cmds.getAttr(driven_attr, settable=True) and not cmds.getAttr(driven_attr, lock=True):
				copied = cmds.copyKey('{}.{}'.format(control_board, driver_attr))
				if copied:
					try:
						cmds.pasteKey(driven_attr)
					except RuntimeError:
						logger.error('Failed to paste keys to {}'.format(driven_attr))
					copied_keys.append(driven_attr)

	if len(copied_keys) == 0:
		error_msg = "Missing animation data. Possible incompatible FBX data."
		if reference_node:
			cmds.file(referenceNode=reference_node, removeReference=True)
		return elapsed_time, error_msg

	# Cleanup
	for node in cmds.ls(nodes, type='reference'):
		cmds.file(referenceNode=node, removeReference=True)
		break

	delta_time = time.gmtime(time.time() - start_time)
	elapsed_time = str(time.strftime("%H:%M:%S", delta_time))
	logger.info("Transfer completed in: {}".format(elapsed_time))
	return elapsed_time, error_msg
