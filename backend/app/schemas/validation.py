from app.schemas.memory_output import MemoryV1


def validate_memory(memory: MemoryV1 | dict) -> MemoryV1:
    if isinstance(memory, MemoryV1):
        return MemoryV1.model_validate(memory.model_dump())
    return MemoryV1.model_validate(memory)
