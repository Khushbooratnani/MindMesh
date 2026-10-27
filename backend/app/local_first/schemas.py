"""
Pydantic schemas for the v2 Local-First Private Locker & Ephemeral AI interface.
"""
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class LocalFirstRegisterRequest(BaseModel):
    password: str = Field(..., min_length=8)


class LocalFirstRegisterResponse(BaseModel):
    identity_id: str
    recovery_key: str


class LocalFirstUnlockRequest(BaseModel):
    password: str


class LocalFirstUnlockResponse(BaseModel):
    token: str
    expires_in_seconds: int = 120


class LocalFirstChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)


class LocalFirstRecoverRequest(BaseModel):
    recovery_key: str
    new_password: str = Field(..., min_length=8)


class LocalFirstRecoverResponse(BaseModel):
    message: str
    new_recovery_key: str


class LocalFirstStatusResponse(BaseModel):
    has_locker: bool
    exists: bool
    locked_out: bool
    status: str


# --- Ephemeral Consent-Based AI Schemas ---
class EphemeralAiConsent(BaseModel):
    consent_granted: bool
    purpose: str = Field(..., description="e.g. semantic_extraction, embedding_generation, question_answering")
    retention_policy: str = Field("immediate_destruction", description="Must be 'immediate_destruction'")


class EphemeralExtractionRequest(BaseModel):
    consent: EphemeralAiConsent
    text: str


class EphemeralExtractionResponse(BaseModel):
    clean_text: str
    entities: dict[str, Any]
    semantics: dict[str, Any]
    temporal: dict[str, Any]


class EphemeralEmbeddingRequest(BaseModel):
    consent: EphemeralAiConsent
    texts: List[str]


class EphemeralEmbeddingResponse(BaseModel):
    embeddings: List[List[float]]
    dimension: int


class EphemeralQaRequest(BaseModel):
    consent: EphemeralAiConsent
    query: str
    selected_context: List[str] = Field(..., description="Plaintext snippets explicitly approved by user from local device")


class EphemeralQaResponse(BaseModel):
    query: str
    answer: str
    confidence: float
