from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


class LocalStorageProvider:
    def __init__(
        self,
        storage_dir: Path,
        max_upload_size_mb: int,
    ) -> None:
        self.storage_dir = storage_dir
        self.max_size_bytes = max_upload_size_mb * 1024 * 1024

    async def save(self, upload_file: UploadFile) -> tuple[str, int]:
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        suffix = Path(upload_file.filename or "").suffix[:20]
        destination = self.storage_dir / f"{uuid4().hex}{suffix}"
        total_size = 0

        try:
            with destination.open("wb") as output_file:
                while chunk := await upload_file.read(1024 * 1024):
                    total_size += len(chunk)

                    if total_size > self.max_size_bytes:
                        raise ValueError(
                            "File exceeds the maximum upload size."
                        )

                    output_file.write(chunk)

            if total_size == 0:
                raise ValueError("Uploaded file is empty.")

            return str(destination), total_size

        except Exception:
            destination.unlink(missing_ok=True)
            raise

        finally:
            await upload_file.close()
