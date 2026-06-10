"""
API路由模块
"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
simulation_bp = Blueprint('simulation', __name__)
report_bp = Blueprint('report', __name__)
auth_bp = Blueprint('auth', __name__)
wizard_bp = Blueprint('wizard', __name__)
share_bp = Blueprint('share', __name__)
shared_bp = Blueprint('shared', __name__)
billing_bp = Blueprint('billing', __name__)

from . import graph  # noqa: E402, F401
from . import simulation  # noqa: E402, F401
from . import report  # noqa: E402, F401
from . import auth  # noqa: E402, F401
from . import wizard  # noqa: E402, F401
from . import share  # noqa: E402, F401
from . import shared  # noqa: E402, F401
from . import billing  # noqa: E402, F401

