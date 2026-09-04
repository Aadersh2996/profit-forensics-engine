"""CSV dataset upload endpoint."""

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.config import settings
from app.models.schemas import UploadResponse
from app.services.dataset_ingestion import inspect_csv_dataset


router = APIRouter(prefix="/datasets", tags=["datasets"])
_CHUNK_SIZE = 1024 * 1024


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_csv_dataset(
    dataset_type: str = Form(..., min_length=1, max_length=80),
    file: UploadFile = File(...),
) -> UploadResponse:
    """Persist and inspect one CSV upload before exposing a dataset reference."""

    filename = file.filename or "dataset.csv"
    normalized_dataset_type = dataset_type.strip()
    if not normalized_dataset_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Dataset type must contain at least one non-whitespace character.",
        )
    if Path(filename).suffix.lower() != ".csv":
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only CSV uploads are supported.")

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    destination = settings.upload_dir / f"{uuid4()}.csv"
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    bytes_written = 0
    try:
        with destination.open("wb") as output:
            while chunk := await file.read(_CHUNK_SIZE):
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    output.close()
                    destination.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"CSV upload exceeds the {settings.max_upload_size_mb} MB limit.",
                    )
                output.write(chunk)
        dataset = inspect_csv_dataset(
            path=destination,
            dataset_type=normalized_dataset_type,
            original_filename=filename,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        await file.close()

    return UploadResponse(dataset=dataset, message="CSV dataset uploaded and inspected.")
