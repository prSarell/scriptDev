SHELF_NAME = "mpFX"
SHELF_VERSION = "1.0"

# Scripts deployed to ~/maya/scripts/ but with no shelf button.
EXTRA_SCRIPTS = []

# Scripts from simDev/ — deployed flat to ~/maya/scripts/.
SIMTOOL_SCRIPTS = [
    "bossOceanSetup.py",
]

# Scripts from renderDev/ — deployed flat to ~/maya/scripts/.
RENDERDEV_SCRIPTS = [
    "arnoldCloudSetup.py",
    "arnoldSnowSetup.py",
]

# Each entry defines one shelf button.
BUTTONS = [
    {
        "label": "BOSS Ocean",
        "tooltip": "BOSS Ocean — build a Bifrost spectral-wave ocean on the selected mesh "
                   "(create_spectral_waves + displace_by_wave, sized to the mesh)",
        "icon": "iconBossOcean.png",
        "command": (
            "import importlib\n"
            "import bossOceanSetup\n"
            "importlib.reload(bossOceanSetup)\n"
            "bossOceanSetup.build()"
        ),
    },
    {
        "label": "Freeze Ocean",
        "tooltip": "Freeze Ocean — copy the selected BOSS Ocean at the current frame into a "
                   "static Maya mesh (e.g. to use as terrain)",
        "icon": "iconFreezeOcean.png",
        "command": (
            "import importlib\n"
            "import bossOceanSetup\n"
            "importlib.reload(bossOceanSetup)\n"
            "bossOceanSetup.freeze()"
        ),
    },
    {
        "label": "Cloud",
        "tooltip": "Cloud — turn the selected mesh into an Arnold volume cloud "
                   "(aiStandardVolume + Cloud texture, tuned defaults; bigger container = better clouds)",
        "icon": "iconCloudVolume.png",
        "command": (
            "import importlib\n"
            "import arnoldCloudSetup\n"
            "importlib.reload(arnoldCloudSetup)\n"
            "arnoldCloudSetup.build()"
        ),
    },
    {
        "label": "Snow Land",
        "tooltip": "Snow Land — slope-based landscape shader on the selected mesh or BOSS Ocean "
                   "(Maya Snow texture into aiStandardSurface base colour: snow on flat faces, "
                   "rock on slopes)",
        "icon": "iconSnowLand.png",
        "command": (
            "import importlib\n"
            "import arnoldSnowSetup\n"
            "importlib.reload(arnoldSnowSetup)\n"
            "arnoldSnowSetup.build()"
        ),
    },
]
