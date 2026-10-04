"""Controller layer: parse HTTP requests and wrap responses.

No business rule lives here; everything is delegated to the service layer.
"""

from .calculate_controller import calculate_blueprint
from .history_controller import history_blueprint
from .system_controller import system_blueprint

#: Every blueprint, registered by the application factory.
ALL_BLUEPRINTS = (system_blueprint, calculate_blueprint, history_blueprint)

__all__ = ["ALL_BLUEPRINTS", "calculate_blueprint", "history_blueprint", "system_blueprint"]
