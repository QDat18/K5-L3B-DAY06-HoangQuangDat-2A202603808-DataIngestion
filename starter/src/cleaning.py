"""Rule-based cleaning of the 5481 docx blocks: drop non-clinical parts, tag sections."""
import re
from dataclasses import dataclass, field

from .models import Block


@dataclass
class SectionText:
    section: str
    paragraphs: list[str]


@dataclass
class DroppedRange:
    reason: str
    start: int  # Block.index, inclusive
    end: int    # Block.index, inclusive
    chars: int


@dataclass
class CleanResult:
    sections: list[SectionText] = field(default_factory=list)
    dropped: list[DroppedRange] = field(default_factory=list)


_PHAN_1 = re.compile(r"^PHẦN\s*1\s*$")
_PHAN = re.compile(r"^PHẦN\s*(\d+)\s*$")
_PHU_LUC = re.compile(r"^PHỤ LỤC\s*0?(\d)\b")
_REFS = re.compile(r"^TÀI LIỆU THAM KHẢO\s*:?\s*$")

_HEAD_REASON = ("Phần đầu tài liệu: quyết định, ban biên soạn, lời nói đầu, mục lục, "
                "từ viết tắt (không phải nội dung chuyên môn)")
_TAIL_REASON = ("Từ 'TÀI LIỆU THAM KHẢO' đến hết file: danh sách tham khảo và "
                "mục lục lặp cuối file")


def _section_id(block: Block) -> str | None:
    """Only whole-line paragraph markers open a section; table text never does."""
    if block.kind != "p":
        return None
    if m := _PHAN.match(block.text):
        return f"PHAN_{int(m.group(1))}"
    if m := _PHU_LUC.match(block.text):
        return f"PHU_LUC_{int(m.group(1)):02d}"
    return None


def _dropped(reason: str, part: list[Block]) -> DroppedRange:
    return DroppedRange(reason=reason, start=part[0].index, end=part[-1].index,
                        chars=sum(len(b.text) for b in part))


def clean(blocks: list[Block]) -> CleanResult:
    """Keep PHẦN 1 .. first "TÀI LIỆU THAM KHẢO"; tag each paragraph with its section."""
    start = next((i for i, b in enumerate(blocks)
                  if b.kind == "p" and _PHAN_1.match(b.text)), None)
    if start is None:
        raise ValueError("Không tìm thấy dòng 'PHẦN 1'")
    end = next((i for i in range(start + 1, len(blocks))
                if blocks[i].kind == "p" and _REFS.match(blocks[i].text)), None)
    if end is None:
        raise ValueError("Không tìm thấy dòng 'TÀI LIỆU THAM KHẢO'")

    result = CleanResult()
    if start > 0:
        result.dropped.append(_dropped(_HEAD_REASON, blocks[:start]))

    current: SectionText | None = None
    for block in blocks[start:end]:
        section = _section_id(block)
        if section:
            current = SectionText(section, [])
            result.sections.append(current)
            continue
        lines = block.text.split("\n") if block.kind == "table" else [block.text]
        current.paragraphs.extend(line for line in lines if line.strip())

    result.dropped.append(_dropped(_TAIL_REASON, blocks[end:]))
    return result
