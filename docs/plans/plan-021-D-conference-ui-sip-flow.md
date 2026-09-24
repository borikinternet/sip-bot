# 021-D: conference UI, QR и browser SIP flow

Уровень: `child plan` · Родитель: [`Map-021`](plan-021-web-rag-conference-demo.md)
Статус: `in_progress`
Evidence root: `artifacts/implementation/021-web-rag-sip-demo/D/`

## Цель и граница

Собрать визуальный demo-flow: логотипы, QR-код на заданный URL, описание текущего RAG, тему и примеры вопросов,
статус подготовки и кнопку «Позвонить». После `rag_ready` UI обновляется и включает кнопку только для готового корпуса.
Browser SIP-клиент используется из принятого Map-020 transport contract.

## Source-map, owner и write-set

Owner: frontend state/view and browser-call adapter. Write-set: `demo-web/frontend/`, provided logo assets, QR asset or
runtime generator, UI tests and evidence. Received assets are staged as `assets/partner-logo.svg` and
`assets/project-author.png`; render both in a common small visual tile, using `contain` for the wide logo and `cover`
for the square author photo. No custom SIP stack, no audio proxy and no FreeSWITCH config changes.

## Acceptance

- baseline RAG displays immediately with active call button;
- custom upload displays preparing state, then live title/topic/questions after `rag_ready`;
- QR encodes supplied page URL, not localhost placeholder in final evidence;
- caller ID/session binding is preserved in browser SIP identity;
- browser call enters `mod_callcenter` and reports waiting/connected/ended states;
- greeting text identifies «Василису» and current topic where metadata exists;
- reload does not revive the old custom session;
- no frontend claim implies production auth/security.

## Blocker register

| ID | Trigger | What blocks | Status |
|---|---|---|---|
| B-021-D-1 | final conference hostname/trusted certificate absent | final public QR/live closeout | `resolved for local rehearsal — QR uses 192.168.1.74 and WSS uses the temporary host-to-WSL forwarder; replace later` |
| B-021-D-2 | Map-020 browser client contract changes | browser call | `resolved for local contract; target correlation pending` |

## Test/evidence и closeout

The local UI shell, asset placement, upload/preparing/ready state and browser SIP adapter are implemented; `node
--check demo-web/frontend/app.js` passes. The local QR now encodes `http://192.168.1.74:8080/`, and the exact local
WSS/SIP config is staged in `demo-config.js`. Evidence and promotion conditions are recorded in
[`D/closeout.md`](../../artifacts/implementation/021-web-rag-sip-demo/D/closeout.md).
