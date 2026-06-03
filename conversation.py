import time


class ConversationManager:
    def __init__(self, system_prompt: str = "You are a helpful assistant."):
        self._messages: list[dict] = []
        self.system_prompt = system_prompt

    @property
    def messages(self) -> list[dict]:
        return [{"role": "system", "content": self.system_prompt}] + self._messages

    def add_turn(self, role: str, content: str) -> None:
        self._messages.append({
            "role": role,
            "content": content,
        })

    def reset(self) -> None:
        self._messages.clear()

    def __len__(self) -> int:
        return len(self._messages)
