importScripts("caption-socket.js");

const JOB_STORAGE_KEY = "captionPreparationJob";
const RECONNECT_ALARM = "caption-websocket-reconnect";
const INJECTED = [
  "caption-panel.js",
  "caption-timing.js",
  "caption-speech.js",
  "captions.js"
];

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "captions:prepare") return;
  startPreparation(message)
    .then(() => sendResponse({ ok: true }))
    .catch((error) => sendResponse({ ok: false, error: error.message }));
  return true;
});

chrome.runtime.onStartup.addListener(restoreConnection);
chrome.runtime.onInstalled.addListener(restoreConnection);
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === RECONNECT_ALARM) reconnectStoredJob();
});

async function injectScripts(tabId) {
  await chrome.scripting.executeScript({ target: { tabId }, files: INJECTED });
}

async function startPreparation(message) {
  await injectScripts(message.tabId);
  const stored = await chrome.storage.local.get(JOB_STORAGE_KEY);
  const existing = stored[JOB_STORAGE_KEY];
  if (existing) {
    if (existing.videoUrl !== message.videoUrl) {
      throw new Error("Другая запись уже готовится в расширении");
    }
    await chrome.alarms.create(RECONNECT_ALARM, { periodInMinutes: 0.5 });
    CaptionSocket.connectToJob(existing);
    return;
  }

  const apiUrl = message.apiUrl.replace(/\/$/, "");
  const response = await fetch(`${apiUrl}/api/videos/captions/prepare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      video_url: message.videoUrl,
      mode: message.mode,
      translate_to: message.translateTo || "",
      translation_engine: message.translationEngine || "opus"
    })
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || "Не удалось начать подготовку");
  if (result.status === "complete") {
    CaptionSocket.notifyTab(message.tabId, "captions:prepared", {
      cues: result.cues,
      cached: true,
      assetKey: result.asset_key
    });
    return;
  }

  const job = {
    jobId: result.job_id,
    tabId: message.tabId,
    apiUrl,
    videoUrl: message.videoUrl,
    mode: message.mode
  };
  await chrome.storage.local.set({ [JOB_STORAGE_KEY]: job });
  await chrome.alarms.create(RECONNECT_ALARM, { periodInMinutes: 0.5 });
  CaptionSocket.connectToJob(job);
}

async function restoreConnection() {
  const stored = await chrome.storage.local.get(JOB_STORAGE_KEY);
  const job = stored[JOB_STORAGE_KEY];
  if (!job) return;
  await chrome.alarms.create(RECONNECT_ALARM, { periodInMinutes: 0.5 });
  try {
    await injectScripts(job.tabId);
  } catch (_error) {
    // Если вкладка закрыта, кеш будет доступен при новом запуске.
  }
  CaptionSocket.connectToJob(job);
}

async function reconnectStoredJob() {
  const stored = await chrome.storage.local.get(JOB_STORAGE_KEY);
  if (stored[JOB_STORAGE_KEY]) CaptionSocket.connectToJob(stored[JOB_STORAGE_KEY]);
}
