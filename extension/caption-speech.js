self.CaptionSpeech = (() => {
  const DUCK_VOLUME = 0.2;
  let settings = { tts: false, ttsSource: "translation", ttsProvider: "browser", ttsVoice: "", apiUrl: "" };
  let audio = null;
  let ducked = null;
  let lastKey = "";
  const audioCache = new Map();

  function configure(next) {
    settings = { ...settings, ...next };
  }

  function stop() {
    if ("speechSynthesis" in self) self.speechSynthesis.cancel();
    if (audio) {
      audio.pause();
      audio = null;
    }
    restoreVolume();
  }

  function speak(cue, video) {
    if (!settings.tts) return;
    const translated = Boolean(cue.translation);
    const text = settings.ttsSource === "translation" ? cue.translation || cue.text : cue.text;
    if (!text) return;
    const key = `${cue.start}|${text}`;
    if (key === lastKey) return;
    lastKey = key;
    stop();
    if (settings.ttsProvider === "edge") {
      speakEdge(text, translated, video).catch(() => speakBrowser(text, translated, video));
    } else {
      speakBrowser(text, translated, video);
    }
  }

  function speakBrowser(text, translated, video) {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = translated ? "ru-RU" : "en-US";
    utterance.onstart = () => duck(video);
    utterance.onend = restoreVolume;
    utterance.onerror = restoreVolume;
    self.speechSynthesis.speak(utterance);
  }

  async function speakEdge(text, translated, video) {
    const voice = selectVoice(translated);
    if (!voice) return;
    const url = `${settings.apiUrl}/api/videos/captions/tts/audio?text=${encodeURIComponent(text)}&voice=${voice}`;
    let blobUrl = audioCache.get(url);
    if (!blobUrl) {
      const response = await fetch(url);
      if (!response.ok) throw new Error("Edge TTS недоступен");
      blobUrl = URL.createObjectURL(await response.blob());
      audioCache.set(url, blobUrl);
    }
    audio = new Audio(blobUrl);
    audio.onplaying = () => duck(video);
    audio.onended = restoreVolume;
    audio.onpause = restoreVolume;
    await audio.play();
  }

  function selectVoice(translated) {
    const preferred = settings.ttsVoice || "";
    if (preferred && preferred.startsWith(translated ? "ru" : "en")) return preferred;
    return translated ? "ru-RU-DmitryNeural" : "en-US-AriaNeural";
  }

  function duck(video) {
    if (!video) return;
    ducked = { element: video, volume: video.volume };
    video.volume = DUCK_VOLUME;
  }

  function restoreVolume() {
    if (!ducked) return;
    ducked.element.volume = ducked.volume;
    ducked = null;
  }

  chrome.storage.local.get(
    ["tts", "ttsSource", "ttsProvider", "ttsVoice", "apiUrl"],
    (stored) => configure(stored)
  );
  chrome.storage.onChanged.addListener((changes) => {
    const patch = {};
    for (const [key, value] of Object.entries(changes)) patch[key] = value.newValue;
    configure(patch);
  });

  return { configure, speak, stop };
})();
