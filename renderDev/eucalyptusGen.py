"""
Eucalyptus Curve Generator
Generates NURBS CV curves representing the skeletal structure of four
Australian eucalyptus species at different growth stages.

Each curve carries a 'radiusData' attribute (doubleArray) storing the
stem radius at every CV — ready for later geometry generation.

Usage (Maya Script Editor, Python):
    import eucalyptusGen
    eucalyptusGen.generate('citriodora', 'mature')
    eucalyptusGen.generate('pauciflora', 'mature', exposure=0.8)
    eucalyptusGen.generate('regnans', 'old_growth', seed=7)
    eucalyptusGen.generate('camaldulensis', 'mature', density='dense')
"""

import math
import random

import maya.cmds as cmds


# ---------------------------------------------------------------------------
# Vector math
# ---------------------------------------------------------------------------

def _v(x, y, z):
    return (x, y, z)


def _vadd(a, b):
    return (a[0]+b[0], a[1]+b[1], a[2]+b[2])


def _vsub(a, b):
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])


def _vscale(a, s):
    return (a[0]*s, a[1]*s, a[2]*s)


def _vlen(a):
    return math.sqrt(a[0]*a[0] + a[1]*a[1] + a[2]*a[2])


def _vnorm(a):
    ln = _vlen(a)
    if ln < 1e-12:
        return (0.0, 1.0, 0.0)
    return (a[0]/ln, a[1]/ln, a[2]/ln)


def _vcross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _vdot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]


def _rotate_vec(v, axis, angle_rad):
    """Rodrigues rotation of v around axis by angle_rad."""
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    k = _vnorm(axis)
    cr = _vcross(k, v)
    d = _vdot(k, v)
    return (v[0]*c + cr[0]*s + k[0]*d*(1-c),
            v[1]*c + cr[1]*s + k[1]*d*(1-c),
            v[2]*c + cr[2]*s + k[2]*d*(1-c))


def _perp_vec(v):
    """Return an arbitrary vector perpendicular to v."""
    if abs(v[0]) < 0.9:
        return _vnorm(_vcross(v, (1, 0, 0)))
    return _vnorm(_vcross(v, (0, 0, 1)))


def _lerp(a, b, t):
    return a + (b - a) * t


# ---------------------------------------------------------------------------
# Species parameters  (all lengths in cm)
# ---------------------------------------------------------------------------

SPECIES = {
    'citriodora': {
        'common_name': 'Lemon-Scented Gum',
        'height': (2500, 4000),
        'dbh_radius': (30, 65),
        'clear_bole': 0.50,
        'crown_depth': 0.35,
        'straightness': 0.92,
        'trunk_lean': 0.02,
        'taper_neiloid': 0.04,
        'taper_cone': 0.94,
        'butt_swell': 1.25,
        'scaffold_angle_from_vertical': (30, 50),
        'scaffold_count': (5, 9),
        'attraction_up': 0.35,
        'branch_droop': 0.03,
        'cluster_bias': 0.75,
        'branch_prox_clear': 0.20,
        'crown_width_ratio': (0.35, 0.50),
        # Tip-bifurcation (blood-vessel model)
        'fork_count': 2,
        'fork_angle_range': (18, 38),
        'fork_length_ratio': (0.58, 0.72),
        'min_fork_radius': 1.3,   # cm*scale; terminates recursion
        'fork_droop_base': 0.04,
        'multi_stem': False,
        'buttress': False,
        'rough_bark_height': 0.0,
    },
    'pauciflora': {
        'common_name': 'Snow Gum',
        'height_lowland': (2000, 3000),
        'height_alpine': (400, 700),
        'dbh_radius_lowland': (25, 50),
        'dbh_radius_alpine': (15, 30),
        'clear_bole_lowland': 0.35,
        'clear_bole_alpine': 0.05,
        'crown_depth': 0.60,
        'straightness_lowland': 0.5,
        'straightness_alpine': 0.15,
        'trunk_lean': 0.08,
        'twist_frequency': 3.0,
        'twist_amplitude': 0.12,
        'taper_neiloid': 0.04,
        'taper_cone': 0.88,
        'butt_swell': 1.15,
        'scaffold_angle_from_vertical': (40, 70),
        'scaffold_count': (6, 12),
        'branch_droop': 0.25,
        'cluster_bias': 0.60,
        'branch_prox_clear': 0.15,
        'crown_width_ratio': (0.40, 0.70),
        # Tip-bifurcation
        'fork_count': 2,
        'fork_angle_range': (20, 45),
        'fork_length_ratio': (0.55, 0.70),
        'min_fork_radius': 1.0,
        'fork_droop_base': 0.28,
        'multi_stem_alpine': (2, 4),
        'buttress': False,
        'rough_bark_height': 0.0,
    },
    'regnans': {
        'common_name': 'Mountain Ash',
        'height': (7000, 9000),
        'dbh_radius': (100, 250),
        'clear_bole': 0.65,
        'crown_depth': 0.30,
        'straightness': 0.96,
        'trunk_lean': 0.005,
        'taper_neiloid': 0.03,
        'taper_cone': 0.94,
        'butt_swell': 1.40,
        'scaffold_angle_from_vertical': (40, 65),
        'scaffold_count': (4, 8),
        'branch_droop': 0.10,
        'cluster_bias': 0.50,
        'branch_prox_clear': 0.15,
        'crown_width_ratio': (0.12, 0.20),
        # Tip-bifurcation
        'fork_count': 2,
        'fork_angle_range': (15, 35),
        'fork_length_ratio': (0.60, 0.75),
        'min_fork_radius': 1.5,
        'fork_droop_base': 0.12,
        'multi_stem': False,
        'buttress': True,
        'buttress_count': (4, 7),
        'buttress_height_ratio': 0.15,
        'buttress_spread': 1.8,
        'rough_bark_height': 0.15,
    },
    'camaldulensis': {
        'common_name': 'River Red Gum',
        'height': (2000, 3000),
        'dbh_radius': (50, 100),
        'clear_bole': 0.15,
        'crown_depth': 0.80,
        'straightness': 0.55,
        'trunk_lean': 0.06,
        'taper_neiloid': 0.04,
        'taper_cone': 0.85,
        'butt_swell': 1.20,
        'scaffold_angle_from_vertical': (45, 75),
        'scaffold_count': (6, 12),
        'branch_droop': 0.35,
        'cluster_bias': 0.80,
        'branch_prox_clear': 0.10,
        'crown_width_ratio': (0.80, 1.17),
        # Tip-bifurcation
        'fork_count': 2,
        'fork_angle_range': (22, 50),
        'fork_length_ratio': (0.55, 0.68),
        'min_fork_radius': 1.3,
        'fork_droop_base': 0.40,
        'multi_stem': False,
        'buttress': False,
        'rough_bark_height': 0.02,
    },
}

# Higher max_order values feed the tip-bifurcation model — radius and density
# will terminate recursion before this ceiling in most cases.
AGE_STAGES = {
    'sapling':    {'height_frac': 0.12, 'dbh_frac': 0.08, 'crown_frac': 0.20, 'max_order': 6},
    'young':      {'height_frac': 0.45, 'dbh_frac': 0.30, 'crown_frac': 0.55, 'max_order': 8},
    'mature':     {'height_frac': 1.00, 'dbh_frac': 1.00, 'crown_frac': 1.00, 'max_order': 12},
    'old_growth': {'height_frac': 1.00, 'dbh_frac': 1.20, 'crown_frac': 0.80, 'max_order': 13},
}

# Branch order names — orders > 4 are clamped to 'spray' in Maya output.
ORDER_NAMES = {
    0: 'trunk',
    1: 'scaffold',
    2: 'branch',
    3: 'twig',
    4: 'spray',
}

# min_fork_radius_mult scales the per-species min radius threshold:
#   sparse  → terminates sooner  (fewer levels, lighter crown)
#   typical → baseline
#   dense   → terminates later   (more levels, much denser crown)
DENSITY_TIERS = {
    'sparse':  {'scaffold_mult': 0.8,  'min_fork_radius_mult': 1.8,  'length_mult': 0.90},
    'typical': {'scaffold_mult': 1.0,  'min_fork_radius_mult': 1.0,  'length_mult': 1.00},
    'dense':   {'scaffold_mult': 1.2,  'min_fork_radius_mult': 0.65, 'length_mult': 1.00},
}

GOLDEN_ANGLE = 137.5

# Extra multiplier on top of the natural Murray's Law ratio for the last
# few forking generations before a lineage terminates (keyed by "terminal
# distance": 0 = this generation is the last, 1 = second-to-last, etc.).
# Plain Murray's Law reduction reads as too thick right at branch tips —
# artist feedback: sharpen the last 3 spray sections, most aggressively on
# the very last one.
_TAPER_BOOST = {0: 0.45, 1: 0.65, 2: 0.82}


def _unique_prefix(species_key):
    """Return a unique Maya node name prefix for a new tree of this species."""
    candidate = species_key
    i = 1
    while cmds.objExists(candidate + '_tree_GRP'):
        candidate = '{}_{:03d}'.format(species_key, i)
        i += 1
    return candidate


# ---------------------------------------------------------------------------
# Taper model
# ---------------------------------------------------------------------------

def _trunk_radius(t, dbh_r, neiloid_end, cone_start, butt_swell):
    """Radius at fractional height t (0=base, 1=top)."""
    t = max(0.0, min(t, 1.0))
    if t < neiloid_end:
        swell = 1.0 + (butt_swell - 1.0) * (1.0 - t / neiloid_end) ** 2
        return dbh_r * swell
    elif t < cone_start:
        frac = (t - neiloid_end) / (cone_start - neiloid_end)
        frac = max(0.0, min(frac, 1.0))
        return dbh_r * (1.0 - frac) ** 0.5
    else:
        r_at_cone = dbh_r * 0.08
        frac = (t - cone_start) / (1.0 - cone_start)
        frac = max(0.0, min(frac, 1.0))
        return max(r_at_cone * (1.0 - frac), 1.0)


def _branch_radius(distance, total_length, start_radius, end_radius, power=0.7):
    """Radius along one segment, eased from start_radius at the base to
    end_radius at the tip (thick for most of the length, tapering sharply
    right at the end). end_radius should be the next segment's start radius
    (continuous lineage) — or a small tip value only for genuinely terminal
    segments — so a branch's taper reads as one continuous line rather than
    resetting to a point at every curve boundary."""
    t = distance / total_length if total_length > 0 else 1.0
    t = max(0.0, min(t, 1.0))
    shape = 1.0 - (1.0 - t) ** power
    return max(start_radius + (end_radius - start_radius) * shape, 0.01)


# ---------------------------------------------------------------------------
# Curve data builder
# ---------------------------------------------------------------------------

class _CurveData:
    """Accumulates curve definitions before creating them in Maya."""

    def __init__(self, prefix):
        self.prefix = prefix
        self.curves = []
        self._counters = {}

    def _next_name(self, order):
        tag = ORDER_NAMES.get(min(order, 4), 'spray')
        key = tag
        self._counters.setdefault(key, 0)
        self._counters[key] += 1
        return '{}_{}{:03d}'.format(self.prefix, tag,
                                   self._counters[key])

    def add(self, points, radii, order, parent_name=None, branch_param=0.0):
        if order == 0:
            if not self._counters.get('trunk', 0):
                name = '{}_trunk'.format(self.prefix)
                self._counters['trunk'] = 1
            else:
                # Buttresses are also order 0 — give them unique names
                self._counters.setdefault('buttress', 0)
                self._counters['buttress'] += 1
                name = '{}_buttress{:03d}'.format(self.prefix,
                                                   self._counters['buttress'])
        else:
            name = self._next_name(order)
        self.curves.append({
            'name': name,
            'points': points,
            'radii': radii,
            'order': order,
            'parent': parent_name or '',
            'branch_param': branch_param,
        })
        return name


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class EucalyptusGenerator:

    def __init__(self, species='citriodora', age='mature', seed=42,
                 scale=1.0, exposure=0.5, density='typical'):
        if species not in SPECIES:
            raise ValueError('Unknown species: {}'.format(species))
        if age not in AGE_STAGES:
            raise ValueError('Unknown age stage: {}'.format(age))
        if density not in DENSITY_TIERS:
            raise ValueError('Unknown density: {}'.format(density))

        self.species_key = species
        self.sp = SPECIES[species]
        self.age = AGE_STAGES[age]
        self.age_name = age
        self.scale = scale
        self.exposure = max(0.0, min(1.0, exposure))
        self.rng = random.Random(seed)
        self._density = DENSITY_TIERS[density]
        self.density_name = density
        self._tree_prefix = _unique_prefix(species)
        self.data = _CurveData(self._tree_prefix)

    # --- parameter resolution (handles pauciflora altitude blending) ---

    def _param(self, key, low_key=None, high_key=None):
        """Resolve a species param, blending lowland/alpine for pauciflora."""
        if self.species_key == 'pauciflora' and low_key and low_key in self.sp:
            lo = self.sp[low_key]
            hi = self.sp.get(high_key, lo)
            if isinstance(lo, tuple):
                return tuple(_lerp(a, b, self.exposure) for a, b in zip(lo, hi))
            return _lerp(lo, hi, self.exposure)
        return self.sp[key]

    def _range(self, key, low_key=None, high_key=None):
        val = self._param(key, low_key, high_key)
        if isinstance(val, tuple):
            return self.rng.uniform(val[0], val[1])
        return val

    def _irange(self, key, low_key=None, high_key=None):
        val = self._param(key, low_key, high_key)
        if isinstance(val, tuple):
            return self.rng.randint(int(val[0]), int(val[1]))
        return int(val)

    # --- trunk ---

    def _build_trunk(self):
        if self.species_key == 'pauciflora':
            height = self._range('height_lowland', 'height_lowland',
                                 'height_alpine')
            dbh_r = self._range('dbh_radius_lowland', 'dbh_radius_lowland',
                                'dbh_radius_alpine')
            clear_bole = _lerp(self.sp['clear_bole_lowland'],
                               self.sp['clear_bole_alpine'], self.exposure)
            straightness = _lerp(self.sp['straightness_lowland'],
                                 self.sp['straightness_alpine'], self.exposure)
        else:
            height = self._range('height')
            dbh_r = self._range('dbh_radius')
            clear_bole = self.sp['clear_bole']
            straightness = self.sp['straightness']

        height *= self.age['height_frac'] * self.scale
        dbh_r *= self.age['dbh_frac'] * self.scale

        num_cvs = max(8, int(height / (50 * self.scale)))
        lean = self.sp['trunk_lean']

        points = []
        radii = []
        direction = _v(0, 1, 0)
        lean_dir = _vnorm(_v(self.rng.uniform(-1, 1), 0,
                             self.rng.uniform(-1, 1)))
        pos = _v(0, 0, 0)

        step = height / (num_cvs - 1)

        for i in range(num_cvs):
            t = i / (num_cvs - 1)
            r = _trunk_radius(t, dbh_r, self.sp['taper_neiloid'],
                              self.sp['taper_cone'], self.sp['butt_swell'])
            points.append(pos)
            radii.append(r)

            if i < num_cvs - 1:
                wobble_scale = (1.0 - straightness) * step * 0.15
                wobble = _v(self.rng.gauss(0, wobble_scale),
                            0,
                            self.rng.gauss(0, wobble_scale))

                twist = _v(0, 0, 0)
                if self.species_key == 'pauciflora':
                    freq = self.sp['twist_frequency']
                    amp = self.sp['twist_amplitude'] * step * self.exposure
                    twist = _v(math.sin(t * freq * math.pi * 2) * amp,
                               0,
                               math.cos(t * freq * math.pi * 1.7) * amp)

                lean_offset = _vscale(lean_dir, lean * step * t)
                step_vec = _vadd(_vscale(direction, step),
                                 _vadd(wobble, _vadd(twist, lean_offset)))
                pos = _vadd(pos, step_vec)
                direction = _vnorm(_vsub(pos, points[-1]))

        trunk_name = self.data.add(points, radii, order=0)
        return trunk_name, points, radii, height, dbh_r, clear_bole

    # --- clustered branch placement ---

    def _clustered_indices(self, start, end, count, bias):
        """
        Return `count` indices in [start, end), biased toward the distal end.
        bias=0.0 → uniform; bias→1.0 → strongly clustered at the tip.
        """
        available = end - start
        if available <= 0 or count <= 0:
            return []
        power = max(0.05, 1.0 - bias)
        indices = []
        for _ in range(count):
            u = self.rng.random()
            biased = u ** power
            idx = start + int(biased * available)
            indices.append(min(idx, end - 1))
        return sorted(indices)

    def _min_fork_radius(self):
        return (self.sp['min_fork_radius']
                * self.scale
                * self._density['min_fork_radius_mult']
                * self.age['dbh_frac'])

    def _terminal_distance(self, r, order, min_r, base_ratio, cap=3):
        """0 if the node at (r, order) is itself terminal (no children
        will be built from it), 1 if its child would be terminal, etc,
        capped at `cap` (meaning "far from the tip"). Always predicted
        using the natural, unboosted ratio."""
        dist = 0
        cur_r = r
        cur_order = order
        while dist < cap:
            is_terminal = (cur_order + 1 > self.age['max_order']
                          or cur_r <= min_r)
            if is_terminal:
                return dist
            cur_r *= base_ratio
            cur_order += 1
            dist += 1
        return dist

    def _boosted_child_radius(self, parent_fork_r, order, min_r, base_ratio):
        """Murray's Law child radius from parent_fork_r, with extra
        tapering for the last few generations before a lineage terminates
        — plain Murray's Law reads as too thick right at branch tips."""
        natural_child_r = parent_fork_r * base_ratio
        term_dist = self._terminal_distance(natural_child_r, order, min_r,
                                            base_ratio)
        boost = _TAPER_BOOST.get(term_dist, 1.0)
        return natural_child_r * boost

    # --- scaffold branches (order=1) ---

    def _build_branches(self, parent_name, parent_points, parent_radii,
                        parent_height, order=1, clear_bole_frac=0.15):
        """Build scaffold branches off the trunk, then launch tip bifurcation."""
        if order != 1:
            return

        d = self._density
        raw_count = self._irange('scaffold_count')
        count = max(1, int(round(raw_count * d['scaffold_mult'])))
        angle_range = self.sp['scaffold_angle_from_vertical']
        base_droop = self.sp['branch_droop']
        # Scaffold uses a mild distal bias — crown spreads above the clear bole.
        cluster_bias = self.sp.get('cluster_bias', 0.5) * 0.35

        num_parent_cvs = len(parent_points)
        start_idx = max(1, int(num_parent_cvs * clear_bole_frac))
        end_idx = num_parent_cvs - 1

        if start_idx >= end_idx:
            return

        branch_indices = self._clustered_indices(start_idx, end_idx,
                                                 count, cluster_bias)
        phyllotaxis_offset = self.rng.uniform(0, 360)

        for bi, parent_idx in enumerate(branch_indices):
            branch_param = parent_idx / (num_parent_cvs - 1)
            origin = parent_points[parent_idx]
            parent_r = parent_radii[parent_idx]

            branch_r = parent_r * self.rng.uniform(0.40, 0.65)
            if branch_r < 0.5 * self.scale * self.age['dbh_frac']:
                continue

            parent_dir = _v(0, 1, 0)
            if parent_idx > 0:
                parent_dir = _vnorm(_vsub(parent_points[parent_idx],
                                         parent_points[parent_idx - 1]))

            angle = math.radians(self.rng.uniform(angle_range[0],
                                                  angle_range[1]))
            phi = math.radians(phyllotaxis_offset + bi * GOLDEN_ANGLE
                               + self.rng.gauss(0, 18))

            perp = _perp_vec(parent_dir)
            branch_dir = _rotate_vec(parent_dir, perp, angle)
            branch_dir = _rotate_vec(branch_dir, parent_dir, phi)

            attraction_up = self.sp.get('attraction_up', 0.0)
            if attraction_up:
                branch_dir = _vnorm(_vadd(
                    _vscale(branch_dir, 1.0 - attraction_up),
                    _vscale((0, 1, 0), attraction_up)))

            crown_width = self._range('crown_width_ratio') * parent_height
            branch_length = crown_width * self.rng.uniform(0.15, 0.90)
            branch_length *= self.age['crown_frac'] * d['length_mult']
            branch_length = max(branch_length, 50.0 * self.scale)

            num_cvs = max(4, int(branch_length / (25 * self.scale)))
            step = branch_length / (num_cvs - 1)
            droop = base_droop * self.rng.uniform(0.5, 1.5)
            wobble_s = 0.06 * step

            # The branch's tip is where tip-bifurcation picks up. _build_fork
            # narrows fork_r by Murray's Law (plus near-tip taper boost)
            # once more to get the first forked children's actual start
            # radius, so the scaffold's own taper must end at that same
            # value (not fork_r itself) to read as one continuous line —
            # unless the fork never actually gets built (too thin already).
            fork_r = min(branch_r * 0.7, 14.0 * self.scale)
            fork_count = self.sp.get('fork_count', 2)
            base_ratio = fork_count ** (-1.0 / 2.5)
            tip_radius = 0.15 * self.scale
            if fork_r <= self._min_fork_radius():
                branch_end_r = tip_radius
            else:
                branch_end_r = self._boosted_child_radius(
                    fork_r, 2, self._min_fork_radius(), base_ratio)

            b_points = []
            b_radii = []
            pos = origin
            direction = branch_dir

            for j in range(num_cvs):
                t = j / (num_cvs - 1)
                r = _branch_radius(j * step, branch_length, branch_r,
                                   branch_end_r)
                b_points.append(pos)
                b_radii.append(r)

                if j < num_cvs - 1:
                    gravity = _v(0, -droop * step * t * 0.35, 0)
                    wobble = _v(self.rng.gauss(0, wobble_s), 0,
                                self.rng.gauss(0, wobble_s))
                    pos = _vadd(pos, _vadd(_vscale(direction, step),
                                          _vadd(gravity, wobble)))
                    if j > 0:
                        direction = _vnorm(_vsub(pos, b_points[-1]))

            branch_name = self.data.add(
                b_points, b_radii, order=1,
                parent_name=parent_name, branch_param=branch_param)

            # Launch capillary-style bifurcation from the scaffold tip.
            # (fork_r/branch_end_r above already cap the starting radius to
            # prevent regnans' massive trunk from causing exponential
            # over-branching.)
            self._build_fork(branch_name, b_points, fork_r, branch_length,
                             order=2)

    # --- tip bifurcation (the capillary / blood-vessel model) ---

    def _build_fork(self, parent_name, parent_points, parent_fork_r,
                    parent_length, order):
        """
        Recursively split a branch tip into fork_count children.
        Murray's Law governs radius reduction; min_fork_radius terminates
        recursion so the crown self-limits to a natural density.
        """
        if order > self.age['max_order']:
            return

        min_r = self._min_fork_radius()
        if parent_fork_r <= min_r:
            return

        fork_count = self.sp.get('fork_count', 2)
        # Murray's Law: sum of child cross-sections equals parent's, with
        # extra tapering applied near the tip (see _TAPER_BOOST).
        base_ratio = fork_count ** (-1.0 / 2.5)
        child_r = self._boosted_child_radius(parent_fork_r, order, min_r,
                                             base_ratio)

        # Look one generation ahead so each child's own taper ends at the
        # radius its own children will start from (continuous lineage),
        # rather than tapering to a point unless it's truly the last fork.
        # Terminality must mirror the check the recursive call itself will
        # make (child_r <= min_r), not a further-reduced grandchild value.
        child_is_terminal = (order + 1 > self.age['max_order']
                             or child_r <= min_r)
        tip_radius = 0.15 * self.scale
        if child_is_terminal:
            child_end_r = tip_radius
        else:
            child_end_r = self._boosted_child_radius(child_r, order + 1,
                                                      min_r, base_ratio)

        tip = parent_points[-1]
        parent_dir = _vnorm(_vsub(parent_points[-1], parent_points[-2]))

        fork_angle_range = self.sp.get('fork_angle_range', (20, 40))
        fork_length_ratio = self.sp.get('fork_length_ratio', (0.60, 0.70))
        fork_droop_base = self.sp.get('fork_droop_base', 0.20)

        # Droop and wobble increase as we go deeper into the crown.
        depth = order - 2
        droop = (fork_droop_base * (1.0 + depth * 0.15)
                 * self.rng.uniform(0.6, 1.4))
        gravity_mult = min(0.4 + depth * 0.12, 1.4)
        wobble_s_factor = 0.04 + depth * 0.015

        phyllotaxis_offset = self.rng.uniform(0, 360)

        for i in range(fork_count):
            angle = math.radians(self.rng.uniform(*fork_angle_range))
            phi = math.radians(phyllotaxis_offset + i * (360.0 / fork_count)
                               + self.rng.gauss(0, 12))

            perp = _perp_vec(parent_dir)
            child_dir = _rotate_vec(parent_dir, perp, angle)
            child_dir = _rotate_vec(child_dir, parent_dir, phi)

            attraction_up = self.sp.get('attraction_up', 0.0)
            if attraction_up:
                child_dir = _vnorm(_vadd(
                    _vscale(child_dir, 1.0 - attraction_up),
                    _vscale((0, 1, 0), attraction_up)))

            ratio = self.rng.uniform(*fork_length_ratio)
            child_length = parent_length * ratio
            child_length = max(child_length, 2.0 * self.scale)

            num_cvs = max(3, int(child_length / (15 * self.scale)))
            step = child_length / (num_cvs - 1)
            wobble_s = wobble_s_factor * step

            c_points = []
            c_radii = []
            pos = tip
            direction = child_dir

            for j in range(num_cvs):
                t = j / (num_cvs - 1)
                r = _branch_radius(j * step, child_length, child_r,
                                   child_end_r)
                c_points.append(pos)
                c_radii.append(r)

                if j < num_cvs - 1:
                    gravity = _v(0, -droop * step * t * gravity_mult, 0)
                    wobble = _v(self.rng.gauss(0, wobble_s), 0,
                                self.rng.gauss(0, wobble_s))
                    pos = _vadd(pos, _vadd(_vscale(direction, step),
                                          _vadd(gravity, wobble)))
                    if j > 0:
                        direction = _vnorm(_vsub(pos, c_points[-1]))

            child_name = self.data.add(c_points, c_radii, order=order,
                                       parent_name=parent_name,
                                       branch_param=1.0)
            self._build_fork(child_name, c_points, child_r, child_length,
                             order + 1)

    # --- buttresses (regnans) ---

    def _build_buttresses(self, trunk_name, trunk_points, trunk_radii, height):
        if not self.sp.get('buttress'):
            return
        count = self._irange('buttress_count')
        buttress_h = height * self.sp['buttress_height_ratio']
        spread = self.sp['buttress_spread']

        for bi in range(count):
            angle = math.radians(bi * (360.0 / count) +
                                 self.rng.uniform(-15, 15))
            outward = _v(math.cos(angle), 0, math.sin(angle))

            base_r = trunk_radii[0] * spread
            num_cvs = max(4, int(buttress_h / (30 * self.scale)))
            points = []
            radii = []

            for j in range(num_cvs):
                t = j / (num_cvs - 1)
                h = t * buttress_h
                spread_frac = (1.0 - t) ** 2
                lateral = _vscale(outward, base_r * spread_frac * 0.5)
                pos = _vadd(_v(0, h, 0), lateral)
                r = trunk_radii[0] * (1.0 - t) * 0.3
                points.append(pos)
                radii.append(max(r, 2.0))

            self.data.add(points, radii, order=0,
                          parent_name=trunk_name, branch_param=0.0)

    # --- multi-stem (pauciflora alpine) ---

    def _build_multi_stem(self):
        if self.species_key != 'pauciflora' or self.exposure < 0.5:
            return self._build_single_tree()

        stem_count = self.rng.randint(*self.sp['multi_stem_alpine'])
        all_trunks = []

        for si in range(stem_count):
            splay_angle = math.radians(self.rng.uniform(10, 35))
            splay_dir = math.radians(si * (360.0 / stem_count) +
                                     self.rng.uniform(-20, 20))

            trunk_name, pts, rad, h, dbh_r, cb = self._build_trunk()

            offset = _v(math.cos(splay_dir) * 30 * self.scale,
                        0,
                        math.sin(splay_dir) * 30 * self.scale)
            splay_vec = _v(math.cos(splay_dir) * math.sin(splay_angle),
                           math.cos(splay_angle),
                           math.sin(splay_dir) * math.sin(splay_angle))

            adjusted_pts = []
            for i, p in enumerate(pts):
                t = i / max(1, len(pts) - 1)
                lean_amount = t * splay_angle * h * 0.01
                adj = _vadd(p, _vadd(offset,
                            _vscale(splay_vec, lean_amount)))
                adjusted_pts.append(adj)

            ci = len(self.data.curves) - 1
            self.data.curves[ci]['points'] = adjusted_pts
            self.data.curves[ci]['name'] = '{}_trunk_{:03d}'.format(
                self._tree_prefix, si + 1)
            trunk_name = self.data.curves[ci]['name']

            self._build_branches(trunk_name, adjusted_pts, rad, h,
                                 order=1, clear_bole_frac=cb)
            all_trunks.append(trunk_name)

        return all_trunks

    # --- orchestrator ---

    def _build_single_tree(self):
        trunk_name, pts, rad, h, dbh_r, cb = self._build_trunk()
        self._build_buttresses(trunk_name, pts, rad, h)
        self._build_branches(trunk_name, pts, rad, h,
                             order=1, clear_bole_frac=cb)
        return [trunk_name]

    def generate(self):
        """Generate all curve data and create Maya objects."""
        if (self.species_key == 'pauciflora' and self.exposure >= 0.5):
            self._build_multi_stem()
        else:
            self._build_single_tree()
        return self._create_maya_curves()

    # --- Maya output ---

    def _create_maya_curves(self):
        tree_grp = cmds.group(empty=True,
                              name='{}_tree_GRP'.format(self._tree_prefix))

        colors = {
            0: (0.45, 0.30, 0.15),
            1: (0.55, 0.40, 0.20),
            2: (0.50, 0.55, 0.25),
            3: (0.40, 0.60, 0.30),
            4: (0.35, 0.65, 0.35),
        }

        created = []
        node_by_name = {}
        # self.data.curves is already parent-before-child order, since every
        # branch is added to the list immediately as it forks from a curve
        # that was added earlier.
        for cd in self.data.curves:
            if len(cd['points']) < 2:
                continue
            crv = cmds.curve(p=cd['points'], d=min(3, len(cd['points']) - 1),
                             name=cd['name'])
            # Parent to the actual curve this one grew from, so posing a
            # branch carries everything that forked from it along with it.
            parent_node = node_by_name.get(cd['parent'], tree_grp)
            cmds.parent(crv, parent_node)
            # Resolve to full path — short name becomes ambiguous if the scene
            # already has a same-named curve from a previous build.
            parent_long = (cmds.ls(parent_node, long=True) or [parent_node])[0]
            matches = cmds.ls(crv, long=True) or [crv]
            crv = next((m for m in matches
                        if m.rsplit('|', 1)[0] == parent_long), matches[0])
            node_by_name[cd['name']] = crv

            p0 = cd['points'][0]
            cmds.setAttr(crv + '.rotatePivot', p0[0], p0[1], p0[2], type='double3')
            cmds.setAttr(crv + '.scalePivot',  p0[0], p0[1], p0[2], type='double3')

            cmds.addAttr(crv, longName='radiusData', dataType='doubleArray')
            cmds.setAttr('{}.radiusData'.format(crv), cd['radii'],
                         type='doubleArray')

            cmds.addAttr(crv, longName='branchOrder', attributeType='short')
            cmds.setAttr('{}.branchOrder'.format(crv), cd['order'])

            if cd['parent']:
                cmds.addAttr(crv, longName='parentCurve', dataType='string')
                cmds.setAttr('{}.parentCurve'.format(crv), cd['parent'],
                             type='string')

            cmds.addAttr(crv, longName='branchParam', attributeType='double')
            cmds.setAttr('{}.branchParam'.format(crv), cd['branch_param'])

            r, g, b = colors[min(cd['order'], 4)]
            cmds.setAttr('{}.overrideEnabled'.format(crv), 1)
            cmds.setAttr('{}.overrideRGBColors'.format(crv), 1)
            cmds.setAttr('{}.overrideColorRGB'.format(crv), r, g, b)

            created.append(crv)

        cmds.select(tree_grp)
        print('[eucalyptusGen] {} — {} curves ({}, {}, {})'.format(
            self._tree_prefix, len(created),
            self.sp.get('common_name', self.species_key),
            self.age_name, self.density_name))
        return tree_grp


# ---------------------------------------------------------------------------
# Geometry generation (preview)
# ---------------------------------------------------------------------------

def _tube_from_curve(points, radii, sections=8):
    """Build a polygon tube approximating a tapered tube through points/radii.

    A NURBS circle profile is placed at every point, oriented to the local
    tangent and scaled to that point's radius, then lofted and converted to
    polygons. One mesh per curve — callers don't need to merge anything.
    """
    n = len(points)
    profiles = []
    for i in range(n):
        if i == 0:
            tangent = _vsub(points[1], points[0])
        elif i == n - 1:
            tangent = _vsub(points[-1], points[-2])
        else:
            tangent = _vsub(points[i + 1], points[i - 1])
        tangent = _vnorm(tangent)
        r = max(radii[i], 0.01)
        circ = cmds.circle(center=points[i], normal=tangent, radius=r,
                           sections=sections, ch=False)[0]
        profiles.append(circ)

    surf = cmds.loft(profiles, ch=False, degree=1, uniform=True,
                     polygon=0)[0]
    cmds.delete(profiles)

    mesh = cmds.nurbsToPoly(surf, ch=False, mnd=1, format=2, polygonType=1,
                            uNumber=1, vNumber=1)[0]
    cmds.delete(surf)

    # cmds.circle(normal=...) profiles loft into surfaces whose normals
    # point into the tube, not out of it — reverse so the outside of the
    # branch renders its front face.
    cmds.polyNormal(mesh, normalMode=0, userNormalMode=0, ch=False)

    return mesh


def generate_geometry(tree_grp):
    """Build a separate preview polygon tube mesh for every curve under
    tree_grp, using each curve's stored radiusData. No merging — each curve
    gets its own mesh, parented under a sibling '<prefix>_geo_GRP'.

    Returns the name of the geo group node.
    """
    if not cmds.objExists(tree_grp):
        raise ValueError('No tree group found: {}'.format(tree_grp))

    prefix = tree_grp.rsplit('|', 1)[-1]
    if prefix.endswith('_tree_GRP'):
        prefix = prefix[:-len('_tree_GRP')]
    geo_grp = cmds.group(empty=True, name='{}_geo_GRP'.format(prefix))

    curves = cmds.listRelatives(tree_grp, allDescendents=True,
                                type='transform', fullPath=True) or []
    created = []
    for crv in curves:
        if not cmds.attributeQuery('radiusData', node=crv, exists=True):
            continue
        radii = cmds.getAttr('{}.radiusData'.format(crv))
        shapes = cmds.listRelatives(crv, shapes=True, fullPath=True)
        if not shapes or not radii:
            continue
        spans = cmds.getAttr(shapes[0] + '.spans')
        degree = cmds.getAttr(shapes[0] + '.degree')
        num_cvs = spans + degree
        points = [cmds.pointPosition('{}.cv[{}]'.format(crv, i), world=True)
                  for i in range(num_cvs)]
        if len(points) < 2 or len(points) != len(radii):
            continue

        mesh = _tube_from_curve(points, radii)
        short_name = crv.rsplit('|', 1)[-1]
        mesh = cmds.rename(mesh, '{}_geo'.format(short_name))
        cmds.parent(mesh, geo_grp)
        created.append(mesh)

    print('[eucalyptusGen] geometry preview — {} meshes'.format(len(created)))
    return geo_grp


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(species='citriodora', age='mature', seed=42, scale=1.0,
             exposure=0.5, density='typical'):
    """Generate a eucalyptus tree as NURBS curves.

    Args:
        species:  'citriodora', 'pauciflora', 'regnans', 'camaldulensis'
        age:      'sapling', 'young', 'mature', 'old_growth'
        seed:     random seed for reproducibility
        scale:    size multiplier (1.0 = centimetres)
        exposure: 0-1, altitude/exposure for pauciflora (0=lowland, 1=alpine)
        density:  'sparse', 'typical', 'dense'

    Returns:
        Name of the top-level group node.
    """
    gen = EucalyptusGenerator(species=species, age=age, seed=seed,
                              scale=scale, exposure=exposure, density=density)
    return gen.generate()
