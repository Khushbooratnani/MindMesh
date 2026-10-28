from app.services.llm_service import LLMService
from app.services.transcript_normalizer import TranscriptNormalizer, detect_script


def test_script_detection():
    """Verify script detection across Devanagari, Urdu/Arabic, and Latin."""
    assert detect_script("Had coffee in Mussoorie") == "latin"
    assert detect_script("कल हम मसूरी में मिले थे") == "devanagari"
    assert detect_script("کل ہم مسوری میں ملے تھے") == "arabic"
    assert detect_script("Roadmap finalize करो") == "mixed"
    assert detect_script("") == "unknown"


def test_normalizer_english_speech_preserved():
    """1. English transcript: 'Had coffee in Mussoorie near Mall Road.' remains accurate English."""
    normalizer = TranscriptNormalizer(llm_service=LLMService(model_name="mock-memory-extractor"))
    res = normalizer.normalize(
        raw_transcript="Had coffee in Mussoorie near Mall Road.",
        detected_language="en",
    )
    assert res.normalized_text == "Had coffee in Mussoorie near Mall Road."
    assert res.display_script == "latin"
    assert res.normalized_language == "en"


def test_normalizer_devanagari_hindi_to_roman_hindi():
    """2. Devanagari Hindi normalized to Roman Hindi (NOT English translation)."""
    normalizer = TranscriptNormalizer(llm_service=LLMService(model_name="mock-memory-extractor"))
    res = normalizer.normalize(
        raw_transcript="कल हम मसूरी में अक्षत से मिले थे",
        detected_language="hi",
    )
    assert "Kal" in res.normalized_text
    assert "Mussoorie" in res.normalized_text
    assert "Akshat" in res.normalized_text
    assert "mile the" in res.normalized_text
    assert res.normalized_language == "hi"
    assert res.display_script == "latin"
    # Ensure it was NOT translated into English
    assert "yesterday" not in res.normalized_text.lower()
    assert "we met" not in res.normalized_text.lower()


def test_normalizer_urdu_script_to_roman_hindi():
    """3. Urdu-script Hindi normalized to Roman Hindi."""
    normalizer = TranscriptNormalizer(llm_service=LLMService(model_name="mock-memory-extractor"))
    res = normalizer.normalize(
        raw_transcript="کل ہم مسوری میں ملے تھے",
        detected_language="ur",
    )
    assert "Kal" in res.normalized_text
    assert "Mussoorie" in res.normalized_text
    assert "mile the" in res.normalized_text
    assert res.display_script == "latin"
    # Ensure no Urdu script remains in the normalized output
    assert detect_script(res.normalized_text) == "latin"


def test_normalizer_hinglish_preserved():
    """4. Hinglish speech preserved without translating into full English."""
    normalizer = TranscriptNormalizer(llm_service=LLMService(model_name="mock-memory-extractor"))
    res = normalizer.normalize(
        raw_transcript="Project roadmap finalize ho gaya hai, sync call schedule karo.",
        detected_language="hi",
    )
    assert "Project roadmap finalize ho gaya hai" in res.normalized_text
    assert "sync call schedule karo" in res.normalized_text
    assert res.normalized_language in ("mixed", "hi")
    assert res.display_script == "latin"


def test_normalizer_proper_noun_asr_correction():
    """5. Obvious proper-noun ASR phonetic error 'Masori' -> 'Mussoorie'."""
    normalizer = TranscriptNormalizer(llm_service=LLMService(model_name="mock-memory-extractor"))
    res = normalizer.normalize(
        raw_transcript="Masori was really beautiful and peaceful.",
        detected_language="en",
    )
    assert "Mussoorie" in res.normalized_text
    assert "Masori" not in res.normalized_text


def test_normalizer_unknown_name_not_aggressively_autocorrected():
    """6. Unknown name (e.g. 'Rohanxyz') is preserved without hallucinating a different name."""
    normalizer = TranscriptNormalizer(llm_service=LLMService(model_name="mock-memory-extractor"))
    res = normalizer.normalize(
        raw_transcript="Met Rohanxyz at the cafe.",
        detected_language="en",
    )
    assert "Rohanxyz" in res.normalized_text


def test_normalizer_no_translation_to_english():
    """7. Hindi input is NEVER translated to English."""
    normalizer = TranscriptNormalizer(llm_service=LLMService(model_name="mock-memory-extractor"))
    res = normalizer.normalize(
        raw_transcript="कल हम अक्षत से मिले थे",
        detected_language="hi",
    )
    assert "Kal" in res.normalized_text
    assert "Akshat" in res.normalized_text
    assert "Yesterday" not in res.normalized_text


def test_normalizer_no_hallucination_on_unclear_audio():
    """8. Muffled / short audio transcript is not expanded with hallucinated facts."""
    normalizer = TranscriptNormalizer(llm_service=LLMService(model_name="mock-memory-extractor"))
    short_raw = "Testing voice memo one two three."
    res = normalizer.normalize(
        raw_transcript=short_raw,
        detected_language="en",
    )
    assert res.normalized_text == short_raw


def test_normalizer_english_proper_nouns_preserved():
    """9. English proper nouns like 'McDonald's' remain accurately preserved."""
    normalizer = TranscriptNormalizer(llm_service=LLMService(model_name="mock-memory-extractor"))
    raw = "Had lunch at McDonald's with Sarah."
    res = normalizer.normalize(raw_transcript=raw, detected_language="en")
    assert "McDonald's" in res.normalized_text
    assert "Sarah" in res.normalized_text


def test_audio_processor_end_to_end_preserves_raw_whisper_and_normalizes_clean():
    """10. End-to-end AudioProcessor preserves raw_text (ASR) while setting normalized clean_text."""
    from app.services.audio_processor import AudioProcessor
    from app.services.whisper_service import WhisperService
    from pathlib import Path

    def mock_transcribe(file_path: Path):
        return {
            "transcript": "Masori trip was amazing with Akshat.",
            "language": "en",
            "language_probability": 0.98,
            "duration": 4.2,
            "segments": [],
        }

    whisper = WhisperService(mock_transcriber=mock_transcribe)
    processor = AudioProcessor(whisper_service=whisper)

    # Valid wav header
    riff_bytes = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00" + b"\x00" * 32
    result = processor.process(file_bytes=riff_bytes, filename="voice.wav")

    # Raw transcript preserved verbatim
    assert result.raw_text == "Masori trip was amazing with Akshat."
    # Clean transcript has proper noun normalized
    assert result.clean_text == "Mussoorie trip was amazing with Akshat."
    # Telemetry preserved
    assert result.detected_language == "en"
    assert result.language_probability == 0.98
    assert result.display_script == "latin"
