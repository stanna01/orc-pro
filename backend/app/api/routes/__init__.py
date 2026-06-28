from .checklists import router as checklists
from .health import router as health
from .uploads import router as uploads
from .ocr_processing import router as ocr_processing

__all__ = ["checklists", "health", "uploads", "ocr_processing"]
