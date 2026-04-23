import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

_ANALYSIS_CACHE = {}


async def analyze_project(title: str, description: str) -> str:
    """Анализирует заказ через GPT-4o-mini. Возвращает короткую оценку или пустую строку."""
    if not OPENAI_API_KEY:
        return ""

    cache_key = f"{title[:50]}_{description[:50]}"
    if cache_key in _ANALYSIS_CACHE:
        return _ANALYSIS_CACHE[cache_key]

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты эксперт по фриланс-биржам. Проанализируй заказ и дай ОДНУ фразу максимум 8 слов. "
                        "Оцени: полнота ТЗ, адекватность бюджета, красные флаги. "
                        "Ответь простым текстом без кавычек и форматирования."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Название: {title}\nОписание: {description[:600]}",
                },
            ],
            max_tokens=40,
            temperature=0.3,
        )
        result = resp.choices[0].message.content.strip().replace("\n", " ")
        _ANALYSIS_CACHE[cache_key] = result
        return result
    except Exception as e:
        print(f"AI analysis error: {e}")
        return ""
