self.CaptionSpeech = (() => {
  const DUCK_VOLUME = 0.2;
  let settings = {
    tts: false,
    ttsSource: "translation",
    ttsProvider: "browser",
    ttsVoice: "",
    browserVoice: "",
    browserRate: 1,
    browserPitch: 1,
    browserVolume: 1,
    edgeRate: 0,
    edgePitch: 0,
    edgeVolume: 0,
    apiUrl: ""
  };
  let audio = null;
  let ducked = null;
  let lastKey = "";
  let playbackVersion = 0;
  const audioCache = new Map();

  function configure(next) {
    const wasEnabled = settings.tts;
    settings = { ...settings, ...next };
    if (wasEnabled && !settings.tts) stop();
  }

  function stop() {
    playbackVersion += 1;
    if ("speechSynthesis" in self) self.speechSynthesis.cancel();
    if (audio) {
      audio.pause();
      audio = null;
    }
    restoreVolume();
  }

  function speak(cue, video) {
    if (!settings.tts) return;
    const translated = settings.ttsSource === "translation" && Boolean(cue.translation);
    const text = translated ? cue.translation : cue.text;
    if (!text) return;
    const key = `${cue.start}|${text}`;
    if (key === lastKey) return;
    lastKey = key;
    stop();
    if (settings.ttsProvider === "edge") {
      const version = playbackVersion;
      speakEdge(text, translated, video, version).catch(() => {
        if (settings.tts && version === playbackVersion) {
          speakBrowser(text, translated, video);
        }
      });
    } else {
      speakBrowser(text, translated, video);
    }
  }

  function speakBrowser(text, translated, video) {
    const utterance = new SpeechSynthesisUtterance(text);
    const language = translated ? "ru-RU" : "en-US";
    utterance.lang = language;
    utterance.voice = findBrowserVoice(language);
    utterance.rate = clamp(settings.browserRate, 0.5, 2, 1);
    utterance.pitch = clamp(settings.browserPitch, 0, 2, 1);
    utterance.volume = clamp(settings.browserVolume, 0, 1, 1);
    utterance.onstart = () => duck(video);
    utterance.onend = restoreVolume;
    utterance.onerror = restoreVolume;
    self.speechSynthesis.speak(utterance);
  }

  async function speakEdge(text, translated, video, version) {
    const voice = selectVoice(translated);
    if (!voice) return;
    const url = new URL("/api/videos/captions/tts/audio", settings.apiUrl);
    url.searchParams.set("text", text);
    url.searchParams.set("voice", voice);
    url.searchParams.set("rate", String(clamp(settings.edgeRate, -50, 50, 0)));
    url.searchParams.set("pitch", String(clamp(settings.edgePitch, -50, 50, 0)));
    url.searchParams.set("volume", String(clamp(settings.edgeVolume, -50, 50, 0)));
    const audioUrl = url.toString();
    let blobUrl = audioCache.get(audioUrl);
    if (!blobUrl) {
      const response = await fetch(audioUrl);
      if (!response.ok) throw new Error("Edge TTS недоступен");
      blobUrl = URL.createObjectURL(await response.blob());
      audioCache.set(audioUrl, blobUrl);
    }
    if (!settings.tts || version !== playbackVersion) return;
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

  function findBrowserVoice(language) {
    if (!("speechSynthesis" in self)) return null;
    const voices = self.speechSynthesis.getVoices();
    return voices.find(
      (voice) => voice.voiceURI === settings.browserVoice
        && voice.lang.toLowerCase().startsWith(language.slice(0, 2).toLowerCase())
    ) || voices.find(
      (voice) => voice.default
        && voice.lang.toLowerCase().startsWith(language.slice(0, 2).toLowerCase())
    ) || null;
  }

  function clamp(value, minimum, maximum, fallback) {
    const number = Number(value);
    return Number.isFinite(number) ? Math.min(maximum, Math.max(minimum, number)) : fallback;
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
    [
      "tts", "ttsSource", "ttsProvider", "ttsVoice", "browserVoice",
      "browserRate", "browserPitch", "browserVolume",
      "edgeRate", "edgePitch", "edgeVolume", "apiUrl"
    ],
    (stored) => configure(stored)
  );
  chrome.storage.onChanged.addListener((changes) => {
    const patch = {};
    for (const [key, value] of Object.entries(changes)) patch[key] = value.newValue;
    configure(patch);
  });

  return { configure, speak, stop };
})();
