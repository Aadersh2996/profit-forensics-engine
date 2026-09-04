"""Persist normalized Razorpay records using the same CSV-backed dataset contract."""

from __future__ import annotations

import csv
from pathlib import Path
from uuid import uuid4

from app.models.schemas import DatasetMetadata


def persist_normalized_razorpay_dataset(
    *, upload_dir: Path, resource: str, records: list[dict[str, object]]
) -> DatasetMetadata:
    """Write one normalized provider resource as a temporary investigator CSV input."""

    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / f"razorpay-{resource}-{uuid4()}.csv"
    columns = list(dict.fromkeys(key for record in records for key in record))
    with destination.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        if columns:
            writer.writeheader()
            writer.writerows(records)
    return DatasetMetadata(
        dataset_id=str(uuid4()),
        dataset_type=resource,
        path=str(destination),
        row_count=len(records),
        columns=columns,
        source="razorpay",
        metadata={"resource": resource},
    )
