import json
from pathlib import Path

from sip_bot.llm import LlmFacade, OllamaHttpClient, StreamEventKind
from sip_bot.prompt.manager import GenerationProfile, PromptSpec, SkillPromptManager, SkillSpec
from sip_bot.retrieval.contracts import KnowledgeContext


class Response:
    def __init__(self, lines):
        self.lines = list(lines)
        self.closed = False

    def readline(self):
        return b"" if self.closed or not self.lines else self.lines.pop(0)

    def read(self, amount=-1):
        return b"{}"

    def close(self):
        self.closed = True


def request(tmp_path: Path):
    store = __import__("sip_bot.context.store", fromlist=["ContextStore"]).ContextStore(tmp_path, "contract-call")
    snapshot = store.append_user("turn-1", "Почему небо голубое?")
    return SkillPromptManager(
        skill=SkillSpec("answer-ru", "1", "answer"),
        prompt=PromptSpec("prompt", "1", "{instruction}:{knowledge}:{user_text}"),
        profile=GenerationProfile("profile", "1", 128, 0.0),
        output_schema_id="schema-v1",
    ).prepare(
        call_id="contract-call",
        turn_id="turn-1",
        final_user_text="Почему небо голубое?",
        snapshot=snapshot,
        knowledge_context=KnowledgeContext("ctx", "q", (), False, 0.7, 3, "idx", "embed"),
    )


def test_ollama_chat_contract_accepts_generate_style_response(tmp_path: Path):
    observed = []

    def opener(url, body, timeout):
        observed.append((url, json.loads(body.decode("utf-8"))))
        return Response(
            [
                '{"response":"{\\"action\\":\\"answer\\",\\"text\\":\\"готово\\"}","done":true}\n'.encode("utf-8")
            ]
        )

    operation = LlmFacade(OllamaHttpClient(opener=opener, chat_model="qwen-test")).start_chat(request(tmp_path))
    events = list(operation)

    assert any(event.kind is StreamEventKind.DECISION for event in events)
    assert events[-1].kind is StreamEventKind.COMPLETED
    assert observed[0][0] == "http://127.0.0.1:11434/api/chat"
    assert observed[0][1]["model"] == "qwen-test"
    assert observed[0][1]["format"]["additionalProperties"] is False
    assert observed[0][1]["format"]["properties"]["action"]["enum"] == ["offer_transfer"]
