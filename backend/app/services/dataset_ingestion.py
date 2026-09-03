"""CSV dataset ingestion helpers that create lightweight dataset references."""

from pathlib import Path
from uuid import uuid4

import pandas as pd

from app.models.schemas import DatasetMetadata


def inspect_csv_dataset(
    *, path: Path, dataset_type: str, original_filename: str | None
) -> DatasetMetadata:
    """Read CSV metadata without retaining the DataFrame beyond ingestion."""

    try:
        frame = pd.read_csv(path)
    except (OSError, UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        raise ValueError("The uploaded file is not a readable CSV dataset.") from exc
    return DatasetMetadata(
        dataset_id=str(uuid4()),
        dataset_type=dataset_type,
        path=str(path),
        row_count=len(frame),
        columns=[str(column) for column in frame.columns],
        source="csv",
        metadata={"original_filename": original_filename} if original_filename else {},
    )
