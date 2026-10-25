from enum import Enum


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    VALIDATING = "validating"
    QUEUED = "queued"
    PROCESSING = "processing"
    PARSED = "parsed"
    INDEXED = "indexed"
    FAILED = "failed"
    DELETING = "deleting"
    DELETED = "deleted"
