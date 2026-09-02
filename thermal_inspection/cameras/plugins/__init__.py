"""
Camera Plugin Package Auto-Registration.

Importing this package automatically registers all built-in camera plugins.
"""
from . import boson
from . import tau2
from . import lepton
from . import firefly
from . import uvc
from . import gige
from . import realsense

__all__ = ['boson', 'tau2', 'lepton', 'firefly', 'uvc', 'gige', 'realsense']
