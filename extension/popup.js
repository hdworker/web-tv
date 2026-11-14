const fields = {
  mode: document.querySelector("#mode"),
  translateTo: document.querySelector("#translateTo"),
  translationEngine: document.querySelector("#translationEngine"),
  tts: document.querySelector("#tts"),
  ttsSource: document.querySelector("#ttsSource"),
  ttsProvider: document.querySelector("#ttsProvider"),
  ttsVoice: document.querySelector("#ttsVoice"),
  apiUrl: document.querySelector("#apiUrl")
};
const button = document.querySelector("#prepare");
const statusText = document.querySelector("#status");
const STORED = ["mode", "translateTo", "translationEngine", "tts", "ttsSource", "ttsProvider", "ttsVoice", "apiUrl"];

chrome.storage.local.get(STORED, (settings) => {
  for (const [key, element] of Object.entries(fields)) {
    if (settings[key] === undefined) continue;
    if (element.type === "checkbox") element.checked = Boolean(settings[key]);
    else element.value = settings[key];
  }
  refreshVoices();
});

for (const element of [fields.ttsProvider, fields.ttsSource, fields.apiUrl]) {
  element.addEventListener("change", refreshVoices);
}

async function refreshVoices() {
  if (fields.ttsProvider.value !== "edge") return;
  // Edge TTS отдаёт звук только когда язык голоса совпадает с языком текста.
  const lang = fields.ttsSource.value === "translation" ? "ru" : "en";
  const base = fields.apiUrl.value.trim().replace(/\/$/, "");
  const selected = fields.ttsVoice.value;
  fields.ttsVoice.innerHTML = '<option value="">Загружаю голоса…</option>';
  try {
    const response = await fetch(`${base}/api/videos/captions/tts/voices?lang=${lang}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "голоса не найдены");
    const voices = payload.voices || [];
    if (!voices.length) throw new Error("голоса не найдены");
    fields.ttsVoice.innerHTML = voices
      .map((voice) => `<option value="${voice.name}">${voice.name} · ${voice.locale}</option>`)
      .join("");
    const keep = voices.some((voice) => voice.name === selected);
    fields.ttsVoice.value = keep ? selected : voices[0].name;
  } catch (error) {
    fields.ttsVoice.innerHTML = '<option value="">Голоса недоступны</option>';
    statusText.textContent = `Edge TTS: ${error.message}`;
  }
}

function currentSettings() {
  return {
    mode: fields.mode.value,
    translateTo: fields.translateTo.value,
    translationEngine: fields.translationEngine.value,
    tts: fields.tts.checked,
    ttsSource: fields.ttsSource.value,
    ttsProvider: fields.ttsProvider.value,
    ttsVoice: fields.ttsVoice.value,
    apiUrl: fields.apiUrl.value.trim()
  };
}

button.addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.url?.startsWith("https://webtv.un.org/")) {
    statusText.textContent = "Откройте видео на webtv.un.org";
    return;
  }
  if (fields.tts.checked && fields.ttsSource.value === "translation" && !fields.translateTo.value) {
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
      apiUrl: settings.apiUrl
    });
    if (!response?.ok) throw new Error(response?.error || "Не удалось начать подготовку");
    statusText.textContent = "Подготовка запущена. Видео пока не запускайте.";
  } catch (error) {
    statusText.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
