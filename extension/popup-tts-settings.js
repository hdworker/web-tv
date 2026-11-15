self.PopupTtsSettings = (() => {
  const keys = [
    "tts", "ttsSource", "ttsProvider", "ttsVoice", "browserVoice",
    "browserRate", "browserPitch", "browserVolume",
    "edgeRate", "edgePitch", "edgeVolume"
  ];
  const defaults = {
    tts: false,
    ttsSource: "translation",
    ttsProvider: "browser",
    ttsVoice: "", browserVoice: "",
    browserRate: 1, browserPitch: 1, browserVolume: 1,
    edgeRate: 0, edgePitch: 0, edgeVolume: 0
  };
  const fields = Object.fromEntries(keys.map((id) => [id, document.querySelector(`#${id}`)]));
  let settings = { ...defaults };

  function init(stored) {
    settings = { ...defaults, ...stored };
    for (const key of keys) {
      const field = fields[key];
      if (key === "tts") field.checked = Boolean(settings[key]);
      else if (key !== "ttsVoice" && key !== "browserVoice") field.value = String(settings[key]);
    }
    bindControls();
    updateReadouts();
    updateVisibleEngine();
    refreshVoices();
    if ("speechSynthesis" in self) {
      self.speechSynthesis.addEventListener("voiceschanged", refreshBrowserVoices);
    }
  }

  function bindControls() {
    for (const key of keys) {
      if (key === "ttsVoice" || key === "browserVoice") continue;
      fields[key].addEventListener("input", updateReadouts);
      fields[key].addEventListener("change", persist);
    }
    for (const key of ["ttsProvider", "ttsSource"]) {
      fields[key].addEventListener("change", () => {
        updateVisibleEngine();
        refreshVoices();
        persist();
      });
    }
    fields.ttsVoice.addEventListener("change", persist);
    fields.browserVoice.addEventListener("change", persist);
    document.querySelector("#apiUrl").addEventListener("change", refreshVoices);
  }

  function readSettings() {
    return {
      tts: fields.tts.checked,
      ttsSource: fields.ttsSource.value,
      ttsProvider: fields.ttsProvider.value,
      ttsVoice: fields.ttsVoice.value,
      browserVoice: fields.browserVoice.value,
      browserRate: Number(fields.browserRate.value),
      browserPitch: Number(fields.browserPitch.value),
      browserVolume: Number(fields.browserVolume.value),
      edgeRate: Number(fields.edgeRate.value),
      edgePitch: Number(fields.edgePitch.value),
      edgeVolume: Number(fields.edgeVolume.value)
    };
  }

  function persist() {
    settings = readSettings();
    chrome.storage.local.set(settings);
  }

  function updateVisibleEngine() {
    const browser = fields.ttsProvider.value === "browser";
    document.querySelector("#browserTtsSettings").hidden = !browser;
    document.querySelector("#edgeTtsSettings").hidden = browser;
  }

  function updateReadouts() {
    const values = {
      browserRateValue: `${Number(fields.browserRate.value).toFixed(1).replace(".", ",")}×`,
      browserPitchValue: Number(fields.browserPitch.value).toFixed(1).replace(".", ","),
      browserVolumeValue: `${Math.round(Number(fields.browserVolume.value) * 100)}%`,
      edgeRateValue: signed(fields.edgeRate.value, "%"),
      edgePitchValue: `${signed(fields.edgePitch.value, "")} Гц`,
      edgeVolumeValue: signed(fields.edgeVolume.value, "%")
    };
    for (const [id, value] of Object.entries(values)) {
      document.querySelector(`#${id}`).textContent = value;
    }
  }

  function signed(value, suffix) {
    const number = Number(value);
    return `${number > 0 ? "+" : ""}${number}${suffix}`;
  }

  function refreshVoices() {
    return fields.ttsProvider.value === "browser" ? refreshBrowserVoices() : refreshEdgeVoices();
  }

  function refreshBrowserVoices() {
    if (!("speechSynthesis" in self)) return;
    const language = fields.ttsSource.value === "translation" ? "ru" : "en";
    const voices = self.speechSynthesis.getVoices()
      .filter((voice) => voice.lang.toLowerCase().startsWith(language));
    fillOptions(fields.browserVoice, voices.map((voice) => ({
      value: voice.voiceURI,
      label: `${voice.name} · ${voice.lang}`,
      default: voice.default
    })), settings.browserVoice, "Автоматически по языку");
  }

  async function refreshEdgeVoices() {
    const base = document.querySelector("#apiUrl").value.trim().replace(/\/$/, "");
    const language = fields.ttsSource.value === "translation" ? "ru" : "en";
    try {
      const response = await fetch(`${base}/api/videos/captions/tts/voices?lang=${language}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "голоса недоступны");
      fillOptions(fields.ttsVoice, payload.voices.map((voice) => ({
        value: voice.name, label: `${voice.name} · ${voice.locale}`
      })), settings.ttsVoice, "Выберите голос Edge");
    } catch (_error) {
      fillOptions(fields.ttsVoice, [], "", "Голоса недоступны");
    }
  }

  function fillOptions(select, options, preferred, emptyLabel) {
    const previous = select.value;
    select.replaceChildren();
    const placeholder = new Option(emptyLabel, "");
    select.append(placeholder);
    for (const item of options) select.append(new Option(item.label, item.value));
    select.value = options.some((item) => item.value === preferred)
      ? preferred
      : options.find((item) => item.default)?.value || "";
    if (options.length && previous !== select.value) {
      const key = select.id;
      settings[key] = select.value;
      chrome.storage.local.set({ [key]: select.value });
    }
  }

  return { keys, init, readSettings };
})();
