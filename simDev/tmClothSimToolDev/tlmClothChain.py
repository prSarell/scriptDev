# Maya 2025–ready version
import maya.cmds as cmds
import maya.mel as mel
import os
from functools import partial
import importlib
from maya.api.OpenMaya import MVector  # API 2.0

def scriptJobFunction(*args):
	clothRigName = cmds.text('clothRig_text', q=True, l=True).partition(': ')[2]
	for i in cmds.listRelatives(clothRigName + '_nCloth_grp') or []:
		if 'dynamicConstraint' in i:
			if cmds.keyframe(clothRigName + '_dynamicConstraint' + i.partition('dynamicConstraint')[2], q=True, kc=True) != 0:
				newValue = "%.3f" % cmds.getAttr(clothRigName + '_dynamicConstraintShape' + i.partition('dynamicConstraint')[2] + '.strength')
				cmds.textField('segment_' + i.partition('dynamicConstraint')[2] + '_textField', e=True, tx=newValue)
				currTime = cmds.currentTime(q=True)
				keys = cmds.keyframe(clothRigName + '_dynamicConstraintShape' + i.partition('dynamicConstraint')[2], q=True) or []
				if currTime in keys:
					cmds.textField('segment_' + i.partition('dynamicConstraint')[2] + '_textField', e=True, bgc=(.85, .4, .4))
				else:
					cmds.textField('segment_' + i.partition('dynamicConstraint')[2] + '_textField', e=True, bgc=(.15,.15,.15))
			else:
				cmds.textField('segment_' + i.partition('dynamicConstraint')[2] + '_textField', e=True, bgc=(.15,.15,.15))
				cmds.iconTextButton('keyframe_button' + i.partition('dynamicConstraint')[2], e=True, image1='autoKeyframeOff.png')

def scriptJobFunction2(controlsList, *args):
	clothRigName = cmds.text('clothRig_text', q=True, l=True).partition(': ')[2]
	for i in controlsList or []:
		if cmds.keyframe(i, q=True, kc=True) != 0:
			newValue = "%.2f" % cmds.getAttr(i + '.blendParent1')
			cmds.textField(i + '_textField', e=True, tx=newValue)

def refreshTool(*args):
	# Reload this tool’s module (update "tlmClothChain" below if your file/module is named differently)
	import sys
	mod_name = 'tlmClothChain'  # <-- change to the actual module name for your file if different
	if mod_name in sys.modules:
		importlib.reload(sys.modules[mod_name])
		mod = sys.modules[mod_name]
	else:
		mod = __import__(mod_name)
	run = mod.SimClothRig()
	# Defer showing the UI (pass the callable; don't call it immediately)
	cmds.evalDeferred(run.UI)

class SimClothRig():
	def __init__(self):
		self.presetsList = ['custom', 'airBag', 'beachBall', 'burlap', 'chainMail', 'chiffon', 'concrete', 'heavyDenim', 'honey', 'lava', 'looseThickKnit', 'plasticShell', 'putty', 'rubberSheet', 'silk', 'softSheetMetal', 'solidRubber', 'thickLeather', 'tshirt', 'waterBalloon', 'waterVolume']
		self.nClothSettingsName = ['bounce', 'friction', 'damp', 'stickiness', 'pointMass', 'stretchResistance', 'compressionResistance', 'bendResistance', 'rigidity', 'stretchDamp']
		self.customPreset = [0, 2, 0.25, 0, 1.5, 200, 200, 3, 0.01, 0.1]

	def _get_nucleus(self, clothRigName):
		connections = cmds.listConnections(clothRigName + '_nClothShape1', type='nucleus') or []
		return connections[0] if connections else None

	def UI(self, parent='clothChain_mainWindow', *args):
		if parent == 'clothChain_mainWindow':
			if cmds.window("clothChain_mainWindow", exists=True):
				cmds.deleteUI("clothChain_mainWindow")
			cmds.window("clothChain_mainWindow", tlb=1, sizeable=True, mxb=False, title="SimClothRig")

		cmds.columnLayout('SimClothRig', adjustableColumn=1, p=parent)
		cmds.scrollLayout('scrollLayout', hst=15, vst=15, cr=True, w=470, h=762)
		cmds.separator(st='none', h=5)

		cmds.columnLayout('clothChain_frameLayout', adjustableColumn=2, columnAttach=('both', 5))
		cmds.rowLayout('rowLayout_info', nc=2, cw2=[275, 30], adjustableColumn=1) 
		cmds.text('Create Proxy Geometry', h=16, bgc=(.22,.22,.22), al='center', fn="boldLabelFont")
		cmds.iconTextButton(w=20, h=20,style='iconOnly', image1='info.png', ann='Click here to see the script info.')
		cmds.popupMenu(b=1)
		cmds.menuItem('Refresh UI', c=refreshTool)
		cmds.menuItem('Help',)

		cmds.rowLayout('createLoc_rowLayout2', nc=4, adjustableColumn=2, p='clothChain_frameLayout')
		cmds.text('Cloth Rig Name:')
		cmds.textField('clothRigName_textField', w=150)
		cmds.text(' Number of Segments:')
		cmds.textField('numSegments_textField', w=40, tx='3')

		cmds.button(l='Create Proxy Geo', w=100, c=self.createBaseGeo, p='clothChain_frameLayout')
		cmds.separator(st='none', h=10,  p='clothChain_frameLayout')

		cmds.frameLayout('buildClothRig_frameLayout', lv=False, bv=False, p='clothChain_frameLayout')
		cmds.rowLayout('buildClothRig_rowLayout', nc=2, cw2=[275, 30], adjustableColumn=1)
		cmds.text('Build Cloth Rig', h=16, bgc=(.22,.22,.22), al='center', fn="boldLabelFont")

		cmds.columnLayout('pasteFrom_columnLayout', adj=1, cat=['right', 0], p='buildClothRig_frameLayout')
		cmds.rowLayout('pasteFrom_rowLayout', nc=3, adj=1)
		cmds.text('Joints:', al='left', p='pasteFrom_rowLayout')
		cmds.iconTextButton(w=30, image1='nudgeDown.png', ann='Click here to add the selected objects into the list.', c=partial(self.addObjs, 'joints_scrollList'), p='pasteFrom_rowLayout')
		cmds.iconTextButton(w=25, image1='SP_TrashIcon.png', ann='Click here to DELETE objects from the list.', c=partial(self.delObjs, 'joints_scrollList'), p='pasteFrom_rowLayout')
		cmds.textScrollList('joints_scrollList', allowMultiSelection=True, h=80, w=195, p='pasteFrom_columnLayout')

		cmds.rowLayout('buildCloth_rowLayout', nc=3, adjustableColumn=3, p='buildClothRig_frameLayout')
		cmds.optionMenu('baseGeo_list', label='Proxy Geometry:', w=172)
		self.feedOptionMenu('baseGeo')

		cmds.text(' ')
		cmds.button(l='Build Cloth Rig', h=20, bgc=(.6, .5, .9), c=self.buildClothRig)
		cmds.separator(st='none', h=5, p='buildClothRig_frameLayout')

		### SETTINGS
		cmds.frameLayout('settings_frameLayout', lv=False, bv=False, p='clothChain_frameLayout')
		cmds.text('Settings', h=16, bgc=(.22,.22,.22), al='center', fn="boldLabelFont", p='settings_frameLayout')

		cmds.rowLayout('buildClothRig_rowLayout3', nc=8, p='settings_frameLayout')
		cmds.text('Gravity:')
		cmds.textField('gravity_textField', w=40, alwaysInvokeEnterCommandOnReturn=True, ec=partial(self.nucleusChange, 'gravity'))
		cmds.text(' Start Frame:', al='left',)
		cmds.textField('startFrame_textField', w=40, alwaysInvokeEnterCommandOnReturn=True, ec=partial(self.nucleusChange, 'startFrame'))
		cmds.text(' Time Scale:')
		cmds.textField('timeScale_textField', w=40, alwaysInvokeEnterCommandOnReturn=True, ec=partial(self.nucleusChange, 'timeScale'))
		cmds.text(' Space Scale:')
		cmds.textField('spaceScale_textField', w=40, alwaysInvokeEnterCommandOnReturn=True, ec=partial(self.nucleusChange, 'spaceScale'))

		cmds.rowLayout('collider_rowLayout', adj=1, nc=4, p='settings_frameLayout')
		cmds.optionMenu('colliders_list', label='Colliders:', w=190, cc=self.loadSettings)
		cmds.iconTextButton(w=30, image1='nudgeLeft.png', ann='Click here to add the selected objects into the collider list.', c=self.addColliderObjs)
		cmds.iconTextButton(w=25, image1='SP_TrashIcon.png', ann='Click here to DELETE objects from the collider list.', c=self.delColliderObjs)

		cmds.rowLayout('collider_rowLayout2', nc=2, adjustableColumn=2, p='collider_rowLayout')
		cmds.text('Collision Thickness:')
		cmds.textField('colliderColThickness_textField', w=40, alwaysInvokeEnterCommandOnReturn=True, ec=self.colliderCollisionThickness)

		cmds.text('Cloth Rig Settings:', fn="boldLabelFont", p='settings_frameLayout')

		cmds.rowLayout('clothRigSettings_rowLayout', adj=1, nc=5, cw1=200, p='settings_frameLayout')
		cmds.optionMenu('clothRig_list', label='Cloth Rig:', w=200, cc=self.loadSettings)
		cmds.checkBox('clothRig_checkBox', bgc=(.2,.4,.2), v=True, l='On ', onc=self.clothRigState, ofc=self.clothRigState)
		cmds.text('  ')
		cmds.button('segmentStregth_button', l='Set Influence', w=100, p='clothRigSettings_rowLayout', c=self.segmentOffsetUI)
		cmds.button('presets_list', label='Presets*', w=70, p='clothRigSettings_rowLayout')
		cmds.popupMenu('presets_popupMenu', b=1)
		for i in self.presetsList:
			cmds.menuItem(i + '_preset', label=i, c=partial(self.loadPreset, i))

		cmds.paneLayout('pane_layout2', cn='vertical2', p='settings_frameLayout')
		cmds.columnLayout('clothRigSettings_columnLayout', adj=1, cat=['right', 0], p='pane_layout2')
		for nm, label in [('bounce','Bounce'),('friction','Friction'),('damp','Damp'),('stickiness','Stickiness'),('pointMass','Point Mass')]:
			row = 'row_'+nm
			cmds.rowLayout(row, h=19, nc=2, p='clothRigSettings_columnLayout')
			cmds.textField(nm+'_textField', w=55, h=18, alwaysInvokeEnterCommandOnReturn=True, ec=partial(self.applyClothSettings, nm))
			cmds.text(label)

		cmds.columnLayout('clothRigSettings_columnLayout2', adj=1, cat=['right', 0], p='pane_layout2')
		for nm, label in [('stretchResistance','Stretch Resistance'),('compressionResistance','Compression Resistance'),('bendResistance','Bend Resistance'),('rigidity','Rigidity'),('stretchDamp','Stretch Damp')]:
			row = 'row_'+nm
			cmds.rowLayout(row, h=19, nc=2, p='clothRigSettings_columnLayout2')
			cmds.textField(nm+'_textField', w=55, h=18, alwaysInvokeEnterCommandOnReturn=True, ec=partial(self.applyClothSettings, nm))
			cmds.text(label)

		self.feedOptionMenu('clothRig')

		cmds.rowLayout('buildClothRig_rowLayout2', nc=3, adjustableColumn=2, p='settings_frameLayout')
		cmds.text('Collision Thickness:')
		cmds.floatSliderGrp('colThickness_slider',  f=True, min=0.1, max=10, value=1, step=.1, dc=self.collisionThicknessSlider)
		cmds.frameLayout('settings_frameLayout2', lv=False, bv=False, p='buildClothRig_rowLayout2')
		cmds.palettePort('palette', dim=(1, 1), ed=True, ced=True, rgb=[0, 1, .8, 0], ce=self.collisionThicknessColor)

		### PREVIEW AND BAKE
		cmds.separator(st='none', h=5, p='settings_frameLayout')
		cmds.frameLayout('preview_frameLayout', lv=False, bv=False, p='settings_frameLayout')
		cmds.text('Preview and Bake', h=16, bgc=(.22,.22,.22), al='center', fn="boldLabelFont", p='preview_frameLayout')

		cmds.columnLayout('copyFrom_columnLayout', adj=1, cat=['left', 0], p='preview_frameLayout')
		cmds.rowLayout('copyFrom_rowLayout', nc=3, adj=1)
		cmds.text('Controls: ', al='left', p='copyFrom_rowLayout')
		cmds.iconTextButton(w=30, image1='nudgeDown.png', ann='Click here to add the selected objects into the list.', c=partial(self.addObjs, 'controls_scrollList'), p='copyFrom_rowLayout')
		cmds.iconTextButton(w=25, image1='SP_TrashIcon.png', ann='Click here to DELETE objects from the list.', c=partial(self.delObjs, 'controls_scrollList'), p='copyFrom_rowLayout')
		cmds.textScrollList('controls_scrollList', allowMultiSelection=True, h=80, w=195, p='copyFrom_columnLayout')

		cmds.rowLayout('rigSimSwitch_rowLayout', nc=2, adjustableColumn=1, p='preview_frameLayout')
		cmds.button(l='Preview on Rig', bgc=(.8,.8,.6), c=self.previewSim)
		cmds.button('undo_button', l='Undo Preview', w=210, bgc=(.2,.2,.2), en=False, c=self.undoPreview)

		cmds.frameLayout('transferSim_frameLayout', lv=False, bv=False, p='clothChain_frameLayout')
		cmds.separator(st='none')
		cmds.separator(st='in')
		cmds.rowLayout('transferSim_rowLayout', nc=7, adjustableColumn=5, p='transferSim_frameLayout')
		cmds.checkBox('bakeOnAnimLayer_checkBox', l='Create AnimLayer')
		cmds.text(' Sample by:')
		cmds.textField('sampleByValue_textField', tx='1', w=35)
		cmds.text(' ')
		cmds.button(l='Bake!', bgc=(.3, .5, .3), c=self.bakeFinalSim)
		cmds.text(' ')
		cmds.checkBox('deleteClothRig_checkBox', l='Delete Cloth Rig?')

		if parent == 'clothChain_mainWindow':
			cmds.showWindow("clothChain_mainWindow")

		if cmds.objExists('clothSimChain_grp'): 
			self.loadSettings()
		elif cmds.objExists('allBaseGeo_grp'):
			cmds.frameLayout('settings_frameLayout', e=True, en=False)
			cmds.frameLayout('transferSim_frameLayout', e=True, en=False)
		else:
			cmds.frameLayout('buildClothRig_frameLayout', e=True, en=False)
			cmds.frameLayout('settings_frameLayout', e=True, en=False)
			cmds.frameLayout('transferSim_frameLayout', e=True, en=False)

	def segmentOffsetUI(self, *args):
		clothRigName = cmds.optionMenu('clothRig_list', q=True, v=True)
		if cmds.window("segmentOffset_window", exists=True):
			cmds.deleteUI("segmentOffset_window")
		cmds.window("segmentOffset_window", tlb=1, sizeable=True, mxb=False, title="Set Influence")
		cmds.frameLayout('segmentOffset_frameLayout', bv=False, lv=False, mw=7, mh=7)
		cmds.text('clothRig_text', l='Cloth Rig: ' + clothRigName, h=16, bgc=(.22,.22,.22), al='center', fn="boldLabelFont", p='segmentOffset_frameLayout')

		cmds.rowColumnLayout('segmentOffset_rowColumnLayout', numberOfColumns=3, p='segmentOffset_frameLayout')
		cmds.rowLayout('options_rowLayout2', nc=4, p='segmentOffset_frameLayout')
		cmds.text('Multiply by: ')
		cmds.textField('multiply_textField', ec=self.multiplyStrength, alwaysInvokeEnterCommandOnReturn=True, w=33)
		cmds.separator(style='in', w=10, h=20, hr=False)
		cmds.iconTextButton('Invert', w=22, h=18, image1='invertSelection.png', ann='Invert values', c=self.invertSegmentOffset)

		cmds.showWindow("segmentOffset_window")
		cmds.window('segmentOffset_window', e=True, w=40, h=40)
		self.loadSegmentsList()
		# Keep your existing job target (module name) the same as the file’s module name
		cmds.scriptJob(e=["timeChanged", scriptJobFunction], p="segmentOffset_window")

	def invertSegmentOffset(self, *args):
		clothRigName = cmds.text('clothRig_text', q=True, l=True).partition(': ')[2]
		values = []
		for i in cmds.listRelatives(clothRigName + '_nCloth_grp') or []:
			if 'dynamicConstraint' in i:
				textFieldName = 'segment_' + i.partition('dynamicConstraint')[2] + '_textField'
				textFieldValue = cmds.textField(textFieldName, q=True, tx=True)
				values.append(textFieldValue)
		for i in range(len(values)):
			textFieldName = 'segment_' + str(i + 1) + '_textField'
			cmds.textField(textFieldName, e=True, tx=values[((i + 1) * -1)])
			cmds.setAttr(clothRigName + '_dynamicConstraint' + str(i + 1) + '.str', float(values[((i + 1) * -1)]))

	def discreteDropoffUI(self, controlsList, *args):
		clothRigName = cmds.optionMenu('clothRig_list', q=True, v=True)
		if cmds.window("discreteDropoff_window", exists=True):
			cmds.deleteUI("discreteDropoff_window")
		cmds.window("discreteDropoff_window", tlb=1, sizeable=True, mxb=False, title="Discrete Falloff")
		cmds.frameLayout('discreteDropoff_frameLayout', bv=False, lv=False, mw=7, mh=7)
		cmds.rowLayout('clothRigName_rowLayout', nc=2, p='discreteDropoff_frameLayout')
		cmds.text('Cloth Rig: ')
		cmds.text('clothRig', l=clothRigName, fn="boldLabelFont")
		cmds.rowColumnLayout('discreteDropoff_rowColumnLayout', numberOfColumns=2, p='discreteDropoff_frameLayout')
		cmds.showWindow("discreteDropoff_window")
		cmds.window('discreteDropoff_window', e=True, w=40, h=40)
		self.loadDiscreteList(controlsList)
		cmds.scriptJob(e=["timeChanged", partial(scriptJobFunction2, controlsList)], p='discreteDropoff_window')

	def loadSegmentsList(self, *args):
		clothRigName = cmds.optionMenu('clothRig_list', q=True, v=True)
		for i in cmds.listRelatives(clothRigName + '_nCloth_grp') or []:
			if 'dynamicConstraint' in i:
				cmds.text('Influence ' + i.partition('dynamicConstraint')[2] + '  ', p='segmentOffset_rowColumnLayout')
				value = "%.3f" % cmds.getAttr(clothRigName + '_dynamicConstraintShape' + i.partition('dynamicConstraint')[2] + '.strength')
				cmds.textField('segment_' + i.partition('dynamicConstraint')[2] + '_textField', w=50, bgc=(.15,.15,.15), tx=value, alwaysInvokeEnterCommandOnReturn=True, ec=partial(self.applyStrength, i.partition('dynamicConstraint')[2]), p='segmentOffset_rowColumnLayout')
				if cmds.keyframe(clothRigName + '_dynamicConstraint' + i.partition('dynamicConstraint')[2], q=True, kc=True) == 0:
					cmds.iconTextButton('keyframe_button' + i.partition('dynamicConstraint')[2], w=20, h=20,style='iconOnly', image1='autoKeyframeOff.png', c=partial(self.dynConstraintKey, i.partition('dynamicConstraint')[2]), p='segmentOffset_rowColumnLayout')
				else:
					cmds.iconTextButton('keyframe_button' + i.partition('dynamicConstraint')[2], w=20, h=20,style='iconOnly', image1='autoKeyframeOn.png', c=partial(self.dynConstraintKey, i.partition('dynamicConstraint')[2]), p='segmentOffset_rowColumnLayout')
				cmds.popupMenu('segmentKeyframe_popupMenu')
				cmds.menuItem('Select', c=partial(self.selectDynConstraint, clothRigName + '_dynamicConstraint' + i.partition('dynamicConstraint')[2], 'no'))
				cmds.menuItem('Select all', c=partial(self.selectDynConstraint, clothRigName + '_dynamicConstraint' + i.partition('dynamicConstraint')[2], 'yes'))
				cmds.menuItem('Delete keys')
				currTime = cmds.currentTime(q=True)
				try:
					keys = cmds.keyframe(clothRigName + '_dynamicConstraintShape' + i.rpartition('dynamicConstraint')[2], q=True) or []
					if currTime in keys:
						cmds.textField('segment_' + i.rpartition('dynamicConstraint')[2] + '_textField', e=True, bgc=(.85, .4, .4))
				except TypeError:
					pass

	def loadDiscreteList(self, controlsList, *args):
		clothRigName = cmds.optionMenu('clothRig_list', q=True, v=True)
		for i in controlsList or []:
			cmds.rowLayout(i + 'previewSettings_rowLayout', nc=2, adjustableColumn=2, p='discreteDropoff_rowColumnLayout')
			value = "%.2f" % cmds.getAttr(i + '.blendParent1')
			cmds.textField(i + '_textField', w=50, tx=value, ec=partial(self.applyBlendparent, i))
			cmds.text(i, al='left')
			if cmds.keyframe(i + '.blendParent1', q=True, kc=True) == 0:
			  	cmds.iconTextButton('keyframe_button' + i, w=20, h=20,style='iconOnly', image1='autoKeyframeOff.png', c=partial(self.blenParentKey, i), p='discreteDropoff_rowColumnLayout')
			else:
				cmds.iconTextButton('keyframe_button' + i, w=20, h=20,style='iconOnly', image1='autoKeyframeOn.png', c=partial(self.blenParentKey, i), p='discreteDropoff_rowColumnLayout')
			cmds.popupMenu('fallOffSettings_popupMenu')
			cmds.menuItem('Select', c='cmds.select(%s, r=True)' % i)

	def addObjs(self, scrollListName, *args):
		allObjects = cmds.ls(sl=True) or []
		try:
			for i in allObjects:
				existing = cmds.textScrollList(scrollListName, q=True, ai=True) or []
				if i in existing:
					cmds.warning('Object ' + str(i) + ' already in the list.')
				else:
					cmds.textScrollList(scrollListName, e=True, append=i)
		except Exception:
			if allObjects:
				cmds.textScrollList(scrollListName, e=True, append=allObjects)

	def delObjs(self, scrollListName, *args):
		itemToDelete = cmds.textScrollList(scrollListName, q=True, si=True) or []
		if itemToDelete:
			cmds.textScrollList(scrollListName, e=True, ri=itemToDelete)

	def addColliderObjs(self, *args):
		sel_list = cmds.ls(sl=True) or []
		if not sel_list:
			cmds.warning('Select a collider object first.')
			return
		sel = sel_list[0]
		if cmds.objExists('passiveColliders_grp'):
			try:
				ils = cmds.optionMenu('colliders_list', q=True, ils=True) or []
				if sel + '_collider' in ils:
					cmds.warning('Object ' + sel + ' already in the list.')
				else:
					cmds.menuItem(sel + '_collider', label=sel, p='colliders_list')
					mel.eval("makeCollideNCloth;")
					nRigidShape = cmds.ls(sl=True)[0]  # nRigidShape
					nRigidObj = nRigidShape.replace('nRigidShape', 'nRigid')
					cmds.parent(nRigidObj, 'passiveColliders_grp')
					cmds.rename(sel + '_' + nRigidObj)
			except Exception:
				cmds.menuItem(sel + '_collider', label=sel, p='colliders_list')
				mel.eval("makeCollideNCloth;")
				nRigidShape = cmds.ls(sl=True)[0]
				nRigidObj = nRigidShape.replace('nRigidShape', 'nRigid')
				cmds.parent(nRigidObj, 'passiveColliders_grp')
				cmds.rename(sel + '_' + nRigidObj)

			cmds.optionMenu('colliders_list', e=True, v=sel)
			colliderObj = cmds.optionMenu('colliders_list', q=True, v=True)
			thickValue = "%.2f" % cmds.getAttr(colliderObj + '_nRigidShape1.thickness') 
			cmds.textField('colliderColThickness_textField', e=True, tx=thickValue)
		else:
			cmds.warning('Create a Cloth Rig first.')

	def delColliderObjs(self, *args):
		try:
			itemToDelete = cmds.optionMenu('colliders_list', q=True, v=True)
			if itemToDelete:
				cmds.deleteUI(itemToDelete + '_collider')
				for i in cmds.listRelatives('passiveColliders_grp') or []:
					if itemToDelete in i:
						cmds.delete(i)
				if cmds.listRelatives('passiveColliders_grp', ad=True) is None:
					cmds.textField('colliderColThickness_textField', e=True, tx='')
				else:
					colliderObj = cmds.optionMenu('colliders_list', q=True, v=True)
					thickValue = "%.2f" % cmds.getAttr(colliderObj + '_nRigidShape1.thickness') 
					cmds.textField('colliderColThickness_textField', e=True, tx=thickValue)
		except Exception:
			pass

	def cacheCheck(self, name, *args):
		return cmds.objExists(name + '_bsGeoShapeCache1')

	def cacheCheckUI(self, *args):
		clothRigName = cmds.optionMenu('clothRig_list', q=True, v=True)
		if cmds.objExists(clothRigName + '_preview_grp'):
			controlsList = []
			for i in cmds.listAttr(clothRigName + '_controlNames') or []:
				if len(i) <= 3:
					controlsList.append(cmds.getAttr(clothRigName + '_controlNames.' + i))
			if not cmds.columnLayout('previewSettings_columnLayout', exists=True):
				cmds.columnLayout('previewSettings_columnLayout', adjustableColumn=1, p='settings_frameLayout')
				cmds.text('Dropoff Settings:', fn="boldLabelFont")
				cmds.rowLayout('previewSettings_rowLayout', nc=3, adjustableColumn=2)
				cmds.text('Overall Dropoff:')
				cmds.floatSliderGrp('dropoff_slider', f=True, w=100, min=0, max=1, value=1, step=.1, dc=self.overAllDropoff)
				cmds.button('singleDropoff_button', l='Discrete Dropoff', c=partial(self.discreteDropoffUI, controlsList))
				self.cacheCheckUI(clothRigName)
				cmds.setAttr(clothRigName + '_nCloth_grp.visibility', 0)

			if cmds.textScrollList('controls_scrollList', q=True, ai=True) is None:
				cmds.textScrollList('controls_scrollList', e=True, append=controlsList)
			cmds.button('undo_button', l='Undo Preview', e=True, en=True)
			cmds.button('segmentStregth_button', e=True, en=False)
			cmds.button('presets_list', e=True, en=False)
			cmds.checkBox('clothRig_checkBox', e=True, en=False)
			cmds.paneLayout('pane_layout2', e=True, en=False)
			cmds.rowLayout('buildClothRig_rowLayout2', e=True, en=False)
		else:
			if cmds.columnLayout('previewSettings_columnLayout', exists=True):
				cmds.deleteUI('previewSettings_columnLayout')
			cmds.button('undo_button', l='Undo Preview', e=True, en=False)
			cmds.button('segmentStregth_button', e=True, en=True)
			cmds.button('presets_list', e=True, en=True)
			cmds.checkBox('clothRig_checkBox', e=True, en=True)
			cmds.paneLayout('pane_layout2', e=True, en=True)
			cmds.rowLayout('buildClothRig_rowLayout2', e=True, en=True)

	def clothRigState(self, *args):
		clothRigName = cmds.optionMenu('clothRig_list', q=True, v=True)
		value = cmds.checkBox('clothRig_checkBox', q=True, v=True)
		if value == 0:
			cmds.checkBox('clothRig_checkBox', e=True, bgc=(.4,.2,.2), l='Off ')
			cmds.setAttr(clothRigName + '_nClothShape1.isDynamic', 0)
		if value == 1:
			cmds.checkBox('clothRig_checkBox', e=True, bgc=(.2,.4,.2), l='On ')
			cmds.setAttr(clothRigName + '_nClothShape1.isDynamic', 1)

	def loadNclothSettings(self, *args):
		clothRigName = cmds.optionMenu('clothRig_list', q=True, v=True)
		for i in self.nClothSettingsName:
			value = "%.2f" % cmds.getAttr(clothRigName + '_nClothShape1.' + i)
			cmds.textField(i + '_textField', e=True, tx=value)

	def createBaseGeo(self, *args):
		raw = cmds.textField('clothRigName_textField', q=True, tx=True)
		objName = (raw or '').replace(' ', '_')
		try:
			cmds.frameLayout('buildClothRig_frameLayout', e=True, en=True)
			if not cmds.objExists('allBaseGeo_grp'):
				cmds.group(empty=True, name='allBaseGeo_grp')

			segmentsNumber = int(cmds.textField('numSegments_textField', q=True, tx=True))
			cmds.group(empty=True, name=objName + '_baseGeo_grp')
			cmds.polyPlane(n=objName + '_baseGeo', w=5, h=15, sy=segmentsNumber, sx=1)

			cmds.setAttr(objName + '_baseGeoShape.overrideEnabled', 1)
			cmds.setAttr(objName + '_baseGeoShape.overrideDisplayType', 2)

			cmds.parent(objName + '_baseGeo', objName + '_baseGeo_grp')
			cmds.setAttr(objName + '_baseGeo.rotateX', 90)

			self.vtxGrpList = []
			for i in range(0, (segmentsNumber + 1) * 2, 2):
				self.vtxGrpList.append(objName + '_baseGeo.vtx[%s:%s]' % (i, i + 1))

			cmds.circle(n=objName + '_main_CTRL', nr=[0, 1, 0], r=4)
			cmds.parent(objName + '_main_CTRL', objName + '_baseGeo_grp')

			for i in range(len(self.vtxGrpList)):
				cmds.select(cl=True)
				cmds.select(self.vtxGrpList[i], add=True)
				clusterObj = cmds.cluster(n=objName + '_cluster_%s_' % str(i), envelope=1)
				cmds.group(n=objName + '_cluster_%s_grp' % str(i))
				cmds.parent(objName + '_cluster_%s_grp' % str(i), objName + '_baseGeo_grp')
				curveObj = cmds.curve(n=objName + '_shape_%s_CTRL' % str(i), d=1, p=[(3, 0, 1), (3, 0, -1), (-3, 0, -1), (-3, 0, 1), (3, 0, 1)])
				cmds.parent(objName + '_shape_%s_CTRL' % str(i), objName + '_main_CTRL')
				cmds.parentConstraint(clusterObj, curveObj, n='cluster%s_parentConstraint1' % str(i))
			cmds.delete('cluster*_parentConstraint1')

			for i in range(segmentsNumber + 1):
				cmds.select(objName + '_shape_%s_CTRL' % str(i), r=True)
				mel.eval("channelBoxCommand -freezeTranslate;")
				cmds.parentConstraint(objName + '_shape_%s_CTRL' % str(i), objName + '_cluster_%s_Handle' % str(i))
				cmds.scaleConstraint(objName + '_shape_%s_CTRL' % str(i), objName + '_cluster_%s_Handle' % str(i))
				cmds.setAttr(objName + '_cluster_%s_Handle.visibility' % str(i), 0)

			self.feedOptionMenu('baseGeo')
			cmds.parent(objName + '_baseGeo_grp', 'allBaseGeo_grp')
			cmds.select(objName + '_main_CTRL', r=True)
		except TypeError:
			cmds.warning('Add controls into field first.')

	def buildClothRig(self, *args):
		clothRigName = cmds.optionMenu('baseGeo_list', q=True, v=True)
		jointsSelected = cmds.textScrollList('joints_scrollList', q=True, ai=True)
		start_fr = int(cmds.playbackOptions(q=True, minTime=True))

		if cmds.objExists(clothRigName + '_clothRig_grp'):
			cmds.warning('Cloth Rig already exists.')
			return

		if cmds.textScrollList('joints_scrollList', q=True, ai=True) is None:
			cmds.warning('Add joints first.')
			return

		cmds.frameLayout('settings_frameLayout', e=True, en=True)
		cmds.frameLayout('transferSim_frameLayout', e=True, en=True)

		if not cmds.objExists('clothSimChain_grp'):
			cmds.group(empty=True, name='clothSimChain_grp')
			cmds.group(empty=True, name='passiveColliders_grp', p='clothSimChain_grp')

		cmds.group(empty=True, name=clothRigName + '_clothRig_grp', p='clothSimChain_grp')
		cmds.group(empty=True, name=clothRigName + '_geo_grp', p=clothRigName + '_clothRig_grp')
		cmds.group(empty=True, name=clothRigName + '_nCloth_grp', p=clothRigName + '_clothRig_grp')
		cmds.group(empty=True, name=clothRigName + '_follicles_grp', p=clothRigName + '_clothRig_grp')
				
		cmds.duplicate(clothRigName + '_baseGeo', n=clothRigName + '_skinGeo')
		cmds.parent(clothRigName + '_skinGeo', clothRigName + '_geo_grp')
		cmds.duplicate(clothRigName + '_baseGeo', n=clothRigName + '_simGeo')
		cmds.parent(clothRigName + '_simGeo', clothRigName + '_geo_grp')
		cmds.duplicate(clothRigName + '_baseGeo', n=clothRigName + '_bsGeo')
		cmds.parent(clothRigName + '_bsGeo', clothRigName + '_geo_grp')

		cmds.select(clothRigName + '_simGeo', r=True)
		mel.eval("createNCloth 0")
		cmds.rename('nCloth1', clothRigName + '_nCloth1')
		cmds.parent(clothRigName + '_nCloth1', clothRigName + '_nCloth_grp')
		nucleus_node = (cmds.listConnections(clothRigName + '_nClothShape1', type='nucleus') or ['nucleus1'])[0]
		cmds.parent(nucleus_node, clothRigName + '_nCloth_grp')

		for idx in range(len(self.nClothSettingsName)):
			cmds.setAttr(clothRigName + '_nClothShape1.' + self.nClothSettingsName[idx], self.customPreset[idx])

		cmds.setAttr(clothRigName + '_nClothShape1.solverDisplay', 1)

		cmds.select(jointsSelected, r=True)
		cmds.select(clothRigName + '_skinGeo', add=True)
		cmds.skinCluster(jointsSelected, clothRigName + '_skinGeo', tsb=True)

		segmentsNumber = len(cmds.listRelatives(clothRigName + '_main_CTRL') or []) - 2
		self.vtxGrpList = []
		for i in range(0, (segmentsNumber + 1) * 2, 2):
			self.vtxGrpList.append(clothRigName + '_skinGeo.vtx[%s:%s]' % (i, i + 1))

		for i in self.vtxGrpList:
			skinVertex = i
			simVertex = i.replace('_skinGeo', '_simGeo')
			cmds.select(skinVertex, r=True)
			cmds.select(simVertex, add=True)
			mel.eval("createNConstraint pointToPoint 0;")

		cmds.rename('nRigid1', clothRigName +'_nRigid1')
		cmds.parent(clothRigName +'_nRigid1', clothRigName + '_nCloth_grp')
		for i in cmds.ls(typ='dynamicConstraint') or []:
			if not '_' in i:
				dynConstName = i.split('Shape')[0] + i.split('Shape')[1]
				cmds.rename(dynConstName, clothRigName + '_' + dynConstName)
				cmds.parent(clothRigName + '_' + dynConstName, clothRigName + '_nCloth_grp')
				cmds.setAttr(clothRigName + '_' + dynConstName + '.visibility', 0)

		cmds.blendShape(clothRigName + '_simGeo', clothRigName + '_bsGeo', origin='world')
		blendshapeNode = cmds.ls(cmds.listHistory(clothRigName + '_bsGeo'), type='blendShape')[0]
		cmds.rename(blendshapeNode, clothRigName + '_' + blendshapeNode)
		cmds.setAttr(clothRigName + '_' + blendshapeNode + '.%s_simGeo' % clothRigName, 1)

		self.createFollicles()

		# Delete only the base Geo group/node (use cmds.delete, not deleteUI)
		if cmds.objExists(clothRigName + '_baseGeo_grp'):
			cmds.delete(clothRigName + '_baseGeo_grp')
		if cmds.objExists('allBaseGeo_grp') and (cmds.listRelatives('allBaseGeo_grp') is None):
			cmds.delete('allBaseGeo_grp')

		cmds.menuItem(clothRigName + '_clothRig', label=clothRigName, p='clothRig_list')
		cmds.optionMenu('clothRig_list', e=True, v=clothRigName)

		cmds.setAttr(nucleus_node + '.startFrame', start_fr)
		cmds.setAttr(nucleus_node + '.timeScale', 1.5)
		cmds.setAttr(nucleus_node + '.spaceScale', 1.5)

		self.loadSettings()

		constraintNodesList = []
		for i in cmds.listRelatives(clothRigName + '_nCloth_grp') or []:
			if 'dynamicConstraint' in i:
				constraintNodesList.append(i)

		for i in constraintNodesList:
			if i == constraintNodesList[0]:
				cmds.setAttr(i + '.strength', 0.9)
			elif i == constraintNodesList[-1]:
				cmds.setAttr(i + '.strength', 0.01)
			else:
				cmds.setAttr(i + '.strength', (1.0 / float(i.rpartition('dynamicConstraint')[2])) * .1)

		cmds.textScrollList('joints_scrollList', e=True, ra=True)
		cmds.textScrollList('controls_scrollList', e=True, ra=True)
		cmds.setAttr(clothRigName + '_follicles_grp.visibility', 0)

	def feedOptionMenu(self, mode, *args):
		items = cmds.optionMenu(mode + '_list', q=True, ils=True)
		if items is not None:
			for i in cmds.ls('*_' + mode + '_grp', type='transform'):
				name = i.partition(mode + '_grp')[0]
				if name not in items:
					cmds.menuItem(name + mode, label=name[:-1], p=mode + '_list')
		else:
			for i in cmds.ls('*_' + mode + '_grp', type='transform'):
				name = i.partition(mode + '_grp')[0]
				cmds.menuItem(name + mode, label=name[:-1], p=mode + '_list')

	def loadPreset(self, presetOption, *args):
		clothRigName = cmds.optionMenu('clothRig_list', q=True, v=True)
		location = os.environ.get("MAYA_LOCATION", "")
		if presetOption != 'custom':
			mel.eval('''applyPresetToNode "%s_nClothShape1" "" "" "%s/presets/attrPresets/nCloth/%s.mel" 1;''' % (clothRigName, location, presetOption))
			cmds.setAttr(clothRigName + '_nClothShape1.solverDisplay', 1)
			self.loadNclothSettings()
		else:
			for idx in range(len(self.nClothSettingsName)):
				cmds.setAttr(clothRigName + '_nClothShape1.' + self.nClothSettingsName[idx], self.customPreset[idx])
			cmds.setAttr(clothRigName + '_nClothShape1.tangentialDrag', 0)
			cmds.setAttr(clothRigName + '_nClothShape1.bendAngleDropoff', 0)
			cmds.setAttr(clothRigName + '_nClothShape1.scalingRelation', 0)
			cmds.setAttr(clothRigName + '_nClothShape1.restLengthScale', 1)
			self.loadNclothSettings()

	def loadSettings(self, *args):
		clothRigName = cmds.optionMenu('clothRig_list', q=True, v=True)
		nucleus = self._get_nucleus(clothRigName)
		if nucleus:
			gravity =  "%.2f" % cmds.getAttr(nucleus + '.gravity')
			startFrame = cmds.getAttr(nucleus + '.startFrame')
			timeScale = "%.2f" % cmds.getAttr(nucleus + '.timeScale')
			spaceScale = "%.2f" % cmds.getAttr(nucleus + '.spaceScale')
			cmds.textField('gravity_textField', e=True, tx=gravity)
			cmds.textField('startFrame_textField', e=True, tx=str(startFrame))
			cmds.textField('timeScale_textField', e=True, tx=timeScale)
			cmds.textField('spaceScale_textField', e=True, tx=spaceScale)

		if cmds.objExists(clothRigName + '_nClothShape1'):
			colThickness = cmds.getAttr(clothRigName + '_nClothShape1.thickness')
			colThicknessColor = cmds.getAttr(clothRigName + '_nClothShape1.displayColor')[0]
			cmds.floatSliderGrp('colThickness_slider', e=True, v=colThickness)
			cmds.palettePort('palette', e=True, rgb=[0, colThicknessColor[0], colThicknessColor[1], colThicknessColor[2]], redraw=True)

			isDynamicValue = cmds.getAttr(clothRigName + '_nClothShape1.isDynamic')
			if isDynamicValue == 0:
				cmds.checkBox('clothRig_checkBox', e=True, bgc=(.4,.2,.2), l='Off ')
				cmds.setAttr(clothRigName + '_nClothShape1.isDynamic', 0)
				cmds.checkBox('clothRig_checkBox', e=True, v=0)
			else:
				cmds.checkBox('clothRig_checkBox', e=True, bgc=(.2,.4,.2), l='On ')
				cmds.setAttr(clothRigName + '_nClothShape1.isDynamic', 1)
				cmds.checkBox('clothRig_checkBox', e=True, v=1)

			if cmds.listRelatives('passiveColliders_grp', ad=True) is not None:
				for i in cmds.listRelatives('passiveColliders_grp') or []:
					ils = cmds.optionMenu('colliders_list', q=True, ils=True) or []
					if not ils or (i.rpartition('_')[0] + '_collider') not in ils:
						cmds.menuItem(i.rpartition('_')[0] + '_collider', l=i.rpartition('_')[0], p='colliders_list')
				colliderObj = cmds.optionMenu('colliders_list', q=True, v=True)
				if colliderObj:
					thickValue = "%.2f" % cmds.getAttr(colliderObj + '_nRigidShape1.thickness') 
					cmds.textField('colliderColThickness_textField', e=True, tx=thickValue)

			self.loadNclothSettings()
			self.cacheCheckUI(clothRigName)

	def colliderCollisionThickness(self, *args):
		colliderObj = cmds.optionMenu('colliders_list', q=True, v=True)
		value = float(cmds.textField('colliderColThickness_textField', q=True, tx=True))
		cmds.setAttr(colliderObj + '_nRigidShape1.thickness', value)

	def collisionThicknessSlider(self, *args):
		clothRigName = cmds.optionMenu('clothRig_list', q=True, v=True)
		value = cmds.floatSliderGrp('colThickness_slider', q=True, v=True)
		cmds.setAttr(clothRigName + '_nClothShape1.thickness', value)

	def collisionThicknessColor(self, *args):
		clothRigName = cmds.optionMenu('clothRig_list', q=True, v=True)
		color = cmds.palettePort('palette', q=True, rgb=True)
		mel.eval('''setAttr "%s_nClothShape1.displayColor" -type double3 %s %s %s ;''' % (clothRigName, str(color[0]), str(color[1]), str(color[2])))

	def createFollicles(self, *args):
		clothRigName = cmds.optionMenu('baseGeo_list', q=True, v=True)
		segmentsNumber = len(cmds.listRelatives(clothRigName + '_main_CTRL') or []) - 2
		for i in range(0, (segmentsNumber + 1) * 2, 2):
			cmds.createNode('follicle', n=clothRigName + '_fol' + str(i) + 'Shape')
			cmds.connectAttr(clothRigName + '_bsGeoShape.worldMatrix[0]', clothRigName + '_fol' + str(i) + 'Shape.inputWorldMatrix')
			cmds.connectAttr(clothRigName + '_bsGeoShape.outMesh', clothRigName + '_fol' + str(i) + 'Shape.inputMesh')
			cmds.connectAttr(clothRigName + '_fol' + str(i) + 'Shape.outTranslate', clothRigName + '_fol' + str(i) + '.translate')
			cmds.connectAttr(clothRigName + '_fol' + str(i) + 'Shape.outRotate', clothRigName + '_fol' + str(i) + '.rotate')
			cmds.setAttr(clothRigName + '_fol' + str(i) + 'Shape.parameterU', .5)
			cmds.parent(clothRigName + '_fol' + str(i), clothRigName + '_follicles_grp')

		for i in range(segmentsNumber + 1):
			vtx_i = i * 2
			cmds.setAttr(clothRigName + '_fol' + str(vtx_i) + 'Shape.parameterV', i * (1.0 / float(segmentsNumber)))

	def previewSim(self, *args):
		clothRigName = cmds.optionMenu('clothRig_list', q=True, v=True)
		start_fr = int(cmds.playbackOptions(q=True, minTime=True))
		end_fr = int(cmds.playbackOptions(q=True, maxTime=True))
		cmds.currentTime(start_fr)

		if not cmds.objExists(clothRigName + '_preview_grp'):
			self.controlsList = cmds.textScrollList('controls_scrollList', q=True, ai=True)
			if self.controlsList is None:
				cmds.warning('Add controls first.')
				return

			cmds.group(empty=True, name=clothRigName + '_preview_grp', p=clothRigName + '_clothRig_grp')

			controlDic = {}
			for i in self.controlsList:
				controlDic[i] = cmds.xform(i, q=True, ws=True, piv=True)[:3]

			folliclesDic = {}
			for i in cmds.listRelatives(clothRigName + '_follicles_grp') or []:
				folliclesDic[i] = cmds.xform(i, q=True, ws=True, piv=True)[:3]

			toUseDic = {}
			for i in controlDic.keys():
				distanceDic = {}
				for k in folliclesDic.keys():
					a = MVector(*controlDic[i])
					b = MVector(*folliclesDic[k])
					c = a - b
					distanceDic[k] = c.length()
				toUseValue = min(float(s) for s in distanceDic.values())
				for key in distanceDic.keys():
					if distanceDic[key] == toUseValue:
						toUseDic[i] = key

			locsCreated = []
			for i in toUseDic.values():
				cmds.spaceLocator(n=i + '_loc')
				cmds.parentConstraint(i, i + '_loc')
				cmds.parent(i + '_loc', clothRigName + '_preview_grp')
				locsCreated.append(i + '_loc')

			cmds.select(locsCreated)
			cmds.refresh(su=True)
			cmds.bakeResults(t=(start_fr, end_fr), simulation=True, sampleBy=1)
			cmds.refresh(su=False)

			for i in toUseDic.values():
				if cmds.objExists(i + '_loc_parentConstraint1'):
					cmds.delete(i + '_loc_parentConstraint1')

			for i in toUseDic:
				attributesLock = {'translate': [], 'rotate': []}
				for att in ['.tx', '.ty', '.tz', '.rx', '.ry', '.rz']:
					if cmds.getAttr(i + att, l=True) and 't' in att:
						attributesLock['translate'].append(att[-1])
					elif cmds.getAttr(i + att, l=True) and 'r' in att:
						attributesLock['rotate'].append(att[-1])
				cmds.parentConstraint(toUseDic[i] + '_loc', i, sr=attributesLock['rotate'], st=attributesLock['translate'], mo=True)
				cmds.setKeyframe(i)
				cmds.setAttr(i + '.blendParent1', 1)

			cmds.checkBox('clothRig_checkBox', e=True, bgc=(.4,.2,.2), v=False, l='Off ')
			cmds.setAttr(clothRigName + '_nClothShape1.isDynamic', 0)

			cmds.spaceLocator(n=clothRigName + '_controlNames')
			cmds.parent(clothRigName + '_controlNames', clothRigName + '_clothRig_grp')
			cmds.setAttr(clothRigName + '_controlNames.visibility', 0)
			for i in range(len(self.controlsList)):
				attName = chr(i + ord('a')).upper()
				cmds.addAttr(clothRigName + '_controlNames', ln=attName, dt='string') 
				cmds.setAttr(clothRigName + '_controlNames.' + attName, self.controlsList[i], type='string')

			cmds.select(clear=True)

			cmds.columnLayout('previewSettings_columnLayout', adjustableColumn=1, p='settings_frameLayout')
			cmds.text('Dropoff Settings:', fn="boldLabelFont")
			cmds.rowLayout('previewSettings_rowLayout', nc=3, adjustableColumn=2)
			cmds.text('Overall Dropoff:')
			cmds.floatSliderGrp('dropoff_slider', f=True, w=100, min=0, max=1, value=1, step=.1, dc=self.overAllDropoff)
			cmds.button('singleDropoff_button', l='Discrete Dropoff', c=partial(self.discreteDropoffUI, self.controlsList))
			self.cacheCheckUI(clothRigName)
			cmds.setAttr(clothRigName + '_nCloth_grp.visibility', 0)
		else:
			cmds.warning("Cloth Rig '%s' already in preview mode. Right click to load Dropoff Settings." % clothRigName)

	def overAllDropoff(self, *args):
		clothRigName = cmds.optionMenu('clothRig_list', q=True, v=True)
		controlsList = []
		for i in cmds.listAttr(clothRigName + '_controlNames') or []:
			if len(i) <= 3:
				controlsList.append(cmds.getAttr(clothRigName + '_controlNames.' + i))
		value = float(cmds.floatSliderGrp('dropoff_slider', q=True, v=True))
		for i in controlsList:
			cmds.setAttr(i + '.blendParent1', value)

	def undoPreview(self, *args):
		clothRigName = cmds.optionMenu('clothRig_list', q=True, v=True)
		cmds.delete(clothRigName + '_preview_grp')
		cmds.delete(clothRigName + '_controlNames')
		cmds.checkBox('clothRig_checkBox', e=True, bgc=(.2,.4,.2), v=True, l='On ')
		cmds.setAttr(clothRigName + '_nClothShape1.isDynamic', 1)
		if cmds.columnLayout('previewSettings_columnLayout', exists=True):
			cmds.deleteUI('previewSettings_columnLayout')
		if cmds.window('clothChain_window', exists=True):
			cmds.window('clothChain_window', e=True, h=40)
		self.cacheCheckUI(clothRigName)
		cmds.setAttr(clothRigName + '_nCloth_grp.visibility', 1)

	def bakeFinalSim(self, *args):
		clothRigName = cmds.optionMenu('clothRig_list', q=True, v=True)
		controlsList = cmds.textScrollList('controls_scrollList', q=True, ai=True)
		start_fr = int(cmds.playbackOptions(q=True, minTime=True))
		end_fr = int(cmds.playbackOptions(q=True, maxTime=True))
		sampleByValue = int(cmds.textField('sampleByValue_textField', q=True, tx=True))
		animLayer = cmds.checkBox('bakeOnAnimLayer_checkBox', q=True, v=True)

		if cmds.objExists(clothRigName + '_preview_grp'):
			cmds.refresh(su=True)
			if animLayer:
				cmds.bakeResults(controlsList, t=(start_fr, end_fr), sampleBy=sampleByValue, bakeOnOverrideLayer=True, simulation=True)
				cmds.rename('BakeResults', clothRigName + '_simLayer')
			else:
				cmds.bakeResults(controlsList, t=(start_fr, end_fr), sampleBy=sampleByValue, simulation=True)
			cmds.refresh(su=False)

			cmds.delete(clothRigName + '_preview_grp')
			cmds.delete(clothRigName + '_controlNames')

			if cmds.columnLayout('previewSettings_columnLayout', exists=True):
				cmds.deleteUI('previewSettings_columnLayout')
			self.cacheCheckUI(clothRigName)
			cmds.setAttr(clothRigName + '_nCloth_grp.visibility', 1)

			for control in controlsList or []:
				for i in cmds.listRelatives(control) or []:
					if 'parentConstraint1' in i:
						cmds.delete(i)

			if cmds.checkBox('deleteClothRig_checkBox', q=True, v=True):
				cmds.delete(clothRigName + '_clothRig_grp')
				children = cmds.listRelatives('clothSimChain_grp') or []
				if len(children) == 1:
					cmds.delete('clothSimChain_grp')

			mel.eval('print "Done!";')
		else:
			cmds.warning('Preview your simulation first.')

	### SETTINGS OPERATIONS
	def nucleusChange(self, attribute, *args):
		clothRigName = cmds.optionMenu('clothRig_list', q=True, v=True)
		nucleus = self._get_nucleus(clothRigName)
		if nucleus:
			value = float(cmds.textField(attribute + '_textField', q=True, tx=True))
			cmds.setAttr(nucleus + '.' + attribute, value)

	def applyClothSettings(self, option, *args):
		clothRigName = cmds.optionMenu('clothRig_list', q=True, v=True)
		value = float(cmds.textField(option + '_textField', q=True, tx=True))
		# Fix: write to shape node
		cmds.setAttr(clothRigName + '_nClothShape1.%s' % option, value)

	def applyStrength(self, segmentNumber, *args):
		clothRigName = cmds.optionMenu('clothRig_list', q=True, v=True)
		value = float(cmds.textField('segment_' + segmentNumber + '_textField', q=True, tx=True))
		cmds.setAttr(clothRigName + '_dynamicConstraintShape%s.strength' % segmentNumber, value)
		currTime = cmds.currentTime(q=True)
		try:
			keys = cmds.keyframe(clothRigName + '_dynamicConstraintShape' + segmentNumber, q=True) or []
			if currTime in keys:
				cmds.textField('segment_' + segmentNumber + '_textField', e=True, bgc=(.85, .4, .4))
		except TypeError:
			pass

	def applyBlendparent(self, control, *args):
		value = float(cmds.textField(control + '_textField', q=True, tx=True))
		cmds.setAttr(control + '.blendParent1', value)

	def multiplyStrength(self, *args):
		clothRigName = cmds.text('clothRig_text', q=True, l=True).partition(': ')[2]
		factor = float(cmds.textField('multiply_textField', q=True, tx=True))
		constraintNodesList = []
		for i in cmds.listRelatives(clothRigName + '_nCloth_grp') or []:
			if 'dynamicConstraint' in i:
				constraintNodesList.append(i)
		for i in constraintNodesList:
			currValue = float(cmds.textField('segment_' + i.rpartition('dynamicConstraint')[2] + '_textField', q=True, tx=True))
			newVal = currValue * factor
			cmds.setAttr(i + '.strength', newVal)
			cmds.textField('segment_' + i.rpartition('dynamicConstraint')[2] + '_textField', e=True, tx=str(newVal))
			currTime = cmds.currentTime(q=True)
			try:
				keys = cmds.keyframe(clothRigName + '_dynamicConstraintShape' + i.rpartition('dynamicConstraint')[2], q=True) or []
				if currTime in keys:
					cmds.textField('segment_' + i.rpartition('dynamicConstraint')[2] + '_textField', e=True, bgc=(.85, .4, .4))
			except TypeError:
				pass

	def selectDynConstraint(self, node, selAll, *args):
		clothRigName = cmds.text('clothRig_text', q=True, l=True).partition(': ')[2]
		if selAll == 'no':
			cmds.select(node, r=True)
		else:
			cmds.select(cl=True)
			for i in cmds.listRelatives(clothRigName + '_nCloth_grp') or []:
				if 'dynamicConstraint' in i:
					cmds.select(i, add=True)

	def dynConstraintKey(self, segmentNumber, *args):
		clothRigName = cmds.text('clothRig_text', q=True, l=True).partition(': ')[2]
		cmds.iconTextButton('keyframe_button' + segmentNumber, e=True, image1='autoKeyframeOn.png')
		cmds.setKeyframe(clothRigName + '_dynamicConstraint' + segmentNumber + '.str')
		currTime = cmds.currentTime(q=True)
		keys = cmds.keyframe(clothRigName + '_dynamicConstraintShape' + segmentNumber, q=True) or []
		if currTime in keys:
			cmds.textField('segment_' + segmentNumber + '_textField', e=True, bgc=(.85, .4, .4))

	def blenParentKey(self, control, *args):
		cmds.iconTextButton('keyframe_button' + control, e=True, image1='autoKeyframeOn.png')
		cmds.setKeyframe(control + '.blendParent1')
