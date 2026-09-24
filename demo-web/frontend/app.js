/* Conference demo UI. SIP transport is injected through window.DEMO_SIP_CONFIG. */

const state = { session: null, socket: null, sip: null, call: null, callEnded: false, callSetup: false, callMarked: false, callPhase: "" };
const $ = (id) => document.getElementById(id);

const stateLabels = {
  baseline: "Базовый корпус",
  preparing: "Готовим корпус…",
  ready: "Корпус готов",
  active_call: "SIP-вызов выполняется",
  failed: "Ошибка подготовки",
  stale: "Сессия завершена",
};

function setMessage(text, error = false) {
  $("upload-message").textContent = text || "";
  $("upload-message").style.color = error ? "#b83d3d" : "";
}

function setCallPhase(text, error = false) {
  state.callPhase = text;
  $("status-text").textContent = text;
  $("status-dot").className = `status-dot ${error ? "error" : ""}`;
  $("call-message").textContent = text;
  $("call-message").style.color = error ? "#b83d3d" : "";
}

function setAudioMessage(text, error = false) {
  $("audio-message").textContent = text;
  $("audio-message").style.color = error ? "#b83d3d" : "";
}

function render(status) {
  state.session = status;
  $("caller-id").textContent = status.caller_id || "—";
  $("status-text").textContent = state.callPhase || stateLabels[status.state] || status.state;
  $("corpus-state").textContent = stateLabels[status.state] || status.state;
  if (!state.callPhase) $("status-dot").className = `status-dot ${status.state === "ready" || status.state === "baseline" ? "ready" : status.state === "failed" || status.state === "stale" ? "error" : ""}`;
  const metadata = status.metadata;
  if (metadata) {
    $("corpus-title").textContent = metadata.title || "Без названия";
    $("corpus-description").textContent = metadata.description || "Описание не задано.";
    $("corpus-topic").textContent = metadata.topic || "Тема не указана";
    $("question-list").innerHTML = (metadata.questions || []).length
      ? metadata.questions.map((question) => `<li>${escapeHtml(question)}</li>`).join("")
      : "<li>Проверенных примеров вопросов пока нет. Можно задать свой вопрос по указанной теме.</li>";
  }
  $("call-button").textContent = state.call ? "Завершить звонок" : "Позвонить";
  $("call-button").disabled = state.callSetup || (!state.call && !status.call_enabled);
  $("upload-button").disabled = status.state === "preparing" || status.state === "active_call";
  if (status.error) setMessage(status.error, true);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

function renderQr() {
  const url = window.DEMO_PUBLIC_URL;
  const tile = $("qr-placeholder");
  if (!url || !tile) return;
  tile.textContent = "";
  const image = document.createElement("img");
  image.src = window.DEMO_QR_ASSET || "/assets/qr-demo-ip.png";
  image.alt = `QR-код: ${url}`;
  tile.appendChild(image);
  $("qr-message").textContent = `Сканируйте, чтобы открыть локальный demo: ${url}`;
}

async function jsonRequest(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || payload.message || `HTTP ${response.status}`);
  return payload;
}

async function openSession() {
  const status = await jsonRequest("/api/session");
  render(status);
  state.socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/${status.session_id}`);
  state.socket.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === "ping") state.socket.send(JSON.stringify({ type: "pong" }));
    if (payload.status) render(payload.status);
  };
  state.socket.onclose = () => {
    $("status-text").textContent = "Связь с web-сессией потеряна";
    $("status-dot").className = "status-dot error";
  };
}

$("file-input").addEventListener("change", (event) => {
  const file = event.target.files[0];
  $("file-label").textContent = file ? `${file.name} · ${Math.ceil(file.size / 1024)} КиБ` : "Выбрать файл";
});

$("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = $("file-input").files[0];
  if (!file) return setMessage("Сначала выберите .md, .txt или .pdf файл", true);
  const form = new FormData();
  form.append("file", file, file.name);
  try {
    setMessage("Файл принят. Формируем metadata и вектора…");
    render({ ...state.session, state: "preparing", call_enabled: false, metadata: state.session.metadata });
    render(await jsonRequest(`/api/session/${state.session.session_id}/upload`, { method: "POST", body: form }));
  } catch (error) {
    setMessage(error.message, true);
  }
});

$("call-button").addEventListener("click", async () => {
  if (state.call) {
    setCallPhase("Завершаем звонок…");
    state.call.terminate();
    return;
  }
  if (!state.session?.call_enabled || state.callSetup) return;
  state.callSetup = true;
  state.callEnded = false;
  state.callMarked = false;
  state.callPhase = "";
  setAudioMessage("Ожидаем входящий аудиопоток…");
  $("call-button").disabled = true;
  try {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      throw new Error("Для микрофона откройте страницу по HTTPS или через localhost. HTTP по IP браузер блокирует.");
    }
    setCallPhase("Запрашиваем доступ к микрофону…");
    const microphone = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    microphone.getTracks().forEach((track) => track.stop());
    await connectSip();
    setCallPhase("SIP-сервер подключён. Отправляем вызов…");
    await jsonRequest(`/api/session/${state.session.session_id}/call/started`, { method: "POST" });
    state.callMarked = true;
    startSipCall();
  } catch (error) {
    await endSipCall(`Звонок не начался: ${error.message || error}`, true);
  } finally {
    state.callSetup = false;
    if (state.session) render(state.session);
  }
});

async function connectSip() {
  const config = window.DEMO_SIP_CONFIG;
  if (!config || !window.JsSIP) {
    throw new Error("SIP-клиент не загружен");
  }
  const callerId = state.session.caller_id;
  if (!callerId || !config.sipDomain || !config.targetUri || !config.wsUrl) {
    throw new Error("SIP-конфигурация неполная: нужны wsUrl, sipDomain и targetUri");
  }
  const socket = new JsSIP.WebSocketInterface(config.wsUrl);
  const ua = new JsSIP.UA({
    sockets: [socket],
    uri: `sip:${callerId}@${config.sipDomain}`,
    authorization_user: config.authUser,
    password: config.password,
    register: false,
    session_timers: false,
  });
  state.sip = ua;
  setCallPhase(`Подключаемся к SIP-серверу ${config.wsUrl}…`);
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`SIP WebSocket ${config.wsUrl} не ответил за 10 секунд`)), 10000);
    ua.once("connected", () => { clearTimeout(timer); resolve(); });
    ua.once("disconnected", (event) => {
      clearTimeout(timer);
      reject(new Error(`SIP WebSocket ${config.wsUrl}: ${event.reason || event.code || "соединение закрыто"}`));
    });
    ua.start();
  });
}

function startSipCall() {
  const config = window.DEMO_SIP_CONFIG;
  const session = state.sip.call(config.targetUri, {
    mediaConstraints: { audio: true, video: false },
    pcConfig: config.pcConfig || {},
    eventHandlers: {
      peerconnection: (event) => attachRemoteAudio(event.peerconnection),
    },
  });
  state.call = session;
  attachRemoteAudio(session.connection);
  if (state.session) render(state.session);
  session.on("progress", (event) => {
    const code = event.response?.status_code;
    setCallPhase(code ? `SIP ${code}: вызов обрабатывается FreeSWITCH…` : "Вызов обрабатывается FreeSWITCH…");
  });
  session.on("accepted", () => setCallPhase("SIP 200: FreeSWITCH ответил; ожидайте соединения с Василисой…"));
  session.on("ended", () => endSipCall("Разговор завершён"));
  session.on("failed", (event) => {
    const code = event.message?.status_code;
    endSipCall(`SIP-вызов не состоялся${code ? ` (${code})` : ""}: ${event.cause || "неизвестная причина"}`, true);
  });
  session.on("confirmed", () => {
    setCallPhase("SIP-соединение установлено. Если Василиса занята, играет очередь; ожидайте её ответа.");
    attachRemoteAudio(session.connection);
    setTimeout(() => {
      if (state.call === session && !$("remote-audio").srcObject) {
        setAudioMessage("Входящий аудиопоток не подключился.", true);
      }
    }, 5000);
  });
  session.on("peerconnection", (event) => attachRemoteAudio(event.peerconnection));
}

function attachRemoteAudio(connection) {
  if (!connection || connection.__demoAudioAttached) return;
  connection.__demoAudioAttached = true;
  const attachTrack = (track, stream) => {
    if (!track || track.kind !== "audio") return;
    const audio = $("remote-audio");
    if (audio.srcObject?.getAudioTracks().some((existing) => existing.id === track.id)) return;
    audio.srcObject = stream || new MediaStream([track]);
    audio.play().then(
      () => setAudioMessage("Воспроизведение входящего аудиопотока запущено."),
      (error) => setAudioMessage(`Аудиопоток получен, но браузер не воспроизводит его: ${error.message}`, true),
    );
  };
  connection.addEventListener("track", (event) => {
    attachTrack(event.track, event.streams?.[0]);
  });
  for (const receiver of connection.getReceivers?.() || []) attachTrack(receiver.track);
}

async function endSipCall(message, error = false) {
  if (state.callEnded) return;
  state.callEnded = true;
  const sip = state.sip;
  state.sip = null;
  state.call = null;
  if (state.callMarked && state.session) {
    const status = await jsonRequest(`/api/session/${state.session.session_id}/call/ended`, { method: "POST" }).catch(() => null);
    if (status) render(status);
  }
  state.callMarked = false;
  if (sip) sip.stop();
  $("remote-audio").pause();
  $("remote-audio").srcObject = null;
  setAudioMessage("");
  setCallPhase(message, error);
  if (state.session) render(state.session);
}

renderQr();
openSession().catch((error) => {
  $("status-text").textContent = error.message;
  $("status-dot").className = "status-dot error";
});
