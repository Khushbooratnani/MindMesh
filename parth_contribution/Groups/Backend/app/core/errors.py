class IngestionError(Exception):
    code = "INGESTION_ERROR"
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class EmptyTextError(IngestionError):
    code = "EMPTY_TEXT"
    status_code = 400


class UnsupportedMediaTypeError(IngestionError):
    code = "INVALID_MEDIA_TYPE"
    status_code = 400


class FileTooLargeError(IngestionError):
    code = "FILE_TOO_LARGE"
    status_code = 413


class UnsupportedFileFormatError(IngestionError):
    code = "UNSUPPORTED_FILE_FORMAT"
    status_code = 400


class LLMExtractionError(IngestionError):
    code = "LLM_EXTRACTION_FAILED"
    status_code = 502


class InvalidLLMJSONError(IngestionError):
    code = "INVALID_LLM_JSON"
    status_code = 502


class TranscriptionFailedError(IngestionError):
    code = "TRANSCRIPTION_FAILED"
    status_code = 502


class ImageUnderstandingFailedError(IngestionError):
    code = "IMAGE_UNDERSTANDING_FAILED"
    status_code = 502


class UnauthorizedGroupAccessError(IngestionError):
    code = "UNAUTHORIZED_GROUP_ACCESS"
    status_code = 403


class SchemaValidationError(IngestionError):
    code = "SCHEMA_VALIDATION_FAILED"
    status_code = 500


class Phase2Error(IngestionError):
    code = "PHASE2_ERROR"
    status_code = 500


class MemorySearchError(Phase2Error):
    code = "MEMORY_SEARCH_ERROR"
    status_code = 500

