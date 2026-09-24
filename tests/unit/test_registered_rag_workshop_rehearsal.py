from __future__ import annotations

from tools.knowledge.registered_rag_workshop_rehearsal import _assistant_text_for_turn


def test_assistant_answer_lookup_ignores_call_greeting() -> None:
    dialogue_turns = [
        {"turn": {"role": "assistant", "turn_id": "call-in-0:greeting", "text": "Алло."}},
        {"turn": {"role": "user", "turn_id": "call-in-0:turn-4", "text": "Вопрос"}},
        {
            "turn": {
                "role": "assistant",
                "turn_id": "call-in-0:turn-4:answer",
                "text": "Подключить оператора?",
            }
        },
    ]

    assert _assistant_text_for_turn(dialogue_turns, "turn-4") == "Подключить оператора?"
