# ADR-004: Process-local event bus для control plane

Статус: `accepted`  
Дата принятия: `2026-09-02`

## Контекст

В боте несколько компонентов публикуют control-plane события, а у некоторых событий может быть несколько подписчиков:
SIP/media adapter, speech ingress, LLM Facade, playback, transfer и отчётность. Прямые связи между всеми publishers и
subscribers быстро создают связность и затрудняют lifecycle/cancellation.

При этом audio и крупные текстовые payload должны идти напрямую по data plane. Универсальная шина не должна превращаться
в транзит PCM, ASR/TTS stream или RAG-контекста.

## Решение

Вводится один process-local singleton `Control Event Bus` для доставки typed control-plane event envelopes и команд между
компонентами одного процесса.

- Dispatcher/Dialogue FSM остаётся владельцем смыслового состояния, переходов и semantic SIP actions.
- Event bus владеет только подписками, доставкой control events/commands, lifecycle подписчиков и bounded delivery.
- PCM, media frames, ASR/TTS streams, большие тексты и RAG-фрагменты через bus не проходят.
- Bus не исполняет действия, не меняет FSM напрямую и не заменяет прямые data-plane channels.
- Закрытие call scope отписывает/закрывает его подписки; terminal/cancel events не должны доставляться закрытым подписчикам.

## Рассмотренные альтернативы

### Прямые связи каждого publisher с каждым subscriber

Отклонено как основная схема: растёт число связей, а lifecycle и fan-out становятся распределёнными и плохо обозримыми.
Прямые data-plane каналы сохраняются там, где они нужны для payload.

### Универсальная шина для audio и text payload

Отклонено: это добавило бы лишние копирования, синхронизации и скрытую задержку, а также смешало бы transport и control
semantics.

### Внешний брокер сообщений

Отклонено для MVP: отдельный процесс/сервис не нужен для одного локального разговора и расширил бы scope.

## Последствия

Положительные:

- один control-plane fan-out для нескольких подписчиков;
- явный владелец подписок и закрытия;
- Dispatcher остаётся единственным владельцем FSM и необратимых действий;
- data-plane payload не проходит через дополнительный универсальный транспорт.

Отрицательные:

- появляется ещё один typed control contract;
- bus требует bounded delivery, unsubscribe и close tests;
- глобальный singleton допустим только в границах одного application process и одного MVP runtime.

## Связанные документы

- [Архитектура MVP](../architecture.md)
- [Техническое задание](../technical-specification.md)
- [Map-002-I](../plans/plan-002-I-boundary-interaction-map.md)
- [Plan-002-E](../plans/plan-002-E-dispatcher-dialogue-fsm.md)

