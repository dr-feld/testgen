from __future__ import annotations


def postprocess(raw_response: str) -> str:
    """Простая постобработка ответа LLM (MVP версия)"""
    # Извлекаем код из ```cpp ... ```
    if "```cpp" in raw_response:
        start = raw_response.find("```cpp") + 6
        end = raw_response.find("```", start)
        if end != -1:
            return raw_response[start:end].strip()
    
    elif "```" in raw_response:
        start = raw_response.find("```") + 3
        end = raw_response.find("```", start)
        if end != -1:
            return raw_response[start:end].strip()
    
    # Если блоков нет — возвращаем как есть
    return raw_response.strip()