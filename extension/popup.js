const fields = {
  mode: document.querySelector("#mode"),
  translateTo: document.querySelector("#translateTo"),
  translationEngine: document.querySelector("#translationEngine"),
  captionOffset: document.querySelector("#captionOffset"),
  liveStream: document.querySelector("#liveStream"),
  apiUrl: document.querySelector("#apiUrl")
};
const button = document.querySelector("#prepare");
const stopLiveButton = document.querySelector("#stopLive");
const statusText = document.querySelector("#status");
const STORED = [
  "mode", "translateTo", "translationEngine", "captionOffset",
  "apiUrl", ...PopupTtsSettings.keys
];

chrome.storage.local.get(STORED, (settings) => {
  for (const [key, element] of Object.entries(fields)) {
    if (settings[key] === undefined) continue;
    if (element.type === "checkbox") element.checked = Boolean(settings[key]);
    else element.value = settings[key];
  }
  PopupTtsSettings.init(settings);
});

refreshStopButton();
chrome.storage.onChanged.addListener(refreshStopButton);

fields.captionOffset.addEventListener("change", () => {
  const offset = normalizeCaptionOffset(fields.captionOffset.value);
  fields.captionOffset.value = offset.toFixed(1);
  chrome.storage.local.set({ captionOffset: offset });
});

function normalizeCaptionOffset(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 0;
  return Math.round(Math.max(-3, Math.min(3, parsed)) * 10) / 10;
}

function currentSettings() {
  return {
    mode: fields.mode.value,
    translateTo: fields.translateTo.value,
    translationEngine: fields.translationEngine.value,
    captionOffset: normalizeCaptionOffset(fields.captionOffset.value),
    apiUrl: fields.apiUrl.value.trim(),
    ...PopupTtsSettings.readSettings()
  };
}

button.addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.url?.startsWith("https://webtv.un.org/")) {
    statusText.textContent = "Откройте видео на webtv.un.org";
    return;
  }
  const tts = PopupTtsSettings.readSettings();
  if (tts.tts && tts.ttsSource === "translation" && !fields.translateTo.value) {
    statusText.textContent = "Для озвучки перевода включите перевод";
    return;
  }
  const settings = currentSettings();
  await chrome.storage.local.set(settings);
  button.disabled = true;
  try {
    const health = await fetch(
      `${settings.apiUrl}/api/videos/live-transcription/health?mode=${settings.mode}`
    );
    const readiness = await health.json();
    if (!health.ok || !readiness.ready) {
      throw new Error(readiness.detail || "ASR API не готов");
    }
    const response = await chrome.runtime.sendMessage({
      type: "captions:prepare",
      tabId: tab.id,
      videoUrl: tab.url,
      mode: settings.mode,
      translateTo: settings.translateTo,
      translationEngine: settings.translationEngine,
      liveStream: fields.liveStream.checked,
      apiUrl: settings.apiUrl
    });
    if (!response?.ok) throw new Error(response?.error || "Не удалось начать подготовку");
    statusText.textContent = fields.liveStream.checked
      ? "Подключаюсь к эфиру. Остановить распознавание можно из этого окна."
      : "Подготовка запущена. Видео пока не запускайте.";
  } catch (error) {
    statusText.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

stopLiveButton.addEventListener("click", stopLiveCapture);

async function stopLiveCapture() {
  const { captionPreparationJob: job } = await chrome.storage.local.get("captionPreparationJob");
  if (!job?.liveStream) {
    statusText.textContent = "Активная онлайн-трансляция не найдена";
    refreshStopButton();
    return;
  }
  try {
    const response = await fetch(
      `${job.apiUrl}/api/videos/captions/jobs/${job.jobId}/stop`,
      { method: "POST" }
    );
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Не удалось остановить эфир");
    statusText.textContent = "Останавливаю эфир и сохраняю распознанные фразы…";
  } catch (error) {
    statusText.textContent = error.message;
  }
}

function refreshStopButton() {
  chrome.storage.local.get("captionPreparationJob", ({ captionPreparationJob: job }) => {
    stopLiveButton.hidden = !job?.liveStream;
  });
}
