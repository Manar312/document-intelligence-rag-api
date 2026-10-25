import logging
import unicodedata
from pathlib import Path

import pymupdf


logger = logging.getLogger(__name__)


class PDFParserProvider:
    @staticmethod
    def count_unexpected_control_characters(text: str) -> int:
        """Count control characters except normal whitespace controls."""
        return sum(
            1
            for character in text
            if unicodedata.category(character) == "Cc"
            and character not in "\n\r\t"
        )

    def extract_pages(self, file_path: str | Path) -> list[dict[str, object]]:
        pages: list[dict[str, object]] = []

        with pymupdf.open(file_path) as pdf:
            for page_number, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()

                control_count = self.count_unexpected_control_characters(text)

                if control_count:
                    percentage = (
                        control_count / len(text) * 100
                        if text
                        else 0.0
                    )

                    logger.warning(
                        "Unexpected control characters detected in PDF "
                        "page %s: %s characters (%.2f%%). File: %s",
                        page_number,
                        control_count,
                        percentage,
                        file_path,
                    )

                pages.append(
                    {
                        "page_number": page_number,
                        "text": text,
                    }
                )

        return pages
