import os
import json
from typing import Any, Optional, List, Dict
from phase2_orchestration.config import settings

class LLMService:
    def __init__(self, model_name: str = "mock-memory-extractor"):
        self.model_name = model_name

    def format_memories_context(self, memories: List[Dict[str, Any]]) -> str:
        context_blocks = []
        for idx, mem in enumerate(memories, start=1):
            content = mem.get("content", {})
            entities = mem.get("entities", {})
            semantics = mem.get("semantics", {})
            temporal = mem.get("temporal", {})

            block_lines = [f"Memory #{idx}:"]
            summary = content.get("summary") or content.get("clean_text") or content.get("raw_text")
            if summary:
                block_lines.append(f"• Summary: {summary}")

            people = entities.get("people") or entities.get("person")
            if people:
                block_lines.append(f"• People: {', '.join(people) if isinstance(people, list) else str(people)}")

            places = entities.get("places") or entities.get("place")
            if places:
                block_lines.append(f"• Places: {', '.join(places) if isinstance(places, list) else str(places)}")

            topics = semantics.get("topics")
            if topics:
                block_lines.append(f"• Topics: {', '.join(topics) if isinstance(topics, list) else str(topics)}")

            dates = temporal.get("mentioned_dates")
            if dates:
                block_lines.append(f"• Dates: {', '.join(dates) if isinstance(dates, list) else str(dates)}")

            context_blocks.append("\n".join(block_lines))
        return "\n\n".join(context_blocks)

    def answer_from_memories(
        self,
        query: str,
        memories: List[Dict[str, Any]]
    ) -> str:
        """Generates natural answer grounded ONLY in the retrieved MemoryV1 payloads."""
        if not memories or not query or not query.strip():
            return "I couldn't find a relevant memory matching your query."

        # 1. If OpenAI API key is set in environment, use LLM
        api_key = settings.openai_compatible_api_key or os.environ.get("OPENAI_API_KEY")
        if api_key:
            try:
                import httpx
                base_url = settings.openai_compatible_base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
                context = self.format_memories_context(memories)
                messages = [
                    {
                        "role": "system",
                        "content": "You are MindMesh, an AI personal memory assistant. Answer the user's question directly using ONLY the provided memory records. Do not make up facts."
                    },
                    {
                        "role": "user",
                        "content": f"User Question: {query}\n\nRetrieved Memories:\n{context}"
                    }
                ]
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post(
                        f"{base_url.rstrip('/')}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={"model": "gpt-4o-mini", "messages": messages, "temperature": 0.2}
                    )
                    if resp.status_code == 200:
                        return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception:
                pass

        # 2. Local Grounded Synthesis Fallback
        top_mem = memories[0]
        content = top_mem.get("content", {})
        entities = top_mem.get("entities", {})
        summary = content.get("summary") or content.get("clean_text") or content.get("raw_text") or "Relevant memory found."
        
        people = entities.get("people", [])
        places = entities.get("places", [])
        
        extra_details = []
        if people:
            extra_details.append(f"with {', '.join(people)}")
        if places:
            extra_details.append(f"at {', '.join(places)}")
            
        extra_str = f" ({' '.join(extra_details)})" if extra_details else ""
        return f"{summary}{extra_str}"
