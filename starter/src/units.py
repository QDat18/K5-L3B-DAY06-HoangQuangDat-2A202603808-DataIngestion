"""Group cleaned paragraphs into source units (the `page` of a .docx corpus)."""
from .cleaning import CleanResult
from .models import DocumentPage


def build_units(clean: CleanResult, document_id: str = "5481",
                source: str = "5481_QD-BYT_460925.docx",
                min_chars: int = 1500) -> list[DocumentPage]:
    """Units of >= min_chars at paragraph boundaries, never across sections.

    A trailing remainder smaller than min_chars joins the previous unit of its
    section. A section whose whole text is below min_chars becomes one unit
    flagged `short` (it does not count towards the 30-unit minimum).
    """
    units: list[DocumentPage] = []
    for section in clean.sections:
        groups: list[list[str]] = []
        current: list[str] = []
        size = 0
        for paragraph in section.paragraphs:
            size += len(paragraph) + (1 if current else 0)
            current.append(paragraph)
            if size >= min_chars:
                groups.append(current)
                current, size = [], 0
        if current:
            if groups:
                groups[-1].extend(current)
            else:
                groups.append(current)

        for group in groups:
            text = "\n".join(group)
            number = len(units) + 1
            units.append(DocumentPage(
                document_id=document_id, source=source, page=number, text=text,
                metadata={"section": section.section,
                          "unit_id": f"{document_id}-U{number:03d}",
                          "chars": len(text), "short": len(text) < min_chars}))
    return units
