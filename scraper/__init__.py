"""Coleta de vagas junior remotas para o alerta no Discord."""

__version__ = "1.0.0"

from .config import Settings
from .models import Job

__all__ = ["Settings", "Job", "__version__"]
