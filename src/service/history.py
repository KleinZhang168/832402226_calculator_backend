"""History business service: listing, deleting and clearing records."""

from src.config import Config
from src.model import history_model
from src.service.calculator import parse_optional_int
from src.utils.exceptions import NotFoundError, ValidationError


class HistoryService:
    """Calculation history service."""

    @staticmethod
    def list_history(page: str = None, page_size: str = None) -> dict:
        """Return one page of history records, newest first."""
        current_page = parse_optional_int(
            page, default=1, minimum=1, maximum=10 ** 9, field_name="page"
        )
        size = parse_optional_int(
            page_size,
            default=Config.DEFAULT_PAGE_SIZE,
            minimum=1,
            maximum=Config.MAX_PAGE_SIZE,
            field_name="pageSize",
        )

        total = history_model.count_all()
        offset = (current_page - 1) * size
        records = history_model.find_all(limit=size, offset=offset)

        return {
            "total": total,
            "page": current_page,
            "pageSize": size,
            "list": records,
        }

    @staticmethod
    def delete_history(raw_record_id) -> dict:
        """Delete the history record with the given id."""
        record_id = _to_record_id(raw_record_id)
        deleted = history_model.delete_by_id(record_id)
        if deleted == 0:
            raise NotFoundError("No calculation history found with id %d" % record_id)
        return {"id": record_id, "deleted": deleted}

    @staticmethod
    def clear_history() -> dict:
        """Delete every history record (optional feature)."""
        deleted = history_model.delete_all()
        return {"deleted": deleted}


def _to_record_id(raw_record_id) -> int:
    """Convert a path parameter into a valid positive integer id."""
    try:
        record_id = int(raw_record_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("The history id must be an integer") from exc
    if record_id <= 0:
        raise ValidationError("The history id must be greater than 0")
    return record_id
