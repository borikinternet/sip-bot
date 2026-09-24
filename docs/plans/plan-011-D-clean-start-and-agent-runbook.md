# План 011-D: чистый повтор и сценарий для агента без контекста

Уровень: `child plan`  
Идентификатор: `011-D`  
Статус owner review: `accepted — scope из Map-011 принят владельцем 2026-09-20`  
Статус исполнения: `complete — 2026-09-21`  
Родитель: [`Map-011`](plan-011-freeswitch-small-company-callcenter-workshop.md)  
Зависимости: [`011-A`](plan-011-A-debian-wsl-freeswitch-packages.md), [`011-B`](plan-011-B-microsip-two-endpoint-call.md), [`011-C`](plan-011-C-mod-callcenter-queue-agent.md)

## Цель и проверяемый результат

После успешных A–C создать audience/agent runbook по реально проверенным командам и выполнить сценарий с чистого старта WSL, не используя контекст чата и не полагаясь на скрытые defaults.

## Materialized rules

- Инструкция отражает только verified commands/config и конкретную версию package/runtime; draft command нельзя выдавать как испытанный.
- Полный основной сценарий: открыть/start Debian; проверить FreeSWITCH active; открыть два MicroSIP; прямой call 1000→1001; завершить его; caller 1000 звонит в 7000; подождать; answer на agent 1001; проверить connected/audio.
- Зафиксировать, что systemd autostart действует при старте WSL distro; автоматический старт самой WSL при host boot не подразумевается.
- Включить обычный cleanup/recovery, но не очистку Docker, не удаление дистрибутивов и не уничтожение user data.
- Runbook должен быть достаточен агенту без диалога: цель, constraints, source link, exact commands, expected outputs, UI fields, stop conditions, evidence path и who performs manual GUI checks.

## Write-set

- `docs/workshops/freeswitch-callcenter-runbook.md`, `config/workshops/freeswitch/**`, `tools/workshops/**`
- `artifacts/workshops/freeswitch-callcenter/011-D/`
- Map-011 и child plans A–D только для фактических status/evidence updates; реестр/backlog изменяются главным исполнителем.

## Выполнение и acceptance

1. Исполнитель, не используя предшествующую чат-переписку, следует написанному runbook с чистого WSL stop/start.
2. Прямой SIP вызов и callcenter queue/agent call выполняются на двух MicroSIP clients, с owner/участником, который может ответить в GUI и подтвердить звук.
3. Сравнить ожидаемые и фактические outputs, устранить дефект инструкции в разрешённом scope и повторить весь runbook.
4. Результат — manifest с версиями, командами, exit codes, sanitized logs, SIP/queue events и подтверждением live audio. Секреты/пароли и записи разговоров не сохранять.
5. Проверить ссылки, registry/backlog/roadmap и closeout Map-011. Child plan может закрыться только `complete` или concrete `blocked` по APG.

## Blockers

- `011-D-B1`: `resolved 2026-09-21` — независимое context-free review после двух corrective iterations дало PASS.
- `011-D-B2`: `resolved 2026-09-21` — clean repeat совпал с первым успешным direct/queue flow.
- `011-D-B3`: `resolved 2026-09-21` — владелец подтвердил ожидание, answer и слышимость собственного голоса.

## Execution checkpoint — 2026-09-21

- Создан self-contained [`freeswitch-callcenter-runbook.md`](../workshops/freeswitch-callcenter-runbook.md) с exact
  source/hash, WSL import, apt signature, package/config commands, MicroSIP profiles, expected outputs, restart semantics,
  stop conditions и diagnostics.
- После `wsl --terminate Debian-Bookworm-FS` выполнен полный технический повтор: systemd/service/module, две
  registrations, direct bridge, queue `Trying/Receiving/RINGING → Answered/In a queue call/ACTIVE`, cleanup.
- Evidence: [`011-D/clean-repeat.md`](../../artifacts/workshops/freeswitch-callcenter/011-D/clean-repeat.md).
- Runbook не выдаёт CLI за проверку слуха. Владелец 2026-09-21 подтвердил live audibility, `011-D-B3` resolved.
- Независимый субагент без истории переписки выполнил три read-only прохода. Первый нашёл hardcoded D:, пропущенные
  PowerShell/root-shell transitions, session-variable, integrity-check и ExecutionPolicy gaps; второй — ошибочный выбор
  заполненного D: и отсутствие helper exit-code check; после исправлений финальный verdict: `PASS`, blocking/major/minor
  findings отсутствуют, referenced files существуют.
- Все acceptance boundaries выполнены без упрощений; plan complete.
