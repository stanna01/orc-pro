from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, status

UPLOAD_DIR = Path(__file__).resolve().parents[4] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "application/pdf"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])


def _validate_upload_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file extension '{extension}'. Allowed: {allowed}",
        )
    return extension


def _validate_content_type(content_type: str) -> None:
    if content_type not in ALLOWED_CONTENT_TYPES:
        allowed = ", ".join(sorted(ALLOWED_CONTENT_TYPES))
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type '{content_type}'. Allowed: {allowed}",
        )


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_checklist_image(file: UploadFile = File(..., description="Checklist image or PDF file.")) -> Any:
    """Upload checklist scan files and save them to the uploads directory."""
    extension = _validate_upload_extension(file.filename)
    _validate_content_type(file.content_type or "")

    file_id = uuid4().hex
    saved_name = f"{file_id}{extension}"
    saved_path = UPLOAD_DIR / saved_name

    total_bytes = 0
    try:
        with saved_path.open("wb") as destination:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size of {MAX_UPLOAD_SIZE} bytes.",
                    )
                destination.write(chunk)
    except HTTPException:
        if saved_path.exists():
            saved_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        if saved_path.exists():
            saved_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save uploaded file.",
        ) from exc
    finally:
        await file.close()

    return {
        "id": file_id,
        "original_filename": file.filename,
        "saved_path": f"/uploads/{saved_name}",
        "size_bytes": total_bytes,
        "content_type": file.content_type,
    }
