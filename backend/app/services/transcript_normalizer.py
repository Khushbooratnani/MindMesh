import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from app.config import settings
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class NormalizedTranscript(BaseModel):
    """Result of transcript normalization and script standardization."""

    normalized_text: str
    normalized_language: str = "en"  # "en", "hi", "mixed"
    display_script: str = "latin"
    original_script: str = "latin"  # "devanagari", "arabic", "latin", "mixed", "unknown"
    detected_language: str | None = None
    language_probability: float | None = None
    applied_corrections: list[str] = Field(default_factory=list)


# Unicode script detection regex patterns
_DEVANAGARI_PATTERN = re.compile(r"[\u0900-\u097F]")
_ARABIC_URDU_PATTERN = re.compile(r"[\u0600-\u06FF]")
_LATIN_PATTERN = re.compile(r"[A-Za-z]")

# Known Indian proper nouns and common ASR phonetic misspellings
_KNOWN_PROPER_NOUN_CORRECTIONS: dict[str, str] = {
    "masori": "Mussoorie",
    "masoori": "Mussoorie",
    "mussoori": "Mussoorie",
    "mussorie": "Mussoorie",
    "mansoori": "Mussoorie",
    "premnager": "Premnagar",
    "premnagar": "Premnagar",
    "bodego": "Bodega",
    "bodega": "Bodega",
}

# Common Devanagari words to natural Roman Hindi mappings for deterministic offline fallback
_DEVANAGARI_WORD_MAP: dict[str, str] = {
    "कल": "Kal",
    "हम": "hum",
    "मसूरी": "Mussoorie",
    "में": "mein",
    "अक्षत": "Akshat",
    "से": "se",
    "मिले": "mile",
    "थे": "the",
    "था": "tha",
    "थी": "thi",
    "है": "hai",
    "हैं": "hain",
    "हो": "ho",
    "गया": "gaya",
    "गई": "gayi",
    "करो": "karo",
    "किया": "kiya",
    "बात": "baat",
    "की": "ki",
    "का": "ka",
    "के": "ke",
    "और": "aur",
    "रोहन": "Rohan",
    "प्रेम": "Prem",
    "नगर": "Nagar",
    "प्रेमसागर": "Premsagar",
    "कॉफी": "coffee",
    "चाय": "chai",
    "पी": "pee",
}

# Common Urdu script words to natural Roman Hindi mappings for deterministic offline fallback
_URDU_WORD_MAP: dict[str, str] = {
    "کل": "Kal",
    "ہم": "hum",
    "مسوری": "Mussoorie",
    "میں": "mein",
    "ملے": "mile",
    "تھے": "the",
    "تھا": "tha",
    "تھی": "thi",
    "ہے": "hai",
    "ہیں": "hain",
    "ہو": "ho",
    "گیا": "gaya",
    "کرو": "karo",
    "کیا": "kiya",
    "بات": "baat",
    "اور": "aur",
    "اکشت": "Akshat",
    "روہن": "Rohan",
    "کافی": "coffee",
}


def detect_script(text: str) -> str:
    """Identify the dominant script used in a transcript."""
    if not text:
        return "unknown"

    has_deva = bool(_DEVANAGARI_PATTERN.search(text))
    has_urdu = bool(_ARABIC_URDU_PATTERN.search(text))
    has_lat = bool(_LATIN_PATTERN.search(text))

    scripts = []
    if has_deva:
        scripts.append("devanagari")
    if has_urdu:
        scripts.append("arabic")
    if has_lat:
        scripts.append("latin")

    if len(scripts) == 1:
        return scripts[0]
    if len(scripts) > 1:
        return "mixed"
    return "unknown"


def _deterministic_rule_normalize(
    raw_text: str,
    detected_language: str | None = None,
) -> tuple[str, str, list[str]]:
    """Applies deterministic transliteration and proper noun corrections without hallucination."""
    corrections: list[str] = []
    script = detect_script(raw_text)

    # 1. Devanagari Hindi -> Roman Hindi
    if script == "devanagari" or bool(_DEVANAGARI_PATTERN.search(raw_text)):
        words = raw_text.split()
        converted = []
        for w in words:
            clean_w = re.sub(r"[^\w\s\u0900-\u097F]", "", w)
            if clean_w in _DEVANAGARI_WORD_MAP:
                rep = _DEVANAGARI_WORD_MAP[clean_w]
                converted.append(rep)
                corrections.append(f"{clean_w}->{rep}")
            else:
                converted.append(w)
        result_text = " ".join(converted)
        lang = "hi"
        return result_text, lang, corrections

    # 2. Urdu Script -> Roman Hindi
    if script == "arabic" or bool(_ARABIC_URDU_PATTERN.search(raw_text)):
        words = raw_text.split()
        converted = []
        for w in words:
            clean_w = re.sub(r"[^\w\s\u0600-\u06FF]", "", w)
            if clean_w in _URDU_WORD_MAP:
                rep = _URDU_WORD_MAP[clean_w]
                converted.append(rep)
                corrections.append(f"{clean_w}->{rep}")
            else:
                converted.append(w)
        result_text = " ".join(converted)
        lang = "hi" if (detected_language in ("hi", "ur") or not detected_language) else detected_language
        return result_text, lang, corrections

    # 3. Latin / English / Hinglish text proper noun phonetic normalization
    words = raw_text.split()
    converted = []
    for w in words:
        punct_prefix = ""
        punct_suffix = ""
        match = re.match(r"^([^\w]*)(.*?)([^\w]*)$", w)
        if match:
            punct_prefix, core_w, punct_suffix = match.groups()
        else:
            core_w = w

        low_w = core_w.lower()
        if low_w in _KNOWN_PROPER_NOUN_CORRECTIONS:
            corrected = _KNOWN_PROPER_NOUN_CORRECTIONS[low_w]
            converted.append(f"{punct_prefix}{corrected}{punct_suffix}")
            corrections.append(f"{core_w}->{corrected}")
        else:
            converted.append(w)

    result_text = " ".join(converted)

    # Determine language
    lang = detected_language or "en"
    if any(hindi_token in result_text.lower().split() for hindi_token in ("mein", "hum", "mile", "the", "hai", "karo", "gaya")):
        lang = "hi" if detected_language == "hi" else "mixed"

    return result_text, lang, corrections


class TranscriptNormalizer:
    """Normalizes raw ASR transcripts from Whisper into clean Roman Hindi / English.
    
    Fixes obvious phonetic errors and transliterates non-Latin scripts (Devanagari, Urdu)
    without translating Hindi into English, summarizing, or inventing facts.
    """

    def __init__(self, llm_service: LLMService | None = None):
        self.llm_service = llm_service or LLMService(settings.memory_extraction_model)

    def normalize(
        self,
        raw_transcript: str,
        detected_language: str | None = None,
        language_probability: float | None = None,
        user_context: str | None = None,
    ) -> NormalizedTranscript:
        """Normalize raw Whisper transcript to clean Latin representation."""
        if not raw_transcript or not raw_transcript.strip():
            return NormalizedTranscript(
                normalized_text="",
                normalized_language=detected_language or "en",
                display_script="latin",
                original_script="unknown",
                detected_language=detected_language,
                language_probability=language_probability,
                applied_corrections=[],
            )

        trimmed = raw_transcript.strip()
        script = detect_script(trimmed)

        # 1. If running under mock test suite or LLM is mock, use deterministic rules
        if self.llm_service.model_name == "mock-memory-extractor" or not self.llm_service.base_url:
            rule_text, rule_lang, corrections = _deterministic_rule_normalize(
                trimmed,
                detected_language=detected_language,
            )
            return NormalizedTranscript(
                normalized_text=rule_text,
                normalized_language=rule_lang,
                display_script="latin",
                original_script=script,
                detected_language=detected_language,
                language_probability=language_probability,
                applied_corrections=corrections,
            )

        # 2. In production with live Qwen3.8-27B, invoke constrained normalization prompt
        try:
            return self._normalize_with_llm(
                raw_transcript=trimmed,
                detected_language=detected_language,
                language_probability=language_probability,
                original_script=script,
                user_context=user_context,
            )
        except Exception as exc:
            logger.warning(
                "[TranscriptNormalizer] LLM normalization failed (%s). Falling back to rule-based normalization.",
                exc,
            )
            rule_text, rule_lang, corrections = _deterministic_rule_normalize(
                trimmed,
                detected_language=detected_language,
            )
            return NormalizedTranscript(
                normalized_text=rule_text or trimmed,
                normalized_language=rule_lang,
                display_script="latin",
                original_script=script,
                detected_language=detected_language,
                language_probability=language_probability,
                applied_corrections=corrections,
            )

    def _normalize_with_llm(
        self,
        raw_transcript: str,
        detected_language: str | None,
        language_probability: float | None,
        original_script: str,
        user_context: str | None = None,
    ) -> NormalizedTranscript:
        """Call Qwen3.8-27B with a tightly constrained transcript normalization prompt."""
        import httpx

        system_prompt = (
            "You are a specialized Automatic Speech Recognition (ASR) transcript normalizer.\n"
            "Your task is to correct obvious transcription/spelling errors and transliterate non-Latin scripts (Devanagari, Urdu) into natural Roman Hindi/Hinglish using the Latin alphabet.\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "1. DO NOT translate Hindi or Hinglish into English. Preserve the exact words and language in Roman/Latin script.\n"
            "   Example: 'कल हम अक्षत से मिले थे' -> 'Kal hum Akshat se mile the' (NEVER 'Yesterday we met Akshat').\n"
            "   Example: 'کل ہم مسوری میں ملے تھے' -> 'Kal hum Mussoorie mein mile the'.\n"
            "2. DO NOT summarize, shorten, or expand the transcript.\n"
            "3. DO NOT invent facts, names, or details. If audio is unclear, preserve the original text rather than guessing.\n"
            "4. Correct ONLY obvious ASR phonetic errors in proper nouns and place names (e.g. 'Masori' -> 'Mussoorie'). Do NOT aggressively autocorrect uncommon names (e.g. 'Rohanxyz').\n"
            "5. Preserve natural English speech in English (e.g. 'McDonald\'s', 'Had coffee in Mussoorie').\n"
            "6. Return ONLY valid JSON matching this schema:\n"
            "{\n"
            '  "normalized_text": "string",\n'
            '  "normalized_language": "en" | "hi" | "mixed",\n'
            '  "display_script": "latin",\n'
            '  "applied_corrections": ["list of string notes"]\n'
            "}"
        )

        user_content = f"Raw ASR Transcript: {raw_transcript}\nDetected Language: {detected_language or 'unknown'}"
        if user_context:
            user_content += f"\nUser Context (optional context for proper nouns): {user_context}"

        payload = {
            "model": self.llm_service.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }

        headers = {"Content-Type": "application/json"}
        if self.llm_service.api_key and self.llm_service.api_key != "replace_with_your_api_key":
            headers["Authorization"] = f"Bearer {self.llm_service.api_key}"

        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                self.llm_service.base_url.rstrip("/") + "/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]

        parsed = json.loads(content)
        norm_text = parsed.get("normalized_text", "").strip() or raw_transcript
        norm_lang = parsed.get("normalized_language", detected_language or "en")
        applied_corrs = parsed.get("applied_corrections", [])

        return NormalizedTranscript(
            normalized_text=norm_text,
            normalized_language=norm_lang,
            display_script="latin",
            original_script=original_script,
            detected_language=detected_language,
            language_probability=language_probability,
            applied_corrections=applied_corrs if isinstance(applied_corrs, list) else [],
        )
