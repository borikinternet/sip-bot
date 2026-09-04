import json
import threading
from pathlib import Path

from sip_bot.llm import LlmFacade, OllamaHttpClient, StreamEventKind
from sip_bot.llm.types import InferenceStatusKind
from sip_bot.prompt.manager import GenerationProfile, PromptSpec, SkillPromptManager, SkillSpec
from sip_bot.retrieval.contracts import EmbeddingRequest, KnowledgeContext


class FakeResponse:
    def __init__(self, lines=(), body=b"{}"):
        self.lines = list(lines)
        self.body = body
        self.closed = False

    def readline(self):
        if self.closed or not self.lines:
            return b""
        return self.lines.pop(0)

    def read(self, amount=-1):
        return self.body

    def close(self):
        self.closed = True


def make_request(tmp_path: Path):
    snapshot = __import__("sip_bot.context.store", fromlist=["ContextStore"]).ContextStore(tmp_path, "call-g").append_user(
        "turn-1", "Почему небо голубое?"
    )
    knowledge = KnowledgeContext("ctx-1", "Почему небо голубое?", (), False, 0.7, 3, "index-v1", "embed-v1")
    return SkillPromptManager(
        skill=SkillSpec("answer-ru", "1", "Отвечай кратко."),
        prompt=PromptSpec("prompt", "1", "{instruction}\n{knowledge}\n{user_text}"),
        profile=GenerationProfile("profile", "1", 128, 0.0),
        output_schema_id="schema-v1",
    ).prepare(
        call_id="call-g", turn_id="turn-1", final_user_text="Почему небо голубое?", snapshot=snapshot, knowledge_context=knowledge
    )


def chat_client(response, observed=None):
    def opener(url, body, timeout):
        if observed is not None:
            observed.append((url, json.loads(body.decode("utf-8")), timeout))
        return response

    return OllamaHttpClient(
        endpoint="http://127.0.0.1:11434", chat_model="qwen-test", embedding_model="embed-v1", opener=opener
    )


def test_chat_stream_maps_ndjson_to_typed_decision_and_latency(tmp_path: Path):
    response = FakeResponse(
        [
            b'{"message":{"role":"assistant","content":"{\\"action\\":\\"answer\\",\\"text\\":\\""},"done":false}\n',
            '{"message":{"role":"assistant","content":"небо голубое"},"done":false}\n'.encode("utf-8"),
            b'{"message":{"role":"assistant","content":"\\"}"},"done":true}\n',
        ]
    )
    observed = []
    operation = LlmFacade(chat_client(response, observed)).start_chat(make_request(tmp_path), final_user_turn_ns=1)
    events = list(operation)

    assert [event.kind for event in events] == [
        StreamEventKind.STARTED,
        StreamEventKind.DELTA,
        StreamEventKind.DELTA,
        StreamEventKind.DELTA,
        StreamEventKind.DECISION,
        StreamEventKind.COMPLETED,
    ]
    assert events[-2].decision.action == "answer"
    assert events[-2].decision.text == "небо голубое"
    assert operation.status.status is InferenceStatusKind.COMPLETED
    assert operation.trace.final_to_first_usable_ms is not None
    assert operation.trace.request_to_final_result_ms is not None
    assert observed[0][0].endswith("/api/chat")
    assert observed[0][1]["stream"] is True
    assert observed[0][1]["format"] == {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "text"],
        "properties": {
            "action": {"type": "string", "enum": ["offer_transfer"]},
            "text": {"type": "string", "minLength": 1},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
    }
    assert observed[0][1]["think"] is False
    assert observed[0][1]["options"] == {"temperature": 0.1, "num_predict": 192}
    assert response.closed is True


def test_embedding_uses_same_facade_boundary_as_chat():
    observed = []

    def opener(url, body, timeout):
        observed.append((url, json.loads(body.decode("utf-8"))))
        return FakeResponse(body=b'{"embeddings":[[0.25, -1.0, 2]]}')

    facade = LlmFacade(OllamaHttpClient(opener=opener, embedding_model="embed-v1"))
    result = facade.embed(EmbeddingRequest("embedding-1", "Небо голубое", "embed-v1"))

    assert result.request_id == "embedding-1"
    assert result.vector == (0.25, -1.0, 2.0)
    assert observed == [("http://127.0.0.1:11434/api/embed", {"model": "embed-v1", "input": "Небо голубое"})]


def test_warmup_requires_a_complete_structured_chat(tmp_path: Path):
    response = FakeResponse(
        ['{"message":{"content":"{\\"action\\":\\"offer_transfer\\",\\"text\\":\\"Готов\\"}"},"done":true}\n'.encode("utf-8")]
    )
    trace = LlmFacade(chat_client(response)).warmup(make_request(tmp_path))

    assert trace.request_started_ns is not None
    assert trace.final_result_ns is not None
    assert response.closed is True


def test_malformed_final_response_is_failure_not_success(tmp_path: Path):
    response = FakeResponse([b'{"message":{"content":"plain text"},"done":true}\n'])
    operation = LlmFacade(chat_client(response)).start_chat(make_request(tmp_path))
    events = list(operation)

    assert events[-1].kind is StreamEventKind.ERROR
    assert events[-1].error_code == "malformed_response"
    assert operation.status.status is InferenceStatusKind.FAILED
    assert not any(event.kind is StreamEventKind.COMPLETED for event in events)


def test_malformed_ndjson_and_timeout_are_mapped(tmp_path: Path):
    malformed = LlmFacade(chat_client(FakeResponse([b"not-json\n"]))).start_chat(make_request(tmp_path))
    timeout_client = OllamaHttpClient(opener=lambda url, body, timeout: (_ for _ in ()).throw(TimeoutError("slow")))
    timeout = LlmFacade(timeout_client).start_chat(make_request(tmp_path))

    malformed_events = list(malformed)
    timeout_events = list(timeout)

    assert malformed_events[-1].error_code == "malformed_response"
    assert timeout_events[-1].error_code == "timeout"
    assert timeout.status.status is InferenceStatusKind.FAILED


def test_stream_read_timeout_is_mapped_to_typed_failure(tmp_path: Path):
    class TimeoutResponse(FakeResponse):
        def readline(self):
            raise TimeoutError("read timed out")

    operation = LlmFacade(chat_client(TimeoutResponse())).start_chat(make_request(tmp_path))
    events = list(operation)

    assert events[-1].kind is StreamEventKind.ERROR
    assert events[-1].error_code == "timeout"
    assert operation.status.status is InferenceStatusKind.FAILED


def test_cancel_closes_stream_and_suppresses_late_stale_chunk(tmp_path: Path):
    first_read = threading.Event()
    release = threading.Event()

    class BlockingResponse(FakeResponse):
        def readline(self):
            if not self.lines:
                first_read.set()
                release.wait(timeout=2)
                return b'{"message":{"content":"stale"},"done":true}\n'
            return super().readline()

    response = BlockingResponse([b'{"message":{"content":"prefix"},"done":false}\n'])
    operation = LlmFacade(chat_client(response)).start_chat(make_request(tmp_path))
    collected = []

    def consume():
        collected.extend(operation)

    worker = threading.Thread(target=consume)
    worker.start()
    assert first_read.wait(timeout=2)
    operation.cancel(reason="barge_in")
    release.set()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert response.closed is True
    assert [event.kind for event in collected].count(StreamEventKind.CANCELLED) == 1
    assert not any(event.kind is StreamEventKind.COMPLETED for event in collected)
    assert operation.status.status is InferenceStatusKind.CANCELLED
