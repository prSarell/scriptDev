# Maya 2025-ready
import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om2
import math
from functools import partial
import importlib


def refreshTool(*args):
	import sys
	mod_name = 'tlmParticleChain'
	if mod_name in sys.modules:
		importlib.reload(sys.modules[mod_name])
		mod = sys.modules[mod_name]
	else:
		mod = __import__(mod_name)
	run = mod.SimParticleRig()
	cmds.evalDeferred(run.UI)


class SimParticleRig():

	def __init__(self):
		# nHair (dynamic curve) backend -- one hairSystem/follicle per rig,
		# driving a single multi-CV curve rather than one nParticle per
		# segment. customPreset values are simply hairSystem's own node
		# defaults (verified via a headless probe against a fresh
		# hairSystem node), matching how the old nParticle customPreset was
		# also just nParticle's own defaults.
		self.hairSettingsName = ['stiffness', 'drag', 'damp', 'stretchResistance', 'stretchDamp']
		self.customPreset = [0.15, 0.05, 0.0, 10.0, 0.10]
		# 'tentacle' mirrors tlmClothChain.py's own named preset in spirit --
		# a tuned starting point for a muscular chain rather than a floppy one:
		# higher stiffness/stretchResistance so it holds its shape and resists
		# elongating, moderate drag/damp so it doesn't whip forever.
		self.namedPresets = {
			'tentacle': {'stiffness': 0.6, 'drag': 0.15, 'damp': 0.3, 'stretchResistance': 40.0, 'stretchDamp': 0.2},
		}
		self.presetsList = ['custom', 'tentacle']
		# Same 5 named falloff curves as tlmClothChain.py's dynamicConstraint
		# strength profiles -- reused verbatim (same math). Unlike the old
		# nParticle version (which wrote straight to each particle's
		# goalWeight[0]), these now feed the hairSystem's attractionScale
		# ramp position-by-position: one ramp entry per segment, in order,
		# with the hairSystem's own startCurveAttract scalar pinned to 1.0
		# at build time so the ramp value alone is the effective per-segment
		# pull strength -- the same single-number-per-segment semantics the
		# old goalWeight had, just relocated onto a ramp attribute.
		self.constraintProfiles = [
			('baseToTip', 'Base to Tip'),
			('bothEndsPinned', 'Both Ends Pinned'),
			('uniform', 'Uniform'),
			('closeFollow', 'Close Follow'),
			('baseOnly', 'Base Only'),
		]
	# ------------------------------------------------------------------
	# Copied verbatim from tlmClothChain.py -- sim-backend-agnostic.
	# ------------------------------------------------------------------

	@staticmethod
	def get_frame_range():
		tc = 'timeControl1'
		try:
			if cmds.timeControl(tc, q=True, rangeVisible=True):
				raw = cmds.timeControl(tc, q=True, range=True)
				parts = raw.replace('"', '').split(':')
				return int(float(parts[0])), int(float(parts[1]))
		except Exception:
			pass
		return (int(cmds.playbackOptions(q=True, minTime=True)),
		        int(cmds.playbackOptions(q=True, maxTime=True)))

	def _nucleus_space_scale(self):
		"""Nucleus solvers do their internal physics (gravity, mass, etc.) as if
		1 Maya unit = 1 meter, regardless of the scene's actual linear working
		unit. Space Scale corrects for that -- set to (meters per 1 scene unit).
		"""
		metersPerUnit = {
			'mm': 0.001, 'cm': 0.01, 'm': 1.0,
			'in': 0.0254, 'ft': 0.3048, 'yd': 0.9144,
		}
		unit = cmds.currentUnit(q=True, linear=True)
		return metersPerUnit.get(unit, 1.0)

	def _locked_axes(self, ctrl):
		st, sr = [], []
		for att in ['.tx', '.ty', '.tz', '.rx', '.ry', '.rz']:
			if cmds.getAttr(ctrl + att, l=True):
				if 't' in att:
					st.append(att[-1])
				else:
					sr.append(att[-1])
		return st, sr

	def _eulerFilterRotates(self, controlsList, layerName=None):
		"""Straighten out 360-degree Euler wraps introduced by baking a live
		constraint-driven rotation -- identical need/logic to tlmClothChain.py.
		"""
		curves = []
		for control in controlsList or []:
			for axis in ('rotateX', 'rotateY', 'rotateZ'):
				plug = control + '.' + axis
				curve = None
				if layerName and cmds.animLayer(layerName, query=True, exists=True):
					found = cmds.animLayer(layerName, query=True, findCurveForPlug=plug)
					curve = found[0] if found else None
				if not curve:
					conns = cmds.listConnections(plug, type='animCurve', source=True, destination=False) or []
					curve = conns[0] if conns else None
				if curve:
					curves.append(curve)
		if curves:
			cmds.filterCurve(curves, filter='euler')

	def _constraintProfileStrength(self, profile, index, total):
		"""Same 5 named falloff curves as tlmClothChain.py, by 1-indexed
		segment number and total segment count. See tlmClothChain.py for the
		original rationale -- reused verbatim here, just feeding an
		attractionScale ramp entry instead of dynamicConstraint.strength.
		"""
		if profile == 'uniform':
			return 0.5
		if profile == 'baseToTip':
			if index == 1:
				return 0.9
			if index == total:
				return 0.01
			return (1.0 / float(index)) * 0.1
		if profile == 'bothEndsPinned':
			dist = min(index, total + 1 - index)
			distMax = (total + 1) // 2
			if index == 1 or index == total:
				return 0.9
			if dist == distMax:
				return 0.01
			return (1.0 / float(dist)) * 0.1
		if profile == 'closeFollow':
			if total <= 1:
				return 0.9
			base, floor = 0.9, 0.3
			return base - (base - floor) * (index - 1) / float(total - 1)
		if profile == 'baseOnly':
			return 1.0 if index == 1 else 0.0
		raise ValueError('Unknown constraint profile: %r' % profile)

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
			justAdded = False
			try:
				ils = cmds.optionMenu('colliders_list', q=True, ils=True) or []
				if sel + '_collider' in ils:
					cmds.warning('Object ' + sel + ' already in the list.')
				else:
					cmds.menuItem(sel + '_collider', label=sel, p='colliders_list')
					mel.eval("makeCollideNCloth;")
					nRigidShape = cmds.ls(sl=True)[0]
					nRigidObj = nRigidShape.replace('nRigidShape', 'nRigid')
					cmds.parent(nRigidObj, 'passiveColliders_grp')
					cmds.rename(sel + '_' + nRigidObj)
					justAdded = True
			except Exception:
				cmds.menuItem(sel + '_collider', label=sel, p='colliders_list')
				mel.eval("makeCollideNCloth;")
				nRigidShape = cmds.ls(sl=True)[0]
				nRigidObj = nRigidShape.replace('nRigidShape', 'nRigid')
				cmds.parent(nRigidObj, 'passiveColliders_grp')
				cmds.rename(sel + '_' + nRigidObj)
				justAdded = True

			if justAdded:
				# makeCollideNCloth attaches the new nRigid to whichever
				# nucleus Maya currently considers "active" -- not
				# necessarily this rig's own nucleus, especially once more
				# than one Particle Rig (each with its own nucleus) exists
				# in the scene. Reassign explicitly, same defensive pattern
				# buildParticleRig already uses for the hairSystem, or the
				# collider just sits there with no error and never actually
				# collides with this rig's hair.
				rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
				nucleus = self._get_nucleus(rigName)
				nRigidTform = sel + '_' + nRigidObj
				if nucleus and cmds.objExists(nRigidTform):
					nRigidShapeNow = cmds.listRelatives(nRigidTform, shapes=True)[0]
					cmds.select(nRigidShapeNow, r=True)
					mel.eval('assignNSolver "%s"' % nucleus)

			cmds.optionMenu('colliders_list', e=True, v=sel)
			colliderObj = cmds.optionMenu('colliders_list', q=True, v=True)
			thickValue = "%.2f" % cmds.getAttr(colliderObj + '_nRigidShape1.thickness')
			cmds.textField('colliderColThickness_textField', e=True, tx=thickValue)
		else:
			cmds.warning('Create a Particle Rig first.')

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

	def colliderCollisionThickness(self, *args):
		colliderObj = cmds.optionMenu('colliders_list', q=True, v=True)
		value = float(cmds.textField('colliderColThickness_textField', q=True, tx=True))
		cmds.setAttr(colliderObj + '_nRigidShape1.thickness', value)

	# ------------------------------------------------------------------
	# Proxy geo authoring -- copied verbatim from tlmClothChain.py.
	# Sim-backend-agnostic: this only builds/shapes the ribbon and its
	# cross-section controls, it doesn't know or care what drives them.
	# ------------------------------------------------------------------

	def _order_joint_chain(self, selection):
		joints = cmds.ls(selection, type='joint', long=True) or []
		if len(joints) < 2:
			raise RuntimeError('Select at least 2 joints forming a single chain.')

		selSet = set(joints)
		roots = []
		for j in joints:
			ancestors = set()
			parent = cmds.listRelatives(j, parent=True, fullPath=True)
			while parent:
				ancestors.add(parent[0])
				parent = cmds.listRelatives(parent[0], parent=True, fullPath=True)
			if not (ancestors & selSet):
				roots.append(j)
		if len(roots) != 1:
			raise RuntimeError(
				'Selected joints must form a single connected chain (found %d root(s)).' % len(roots))

		ordered = [roots[0]]
		current = roots[0]
		while True:
			children = cmds.listRelatives(current, children=True, type='joint', fullPath=True) or []
			selectedChildren = [c for c in children if c in selSet]
			if not selectedChildren:
				break
			if len(selectedChildren) > 1:
				raise RuntimeError('Selected joints branch at "%s" -- select a single unbranched chain.' % current)
			current = selectedChildren[0]
			ordered.append(current)

		if len(ordered) != len(joints):
			raise RuntimeError('Selected joints do not all belong to the same connected chain.')
		return ordered

	def _joint_chain_row_matrices(self, orderedNodes):
		"""Per-node world matrices derived purely from world POSITIONS, using a
		rotation-minimizing (parallel-transport) frame -- rotate/jointOrient are
		never read, so this works on any ordered list of transforms (joints,
		shape_CTRLs, whatever), not just joints. Local +Y = down-the-chain
		tangent, +Z = up (row[8:11] in the flat 16-list), +X = right.
		"""
		positions = [om2.MVector(*cmds.xform(j, q=True, ws=True, t=True)) for j in orderedNodes]
		n = len(positions)

		aims = []
		for i in range(n):
			if i < n - 1:
				aims.append((positions[i + 1] - positions[i]).normal())
			else:
				aims.append(aims[-1])

		seedUp = om2.MVector(0, 0, 1)
		a0 = aims[0]
		up0 = seedUp - a0 * (seedUp * a0)
		if up0.length() < 1e-6:
			alt = om2.MVector(1, 0, 0)
			up0 = alt - a0 * (alt * a0)
		ups = [up0.normal()]

		for i in range(1, n):
			aPrev, aCur = aims[i - 1], aims[i]
			dot = max(-1.0, min(1.0, aPrev * aCur))
			axis = aPrev ^ aCur
			if axis.length() < 1e-8:
				ups.append(ups[-1])
				continue
			axis = axis.normal()
			angle = math.acos(dot)
			ups.append(ups[-1].rotateBy(om2.MQuaternion(angle, axis)).normal())

		matrices = []
		for pos, aim, up in zip(positions, aims, ups):
			right = (aim ^ up).normal()
			upOrtho = (right ^ aim).normal()
			matrices.append([
				right.x, right.y, right.z, 0.0,
				aim.x,   aim.y,   aim.z,   0.0,
				upOrtho.x, upOrtho.y, upOrtho.z, 0.0,
				pos.x,   pos.y,   pos.z,   1.0,
			])
		return matrices

	# ------------------------------------------------------------------
	# nucleus / hairSystem / follicle / curve lookups.
	# ------------------------------------------------------------------

	def _get_nucleus(self, rigName):
		# Nucleus is looked up via a stored attribute rather than a fixed
		# naming convention, since a rig can now share another rig's
		# nucleus instead of always owning "rigName_nucleus1" (see
		# buildParticleRig's Nucleus: choice). Falls back to the old
		# by-convention name for rigs built before sharing existed.
		grp = rigName + '_particleRig_grp'
		if cmds.objExists(grp) and cmds.attributeQuery('nucleusName', node=grp, exists=True):
			name = cmds.getAttr(grp + '.nucleusName')
			if name and cmds.objExists(name):
				return name
		name = rigName + '_nucleus1'
		return name if cmds.objExists(name) else None

	def _get_existing_rig_names(self):
		names = []
		for grp in cmds.ls('*_particleRig_grp', type='transform') or []:
			names.append(grp.rpartition('_particleRig_grp')[0])
		return names

	def _get_hairSystem(self, rigName):
		name = rigName + '_hairSystemShape1'
		return name if cmds.objExists(name) else None

	def _get_follicle(self, rigName):
		name = rigName + '_follicleShape1'
		return name if cmds.objExists(name) else None

	def _get_goal_curve_shape(self, rigName):
		tform = rigName + '_goalCurve'
		if not cmds.objExists(tform):
			return None
		shapes = cmds.listRelatives(tform, shapes=True) or []
		return shapes[0] if shapes else None

	def _get_out_curve_shape(self, rigName):
		name = rigName + '_outCurveShape'
		return name if cmds.objExists(name) else None

	def _get_segment_count(self, rigName):
		goalShape = self._get_goal_curve_shape(rigName)
		if not goalShape:
			return 0
		return cmds.getAttr(goalShape + '.cp', size=True)

	def _get_aimGroupList(self, rigName):
		grp = rigName + '_aimChain_grp'
		if not cmds.objExists(grp):
			return []
		groups = [i for i in cmds.listRelatives(grp, type='transform') or [] if '_aimGrp_' in i]
		groups.sort(key=lambda g: int(g.rpartition('_aimGrp_')[2]))
		return groups

	# ------------------------------------------------------------------
	# Build the nHair-backed rig.
	# ------------------------------------------------------------------

	def buildParticleRig(self, *args):
		rigName = (cmds.textField('particleRigName_textField', q=True, tx=True) or '').strip().replace(' ', '_')
		jointsSelected = cmds.textScrollList('joints_scrollList', q=True, ai=True)
		start_fr = int(cmds.playbackOptions(q=True, minTime=True))
		end_fr = int(cmds.playbackOptions(q=True, maxTime=True))

		if not rigName:
			cmds.warning('Set a Particle Rig Name first.')
			return
		if cmds.objExists(rigName + '_particleRig_grp'):
			cmds.warning('Particle Rig already exists.')
			return
		if jointsSelected is None or len(jointsSelected) < 2:
			cmds.warning('Add at least 2 joints forming a single chain first.')
			return

		try:
			orderedJoints = self._order_joint_chain(jointsSelected)
		except RuntimeError as e:
			cmds.warning(str(e))
			return

		# Rest positions are captured below from wherever the timeline
		# currently sits -- see tlmClothChain.py's previewSim for why this
		# matters (rest pose and simulation-start pose must agree).
		cmds.currentTime(start_fr)

		cmds.frameLayout('settings_frameLayout', e=True, en=True)
		cmds.frameLayout('transferSim_frameLayout', e=True, en=True)

		if not cmds.objExists('particleSimChain_grp'):
			cmds.group(empty=True, name='particleSimChain_grp')
			cmds.group(empty=True, name='passiveColliders_grp', p='particleSimChain_grp')

		cmds.group(empty=True, name=rigName + '_particleRig_grp', p='particleSimChain_grp')
		cmds.group(empty=True, name=rigName + '_hairSystem_grp', p=rigName + '_particleRig_grp')
		cmds.group(empty=True, name=rigName + '_curves_grp', p=rigName + '_particleRig_grp')
		# Identity-transform parent: everything under here connects world-space
		# positions straight into local .translate, so this group (and every
		# ancestor above it) must never carry its own translate/rotate/scale.
		cmds.group(empty=True, name=rigName + '_aimChain_grp', p=rigName + '_particleRig_grp')

		segCount = len(orderedJoints)
		rowMatrices = self._joint_chain_row_matrices(orderedJoints)
		restPositions = [(m[12], m[13], m[14]) for m in rowMatrices]
		restUps = [(m[8], m[9], m[10]) for m in rowMatrices]

		# Nucleus is either a fresh one for this rig, or an existing rig's
		# nucleus the user explicitly chose to share (Maya nucleus solvers
		# happily drive any number of hairSystems/nCloth/nParticle objects
		# at once -- there's no requirement for one-per-rig, and sharing is
		# what lets hairSystems on the same nucleus collide with each
		# other, which separate nuclei never see). Created/looked-up
		# before the hair system so it's unambiguous at the moment
		# makeCurvesDynamic runs -- assignNSolver below makes the
		# assignment explicit and robust regardless.
		nucleusChoice = cmds.optionMenu('nucleusChoice_list', q=True, v=True) if cmds.optionMenu('nucleusChoice_list', exists=True) else 'New'
		sharedNucleus = None
		if nucleusChoice and nucleusChoice != 'New':
			sharedNucleus = self._get_nucleus(nucleusChoice)
			if not sharedNucleus:
				cmds.warning('Could not find a nucleus for rig "%s" -- building a new one instead.' % nucleusChoice)

		if sharedNucleus:
			nucleus = sharedNucleus
		else:
			nucleus = cmds.createNode('nucleus', name=rigName + '_nucleus1')
			cmds.connectAttr('time1.outTime', nucleus + '.currentTime', f=True)
			# Parented under the shared top-level group, not under this
			# rig's own hierarchy -- a nucleus another rig may later share
			# must not get deleted just because THIS rig does.
			cmds.parent(nucleus, 'particleSimChain_grp')
			cmds.setAttr(nucleus + '.startFrame', start_fr)
			cmds.setAttr(nucleus + '.timeScale', 1.0)
			cmds.setAttr(nucleus + '.spaceScale', self._nucleus_space_scale())
			cmds.setAttr(nucleus + '.subSteps', 10)

		cmds.addAttr(rigName + '_particleRig_grp', ln='nucleusName', dt='string')
		cmds.setAttr(rigName + '_particleRig_grp.nucleusName', nucleus, type='string')

		# Goal curve: one degree-1 CV per joint, each CV driven by a BAKED
		# COPY of that joint's world position (via a jointRef locator), not
		# the live joint itself. Driving straight off the live joint was
		# the original design, but it closes a real dependency cycle the
		# moment a previewed control is (or drives) one of these same
		# joints: control -> joint -> goal curve -> sim -> aim chain ->
		# control ("Cycle on '...CTL.translate'", confirmed live).
		# Disconnecting the goal curve during Preview to break that (tried
		# first) turned out wrong too -- nucleus solvers don't actually
		# cache the whole timeline for arbitrary scrubbing, they only carry
		# state forward incrementally, so a frozen goal meant any later
		# scrub/replay re-solved against a static target and lost the
		# animation entirely. Baking a static per-frame copy of the joint's
		# motion onto a proxy *before* the joint is ever touched by the aim
		# chain keeps the sim fully animation-reactive (the proxy has real
		# per-frame keys, not a live link) while making a cycle structurally
		# impossible -- nothing downstream of the proxy ever connects back
		# into it.
		goalCurve = cmds.curve(d=1, p=restPositions, name=rigName + '_goalCurve')
		goalCurveShape = cmds.listRelatives(goalCurve, shapes=True)[0]
		for i, joint in enumerate(orderedJoints):
			ref = cmds.spaceLocator(name=rigName + '_jointRef_%02d' % i)[0]
			# Stashed so refreshGoalAnimation() can re-bake from the
			# current joint animation later without requiring the joints
			# to be re-selected -- the live pointConstraint below is
			# deleted right after baking (see the cycle note above), so
			# this is the only remaining link back to which joint each
			# locator came from.
			cmds.addAttr(ref, ln='sourceJoint', dt='string')
			cmds.setAttr(ref + '.sourceJoint', joint, type='string')
			con = cmds.pointConstraint(joint, ref, mo=False)[0]
			cmds.bakeResults(ref, t=(start_fr, end_fr), simulation=True, at=['tx', 'ty', 'tz'])
			cmds.delete(con)
			cmds.parent(ref, rigName + '_hairSystem_grp')
			dm = cmds.createNode('decomposeMatrix', name=rigName + '_goalDM_%02d' % i)
			cmds.connectAttr(ref + '.worldMatrix[0]', dm + '.inputMatrix')
			cmds.connectAttr(dm + '.outputTranslate', goalCurveShape + '.controlPoints[%d]' % i, f=True)
		cmds.currentTime(start_fr)
		cmds.parent(goalCurve, rigName + '_hairSystem_grp')

		# makeCurvesDynamic (Hair > Make Selected Curves Dynamic) builds the
		# follicle/hairSystem/output-curve trio; before/after set-diffing to
		# find the new nodes rather than assuming names mirrors the same
		# trick already used for dynamicConstraint springs elsewhere in this
		# file's sibling tool.
		before_hsys = set(cmds.ls(type='hairSystem'))
		before_fol = set(cmds.ls(type='follicle'))
		before_nuc = set(cmds.ls(type='nucleus'))

		cmds.select(goalCurve, r=True)
		# args: surfaceAttach=0, snapToSurface=0, matchPosition=0 (curve is
		# already degree-1, nothing to rebuild), createOutCurves=1, createPfxHair=0
		mel.eval('makeCurvesDynamic 2 { "0", "0", "0", "1", "0" };')

		hairSystem = list(set(cmds.ls(type='hairSystem')) - before_hsys)[0]
		follicle = list(set(cmds.ls(type='follicle')) - before_fol)[0]
		newNucleus = list(set(cmds.ls(type='nucleus')) - before_nuc)

		# Reassign onto our own rig-named nucleus regardless of whichever
		# nucleus makeCurvesDynamic's own "active nucleus" logic picked --
		# same defensive pattern the cloth/particle tools already use for
		# assignNSolver on nCloth/nParticle.
		cmds.select(hairSystem, r=True)
		mel.eval('assignNSolver "%s"' % nucleus)
		for n in newNucleus:
			if cmds.objExists(n) and n != nucleus:
				try:
					cmds.delete(n)
				except Exception:
					pass

		follicleTform = cmds.listRelatives(follicle, parent=True, fullPath=True)[0]
		hairSystemTform = cmds.listRelatives(hairSystem, parent=True, fullPath=True)[0]
		hairSystemTformShort = hairSystemTform.rpartition('|')[2]
		autoFolliclesGrp = hairSystemTformShort + 'Follicles'
		autoOutputGrp = hairSystemTformShort + 'OutputCurves'
		outCurveShapes = cmds.listRelatives(autoOutputGrp, ad=True, type='nurbsCurve') if cmds.objExists(autoOutputGrp) else None
		outCurveTform = cmds.listRelatives(outCurveShapes[0], parent=True)[0] if outCurveShapes else None

		cmds.parent(hairSystemTform, rigName + '_hairSystem_grp')
		# createHairCurveNode.mel reparents the follicle to sit alongside
		# whatever transform the start curve already lived under -- since
		# the goal curve was parented into our rig group above, the
		# follicle typically lands there automatically already (confirmed
		# headlessly); only reparent if it genuinely didn't, to avoid a
		# spurious "already a child of" warning on every build.
		follicleTform = cmds.listRelatives(follicle, parent=True, fullPath=True)[0]
		hairSystemGrpFull = cmds.ls(rigName + '_hairSystem_grp', long=True)[0]
		if follicleTform.rpartition('|')[0] != hairSystemGrpFull:
			cmds.parent(follicleTform, rigName + '_hairSystem_grp')
		if outCurveTform:
			cmds.parent(outCurveTform, rigName + '_curves_grp')
		for leftover in (autoFolliclesGrp, autoOutputGrp):
			if cmds.objExists(leftover) and not (cmds.listRelatives(leftover, children=True) or []):
				cmds.delete(leftover)

		# Rename each transform first, then re-fetch its shape's current
		# name before renaming that -- renaming a transform whose shape
		# still has Maya's auto-derived default name (e.g. hairSystemShape1
		# under hairSystem1) silently renames the shape too, so a shape
		# name captured before the transform rename can no longer resolve
		# (confirmed headlessly).
		hairSystemTformNow = cmds.listRelatives(hairSystem, parent=True, fullPath=True)[0]
		follicleTformNow = cmds.listRelatives(follicle, parent=True, fullPath=True)[0]
		cmds.rename(hairSystemTformNow, rigName + '_hairSystem1')
		hairSystem = cmds.listRelatives(rigName + '_hairSystem1', shapes=True)[0]
		cmds.rename(hairSystem, rigName + '_hairSystemShape1')
		cmds.rename(follicleTformNow, rigName + '_follicle1')
		follicle = cmds.listRelatives(rigName + '_follicle1', shapes=True)[0]
		cmds.rename(follicle, rigName + '_follicleShape1')
		hairSystem = rigName + '_hairSystemShape1'
		follicle = rigName + '_follicleShape1'
		if outCurveTform:
			cmds.rename(outCurveTform, rigName + '_outCurve')
			outCurveShape = cmds.listRelatives(rigName + '_outCurve', shapes=True)[0]
			cmds.rename(outCurveShape, rigName + '_outCurveShape')

		# degree=1 keeps the simulated curve's CVs exactly matching the
		# per-joint point count (verified headlessly -- the default follicle
		# degree rebuilds the output to a smoothed, non-interpolating curve
		# even though the input curve itself was already degree-1).
		cmds.setAttr(follicle + '.degree', 1)
		cmds.setAttr(follicle + '.pointLock', 1)  # Base only -- rest of the strand simulates
		# startCurveAttract left at 1.0 (verified default is 0.0 -- fully
		# free -- which would make the ramp below meaningless). The
		# attractionScale ramp, set per-segment by _applyConstraintProfile,
		# is the actual per-segment control from here on -- same
		# single-number-per-segment semantics the old goalWeight had.
		cmds.setAttr(hairSystem + '.startCurveAttract', 1.0)
		# Collision-thickness display on by default -- the direct hair
		# equivalent of nCloth's own thickness/color/solverDisplay
		# self-display (same displayColor default of yellow, confirmed
		# headlessly). collideWidthOffset is the scale value; the
		# Collision Thickness slider/color swatch in the UI drive it and
		# displayColor respectively. Both solverDisplay (the same
		# Off/Collision Thickness enum nCloth has) and drawCollideWidth
		# exist on hairSystem -- set both since it's unconfirmed which one
		# actually gates the viewport draw.
		cmds.setAttr(hairSystem + '.solverDisplay', 1)
		cmds.setAttr(hairSystem + '.drawCollideWidth', 1)
		# selfCollide defaults to off on a fresh hairSystem (verified
		# headlessly); on by default here so a strand doesn't pass through
		# itself, and so hairSystems that end up sharing a nucleus (see the
		# Nucleus: choice above) actually collide with each other too --
		# there's no separate inter-hairSystem flag, this is the same
		# selfCollide attribute doing both jobs.
		cmds.setAttr(hairSystem + '.selfCollide', 1)

		for idx, attrName in enumerate(self.hairSettingsName):
			cmds.setAttr(hairSystem + '.' + attrName, self.customPreset[idx])

		# Live per-segment position sampling off the simulated output curve --
		# a curveInfo node re-evaluates every frame, giving a connectable
		# world-space position per CV (the curve equivalent of nParticle's
		# worldCentroid output).
		outCurveShapeFull = rigName + '_outCurveShape'
		curveInfo = cmds.createNode('curveInfo', name=rigName + '_outCurveInfo')
		cmds.connectAttr(outCurveShapeFull + '.worldSpace[0]', curveInfo + '.inputCurve')

		simPointLocs = self._wireSimPoints(rigName, curveInfo, segCount)
		self._buildAimChain(rigName, simPointLocs, restUps)

		# menuItem + optionMenu value must be set before loadSettings() --
		# it re-queries 'particleRig_list' itself to know which rig to read,
		# so calling it first (against a still-empty dropdown) left every
		# nucleus field blank after Build.
		cmds.menuItem(rigName + '_particleRig', label=rigName, p='particleRig_list')
		cmds.optionMenu('particleRig_list', e=True, v=rigName)

		# Register this rig as a nucleus-sharing target for the NEXT build,
		# and reset the choice back to "New" -- otherwise building rig #2
		# right after rig #1 would default to silently sharing rig #1's
		# nucleus instead of it being a deliberate choice each time.
		if cmds.optionMenu('nucleusChoice_list', exists=True):
			cmds.menuItem(rigName + '_nucleusChoice', label=rigName, p='nucleusChoice_list')
			cmds.optionMenu('nucleusChoice_list', e=True, v='New')

		self.loadSettings()
		self._applyConstraintProfile(rigName, 'baseToTip')

		cmds.textScrollList('joints_scrollList', e=True, ra=True)
		cmds.textScrollList('controls_scrollList', e=True, ra=True)

		cmds.setAttr(rigName + '_aimChain_grp.visibility', 0)

	def refreshGoalAnimation(self, *args):
		"""Re-bake each jointRef locator from its source joint's CURRENT
		animation, without touching anything else about the built rig.
		buildParticleRig bakes the goal curve's input once and deletes the
		live constraint to avoid a dependency cycle (see the comment
		there) -- the side effect is that any keys added or changed on the
		joints after Build have nothing left to feed into until this is
		run again.
		"""
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		if not rigName or not cmds.objExists(rigName + '_particleRig_grp'):
			cmds.warning('Create a Particle Rig first.')
			return
		if cmds.objExists(rigName + '_preview_grp'):
			cmds.warning('Undo Preview first, then Refresh Goal.')
			return

		start_fr = int(cmds.playbackOptions(q=True, minTime=True))
		end_fr = int(cmds.playbackOptions(q=True, maxTime=True))
		segCount = self._get_segment_count(rigName)

		for i in range(segCount):
			ref = rigName + '_jointRef_%02d' % i
			if not cmds.objExists(ref):
				continue
			joint = cmds.getAttr(ref + '.sourceJoint') if cmds.attributeQuery('sourceJoint', node=ref, exists=True) else None
			if not joint or not cmds.objExists(joint):
				cmds.warning('Source joint for %s not found -- skipped.' % ref)
				continue
			con = cmds.pointConstraint(joint, ref, mo=False)[0]
			cmds.bakeResults(ref, t=(start_fr, end_fr), simulation=True, at=['tx', 'ty', 'tz'])
			cmds.delete(con)

		cmds.currentTime(start_fr)

	def _wireSimPoints(self, rigName, curveInfo, segCount):
		"""Live per-segment position locators, sourced from curveInfo's
		per-CV controlPoints output (the curve equivalent of a particle's
		worldCentroid).
		"""
		simPointLocs = []
		for i in range(segCount):
			simLoc = cmds.spaceLocator(name=rigName + '_simPoint_%02d' % i)[0]
			cmds.connectAttr(curveInfo + '.controlPoints[%d]' % i, simLoc + '.translate')
			cmds.parent(simLoc, rigName + '_curves_grp')
			simPointLocs.append(simLoc)
		return simPointLocs

	def _buildAimChain(self, rigName, simPointLocs, restUps):
		"""Aim chain: flat one-group-per-segment, translate connected
		directly from its sim point, aimed at the next segment's sim point.

		The up vector is computed live per segment rather than read from a
		fixed-offset locator (the first version of this): aimVec = live
		vector between the two sim points, then two chained cross products
		(aimVec x restUp, then that x aimVec) project the segment's
		REST-pose up direction onto the plane perpendicular to whatever the
		LIVE aim direction currently is. A fixed offset locator instead
		(tracking the live point but pointing in a constant world-space
		direction) degenerates the moment the simulated curve swings far
		enough from rest that the aim direction rotates toward that fixed
		direction -- aim and up vectors going near-parallel is a classic
		aimConstraint singularity, and reads as the rig exploding
		(confirmed live -- reported after Preview once the sim was actually
		animation-reactive enough to swing the chain around). This only
		degenerates in the much narrower case where the LIVE aim direction
		itself rotates to exactly match the original REST up reference.
		"""
		segCount = len(simPointLocs)
		aimGrp_grp = rigName + '_aimChain_grp'
		for i in range(segCount - 1):
			aimGrp = cmds.group(em=True, name=rigName + '_aimGrp_%02d' % i, p=aimGrp_grp)
			cmds.connectAttr(simPointLocs[i] + '.translate', aimGrp + '.translate')

			aimVecNode = cmds.createNode('plusMinusAverage', name=rigName + '_aimVec_%02d' % i)
			cmds.setAttr(aimVecNode + '.operation', 2)  # subtract
			cmds.connectAttr(simPointLocs[i + 1] + '.translate', aimVecNode + '.input3D[0]')
			cmds.connectAttr(simPointLocs[i] + '.translate', aimVecNode + '.input3D[1]')

			side = cmds.createNode('vectorProduct', name=rigName + '_upSide_%02d' % i)
			cmds.setAttr(side + '.operation', 2)  # cross product
			cmds.setAttr(side + '.normalizeOutput', 1)
			cmds.connectAttr(aimVecNode + '.output3D', side + '.input1')
			cmds.setAttr(side + '.input2', *restUps[i])

			liveUp = cmds.createNode('vectorProduct', name=rigName + '_upLive_%02d' % i)
			cmds.setAttr(liveUp + '.operation', 2)
			cmds.setAttr(liveUp + '.normalizeOutput', 1)
			cmds.connectAttr(side + '.output', liveUp + '.input1')
			cmds.connectAttr(aimVecNode + '.output3D', liveUp + '.input2')

			aimCon = cmds.aimConstraint(
				simPointLocs[i + 1], aimGrp,
				aimVector=(0, 0, 1), upVector=(0, 1, 0),
				worldUpType='vector', worldUpVector=(0, 1, 0),
				maintainOffset=False,
			)[0]
			cmds.connectAttr(liveUp + '.output', aimCon + '.worldUpVector', f=True)

		# Tip anchor: sits at the last sim point, borrows the last segment's
		# orientation (nothing further along the chain to aim toward).
		tipAnchor = cmds.group(em=True, name=rigName + '_tipAnchor_grp', p=aimGrp_grp)
		cmds.connectAttr(simPointLocs[-1] + '.translate', tipAnchor + '.translate')
		lastAim = rigName + '_aimGrp_%02d' % (segCount - 2)
		if cmds.objExists(lastAim):
			cmds.orientConstraint(lastAim, tipAnchor, mo=False)

	# ------------------------------------------------------------------
	# Constraint (attractionScale ramp) profiles + Set Influence window.
	# ------------------------------------------------------------------

	def _applyConstraintProfile(self, rigName, profile):
		hairSystem = self._get_hairSystem(rigName)
		total = self._get_segment_count(rigName)
		result = {}
		for i in range(total):
			index = i + 1
			strength = self._constraintProfileStrength(profile, index, total)
			pos = float(i) / float(total - 1) if total > 1 else 0.0
			cmds.setAttr('%s.attractionScale[%d].attractionScale_Position' % (hairSystem, i), pos)
			cmds.setAttr('%s.attractionScale[%d].attractionScale_FloatValue' % (hairSystem, i), strength)
			cmds.setAttr('%s.attractionScale[%d].attractionScale_Interp' % (hairSystem, i), 1)
			result[index] = strength
		return result

	def applyConstraintProfilePreset(self, profile, *args):
		rigName = cmds.text('particleRig_text', q=True, l=True).partition(': ')[2]
		strengths = self._applyConstraintProfile(rigName, profile)
		for index, strength in strengths.items():
			textFieldName = 'segment_%d_textField' % index
			if cmds.textField(textFieldName, exists=True):
				cmds.textField(textFieldName, e=True, tx="%.3f" % strength)

	def segmentOffsetUI(self, *args):
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		if cmds.window("particleSegmentOffset_window", exists=True):
			cmds.deleteUI("particleSegmentOffset_window")
		cmds.window("particleSegmentOffset_window", tlb=1, sizeable=True, mxb=False, title="Set Influence")
		cmds.frameLayout('particleSegmentOffset_frameLayout', bv=False, lv=False, mw=7, mh=7)
		cmds.text('particleRig_text', l='Particle Rig: ' + rigName, h=16, bgc=(.22, .22, .22), al='center', fn="boldLabelFont", p='particleSegmentOffset_frameLayout')

		cmds.rowLayout('particleProfile_rowLayout', nc=2, p='particleSegmentOffset_frameLayout')
		cmds.button('constraintProfile_button', l='Profile*', w=60,
		            ann='Apply a named attraction-strength distribution across all segments.')
		cmds.popupMenu('constraintProfile_popupMenu', b=1)
		for profileId, profileLabel in self.constraintProfiles:
			cmds.menuItem(profileLabel, c=partial(self.applyConstraintProfilePreset, profileId))

		cmds.rowColumnLayout('particleSegmentOffset_rowColumnLayout', numberOfColumns=2, p='particleSegmentOffset_frameLayout')
		cmds.showWindow("particleSegmentOffset_window")
		cmds.window('particleSegmentOffset_window', e=True, w=40, h=40)
		self.loadSegmentsList()

	def loadSegmentsList(self, *args):
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		hairSystem = self._get_hairSystem(rigName)
		total = self._get_segment_count(rigName)
		for i in range(total):
			index = i + 1
			cmds.text('Influence %d  ' % index, p='particleSegmentOffset_rowColumnLayout')
			value = "%.3f" % cmds.getAttr('%s.attractionScale[%d].attractionScale_FloatValue' % (hairSystem, i))
			cmds.textField('segment_%d_textField' % index, w=50, bgc=(.15, .15, .15), tx=value,
			                alwaysInvokeEnterCommandOnReturn=True, ec=partial(self.applyStrength, str(index)),
			                p='particleSegmentOffset_rowColumnLayout')

	def applyStrength(self, segmentNumber, *args):
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		value = float(cmds.textField('segment_' + segmentNumber + '_textField', q=True, tx=True))
		hairSystem = self._get_hairSystem(rigName)
		idx = int(segmentNumber) - 1
		cmds.setAttr('%s.attractionScale[%d].attractionScale_FloatValue' % (hairSystem, idx), value)

	# ------------------------------------------------------------------
	# nucleus / hairSystem settings.
	# ------------------------------------------------------------------

	def clothRigState(self, *args):
		# name kept for UI-callback symmetry with tlmClothChain.py; toggles
		# the rig's single follicle between Dynamic and Static.
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		value = cmds.checkBox('particleRig_checkBox', q=True, v=True)
		follicle = self._get_follicle(rigName)
		if follicle:
			cmds.setAttr(follicle + '.simulationMethod', 2 if value else 0)
		if value == 0:
			cmds.checkBox('particleRig_checkBox', e=True, bgc=(.4, .2, .2), l='Off ')
		else:
			cmds.checkBox('particleRig_checkBox', e=True, bgc=(.2, .4, .2), l='On ')

	def nucleusChange(self, attribute, *args):
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		nucleus = self._get_nucleus(rigName)
		if nucleus:
			value = float(cmds.textField(attribute + '_textField', q=True, tx=True))
			cmds.setAttr(nucleus + '.' + attribute, value)

	def loadHairSettings(self, *args):
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		hairSystem = self._get_hairSystem(rigName)
		if hairSystem:
			for nm in self.hairSettingsName:
				value = "%.2f" % cmds.getAttr(hairSystem + '.' + nm)
				cmds.textField(nm + '_textField', e=True, tx=value)

	def applyHairSettings(self, option, *args):
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		value = float(cmds.textField(option + '_textField', q=True, tx=True))
		hairSystem = self._get_hairSystem(rigName)
		if hairSystem:
			cmds.setAttr(hairSystem + '.' + option, value)

	def hairCollisionWidthSlider(self, *args):
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		hairSystem = self._get_hairSystem(rigName)
		if hairSystem:
			value = cmds.floatSliderGrp('hairColWidth_slider', q=True, v=True)
			cmds.setAttr(hairSystem + '.collideWidthOffset', value)

	def hairDisplayColor(self, *args):
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		hairSystem = self._get_hairSystem(rigName)
		if hairSystem:
			color = cmds.palettePort('hairDisplay_palette', q=True, rgb=True)
			mel.eval('''setAttr "%s.displayColor" -type double3 %s %s %s ;''' % (hairSystem, str(color[0]), str(color[1]), str(color[2])))

	def loadPreset(self, presetOption, *args):
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		hairSystem = self._get_hairSystem(rigName)
		if not hairSystem:
			return
		if presetOption in self.namedPresets:
			vals = self.namedPresets[presetOption]
			for nm in self.hairSettingsName:
				cmds.setAttr(hairSystem + '.' + nm, vals[nm])
		else:
			for idx, nm in enumerate(self.hairSettingsName):
				cmds.setAttr(hairSystem + '.' + nm, self.customPreset[idx])
		self.loadHairSettings()

	def loadSettings(self, *args):
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		nucleus = self._get_nucleus(rigName)
		if nucleus:
			cmds.textField('gravity_textField', e=True, tx="%.2f" % cmds.getAttr(nucleus + '.gravity'))
			cmds.textField('startFrame_textField', e=True, tx=str(cmds.getAttr(nucleus + '.startFrame')))
			cmds.textField('timeScale_textField', e=True, tx="%.2f" % cmds.getAttr(nucleus + '.timeScale'))
			cmds.textField('spaceScale_textField', e=True, tx="%.2f" % cmds.getAttr(nucleus + '.spaceScale'))
			cmds.textField('subSteps_textField', e=True, tx=str(cmds.getAttr(nucleus + '.subSteps')))

		if cmds.listRelatives('passiveColliders_grp', ad=True) is not None:
			for i in cmds.listRelatives('passiveColliders_grp') or []:
				ils = cmds.optionMenu('colliders_list', q=True, ils=True) or []
				if not ils or (i.rpartition('_')[0] + '_collider') not in ils:
					cmds.menuItem(i.rpartition('_')[0] + '_collider', l=i.rpartition('_')[0], p='colliders_list')
			colliderObj = cmds.optionMenu('colliders_list', q=True, v=True)
			if colliderObj:
				thickValue = "%.2f" % cmds.getAttr(colliderObj + '_nRigidShape1.thickness')
				cmds.textField('colliderColThickness_textField', e=True, tx=thickValue)

		hairSystem = self._get_hairSystem(rigName)
		if hairSystem:
			colWidth = cmds.getAttr(hairSystem + '.collideWidthOffset')
			cmds.floatSliderGrp('hairColWidth_slider', e=True, v=colWidth)
			color = cmds.getAttr(hairSystem + '.displayColor')[0]
			cmds.palettePort('hairDisplay_palette', e=True, rgb=[0, color[0], color[1], color[2]], redraw=True)

		self.loadHairSettings()
		self.cacheCheckUI(rigName)

	# ------------------------------------------------------------------
	# Optional goal-hunting attractor target.
	# ------------------------------------------------------------------

	def setHuntTarget(self, *args):
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		huntTransform = (cmds.textField('huntTarget_textField', q=True, tx=True) or '').strip()
		if not huntTransform:
			cmds.warning('Set a Hunt Target object first.')
			return
		if not cmds.objExists(huntTransform):
			cmds.warning('Hunt Target "%s" does not exist.' % huntTransform)
			return
		if cmds.objExists(rigName + '_huntLocators_grp'):
			cmds.warning('Hunt target already set on this rig.')
			return
		self._wireHuntTarget(rigName, huntTransform)
		cmds.button('clearHunt_button', e=True, en=True)

	def _wireHuntTarget(self, rigName, huntTransform):
		"""Blend the (already joint-driven) goal curve's CVs toward
		huntTransform, weighted tip-heavy via the same mirrored baseToTip
		math the nParticle version used for its second goalWeight -- nHair
		has no native second-goal concept, so instead of a parallel pull
		this moves the one thing the strand already attracts toward. A
		blendColors node is spliced into each CV's existing
		decomposeMatrix->controlPoints connection; only ever created when
		the user explicitly sets a Hunt Target, so a rig with none has zero
		extra nodes from this, same as before.
		"""
		hairSystem = self._get_hairSystem(rigName)
		goalCurveShape = self._get_goal_curve_shape(rigName)
		total = self._get_segment_count(rigName)
		grp = cmds.group(empty=True, name=rigName + '_huntLocators_grp', p=rigName + '_particleRig_grp')
		huntWeight = 1.0
		if cmds.floatSliderGrp('huntWeight_slider', exists=True):
			huntWeight = cmds.floatSliderGrp('huntWeight_slider', q=True, v=True)
		for i in range(total):
			index = i + 1
			loc = cmds.spaceLocator(name=rigName + '_huntPoint_%02d' % i)[0]
			cmds.pointConstraint(huntTransform, loc, mo=False)
			cmds.parent(loc, grp)

			existing = cmds.listConnections(goalCurveShape + '.controlPoints[%d]' % i,
			                                 source=True, destination=False, plugs=True) or []
			blend = cmds.createNode('blendColors', name=rigName + '_huntBlend_%02d' % i)
			if existing:
				cmds.connectAttr(existing[0], blend + '.color1', f=True)
			cmds.connectAttr(loc + '.translate', blend + '.color2', f=True)
			fall = self._constraintProfileStrength('baseToTip', total - index + 1, total)
			cmds.setAttr(blend + '.blender', fall * huntWeight)
			cmds.connectAttr(blend + '.output', goalCurveShape + '.controlPoints[%d]' % i, f=True)

	def applyHuntWeight(self, *args):
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		if not cmds.objExists(rigName + '_huntLocators_grp'):
			return
		total = self._get_segment_count(rigName)
		huntWeight = cmds.floatSliderGrp('huntWeight_slider', q=True, v=True)
		for i in range(total):
			index = i + 1
			fall = self._constraintProfileStrength('baseToTip', total - index + 1, total)
			blend = rigName + '_huntBlend_%02d' % i
			if cmds.objExists(blend):
				cmds.setAttr(blend + '.blender', fall * huntWeight)

	def clearHuntTarget(self, *args):
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		if not cmds.objExists(rigName + '_huntLocators_grp'):
			return
		goalCurveShape = self._get_goal_curve_shape(rigName)
		total = self._get_segment_count(rigName)
		for i in range(total):
			blend = rigName + '_huntBlend_%02d' % i
			if cmds.objExists(blend):
				srcConns = cmds.listConnections(blend + '.color1', source=True, destination=False, plugs=True) or []
				if srcConns and goalCurveShape:
					cmds.connectAttr(srcConns[0], goalCurveShape + '.controlPoints[%d]' % i, f=True)
				cmds.delete(blend)
		cmds.delete(rigName + '_huntLocators_grp')
		cmds.button('clearHunt_button', e=True, en=False)

	# ------------------------------------------------------------------
	# Preview + Bake -- conceptually the same as tlmClothChain.py, minus
	# the geometry-cache step (nothing here is a deforming mesh to cache).
	# No preview blend/dropoff feature, matching tlmClothChain.py: it was
	# the source of a long-standing keyframe-corruption bug there (a stray
	# setKeyframe() landing on whatever anim layer happened to be selected)
	# and was removed rather than relocated -- preview always shows 100%
	# simulation.
	# ------------------------------------------------------------------

	def cacheCheckUI(self, *args):
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		if cmds.objExists(rigName + '_preview_grp'):
			controlsList = []
			for i in cmds.listAttr(rigName + '_controlNames') or []:
				if len(i) == 1:
					controlsList.append(cmds.getAttr(rigName + '_controlNames.' + i))
			if cmds.textScrollList('controls_scrollList', q=True, ai=True) is None:
				cmds.textScrollList('controls_scrollList', e=True, append=controlsList)
			cmds.setAttr(rigName + '_hairSystem_grp.visibility', 0)
			cmds.button('undo_button', l='Undo Preview', e=True, en=True)
			cmds.button('segmentStregth_button', e=True, en=False)
			cmds.button('presets_list', e=True, en=False)
			cmds.paneLayout('pane_layout2', e=True, en=False)
		else:
			cmds.button('undo_button', l='Undo Preview', e=True, en=False)
			cmds.button('segmentStregth_button', e=True, en=True)
			cmds.button('presets_list', e=True, en=True)
			cmds.paneLayout('pane_layout2', e=True, en=True)

	def _orderControlsAlongChain(self, rigName, controlsList):
		"""Reorder controlsList by where each control actually sits along
		the rig's rest-pose spine (nearest-rest-point arc-length), rather
		than trusting the order they were selected/added in. See
		previewSim() for why this matters.
		"""
		goalCurveShape = self._get_goal_curve_shape(rigName)
		segCount = self._get_segment_count(rigName)
		restPts = [cmds.xform(goalCurveShape + '.cv[%d]' % i, q=True, ws=True, t=True) for i in range(segCount)]

		cumLen = [0.0]
		for a, b in zip(restPts[:-1], restPts[1:]):
			cumLen.append(cumLen[-1] + math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b))))

		def arcParam(ctrl):
			p = cmds.xform(ctrl, q=True, ws=True, t=True)
			bestIdx, bestDist = 0, None
			for i, rp in enumerate(restPts):
				d = sum((x - y) ** 2 for x, y in zip(p, rp))
				if bestDist is None or d < bestDist:
					bestDist, bestIdx = d, i
			return cumLen[bestIdx]

		return sorted(controlsList, key=arcParam)

	def previewSim(self, *args):
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		start_fr = int(cmds.playbackOptions(q=True, minTime=True))
		end_fr = int(cmds.playbackOptions(q=True, maxTime=True))
		cmds.currentTime(start_fr)

		if cmds.objExists(rigName + '_preview_grp'):
			cmds.warning("Particle Rig '%s' already in preview mode." % rigName)
			return

		self.controlsList = cmds.textScrollList('controls_scrollList', q=True, ai=True)
		if self.controlsList is None:
			cmds.warning('Add controls first.')
			return

		aimGroups = self._get_aimGroupList(rigName)
		tipAnchor = rigName + '_tipAnchor_grp'
		if len(self.controlsList) != len(aimGroups) + 1:
			cmds.warning('Number of controls (%d) must match number of segments (%d).' % (
				len(self.controlsList), len(aimGroups) + 1))
			return

		# controlsList order is whatever order they were selected/added in --
		# nothing enforces that matches base-to-tip segment order the way
		# joints get walked into a guaranteed order by _order_joint_chain.
		# With enough controls it's very easy to select them out of sequence
		# (marquee-select, scattered shift-clicks), which pairs the wrong
		# control with the wrong aim group below -- looks exactly like an
		# exploding bake even though the sim itself is fine. Re-sort by where
		# each control actually sits along the rig's rest-pose spine instead
		# of trusting selection order.
		self.controlsList = self._orderControlsAlongChain(rigName, self.controlsList)

		cmds.group(empty=True, name=rigName + '_preview_grp', p=rigName + '_particleRig_grp')

		# Step through the range once so the sim is populated before
		# snapshotting constraints onto it -- nucleus solvers evaluate
		# lazily, so a frame nothing queries never actually gets solved
		# (confirmed headlessly on the nParticle version of this tool: the
		# whole chain sits frozen at rest without this). Querying the
		# output curve's worldSpace every frame forces the solve to run in
		# order, frame by frame.
		outCurveShape = rigName + '_outCurveShape'
		for f in range(start_fr, end_fr + 1):
			cmds.currentTime(f)
			cmds.getAttr(outCurveShape + '.worldSpace[0]')
		cmds.currentTime(start_fr)

		for i in range(len(self.controlsList) - 1):
			ctrl = self.controlsList[i]
			st, sr = self._locked_axes(ctrl)
			cmds.parentConstraint(aimGroups[i], ctrl, sr=sr, st=st, mo=True)
			# Maya auto-creates blendParent1 only if ctrl already had
			# incoming animation on translate/rotate before this constraint
			# was added; when it exists, force it fully onto the sim so
			# the bake below captures the simulation rather than the
			# pre-existing animation.
			if cmds.attributeQuery('blendParent1', node=ctrl, exists=True):
				cmds.setAttr(ctrl + '.blendParent1', 1)

		last_ctrl = self.controlsList[-1]
		st, sr = self._locked_axes(last_ctrl)
		cmds.parentConstraint(tipAnchor, last_ctrl, sr=sr, st=st, mo=True)
		if cmds.attributeQuery('blendParent1', node=last_ctrl, exists=True):
			cmds.setAttr(last_ctrl + '.blendParent1', 1)

		# Preview must NOT stay live off the constraint -- nucleus only
		# solves forward incrementally, so scrubbing while the controls are
		# constraint-driven forces Maya to silently re-simulate from
		# startFrame every time you jump backward, which reads as "preview
		# doesn't scrub." Bake the constrained result onto a throwaway
		# override layer at full (sampleBy=1) fidelity, then drop the
		# constraint -- what's left is plain keyframes, so Preview plays
		# back exactly like the eventual bake would, with no solver in the
		# loop. undoPreview below just deletes this layer to get back to
		# live sim mode; whatever animation existed under it (baked or not)
		# is revealed automatically, which is also a more correct undo than
		# manually restoring a single snapshot pose ever was.
		cmds.refresh(su=True)
		cmds.bakeResults(self.controlsList, t=(start_fr, end_fr), sampleBy=1, bakeOnOverrideLayer=True, simulation=True)
		previewLayer = cmds.rename('BakeResults', rigName + '_previewLayer')
		self._eulerFilterRotates(self.controlsList, layerName=previewLayer)
		cmds.refresh(su=False)

		for ctrl in self.controlsList:
			for c in cmds.listRelatives(ctrl, type='parentConstraint') or []:
				cmds.delete(c)

		cmds.setAttr(rigName + '_hairSystem_grp.visibility', 0)

		cmds.spaceLocator(n=rigName + '_controlNames')
		cmds.parent(rigName + '_controlNames', rigName + '_particleRig_grp')
		cmds.setAttr(rigName + '_controlNames.visibility', 0)
		for i in range(len(self.controlsList)):
			attName = chr(i + ord('a')).upper()
			cmds.addAttr(rigName + '_controlNames', ln=attName, dt='string')
			cmds.setAttr(rigName + '_controlNames.' + attName, self.controlsList[i], type='string')

		cmds.select(clear=True)
		self.cacheCheckUI(rigName)

	def undoPreview(self, *args):
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		# Nothing to hand-restore -- previewSim bakes onto a throwaway
		# override layer rather than leaving a live constraint, so getting
		# back to "sim mode" is just deleting that layer. Maya reveals
		# whatever was underneath (baked animation or none at all)
		# automatically, which also covers a control that already had its
		# own animation before Preview -- a case the old snapshot-based
		# restore never handled correctly.
		previewLayer = rigName + '_previewLayer'
		if cmds.animLayer(previewLayer, q=True, exists=True):
			cmds.delete(previewLayer)
		cmds.delete(rigName + '_preview_grp')
		cmds.delete(rigName + '_controlNames')
		self.cacheCheckUI(rigName)
		cmds.setAttr(rigName + '_hairSystem_grp.visibility', 1)

	def bakeFinalSim(self, *args):
		rigName = cmds.optionMenu('particleRig_list', q=True, v=True)
		controlsList = cmds.textScrollList('controls_scrollList', q=True, ai=True)
		start_fr = int(cmds.playbackOptions(q=True, minTime=True))
		end_fr = int(cmds.playbackOptions(q=True, maxTime=True))
		sampleByValue = int(cmds.textField('sampleByValue_textField', q=True, tx=True))
		animLayer = cmds.checkBox('bakeOnAnimLayer_checkBox', q=True, v=True)

		if cmds.objExists(rigName + '_preview_grp'):
			# previewSim already baked the constrained result onto
			# rigName + '_previewLayer' at sampleBy=1 -- there's no live
			# constraint left to sample here. Re-bake at the user's chosen
			# sample rate while that layer is still present (this correctly
			# collapses its composited values, verified headlessly), then
			# drop it: onto a fresh override layer if "Create AnimLayer" is
			# checked, or straight onto the base animation if not.
			previewLayer = rigName + '_previewLayer'
			cmds.refresh(su=True)
			if animLayer:
				cmds.bakeResults(controlsList, t=(start_fr, end_fr), sampleBy=sampleByValue, bakeOnOverrideLayer=True, simulation=True)
				cmds.rename('BakeResults', rigName + '_simLayer')
				self._eulerFilterRotates(controlsList, layerName=rigName + '_simLayer')
			else:
				cmds.bakeResults(controlsList, t=(start_fr, end_fr), sampleBy=sampleByValue, simulation=True)
				self._eulerFilterRotates(controlsList)
			if cmds.animLayer(previewLayer, q=True, exists=True):
				cmds.delete(previewLayer)
			cmds.refresh(su=False)

			cmds.delete(rigName + '_preview_grp')
			cmds.delete(rigName + '_controlNames')

			self.cacheCheckUI(rigName)
			cmds.setAttr(rigName + '_hairSystem_grp.visibility', 0)

			if cmds.checkBox('deleteClothRig_checkBox', q=True, v=True):
				# The nucleus lives under particleSimChain_grp, not under
				# this rig's own group (so a shared nucleus survives), so
				# deleting the rig group won't take it down automatically.
				# Only delete it here if no OTHER rig still references it --
				# otherwise it's left in the scene (harmless if unused,
				# unlike accidentally deleting one another rig still needs).
				nucleusToCheck = self._get_nucleus(rigName)
				cmds.delete(rigName + '_particleRig_grp')
				if nucleusToCheck and cmds.objExists(nucleusToCheck):
					stillUsed = False
					for grp in cmds.ls('*_particleRig_grp', type='transform') or []:
						if cmds.attributeQuery('nucleusName', node=grp, exists=True) and cmds.getAttr(grp + '.nucleusName') == nucleusToCheck:
							stillUsed = True
							break
					if not stillUsed:
						cmds.delete(nucleusToCheck)
				children = cmds.listRelatives('particleSimChain_grp') or []
				if len(children) == 1:
					cmds.delete('particleSimChain_grp')

			mel.eval('print "Done!";')
		else:
			cmds.warning('Preview your simulation first.')

	# ------------------------------------------------------------------
	# UI
	# ------------------------------------------------------------------

	def UI(self, parent='particleChain_mainWindow', *args):
		if parent == 'particleChain_mainWindow':
			if cmds.window("particleChain_mainWindow", exists=True):
				cmds.deleteUI("particleChain_mainWindow")
			cmds.window("particleChain_mainWindow", sizeable=True, mnb=True, mxb=True, title="SimParticleRig", widthHeight=(490, 800))

		cmds.formLayout('SimParticleRig_form', p=parent)
		cmds.scrollLayout('scrollLayout', hst=15, vst=15, cr=True)
		cmds.formLayout(
			'SimParticleRig_form', e=True,
			attachForm=[
				('scrollLayout', 'top', 0),
				('scrollLayout', 'bottom', 0),
				('scrollLayout', 'left', 0),
				('scrollLayout', 'right', 0),
			]
		)
		cmds.separator(st='none', h=5)

		cmds.columnLayout('particleChain_frameLayout', adjustableColumn=2, columnAttach=('both', 5))
		cmds.rowLayout('rowLayout_info', nc=2, cw2=[275, 30], adjustableColumn=1)
		cmds.text('Build Particle Rig', h=16, bgc=(.22, .22, .22), al='center', fn="boldLabelFont")
		cmds.iconTextButton(w=20, h=20, style='iconOnly', image1='info.png', ann='Click here to see the script info.')
		cmds.popupMenu(b=1)
		cmds.menuItem('Refresh UI', c=refreshTool)
		cmds.menuItem('Help')

		cmds.rowLayout('createLoc_rowLayout2', nc=2, adjustableColumn=2, p='particleChain_frameLayout')
		cmds.text('Particle Rig Name:')
		cmds.textField('particleRigName_textField', w=150)

		cmds.rowLayout('nucleusChoice_rowLayout', nc=2, adjustableColumn=2, p='particleChain_frameLayout')
		cmds.text('Nucleus:', ann='Share an existing rig\'s nucleus instead of creating a new one -- hairSystems on the SAME nucleus can collide with each other; separate nuclei never see each other.')
		cmds.optionMenu('nucleusChoice_list', w=150)
		cmds.menuItem('New', p='nucleusChoice_list')
		for existingRig in self._get_existing_rig_names():
			cmds.menuItem(existingRig + '_nucleusChoice', label=existingRig, p='nucleusChoice_list')
		cmds.separator(st='none', h=10, p='particleChain_frameLayout')

		cmds.frameLayout('buildParticleRig_frameLayout', lv=False, bv=False, p='particleChain_frameLayout')

		cmds.columnLayout('pasteFrom_columnLayout', adj=1, cat=['right', 0], p='buildParticleRig_frameLayout')
		cmds.rowLayout('pasteFrom_rowLayout', nc=3, adj=1)
		cmds.text('Joints:', al='left', p='pasteFrom_rowLayout')
		cmds.iconTextButton(w=30, image1='nudgeDown.png', ann='Click here to add the selected objects into the list.', c=partial(self.addObjs, 'joints_scrollList'), p='pasteFrom_rowLayout')
		cmds.iconTextButton(w=25, image1='SP_TrashIcon.png', ann='Click here to DELETE objects from the list.', c=partial(self.delObjs, 'joints_scrollList'), p='pasteFrom_rowLayout')
		cmds.textScrollList('joints_scrollList', allowMultiSelection=True, h=80, w=195, p='pasteFrom_columnLayout',
		                     ann='Select an ordered joint chain -- each joint becomes one CV of the simulated curve. No proxy geometry needed.')

		cmds.button(l='Build Particle Rig', h=20, bgc=(.5, .7, .9), c=self.buildParticleRig, p='buildParticleRig_frameLayout')
		cmds.separator(st='none', h=5, p='buildParticleRig_frameLayout')

		cmds.rowLayout('huntTarget_rowLayout', nc=4, adjustableColumn=2, p='buildParticleRig_frameLayout')
		cmds.text('Hunt Target (optional):')
		cmds.textField('huntTarget_textField', w=140, ann='Optional attractor the tip reaches toward. Leave empty for a plain skin-follow chain.')
		cmds.button(l='Set', w=40, c=self.setHuntTarget)
		cmds.button('clearHunt_button', l='Clear', w=45, en=False, c=self.clearHuntTarget)
		cmds.rowLayout('huntWeight_rowLayout', nc=2, adjustableColumn=2, p='buildParticleRig_frameLayout')
		cmds.text('Hunt Weight:')
		cmds.floatSliderGrp('huntWeight_slider', f=True, min=0, max=1, value=1, step=.05, dc=self.applyHuntWeight)
		cmds.separator(st='none', h=5, p='buildParticleRig_frameLayout')

		### SETTINGS
		cmds.frameLayout('settings_frameLayout', lv=False, bv=False, p='particleChain_frameLayout')
		cmds.text('Settings', h=16, bgc=(.22, .22, .22), al='center', fn="boldLabelFont", p='settings_frameLayout')

		cmds.rowLayout('buildParticleRig_rowLayout3', nc=10, p='settings_frameLayout')
		cmds.text('Gravity:')
		cmds.textField('gravity_textField', w=40, alwaysInvokeEnterCommandOnReturn=True, ec=partial(self.nucleusChange, 'gravity'))
		cmds.text(' Start Frame:', al='left')
		cmds.textField('startFrame_textField', w=40, alwaysInvokeEnterCommandOnReturn=True, ec=partial(self.nucleusChange, 'startFrame'))
		cmds.text(' Time Scale:')
		cmds.textField('timeScale_textField', w=40, alwaysInvokeEnterCommandOnReturn=True, ec=partial(self.nucleusChange, 'timeScale'))
		cmds.text(' Space Scale:')
		cmds.textField('spaceScale_textField', w=40, alwaysInvokeEnterCommandOnReturn=True, ec=partial(self.nucleusChange, 'spaceScale'))
		cmds.text(' Substeps:')
		cmds.textField('subSteps_textField', w=40, alwaysInvokeEnterCommandOnReturn=True, ec=partial(self.nucleusChange, 'subSteps'))

		cmds.rowLayout('collider_rowLayout', adj=1, nc=4, p='settings_frameLayout')
		cmds.optionMenu('colliders_list', label='Colliders:', w=190, cc=self.loadSettings)
		cmds.iconTextButton(w=30, image1='nudgeLeft.png', ann='Click here to add the selected objects into the collider list.', c=self.addColliderObjs)
		cmds.iconTextButton(w=25, image1='SP_TrashIcon.png', ann='Click here to DELETE objects from the collider list.', c=self.delColliderObjs)

		cmds.rowLayout('collider_rowLayout2', nc=2, adjustableColumn=2, p='collider_rowLayout')
		cmds.text('Collision Thickness:')
		cmds.textField('colliderColThickness_textField', w=40, alwaysInvokeEnterCommandOnReturn=True, ec=self.colliderCollisionThickness)

		cmds.text('Particle Rig Settings:', fn="boldLabelFont", p='settings_frameLayout')

		cmds.rowLayout('particleRigSettings_rowLayout', adj=1, nc=5, cw1=200, p='settings_frameLayout')
		cmds.optionMenu('particleRig_list', label='Particle Rig:', w=200, cc=self.loadSettings)
		cmds.checkBox('particleRig_checkBox', bgc=(.2, .4, .2), v=True, l='On ', onc=self.clothRigState, ofc=self.clothRigState)
		cmds.text('  ')
		cmds.button('segmentStregth_button', l='Set Influence', w=100, p='particleRigSettings_rowLayout', c=self.segmentOffsetUI)
		cmds.button('presets_list', label='Presets*', w=70, p='particleRigSettings_rowLayout')
		cmds.popupMenu('presets_popupMenu', b=1)
		for i in self.presetsList:
			cmds.menuItem(i + '_preset', label=i, c=partial(self.loadPreset, i))

		cmds.button('refreshGoal_button', l='Refresh Goal', h=20, bgc=(.6, .6, .4), p='settings_frameLayout', c=self.refreshGoalAnimation,
		            ann='Re-bake the goal curve from the joints\' CURRENT animation -- use this after adding or changing keys on the joints post-Build.')
		cmds.separator(st='none', h=5, p='settings_frameLayout')

		cmds.paneLayout('pane_layout2', cn='vertical2', p='settings_frameLayout')
		cmds.columnLayout('particleRigSettings_columnLayout', adj=1, cat=['right', 0], p='pane_layout2')
		for nm, label in [('stiffness', 'Stiffness'), ('drag', 'Drag'), ('damp', 'Damp')]:
			row = 'row_' + nm
			cmds.rowLayout(row, h=19, nc=2, p='particleRigSettings_columnLayout')
			cmds.textField(nm + '_textField', w=55, h=18, alwaysInvokeEnterCommandOnReturn=True, ec=partial(self.applyHairSettings, nm))
			cmds.text(label)

		cmds.columnLayout('particleRigSettings_columnLayout2', adj=1, cat=['right', 0], p='pane_layout2')
		for nm, label in [('stretchResistance', 'Stretch Resistance'), ('stretchDamp', 'Stretch Damp')]:
			row = 'row_' + nm
			cmds.rowLayout(row, h=19, nc=2, p='particleRigSettings_columnLayout2')
			cmds.textField(nm + '_textField', w=55, h=18, alwaysInvokeEnterCommandOnReturn=True, ec=partial(self.applyHairSettings, nm))
			cmds.text(label)

		self.feedOptionMenu('particleRig')

		cmds.rowLayout('hairColWidth_rowLayout', nc=3, adjustableColumn=2, p='settings_frameLayout')
		cmds.text('Collision Thickness:')
		cmds.floatSliderGrp('hairColWidth_slider', f=True, min=0, max=10, value=0, step=.1, dc=self.hairCollisionWidthSlider)
		cmds.frameLayout('hairDisplay_frameLayout', lv=False, bv=False, p='hairColWidth_rowLayout')
		cmds.palettePort('hairDisplay_palette', dim=(1, 1), ed=True, ced=True, rgb=[0, 1, .8, 0], ce=self.hairDisplayColor)

		### PREVIEW AND BAKE
		cmds.separator(st='none', h=5, p='settings_frameLayout')
		cmds.frameLayout('preview_frameLayout', lv=False, bv=False, p='settings_frameLayout')
		cmds.text('Preview and Bake', h=16, bgc=(.22, .22, .22), al='center', fn="boldLabelFont", p='preview_frameLayout')

		cmds.columnLayout('copyFrom_columnLayout', adj=1, cat=['left', 0], p='preview_frameLayout')
		cmds.rowLayout('copyFrom_rowLayout', nc=3, adj=1)
		cmds.text('Controls: ', al='left', p='copyFrom_rowLayout')
		cmds.iconTextButton(w=30, image1='nudgeDown.png', ann='Click here to add the selected objects into the list.', c=partial(self.addObjs, 'controls_scrollList'), p='copyFrom_rowLayout')
		cmds.iconTextButton(w=25, image1='SP_TrashIcon.png', ann='Click here to DELETE objects from the list.', c=partial(self.delObjs, 'controls_scrollList'), p='copyFrom_rowLayout')
		cmds.textScrollList('controls_scrollList', allowMultiSelection=True, h=80, w=195, p='copyFrom_columnLayout')

		cmds.rowLayout('rigSimSwitch_rowLayout', nc=2, adjustableColumn=1, p='preview_frameLayout')
		cmds.button(l='Preview on Rig', bgc=(.8, .8, .6), c=self.previewSim)
		cmds.button('undo_button', l='Undo Preview', w=210, bgc=(.2, .2, .2), en=False, c=self.undoPreview)

		cmds.frameLayout('transferSim_frameLayout', lv=False, bv=False, p='particleChain_frameLayout')
		cmds.separator(st='none')
		cmds.separator(st='in')
		cmds.rowLayout('transferSim_rowLayout', nc=7, adjustableColumn=5, p='transferSim_frameLayout')
		cmds.checkBox('bakeOnAnimLayer_checkBox', l='Create AnimLayer')
		cmds.text(' Sample by:')
		cmds.textField('sampleByValue_textField', tx='1', w=35)
		cmds.text(' ')
		cmds.button(l='Bake!', bgc=(.3, .5, .3), c=self.bakeFinalSim)
		cmds.text(' ')
		cmds.checkBox('deleteClothRig_checkBox', l='Delete Particle Rig?')

		if parent == 'particleChain_mainWindow':
			cmds.showWindow("particleChain_mainWindow")

		if cmds.objExists('particleSimChain_grp'):
			self.loadSettings()
		else:
			# No 'allBaseGeo_grp' prerequisite here (unlike tlmClothChain.py) --
			# this tool builds straight off joints, no proxy geo step, so
			# there's nothing gating buildParticleRig_frameLayout beyond a
			# rig not existing yet. Only settings/transfer (which act on an
			# existing rig) stay disabled until one is built.
			cmds.frameLayout('settings_frameLayout', e=True, en=False)
			cmds.frameLayout('transferSim_frameLayout', e=True, en=False)
