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
import json

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
        # After three rounds of a from-scratch "gnarled/sculptural" shape
        # language (branch twist, elbow-kinks, trunk corkscrew) that never
        # landed and made generation noticeably slower (kink/twist-heavy
        # trees hit 12,000+ curves vs citriodora's ~500), simplified back
        # to reusing citriodora's proven branch/fork shape values wholesale.
        # The only real differences from citriodora are a short trunk and
        # low forking (below), plus the pre-existing lowland/alpine
        # height/dbh/multi-stem identity (validated early on as the one
        # part that already read as a convincing snow gum).
        'common_name': 'Snow Gum',
        'height_lowland': (2000, 3000),
        'height_alpine': (400, 700),
        'dbh_radius_lowland': (25, 50),
        'dbh_radius_alpine': (15, 30),
        # Forking starts low to the ground, on a short trunk (see
        # trunk_bole_frac below) — this is the whole visual difference
        # from citriodora.
        'clear_bole_lowland': 0.10,
        'clear_bole_alpine': 0.05,
        'crown_depth': 0.35,
        # Left identical (0.92/0.92) from an earlier build — the trunk read
        # the same regardless of exposure because these values never
        # actually differed. Krummholz research (winter wind/snow damage,
        # not just splay) says alpine stems should visibly wobble/curve
        # along their own length, not just fan apart from the base.
        'straightness_lowland': 0.90,
        'straightness_alpine': 0.45,
        'trunk_lean_lowland': 0.02,
        'trunk_lean_alpine': 0.15,
        # Compound serpentine bends — alternating direction changes along
        # the trunk's length (bend toward the wind axis, then back past
        # vertical the other way, repeatedly) rather than one gentle bow.
        # (count_min, count_max) kink events and a per-kink blend-weight
        # range, both blended lowland->alpine by exposure.
        'trunk_kink_count_lowland': (0, 1),
        'trunk_kink_count_alpine': (5, 8),
        'trunk_kink_weight_lowland': (0.0, 0.05),
        'trunk_kink_weight_alpine': (0.70, 0.95),
        # Same serpentine-kink mechanism, applied to scaffold branches and
        # (fading with depth) forks — gentler than the trunk's since
        # branches are much shorter/thinner and the trunk's own weight
        # range would read as chaotic rather than sculptural at that scale.
        'branch_kink_count_lowland': (0, 1),
        'branch_kink_count_alpine': (1, 3),
        'branch_kink_weight_lowland': (0.10, 0.20),
        'branch_kink_weight_alpine': (0.30, 0.55),
        'taper_neiloid': 0.04,
        'taper_cone': 0.94,
        'butt_swell': 1.25,
        # Trunk only builds up to this fraction of the tree's natural full
        # height — a short, thick bole (like citriodora's trunk cut off
        # just below where it would fork) instead of a tall leading stem.
        'trunk_bole_frac_lowland': 0.30,
        'trunk_bole_frac_alpine': 0.15,
        # Forking this low on the trunk means branches launch from a point
        # that's barely past the neiloid swell (94-98% of dbh_r, vs
        # citriodora's ~70% at its 50%-up attach point) — the default
        # scaffold_radius_frac (0.40-0.65 of the *local* parent radius,
        # tuned around an already-tapered attach point) would read as
        # branches roughly 1.4-1.7x too thick here. Scaled down so absolute
        # branch thickness (relative to dbh_r) lands close to citriodora's,
        # despite the much fatter attach point.
        'scaffold_radius_frac': (0.30, 0.45),
        # Crown must climb ~90-95% of total height from such a low clear
        # bole, vs citriodora's ~50% — see branch_length_mult comment in
        # _build_branches. ~1.85x is (1 - clear_bole) for pauciflora over
        # (1 - clear_bole) for citriodora, i.e. roughly double the vertical
        # distance the crown needs to cover with the same reach formula.
        'branch_length_mult': 1.85,
        # Real canopies read denser toward the top from light competition;
        # pauciflora's very low clear_bole meant branches launching right
        # near the ground got exactly as much twig-forking depth as ones
        # launching near the top, reading as uniformly overgrown ("far too
        # much foliage... especially lower down should be quite sparse").
        # Boosts min_fork_radius (terminates sub-forking sooner) for
        # scaffold branches proportional to how low they attach — see
        # low_crown_sparsity in _build_branches. 0 for every other species.
        'low_crown_sparsity': 0.5,
        # Replaces the generic scaffold+fork model for the crown's own
        # first tier — real snow gums are defined by 2-3 long, thick,
        # snaking limbs (same weight class as the trunk, not thin scaffold
        # branches) that occasionally reiterate into more such limbs
        # further up the tree; thinner lateral branches sprout at
        # arbitrary points along a limb's length rather than only at a
        # forking tip. See _build_main_limbs/_spawn_main_limbs/
        # _build_limb_curve. Not used by any other species.
        'main_limb_count': (2, 3),
        'main_limb_max_reiterations': 3,
        # Raised from 0.25 — with only 2-3 limbs at the base and rare
        # reiteration, the tree read as 2 huge dominant limbs plus
        # everything else (rare reiterations + lateral branches) bunched
        # in a narrow middle band, unbalanced ("the two longest branches
        # are miles too long... the rest are far too clumped in the
        # middle"). More frequent reiteration fills out the height with
        # successive shorter limb generations instead of 2 outliers.
        'main_limb_reiterate_prob': 0.55,
        # Fraction of the remaining vertical climb-to-target-height a limb
        # aims to cover itself (randomised so limbs don't all read as the
        # same length). Halved from (0.35, 0.55) per explicit feedback
        # ("could be 50% shorter") — combined with more frequent
        # reiteration above, more (shorter) limb generations now share
        # the climb instead of 2 limbs each grabbing over a third of it.
        'main_limb_climb_frac': (0.18, 0.30),
        # End radius as a fraction of a limb's own start radius — gentle,
        # trunk-like taper along its length (not the branch model's sharp
        # ease-to-a-point).
        'main_limb_taper': (0.55, 0.78),
        # Wider than scaffold_angle_from_vertical — limbs should read as
        # wandering/snaking in any direction, not consistently ascending.
        'main_limb_angle_from_vertical': (35, 75),
        # Much weaker than the branch-level attraction_up (0.35) — per
        # creative direction, the main limbs themselves twist and turn
        # every which way, while it's specifically the *lateral* branches
        # off them that trend more upward.
        'main_limb_attraction_up': 0.10,
        # Limb-specific kink tuning (see _build_limb_curve) — much more
        # dramatic than the trunk's own kinks even at lowland exposure,
        # since "the limbs need way more S-shape" was explicit feedback
        # regardless of exposure. Deliberately not as steep a
        # lowland->alpine falloff as the trunk's kinks. Kept a notch below
        # the first pass (which used up to 0.80 weight) — several
        # independent, non-ramped, high-weight kinks in a row could
        # compound into a self-crossing tangle even on a long, well-
        # resolved curve (measured up to 315% lateral deviation of chord).
        'main_limb_kink_count_lowland': (4, 6),
        'main_limb_kink_count_alpine': (6, 9),
        'main_limb_kink_weight_lowland': (0.38, 0.55),
        'main_limb_kink_weight_alpine': (0.55, 0.78),
        # Everything below is deliberately identical to citriodora.
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
        # Higher than citriodora's 1.3 (not "identical" — a deliberate
        # compensation): forking low on the trunk means branches start
        # from a much fatter point (trunk hasn't tapered yet that low
        # down), giving Murray's Law more radius to spend before hitting
        # the floor — at 1.3 this produced clean, uninterrupted doubling
        # for 7+ generations (thousands of curves, visibly slow to
        # generate) instead of citriodora's early attrition. 2.0 brings
        # worst-case (old_growth, multi-stem) curve counts from ~13,800
        # down to under 1,500.
        'min_fork_radius': 2.0,
        'fork_droop_base': 0.04,
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
                 scale=1.0, exposure=0.5, density='typical',
                 include_branches=True, bole_frac_override=None):
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
        self._include_branches = include_branches
        self._bole_frac_override = bole_frac_override
        self._tree_prefix = _unique_prefix(species)
        self.data = _CurveData(self._tree_prefix)
        self._limb_counter = 0

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

    def _clamp_ground(self, pos):
        """Snow gum only: the wide-angle main limbs and their kinks can
        otherwise dip a curve below the ground plane (y<0) — real trees
        obviously don't grow into the dirt. Every other species is
        untouched (their much higher clear_bole and gentler wobble/droop
        never produced this in practice, and this guard is species-gated
        to guarantee zero behavior change for them either way)."""
        if self.species_key == 'pauciflora' and pos[1] < 0.0:
            return _v(pos[0], 0.0, pos[2])
        return pos

    def _pauciflora_kink_params(self, prefix='trunk'):
        """(count_min, count_max, weight_lo, weight_hi) for a curve's
        compound-serpentine kinks, blended lowland->alpine by exposure.
        `prefix` selects which species key pair to read (e.g. 'trunk' or
        'branch'), so the trunk and branches/forks can carry independently
        tuned kink intensity while sharing the same blend/lookup logic."""
        lo_count = self.sp.get('{}_kink_count_lowland'.format(prefix), (0, 0))
        hi_count = self.sp.get('{}_kink_count_alpine'.format(prefix), (0, 0))
        count_min = int(round(_lerp(lo_count[0], hi_count[0], self.exposure)))
        count_max = int(round(_lerp(lo_count[1], hi_count[1], self.exposure)))
        count_max = max(count_min, count_max)
        lo_w = self.sp.get('{}_kink_weight_lowland'.format(prefix), (0.0, 0.0))
        hi_w = self.sp.get('{}_kink_weight_alpine'.format(prefix), (0.0, 0.0))
        w_lo = _lerp(lo_w[0], hi_w[0], self.exposure)
        w_hi = _lerp(lo_w[1], hi_w[1], self.exposure)
        return count_min, count_max, w_lo, w_hi

    def _make_kink_events(self, count_min, count_max, w_lo, w_hi, seed_dir,
                          t_lo=0.10, t_span=0.85, t_power=0.5,
                          ramp_weight=True):
        """Compound serpentine kinks: a handful of discrete direction
        changes (t, target_dir, blend_weight), meant to be fed straight
        into a curve-building loop's `direction` (unlike fine wobble, which
        only jitters the emitted point, this actually redirects growth so
        each bend persists and compounds into the next). The first kink
        leans toward seed_dir (e.g. the tree's wind axis, or a branch's own
        launch direction); later kinks swing back roughly the *opposite*
        azimuth each time (with vertical swing and some noise) — a true
        S-curve alternates back and forth across one axis, whereas a fresh
        random direction each time reads as a messy zigzag.

        t_power controls how bend positions are distributed: 0.5 (default,
        used by the trunk) skews toward the tail end of the segment; 1.0
        (used by main limbs) spreads them evenly along the whole length.
        ramp_weight=True (default) ramps weight up toward the last kink so
        the most dramatic bend lands closest to the tip (trunk); False
        draws each kink's weight independently from the same (w_lo, w_hi)
        range, for a consistently snake-like character throughout (limbs)
        rather than one building finale."""
        kink_count = (self.rng.randint(count_min, count_max)
                     if count_max > 0 else 0)
        if kink_count <= 0:
            return []
        t_positions = sorted(t_lo + t_span * (self.rng.random() ** t_power)
                             for _ in range(kink_count))
        kink_events = []
        prev_az = math.atan2(seed_dir[2], seed_dir[0])
        for k, tk in enumerate(t_positions):
            if ramp_weight:
                ramp = k / max(1, kink_count - 1)
                weight = _lerp(w_lo, w_hi, ramp)
            else:
                weight = self.rng.uniform(w_lo, w_hi)
            if k == 0:
                target = seed_dir
            else:
                az = prev_az + math.pi + math.radians(self.rng.gauss(0, 20))
                vert = self.rng.uniform(-0.5, 0.85)
                horiz_mag = (1.0 - vert * vert) ** 0.5
                target = _vnorm(_v(math.cos(az) * horiz_mag, vert,
                                  math.sin(az) * horiz_mag))
                prev_az = az
            kink_events.append((tk, target, weight))
        return kink_events

    def _attraction_up(self):
        """Upward-bending bias applied to scaffold/fork launch directions
        (and dampens droop itself, not just the launch angle — see call
        sites). 0.0 unless the species sets 'attraction_up'."""
        return self.sp.get('attraction_up', 0.0)

    # --- trunk ---

    def _build_trunk(self, lean_dir_rad=None, persist=True):
        """lean_dir_rad: optional fixed lean/wobble-bias direction (radians,
        XZ-plane) to use instead of drawing an independent random one — lets
        a caller (multi-stem alpine trees) make the trunk's own micro-curve
        bend the same way as the tree's overall wind-biased splay, instead
        of two unrelated random directions partly cancelling out.

        persist=False skips adding the trunk as its own Maya curve — used
        by the Snow Gum ground-up rebuild, which folds the trunk's points
        into each main limb's curve instead (one continuous curve/loft from
        root to limb tip, no separate trunk piece)."""
        if self.species_key == 'pauciflora':
            height = self._range('height_lowland', 'height_lowland',
                                 'height_alpine')
            dbh_r = self._range('dbh_radius_lowland', 'dbh_radius_lowland',
                                'dbh_radius_alpine')
            clear_bole = _lerp(self.sp['clear_bole_lowland'],
                               self.sp['clear_bole_alpine'], self.exposure)
            straightness = _lerp(self.sp['straightness_lowland'],
                                 self.sp['straightness_alpine'], self.exposure)
            bole_frac = _lerp(self.sp.get('trunk_bole_frac_lowland', 1.0),
                              self.sp.get('trunk_bole_frac_alpine', 1.0),
                              self.exposure)
            lean = _lerp(self.sp['trunk_lean_lowland'],
                        self.sp['trunk_lean_alpine'], self.exposure)
        else:
            height = self._range('height')
            dbh_r = self._range('dbh_radius')
            clear_bole = self.sp['clear_bole']
            straightness = self.sp['straightness']
            bole_frac = 1.0
            lean = self.sp['trunk_lean']

        if self._bole_frac_override is not None:
            bole_frac = self._bole_frac_override

        height *= self.age['height_frac'] * self.scale
        dbh_r *= self.age['dbh_frac'] * self.scale

        # The trunk curve itself only physically extends to bole_frac of
        # the tree's natural full height (a short, thick bole rather than a
        # tall leading stem) — but `height` is still returned/used as-is
        # for crown sizing downstream, since a naturally tall tree should
        # still get a big crown even if its visible trunk is short.
        built_height = height * bole_frac
        num_cvs = max(8, int(built_height / (50 * self.scale)))

        points = []
        radii = []
        direction = _v(0, 1, 0)
        if lean_dir_rad is not None:
            lean_dir = _v(math.cos(lean_dir_rad), 0, math.sin(lean_dir_rad))
        else:
            lean_dir = _vnorm(_v(self.rng.uniform(-1, 1), 0,
                                 self.rng.uniform(-1, 1)))
        pos = _v(0, 0, 0)

        step = built_height / (num_cvs - 1)

        # Compound serpentine kinks (pauciflora only) — see
        # _make_kink_events for the mechanism itself. The trunk's first
        # kink leans toward the shared wind axis, tying back to the tree-
        # level splay so the whole tree still reads as wind-shaped.
        kink_events = []
        if self.species_key == 'pauciflora':
            count_min, count_max, w_lo, w_hi = self._pauciflora_kink_params()
            kink_events = self._make_kink_events(count_min, count_max,
                                                 w_lo, w_hi, lean_dir)
        next_kink = 0

        for i in range(num_cvs):
            t = i / (num_cvs - 1)
            r = _trunk_radius(t, dbh_r, self.sp['taper_neiloid'],
                              self.sp['taper_cone'], self.sp['butt_swell'])
            points.append(pos)
            radii.append(r)

            if i < num_cvs - 1:
                while (next_kink < len(kink_events)
                      and t >= kink_events[next_kink][0]):
                    _, target, weight = kink_events[next_kink]
                    direction = _vnorm(_vadd(_vscale(direction, 1.0 - weight),
                                            _vscale(target, weight)))
                    next_kink += 1

                wobble_scale = (1.0 - straightness) * step * 0.15
                wobble = _v(self.rng.gauss(0, wobble_scale),
                            0,
                            self.rng.gauss(0, wobble_scale))

                lean_offset = _vscale(lean_dir, lean * step * t)
                step_vec = _vadd(_vscale(direction, step),
                                 _vadd(wobble, lean_offset))
                pos = self._clamp_ground(_vadd(pos, step_vec))
                direction = _vnorm(_vsub(pos, points[-1]))

        trunk_name = self.data.add(points, radii, order=0) if persist else None
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

    # --- main limbs (pauciflora only — see main_limb_* species keys) ---

    def _build_main_limbs(self, parent_name, parent_points, parent_radii,
                         tree_height, clear_bole_frac, dbh_r,
                         combine_trunk=False):
        """Entry point for snow gum's crown architecture. Real snow gums
        are defined by a small number of long, thick, snaking limbs — not
        the generic model's many thin scaffold branches radiating from one
        low point. The trunk's own taper narrows all the way to a small
        floor by its literal tip regardless of how short the stub is (that
        floor is what keeps the *trunk itself* from reading as fat — see
        the taper fix earlier this session), so it's the wrong radius to
        hand off from here: a dbh_r-derived reference is used instead,
        while the trunk's actual tip *position* is kept for visual
        continuity (no gap between trunk and limbs).

        combine_trunk=True is the ground-up rebuild mode: parent_points/
        parent_radii (the trunk, not persisted as its own curve by the
        caller) are folded into each limb's own curve instead of being a
        separate piece, and lateral branches/reiteration are skipped —
        this step is trunk+first-limb geo only."""
        origin = parent_points[-1]
        tip_dir = _vnorm(_vsub(parent_points[-1], parent_points[-2]))
        pre_split_r = dbh_r * 0.85
        remaining_climb = tree_height * (1.0 - clear_bole_frac)
        trunk_points = parent_points if combine_trunk else None
        trunk_radii = parent_radii if combine_trunk else None
        self._spawn_main_limbs(parent_name, origin, tip_dir, pre_split_r,
                               remaining_climb, tree_height, reiteration=0,
                               trunk_points=trunk_points,
                               trunk_radii=trunk_radii)

    def _spawn_main_limbs(self, parent_name, origin, seed_dir, parent_r,
                         remaining_climb, tree_height, reiteration,
                         trunk_points=None, trunk_radii=None):
        """Split parent_r (Murray's Law) into main_limb_count long limbs,
        build each, attach lateral branches along its length, then
        recurse: each limb may itself reiterate into more long limbs
        further up (capped by main_limb_max_reiterations so the skeleton
        stays a small number of dominant limbs, not an exponential
        cascade back into the old 'weed' look).

        trunk_points/trunk_radii present (ground-up rebuild mode): skip
        lateral branches and reiteration entirely — this step builds the
        trunk+first-limb combined curve only, nothing further out on it
        yet."""
        combine_trunk = trunk_points is not None
        count = self._irange('main_limb_count')
        base_ratio = count ** (-1.0 / 2.5)
        child_r = parent_r * base_ratio
        if child_r <= self._min_fork_radius() or remaining_climb <= 30 * self.scale:
            return

        angle_range = self.sp['main_limb_angle_from_vertical']
        attraction_up = self.sp.get('main_limb_attraction_up', 0.0)
        perp_seed = _perp_vec(seed_dir)
        phyllotaxis_offset = self.rng.uniform(0, 360)

        for i in range(count):
            angle = math.radians(self.rng.uniform(*angle_range))
            phi = math.radians(phyllotaxis_offset + i * (360.0 / count)
                               + self.rng.gauss(0, 15))
            limb_dir = _rotate_vec(seed_dir, perp_seed, angle)
            limb_dir = _rotate_vec(limb_dir, seed_dir, phi)
            if attraction_up:
                limb_dir = _vnorm(_vadd(
                    _vscale(limb_dir, 1.0 - attraction_up),
                    _vscale((0, 1, 0), attraction_up)))

            climb_frac = self._range('main_limb_climb_frac')
            limb_climb = remaining_climb * climb_frac
            # Floor raised from 0.2 to 0.35 — a shallow-angle (near-
            # horizontal) limb was getting its length amplified up to 5x
            # just from this conversion, on top of climb_frac, producing
            # occasional single segments 2000+ cm long even after halving
            # climb_frac ("miles too long" outliers). Capped to ~2.9x.
            vert_component = max(0.35, abs(limb_dir[1]))
            limb_length = limb_climb / vert_component

            limb_name, limb_points, limb_radii = self._build_limb_curve(
                parent_name, origin, limb_dir, child_r, limb_length,
                trunk_points=trunk_points, trunk_radii=trunk_radii)

            if combine_trunk:
                # Ground-up rebuild, step 1: trunk+first-limb geo only —
                # no lateral branches, no further limb reiteration yet.
                continue

            if self._include_branches:
                # length_mult_override=1.0 bypasses pauciflora's
                # branch_length_mult (1.85x, tuned to compensate for the
                # *old* trunk-direct scaffold model needing to climb
                # ~90-95% of total height) — lateral branches off a limb
                # are a secondary tier now that the limb itself carries
                # the height, so they should use the plain (citriodora-
                # equivalent) reach, not that compensation.
                self._build_branches(limb_name, limb_points, limb_radii,
                                     tree_height, order=1,
                                     clear_bole_frac=0.0,
                                     length_mult_override=1.0)

            max_reiter = self.sp.get('main_limb_max_reiterations', 0)
            reiter_prob = self.sp.get('main_limb_reiterate_prob', 0.0)
            if reiteration < max_reiter and self.rng.random() < reiter_prob:
                new_remaining = remaining_climb - limb_climb
                if new_remaining > 30 * self.scale:
                    new_dir = _vnorm(_vsub(limb_points[-1], limb_points[-2]))
                    self._spawn_main_limbs(limb_name, limb_points[-1],
                                          new_dir, limb_radii[-1],
                                          new_remaining, tree_height,
                                          reiteration + 1)

    def _build_limb_curve(self, parent_name, origin, direction, start_r,
                         length, trunk_points=None, trunk_radii=None):
        """One long, thick, snaking main limb — structurally a
        continuation of the trunk (gentle linear taper), not a thin
        branch. Lateral branches attach to it afterward via
        _build_branches the same way they'd attach to a trunk.

        Uses its own main_limb_kink_* tuning rather than the trunk's:
        the trunk's kink mechanism was tuned for a short curve with bends
        concentrated near the tail end, which read as too sparse spread
        across a much longer limb. Limbs use t_power=1.0 (bends spread
        evenly along the whole length, not piling up near the tip) and
        ramp_weight=False (every bend similarly dramatic — a consistently
        snake-like character throughout, not one building finale).

        trunk_points/trunk_radii present (ground-up rebuild mode): this
        limb's curve is prefixed with the trunk's own points/radii so the
        two are one continuous curve/loft, not two pieces meeting at a
        seam. The trunk's own taper narrows to a ~1cm floor by its literal
        tip (see _build_main_limbs) which doesn't match this limb's much
        fatter start_r, so the trunk radii's tail is blended toward
        start_r over its last 20% rather than left as a hard step."""
        # Denser than the 50-unit spacing used elsewhere (trunk, branches)
        # — limbs are now shorter (halved climb_frac) but still need
        # enough CVs to carry a dramatic kink smoothly rather than tripping
        # the coarse-curve gate below.
        num_cvs = max(10, int(length / (25 * self.scale)))
        step = length / (num_cvs - 1)
        taper_lo, taper_hi = self.sp.get('main_limb_taper', (0.55, 0.78))
        end_r = start_r * self.rng.uniform(taper_lo, taper_hi)

        straightness = _lerp(self.sp['straightness_lowland'],
                             self.sp['straightness_alpine'], self.exposure)

        # A coarse (few-CV) segment can't render a smooth bend — same
        # reasoning as the branch/fork kink gate.
        kink_events = []
        if num_cvs >= 9:
            count_min, count_max, w_lo, w_hi = self._pauciflora_kink_params(
                'main_limb')
            kink_events = self._make_kink_events(count_min, count_max, w_lo,
                                                 w_hi, direction, t_lo=0.05,
                                                 t_span=0.90, t_power=1.0,
                                                 ramp_weight=False)
        next_kink = 0

        points = []
        radii = []
        pos = origin
        cur_dir = direction

        for j in range(num_cvs):
            t = j / (num_cvs - 1)
            r = _lerp(start_r, end_r, t)
            points.append(pos)
            radii.append(r)

            if j < num_cvs - 1:
                while (next_kink < len(kink_events)
                      and t >= kink_events[next_kink][0]):
                    _, target, weight = kink_events[next_kink]
                    cur_dir = _vnorm(_vadd(
                        _vscale(cur_dir, 1.0 - weight),
                        _vscale(target, weight)))
                    next_kink += 1

                wobble_scale = (1.0 - straightness) * step * 0.15
                wobble = _v(self.rng.gauss(0, wobble_scale), 0,
                           self.rng.gauss(0, wobble_scale))
                # Limbs barely droop under gravity — they're trunk-like
                # and mostly kink-driven, not the pendulous-branch droop
                # model used for lateral branches.
                droop = self.sp.get('branch_droop', 0.0) * 0.3
                gravity = _v(0, -droop * step * t, 0)
                new_pos = self._clamp_ground(_vadd(
                    pos, _vadd(_vscale(cur_dir, step),
                              _vadd(wobble, gravity))))
                if j > 0:
                    cur_dir = _vnorm(_vsub(new_pos, pos))
                pos = new_pos

        if trunk_points:
            # Blend the trunk's tail radii toward this limb's start_r over
            # the last 20% of the trunk — its own taper narrows to a ~1cm
            # floor by the literal tip (see _build_main_limbs), which would
            # otherwise show as a hard step right at the join.
            n = len(trunk_radii)
            blend_start = max(0, int(n * 0.8))
            span = max(1, (n - 1) - blend_start)
            blended_trunk_radii = list(trunk_radii)
            for i in range(blend_start, n):
                t = (i - blend_start) / span
                blended_trunk_radii[i] = _lerp(trunk_radii[i], start_r, t)
            # trunk_points[-1] == origin == points[0] — drop the duplicate.
            curve_points = list(trunk_points[:-1]) + points
            curve_radii = blended_trunk_radii[:-1] + radii
        else:
            curve_points = points
            curve_radii = radii

        limb_name = self.data.add(curve_points, curve_radii, order=0,
                                  parent_name=parent_name)
        idx = len(self.data.curves) - 1
        self._limb_counter += 1
        limb_name = '{}_limb{:03d}'.format(self._tree_prefix,
                                           self._limb_counter)
        self.data.curves[idx]['name'] = limb_name
        return limb_name, points, radii

    # --- scaffold branches (order=1) ---

    def _build_branches(self, parent_name, parent_points, parent_radii,
                        parent_height, order=1, clear_bole_frac=0.15,
                        length_mult_override=None):
        """Build scaffold branches off the trunk, then launch tip
        bifurcation. length_mult_override bypasses the species'
        branch_length_mult when set (used when this is called for
        lateral branches off a pauciflora main limb rather than directly
        off the trunk — see _spawn_main_limbs)."""
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

            r_frac_lo, r_frac_hi = self.sp.get('scaffold_radius_frac',
                                               (0.40, 0.65))
            branch_r = parent_r * self.rng.uniform(r_frac_lo, r_frac_hi)
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

            attraction_up = self._attraction_up()
            if attraction_up:
                branch_dir = _vnorm(_vadd(
                    _vscale(branch_dir, 1.0 - attraction_up),
                    _vscale((0, 1, 0), attraction_up)))

            crown_width = self._range('crown_width_ratio') * parent_height
            branch_length = crown_width * self.rng.uniform(0.15, 0.90)
            branch_length *= self.age['crown_frac'] * d['length_mult']
            # branch_length_mult compensates species whose clear_bole is far
            # from citriodora's 0.5 (which crown_width_ratio was tuned
            # around, covering the remaining ~50% of height above the
            # clear bole) — pauciflora forks from just 5-10% up the trunk,
            # so its crown must climb ~90-95% of the tree's height with the
            # same reach formula, and fell dramatically short (measured
            # ~50% of target height) without this.
            length_mult = (length_mult_override
                          if length_mult_override is not None
                          else self.sp.get('branch_length_mult', 1.0))
            branch_length *= length_mult
            branch_length = max(branch_length, 50.0 * self.scale)

            num_cvs = max(4, int(branch_length / (25 * self.scale)))
            step = branch_length / (num_cvs - 1)
            droop = base_droop * self.rng.uniform(0.5, 1.5)
            wobble_s = 0.06 * step

            # Low-crown sparsity: scaffold branches attaching near the base
            # (branch_param near 0) get a boosted min-fork-radius floor, so
            # their sub-forking terminates sooner and reads sparser — real
            # canopies are denser toward the top from light competition,
            # but pauciflora's very low clear_bole meant branches starting
            # right near the ground got exactly as much twig density as
            # ones starting near the top, reading as uniformly overgrown.
            # Zero effect on other species (low_crown_sparsity defaults 0).
            sparsity = self.sp.get('low_crown_sparsity', 0.0)
            min_r_mult = 1.0 + sparsity * max(0.0, 1.0 - branch_param)

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
            min_r_here = self._min_fork_radius() * min_r_mult
            if fork_r <= min_r_here:
                branch_end_r = tip_radius
            else:
                branch_end_r = self._boosted_child_radius(
                    fork_r, 2, min_r_here, base_ratio)

            # Compound serpentine kinks — same mechanism/S-curve character
            # as the trunk (see _make_kink_events), just scaled to a
            # branch's much shorter length via its own species keys.
            # A coarse (few-CV) segment can't render a smooth S-curve — a
            # kink bending a ~4-point branch looks like a jagged snap
            # rather than a bow, so only apply kinks where there's enough
            # resolution to carry the bend gracefully.
            kink_events = []
            if self.species_key == 'pauciflora' and num_cvs >= 6:
                bc_min, bc_max, bw_lo, bw_hi = self._pauciflora_kink_params(
                    'branch')
                kink_events = self._make_kink_events(bc_min, bc_max,
                                                     bw_lo, bw_hi, branch_dir)
            next_kink = 0

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
                    while (next_kink < len(kink_events)
                          and t >= kink_events[next_kink][0]):
                        _, target, weight = kink_events[next_kink]
                        direction = _vnorm(_vadd(
                            _vscale(direction, 1.0 - weight),
                            _vscale(target, weight)))
                        next_kink += 1

                    # attraction_up also dampens droop itself, not just the
                    # one-time launch bend — otherwise a high-droop species
                    # accumulates enough downward pull over a long branch
                    # to arc all the way over into a closed loop. Species
                    # with tiny droop (citriodora) barely notice since
                    # there's little droop left to dampen.
                    gravity = _v(0, -droop * (1.0 - attraction_up)
                                * step * t * 0.35, 0)
                    wobble = _v(self.rng.gauss(0, wobble_s), 0,
                                self.rng.gauss(0, wobble_s))
                    new_pos = self._clamp_ground(_vadd(
                        pos, _vadd(_vscale(direction, step),
                                  _vadd(gravity, wobble))))
                    if j > 0:
                        direction = _vnorm(_vsub(new_pos, pos))
                    pos = new_pos

            branch_name = self.data.add(
                b_points, b_radii, order=1,
                parent_name=parent_name, branch_param=branch_param)

            # Launch capillary-style bifurcation from the scaffold tip.
            # (fork_r/branch_end_r above already cap the starting radius to
            # prevent regnans' massive trunk from causing exponential
            # over-branching.)
            self._build_fork(branch_name, b_points, fork_r, branch_length,
                             order=2, min_r_mult=min_r_mult)

    # --- tip bifurcation (the capillary / blood-vessel model) ---

    def _build_fork(self, parent_name, parent_points, parent_fork_r,
                    parent_length, order, min_r_mult=1.0):
        """
        Recursively split a branch tip into fork_count children.
        Murray's Law governs radius reduction; min_fork_radius terminates
        recursion so the crown self-limits to a natural density.

        min_r_mult: per-lineage multiplier on min_fork_radius, set once by
        the originating scaffold branch (see low_crown_sparsity in
        _build_branches) and carried unchanged through every recursive
        call, so a whole low-attached branch's lineage stays sparser.
        """
        if order > self.age['max_order']:
            return

        min_r = self._min_fork_radius() * min_r_mult
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
        # Kink weight fades with depth — a deep twig getting the same
        # dramatic bend as the first fork off the scaffold reads as noisy
        # rather than sculptural (same "fade with depth" lesson learned
        # tuning the trunk's kinks).
        kink_depth_scale = max(0.0, 1.0 - depth * 0.25)

        phyllotaxis_offset = self.rng.uniform(0, 360)

        for i in range(fork_count):
            angle = math.radians(self.rng.uniform(*fork_angle_range))
            phi = math.radians(phyllotaxis_offset + i * (360.0 / fork_count)
                               + self.rng.gauss(0, 12))

            perp = _perp_vec(parent_dir)
            child_dir = _rotate_vec(parent_dir, perp, angle)
            child_dir = _rotate_vec(child_dir, parent_dir, phi)

            attraction_up = self._attraction_up()
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

            # See the matching comment in _build_branches — a coarse
            # segment can't carry a kink smoothly.
            kink_events = []
            if (self.species_key == 'pauciflora' and kink_depth_scale > 0
               and num_cvs >= 6):
                fc_min, fc_max, fw_lo, fw_hi = self._pauciflora_kink_params(
                    'branch')
                kink_events = self._make_kink_events(
                    fc_min, fc_max, fw_lo * kink_depth_scale,
                    fw_hi * kink_depth_scale, child_dir)
            next_kink = 0

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
                    while (next_kink < len(kink_events)
                          and t >= kink_events[next_kink][0]):
                        _, target, weight = kink_events[next_kink]
                        direction = _vnorm(_vadd(
                            _vscale(direction, 1.0 - weight),
                            _vscale(target, weight)))
                        next_kink += 1

                    gravity = _v(0, -droop * (1.0 - attraction_up)
                                * step * t * gravity_mult, 0)
                    wobble = _v(self.rng.gauss(0, wobble_s), 0,
                                self.rng.gauss(0, wobble_s))
                    new_pos = self._clamp_ground(_vadd(
                        pos, _vadd(_vscale(direction, step),
                                  _vadd(gravity, wobble))))
                    if j > 0:
                        direction = _vnorm(_vsub(new_pos, pos))
                    pos = new_pos

            child_name = self.data.add(c_points, c_radii, order=order,
                                       parent_name=parent_name,
                                       branch_param=1.0)
            self._build_fork(child_name, c_points, child_r, child_length,
                             order + 1, min_r_mult=min_r_mult)

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

        # Alpine snow gum stems fork low from one shared lignotuber and lean
        # toward a single prevailing wind direction (tree-limit ribbon /
        # krummholz research — the crook has a consistent compass direction
        # across a stand, it isn't a per-stem random splay). One wind axis
        # per tree, stems fanned around it rather than spread evenly over
        # 360 degrees.
        wind_dir = self.rng.uniform(0, 360)
        fan_spread = min(70.0, 14.0 * stem_count)

        for si in range(stem_count):
            splay_angle = math.radians(self.rng.uniform(10, 35))
            stem_frac = ((si / (stem_count - 1)) - 0.5) if stem_count > 1 else 0.0
            splay_dir = math.radians(wind_dir + stem_frac * fan_spread
                                     + self.rng.gauss(0, 8))

            trunk_name, pts, rad, h, dbh_r, cb = self._build_trunk(
                lean_dir_rad=splay_dir)

            # base_jitter is the small fixed footprint of the shared
            # lignotuber itself (stems fuse here); the full splay distance
            # only opens up with height via the offset*t ramp below, instead
            # of the old constant offset that separated every stem's base
            # from t=0.
            base_jitter = _v(self.rng.uniform(-1, 1) * dbh_r * 0.3, 0,
                             self.rng.uniform(-1, 1) * dbh_r * 0.3)
            splay_dist = max(30 * self.scale, dbh_r * 1.5)
            offset = _v(math.cos(splay_dir) * splay_dist, 0,
                        math.sin(splay_dir) * splay_dist)
            splay_vec = _v(math.cos(splay_dir) * math.sin(splay_angle),
                           math.cos(splay_angle),
                           math.sin(splay_dir) * math.sin(splay_angle))

            adjusted_pts = []
            for i, p in enumerate(pts):
                t = i / max(1, len(pts) - 1)
                lean_amount = t * splay_angle * h * 0.01
                adj = _vadd(p, _vadd(base_jitter,
                            _vadd(_vscale(offset, t),
                                  _vscale(splay_vec, lean_amount))))
                adjusted_pts.append(adj)

            ci = len(self.data.curves) - 1
            self.data.curves[ci]['points'] = adjusted_pts
            self.data.curves[ci]['name'] = '{}_trunk_{:03d}'.format(
                self._tree_prefix, si + 1)
            trunk_name = self.data.curves[ci]['name']

            if self._include_branches:
                if self.species_key == 'pauciflora':
                    self._build_main_limbs(trunk_name, adjusted_pts, rad, h,
                                          cb, dbh_r)
                else:
                    self._build_branches(trunk_name, adjusted_pts, rad, h,
                                         order=1, clear_bole_frac=cb)
            all_trunks.append(trunk_name)

        return all_trunks

    # --- orchestrator ---

    def _build_single_tree(self):
        if self.species_key == 'pauciflora':
            # Ground-up rebuild: trunk is not persisted as its own curve —
            # it's folded into each main limb (see _build_main_limbs).
            trunk_name, pts, rad, h, dbh_r, cb = self._build_trunk(
                persist=False)
            if self._include_branches:
                self._build_main_limbs(trunk_name, pts, rad, h, cb, dbh_r,
                                       combine_trunk=True)
            return []

        trunk_name, pts, rad, h, dbh_r, cb = self._build_trunk()
        self._build_buttresses(trunk_name, pts, rad, h)
        if self._include_branches:
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


def _tree_group_for(node):
    """Walk up from node to the enclosing '<prefix>_tree_GRP' transform and
    return its full path, or None if node isn't part of a generated tree."""
    full = cmds.ls(node, long=True)
    if not full:
        return None
    path = ''
    for part in full[0].split('|'):
        if not part:
            continue
        path += '|' + part
        if part.endswith('_tree_GRP'):
            return path
    return None


def generate_geometry_for_selection(nodes):
    """Resolve each node (curve, branch, or tree group) to its owning
    '<prefix>_tree_GRP', dedupe, and build preview geo for every tree found —
    lets the user select any mix of curves/groups across several trees (e.g.
    a cluster built up over a session) and geo them all in one go.

    Returns (results, skipped): results is a list of (tree_grp, geo_grp)
    pairs; skipped is the subset of nodes that aren't part of any tree.
    """
    tree_grps = []
    skipped = []
    for node in nodes:
        grp = _tree_group_for(node)
        if grp and grp not in tree_grps:
            tree_grps.append(grp)
        elif not grp:
            skipped.append(node)

    results = [(grp, generate_geometry(grp)) for grp in tree_grps]
    return results, skipped


def reference_height_cm(species, age, exposure=0.5):
    """Midpoint of a species/age/exposure's natural (scale=1.0) height range,
    in centimetres. Used to convert a target height in metres to the internal
    scale multiplier — see EucalyptusGenUI's Height field."""
    sp = SPECIES[species]
    age_frac = AGE_STAGES[age]['height_frac']
    exposure = max(0.0, min(1.0, exposure))
    if species == 'pauciflora':
        lo = _lerp(sp['height_lowland'][0], sp['height_alpine'][0], exposure)
        hi = _lerp(sp['height_lowland'][1], sp['height_alpine'][1], exposure)
    else:
        lo, hi = sp['height']
    return (lo + hi) / 2.0 * age_frac


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(species='citriodora', age='mature', seed=42, scale=1.0,
             exposure=0.5, density='typical', include_branches=True,
             bole_frac_override=None):
    """Generate a eucalyptus tree as NURBS curves.

    Args:
        species:            'citriodora', 'pauciflora', 'regnans', 'camaldulensis'
        age:                'sapling', 'young', 'mature', 'old_growth'
        seed:               random seed for reproducibility
        scale:              size multiplier (1.0 = centimetres)
        exposure:           0-1, altitude/exposure for pauciflora (0=lowland, 1=alpine)
        density:            'sparse', 'typical', 'dense'
        include_branches:   False builds trunk (and buttresses/multi-stem where
                            applicable) only — no scaffold/fork crown. Useful
                            while tuning trunk form in isolation.
        bole_frac_override: testing-only override for how much of the tree's
                            natural height the trunk curve physically builds
                            to (species default is a short stub, since
                            branches normally continue the rest of the way) —
                            e.g. 0.8 to preview trunk shape/kinks over most of
                            the tree's height with include_branches=False.
                            Leave None for normal species behaviour.

    Returns:
        Name of the top-level group node.
    """
    gen = EucalyptusGenerator(species=species, age=age, seed=seed,
                              scale=scale, exposure=exposure, density=density,
                              include_branches=include_branches,
                              bole_frac_override=bole_frac_override)
    return gen.generate()


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

PRESET_VERSION = 1

_PRESET_FIELDS = ('species', 'age', 'density', 'seed', 'height_m', 'exposure')


def save_preset(filepath, species, age, density, seed, height_m, exposure):
    """Write the UI's generate() parameters to a JSON file so this exact
    tree can be recreated later via load_preset()."""
    data = {
        'version': PRESET_VERSION,
        'species': species,
        'age': age,
        'density': density,
        'seed': seed,
        'height_m': height_m,
        'exposure': exposure,
    }
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def load_preset(filepath):
    """Read a preset JSON written by save_preset(). Returns a dict with
    keys matching _PRESET_FIELDS. Raises ValueError on a malformed or
    incompatible file."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    missing = [k for k in _PRESET_FIELDS if k not in data]
    if missing:
        raise ValueError('Preset {} missing field(s): {}'.format(
            filepath, ', '.join(missing)))
    if data['species'] not in SPECIES:
        raise ValueError('Preset {} has unknown species: {}'.format(
            filepath, data['species']))
    if data['age'] not in AGE_STAGES:
        raise ValueError('Preset {} has unknown age stage: {}'.format(
            filepath, data['age']))
    if data['density'] not in DENSITY_TIERS:
        raise ValueError('Preset {} has unknown density: {}'.format(
            filepath, data['density']))
    return data
