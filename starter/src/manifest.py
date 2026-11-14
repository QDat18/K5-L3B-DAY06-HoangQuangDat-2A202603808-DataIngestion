"""Corpus validation and manifest output."""
import json
from dataclasses import asdict
from pathlib import Path

from .cleaning import DroppedRange
from .models import DocumentPage

PAGE_COUNTING_RULE = (
    "File .docx không có trang thật (số trang Word chỉ là metadata, không dùng). "
    "`page` = số thứ tự đơn vị nguồn (1..N): các đoạn liên tiếp trong cùng một section "
    "được gộp đến khi đạt tối thiểu 1.500 ký tự, cắt ở ranh giới đoạn, không vắt qua "
    "section; phần dư nhỏ hơn 1.500 ký tự nhập vào đơn vị trước. Section ngắn hơn 1.500 "
    "ký tự tạo một đơn vị `short`, không tính vào mốc 30."
)


def validate_corpus(units: list[DocumentPage], min_units: int = 30) -> None:
    """Raise ValueError unless at least `min_units` non-short units exist."""
    counted = sum(1 for u in units if not u.metadata["short"])
    if counted < min_units:
        raise ValueError(f"Corpus chỉ có {counted} đơn vị nội dung hợp lệ, cần ít nhất {min_units}")


def write_manifest(units: list[DocumentPage], dropped: list[DroppedRange], path: Path,
                   accessed_at: str, license_note: str, *,
                   title: str = "", source_path_or_url: str = "",
                   sha256: str | None = None, notes: list[str] | None = None) -> None:
    """Write data/manifest.json: source info, unit list, dropped ranges, notes."""
    first = units[0]
    manifest = {
        "documents": [{
            "source_id": first.document_id,
            "title": title,
            "source_path_or_url": source_path_or_url,
            "license_or_permission": license_note,
            "accessed_at": accessed_at,
            "sha256": sha256,
            "unit_ids": [u.metadata["unit_id"] for u in units],
            "chars": sum(u.metadata["chars"] for u in units),
            "page_counting_rule": PAGE_COUNTING_RULE,
        }],
        "units": [{"unit_id": u.metadata["unit_id"], "page": u.page,
                   "section": u.metadata["section"], "chars": u.metadata["chars"],
                   "short": u.metadata["short"]} for u in units],
        "dropped_ranges": [asdict(d) for d in dropped],
        "notes": notes or [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
