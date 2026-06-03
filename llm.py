import os
from groq import AsyncGroq
from dotenv import load_dotenv


class LLM:
    def __init__(
        self,
        model: str = "llama-3.1-8b-instant",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ):
        load_dotenv()
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY environment variable not set")
        self._client = AsyncGroq(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def generate(self, messages: list[dict]) -> str:
        reply = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout=30,
        )
        return reply.choices[0].message.content
