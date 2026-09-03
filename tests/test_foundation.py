from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.db_models import Base, CaseFileORM, Investigation
from app.models.schemas import TimelineEvent


def test_settings_reject_invalid_confidence_threshold() -> None:
    try:
        Settings(CONFIDENCE_THRESHOLD=1.1)
    except ValueError as exc:
        assert "CONFIDENCE_THRESHOLD" in str(exc)
    else:
        raise AssertionError("invalid confidence threshold was accepted")


def test_timeline_progress_is_bounded() -> None:
    try:
        TimelineEvent(title="Invalid", stage="test", progress=1.1)
    except ValueError as exc:
        assert "progress" in str(exc)
    else:
        raise AssertionError("invalid timeline progress was accepted")


def test_case_files_are_owned_by_an_investigation() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        investigation = Investigation(id="PF-TEST", status="created", confidence=0.0)
        investigation.case_files.append(
            CaseFileORM(
                id="CF-TEST",
                title="Refund concentration",
                status="open",
                confidence=0.8,
                evidence=[],
                priority=1,
            )
        )
        session.add(investigation)
        session.commit()

        persisted = session.get(Investigation, "PF-TEST")
        assert persisted is not None
        assert persisted.case_files[0].investigation_id == "PF-TEST"
