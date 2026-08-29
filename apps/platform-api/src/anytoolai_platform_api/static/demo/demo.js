"use strict";

const POLL_INTERVAL_MS = 2000;
const RUN_TIMEOUT_MS = 90000;
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const WORKFLOWS = {
  analyze: {
    title: "Анализ и уточнение",
    example: "Клиенту нужен первый релиз сервиса как можно скорее. Бюджет — 450 000 рублей. В первую версию должны войти личный кабинет, каталог услуг и уведомления. Точная дата запуска и критерии приёмки пока не определены."
  },
  evaluate: {
    title: "Оценка соответствия",
    example: "Нам нужен специалист, который за четыре недели проведёт аудит продукта, сформирует список приоритетных улучшений и поможет команде внедрить первые изменения. Важно подтвердить опыт запуска B2B-сервисов и умение работать с небольшой командой."
  },
  write: {
    title: "Подготовка убедительного ответа",
    example: "Мы уже запускали похожий B2B-продукт и сократили время подготовки первой версии до пяти недель. Предлагаем начать с короткого аудита, согласовать измеримые критерии результата и показать рабочий прототип в конце первой недели."
  }
};

const RESULT_LABELS = {
  "sections": "Разделы отчёта",
  "summary": "Краткий итог",
  "id": "Идентификатор",
  "title": "Заголовок",
  "content": "Содержание",
  "metadata": "Дополнительные данные",
  "kind": "Тип раздела",
  "scores": "Оценки по критериям",
  "axis_id": "Критерий",
  "score": "Оценка",
  "commentary": "Комментарий",
  "dominant_axes": "Сильные стороны",
  "weakest_axes": "Зоны улучшения",
  "text": "Готовый текст",
  "call_to_action": "Следующий шаг"
};

const accessForm = document.querySelector("#access-form");
const accessCodeInput = document.querySelector("#access-code");
const accessPanel = document.querySelector("#access-panel");
const workflowSection = document.querySelector("#workflow-section");
const sourceText = document.querySelector("#source-text");
const characterCount = document.querySelector("#character-count");
const runButton = document.querySelector("#run-button");
const runPanel = document.querySelector("#run-panel");
const runningWorkflow = document.querySelector("#running-workflow");
const elapsedTime = document.querySelector("#elapsed-time");
const statusMessage = document.querySelector("#status-message");
const resultPanel = document.querySelector("#result-panel");
const resultContent = document.querySelector("#result-content");
const rawJson = document.querySelector("#raw-json");
const technicalProofList = document.querySelector("#technical-proof-list");
const rerunButton = document.querySelector("#rerun-button");

let accessCode = "";
let running = false;
let timerId = null;
let runStartedAt = 0;

function selectedDemoId() {
  const selected = document.querySelector('input[name="demo-workflow"]:checked');
  return selected ? selected.value : "analyze";
}

function updateExample() {
  const workflow = WORKFLOWS[selectedDemoId()];
  sourceText.value = workflow.example;
  updateCharacterCount();
}

function updateCharacterCount() {
  characterCount.textContent = `${Array.from(sourceText.value).length} / 4000`;
}

function showStatus(message, tone = "") {
  statusMessage.textContent = message;
  if (tone) {
    statusMessage.dataset.tone = tone;
  } else {
    delete statusMessage.dataset.tone;
  }
}

function scrollToPanel(panel) {
  panel.scrollIntoView({ behavior: REDUCED_MOTION ? "auto" : "smooth", block: "start" });
}

function setRunningState(nextRunning) {
  running = nextRunning;
  runButton.disabled = nextRunning;
  runPanel.hidden = !nextRunning;
  if (nextRunning) {
    workflowSection.hidden = true;
  }
  if (!nextRunning && timerId !== null) {
    window.clearInterval(timerId);
    timerId = null;
  }
}

function startElapsedTimer() {
  runStartedAt = Date.now();
  elapsedTime.textContent = "0:00";
  timerId = window.setInterval(() => {
    const elapsedSeconds = Math.floor((Date.now() - runStartedAt) / 1000);
    const minutes = Math.floor(elapsedSeconds / 60);
    const seconds = String(elapsedSeconds % 60).padStart(2, "0");
    elapsedTime.textContent = `${minutes}:${seconds}`;
  }, 1000);
}

function appendValue(container, value) {
  if (Array.isArray(value)) {
    const list = document.createElement("ul");
    list.className = "result-list";
    value.forEach((item) => {
      const listItem = document.createElement("li");
      if (item !== null && typeof item === "object") {
        appendValue(listItem, item);
      } else {
        listItem.textContent = String(item);
      }
      list.append(listItem);
    });
    container.append(list);
    return;
  }

  if (value !== null && typeof value === "object") {
    Object.entries(value).forEach(([key, nestedValue]) => {
      const field = document.createElement("div");
      field.className = "result-field";
      const label = document.createElement("strong");
      label.textContent = RESULT_LABELS[key] || key.replaceAll("_", " ");
      field.append(label);
      appendValue(field, nestedValue);
      container.append(field);
    });
    return;
  }

  const paragraph = document.createElement("p");
  paragraph.textContent = value === null ? "—" : String(value);
  container.append(paragraph);
}

function addProofValue(label, value) {
  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent = value === null || value === undefined ? "—" : String(value);
  technicalProofList.append(term, description);
}

function renderResult(result, session) {
  resultContent.replaceChildren();
  technicalProofList.replaceChildren();
  appendValue(resultContent, result.output);
  rawJson.textContent = JSON.stringify(result.output, null, 2);
  addProofValue("scenario_session_id", result.scenario_session_id || session.scenario_session_id);
  addProofValue("job_id", result.job_id || session.job_id);
  addProofValue("result_artifact_id", result.result_artifact_id);
  addProofValue("workflow_id", result.workflow_id);
  addProofValue("workflow_version", result.workflow_version);
  addProofValue("schema_ref", result.schema_ref);
  addProofValue("schema_version", result.schema_version);
  addProofValue("created_at", result.created_at);
  resultPanel.hidden = false;
  scrollToPanel(resultPanel);
}

function timeoutError(sessionId = null) {
  return { code: "timeout", request_id: null, scenario_session_id: sessionId };
}

async function fetchJsonBeforeDeadline(url, options, deadline, sessionId = null) {
  const remaining = deadline - Date.now();
  if (remaining <= 0) {
    throw timeoutError(sessionId);
  }
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), remaining);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    let payload = null;
    try {
      payload = await response.json();
    } catch (error) {
      if (response.ok) {
        throw error;
      }
    }
    return { response, payload };
  } catch (error) {
    if (error && error.name === "AbortError") {
      throw timeoutError(sessionId);
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function responseError(response, payload) {
  const error = (payload && payload.error)
    || { code: "unknown", request_id: response.headers.get("X-Request-ID") };
  return { ...error, http_status: response.status };
}

function isTransientPollError(error) {
  return Boolean(
    (error && error.http_status >= 500 && error.http_status <= 599)
    || (error && error.name === "TypeError")
  );
}

function errorMessage(error) {
  const messages = {
    demo_access_denied: "Код доступа не подошёл. Проверьте его и попробуйте снова.",
    demo_busy: "Сейчас выполняется другая демонстрация. Подождите немного и повторите запуск.",
    demo_daily_limit_exhausted: "Дневной лимит демонстрационных запусков исчерпан.",
    demo_input_invalid: "Проверьте исходный текст: он должен содержать от 1 до 4000 символов.",
    demo_unavailable: "Демонстрация временно недоступна. Сообщите команде AnytoolAI.",
    scenario_failed: "Цепочка завершилась с ошибкой. Новый запуск можно сделать отдельно.",
    scenario_expired: "Время выполнения цепочки истекло.",
    timeout: "Ожидание заняло больше 90 секунд. Сервер продолжает выполнение."
  };
  const base = messages[error.code] || "Не удалось выполнить запрос. Попробуйте ещё раз.";
  const requestSuffix = error.request_id ? ` Код запроса: ${error.request_id}.` : "";
  const sessionSuffix = error.scenario_session_id
    ? ` Технический ID: ${error.scenario_session_id}.`
    : "";
  return `${base}${requestSuffix}${sessionSuffix}`;
}

async function pollSession(sessionId) {
  const deadline = runStartedAt + RUN_TIMEOUT_MS;
  let reconnecting = false;
  while (Date.now() < deadline) {
    const wait = Math.min(POLL_INTERVAL_MS, deadline - Date.now());
    await new Promise((resolve) => window.setTimeout(resolve, wait));
    try {
      const { response, payload: session } = await fetchJsonBeforeDeadline(`/v1/scenario-sessions/${sessionId}`, {
        headers: { Accept: "application/json" }
      }, deadline, sessionId);
      if (!response.ok) {
        throw responseError(response, session);
      }
      if (reconnecting) {
        showStatus("Связь восстановлена. Выполнение продолжается.", "info");
        reconnecting = false;
      }
      if (session.status === "completed" && session.result_artifact_id) {
        const { response: resultResponse, payload: result } = await fetchJsonBeforeDeadline(`/v1/results/${session.result_artifact_id}`, {
          headers: { Accept: "application/json" }
        }, deadline, sessionId);
        if (!resultResponse.ok) {
          throw responseError(resultResponse, result);
        }
        return { result, session };
      }
      if (session.status === "failed" || session.status === "expired") {
        throw { code: `scenario_${session.status}`, request_id: null };
      }
    } catch (error) {
      if (error && ["scenario_failed", "scenario_expired", "timeout"].includes(error.code)) {
        throw error;
      }
      if (!isTransientPollError(error)) {
        throw error;
      }
      reconnecting = true;
      showStatus("Связь с сервером прервалась. Пробуем подключиться снова…", "info");
    }
  }
  throw timeoutError(sessionId);
}

async function startRun() {
  if (running) {
    return;
  }
  const trimmedText = sourceText.value.trim();
  if (!trimmedText || Array.from(trimmedText).length > 4000) {
    showStatus(errorMessage({ code: "demo_input_invalid" }), "error");
    sourceText.focus();
    return;
  }

  const demoId = selectedDemoId();
  resultPanel.hidden = true;
  showStatus("");
  runningWorkflow.textContent = WORKFLOWS[demoId].title;
  setRunningState(true);
  startElapsedTimer();
  const deadline = runStartedAt + RUN_TIMEOUT_MS;

  try {
    const { response, payload: started } = await fetchJsonBeforeDeadline("/v1/demo/runs", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Demo-Access-Code": accessCode
      },
      body: JSON.stringify({ demo_id: demoId, source_text: trimmedText })
    }, deadline);
    if (!response.ok) {
      throw responseError(response, started);
    }
    const completed = await pollSession(started.scenario_session_id);
    setRunningState(false);
    showStatus("Результат получен от платформы.", "info");
    renderResult(completed.result, completed.session);
  } catch (error) {
    setRunningState(false);
    if (error && error.code === "demo_access_denied") {
      accessCode = "";
      accessPanel.hidden = false;
      workflowSection.hidden = true;
      accessCodeInput.focus();
    } else {
      workflowSection.hidden = false;
    }
    showStatus(errorMessage(error || { code: "unknown" }), "error");
  }
}

accessForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const enteredCode = accessCodeInput.value.trim();
  if (!enteredCode) {
    showStatus("Введите код доступа.", "error");
    accessCodeInput.focus();
    return;
  }
  accessCode = enteredCode;
  accessCodeInput.value = "";
  accessPanel.hidden = true;
  workflowSection.hidden = false;
  showStatus("Доступ открыт в этой вкладке. Выберите цепочку и запустите её.", "info");
  scrollToPanel(workflowSection);
});

document.querySelectorAll('input[name="demo-workflow"]').forEach((input) => {
  input.addEventListener("change", updateExample);
});
sourceText.addEventListener("input", updateCharacterCount);
runButton.addEventListener("click", startRun);
rerunButton.addEventListener("click", () => {
  resultPanel.hidden = true;
  workflowSection.hidden = false;
  showStatus("Можно изменить текст или выбрать другую цепочку.", "info");
  scrollToPanel(workflowSection);
});

updateExample();
