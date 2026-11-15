(() => {
if (globalThis.__unCaptionsLoaded) return;
globalThis.__unCaptionsLoaded = true;

const panel = self.CaptionPanel || createPanelFallback();
let cues = [];
let lastCueIndex = -2;
let processing = false;
let statusMessage = "Подготовка субтитров";
let displayTranslation = false;
let captionOffset = 0;

chrome.storage.local.get(["translateTo", "captionOffset"], (settings) => {
  displayTranslation = Boolean(settings.translateTo);
  captionOffset = self.CaptionTiming.normalizeOffset(settings.captionOffset);
});
chrome.storage.onChanged.addListener((changes) => {
  if (changes.translateTo) displayTranslation = Boolean(changes.translateTo.newValue);
  if (changes.captionOffset) {
    captionOffset = self.CaptionTiming.normalizeOffset(changes.captionOffset.newValue);
    lastCueIndex = -2;
    renderCurrentCue();
  }
});

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "captions:status") {
    processing = true;
    const progress = Number.isFinite(message.progress) ? ` (${message.progress}%)` : "";
    statusMessage = `${message.message}${progress}`;
    panel.show(statusMessage, "status");
  }
  if (message?.type === "captions:partial") {
    processing = true;
    cues = Array.isArray(message.cues) ? message.cues : cues;
    statusMessage = `${message.message}. Можно запускать видео; обработка продолжается.`;
    lastCueIndex = -2;
    panel.show(statusMessage, "status");
    bindVideos();
    renderCurrentCue();
  }
  if (message?.type === "captions:failed") {
    processing = false;
    panel.show(`Не удалось подготовить субтитры: ${message.message}`, "error");
  }
  if (message?.type === "captions:prepared") {
    processing = false;
    cues = Array.isArray(message.cues) ? message.cues : [];
    lastCueIndex = -2;
    const cacheLabel = message.cached ? " (из кеша)" : "";
    panel.show(`Готово: ${cues.length} фраз${cacheLabel}. Запустите видео.`, "status");
    bindVideos();
  }
});

function bindVideos() {
  for (const video of document.querySelectorAll("video")) {
    if (video.dataset.unCaptionsBound) continue;
    video.dataset.unCaptionsBound = "true";
    video.addEventListener("timeupdate", () => renderCue(video.currentTime));
    video.addEventListener("seeking", () => {
      self.CaptionSpeech?.stop();
      renderCue(video.currentTime);
    });
    video.addEventListener("pause", () => self.CaptionSpeech?.stop());
    video.addEventListener("play", () => {
      lastCueIndex = -2;
      renderCue(video.currentTime);
    });
    video.addEventListener("loadedmetadata", () => renderCue(video.currentTime));
  }
}

function renderCurrentCue() {
  const video = document.querySelector("video");
  if (video) renderCue(video.currentTime);
}

function renderCue(currentTime) {
  const index = findCue(currentTime);
  if (index === lastCueIndex) return;
  lastCueIndex = index;
  if (index < 0) {
    const latestEnd = cues.length ? cues[cues.length - 1].end : 0;
    if (processing) {
      const waiting = cues.length && currentTime >= latestEnd
        ? `Субтитры готовы до ${Math.floor(latestEnd)} с; готовлю следующие блоки.`
        : statusMessage;
      panel.show(waiting, "status");
      return;
    }
    panel.hide();
    return;
  }
  panel.show(cueText(cues[index]), "caption");
  self.CaptionSpeech?.speak(cues[index], document.querySelector("video"));
}

function cueText(cue) {
  // Показываем перевод, только когда он включён и уже готов.
  return displayTranslation && cue.translation ? cue.translation : cue.text;
}

function createPanelFallback() {
  // Панель создаётся здесь, если отдельный caption-panel.js не загрузился.
  function element() {
    let node = document.getElementById("un-live-captions");
    if (node) return node;
    node = document.createElement("div");
    node.id = "un-live-captions";
    node.setAttribute("role", "status");
    node.style.cssText = [
      "position:fixed", "z-index:2147483647", "left:50%", "bottom:8%",
      "transform:translateX(-50%)", "max-width:min(80vw,900px)",
      "padding:12px 18px", "border-radius:8px", "background:rgba(0,0,0,.82)",
      "color:white", "font:600 20px/1.4 system-ui,sans-serif",
      "text-align:center", "pointer-events:none", "white-space:pre-wrap"
    ].join(";");
    document.documentElement.append(node);
    return node;
  }

  return {
    show(text, state) {
      const node = element();
      node.textContent = text;
      node.dataset.state = state;
      node.style.display = "block";
      node.style.border = state === "error"
        ? "1px solid #f87171"
        : "1px solid transparent";
    },
    hide() {
      element().style.display = "none";
    }
  };
}

function findCue(time) {
  return self.CaptionTiming.findCue(cues, time, captionOffset);
}

new MutationObserver(bindVideos).observe(document.documentElement, {
  childList: true,
  subtree: true
});
bindVideos();
})();
