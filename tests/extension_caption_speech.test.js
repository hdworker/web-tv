const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const test = require("node:test");

test("disabling voiceover cancels speech already playing", () => {
  let onStorageChanged;
  let cancelCount = 0;
  let spokenCount = 0;
  const speechSynthesis = {
    cancel() {
      cancelCount += 1;
    },
    getVoices() {
      return [];
    },
    speak() {
      spokenCount += 1;
    }
  };
  const context = {
    chrome: {
      storage: {
        local: {
          get(_keys, callback) {
            callback({ tts: true, ttsSource: "original", ttsProvider: "browser" });
          }
        },
        onChanged: {
          addListener(callback) {
            onStorageChanged = callback;
          }
        }
      }
    },
    SpeechSynthesisUtterance: class {
      constructor(text) {
        this.text = text;
      }
    },
    speechSynthesis
  };
  context.self = context;
  vm.runInNewContext(
    fs.readFileSync("extension/caption-speech.js", "utf8"),
    context,
    { filename: "extension/caption-speech.js" }
  );

  context.CaptionSpeech.speak({ start: 0, text: "Hello" }, null);
  assert.equal(spokenCount, 1);

  onStorageChanged({ tts: { newValue: false } });
  assert.equal(cancelCount, 2);
});

test("browser voice and speech controls are applied to the utterance", () => {
  let onStorageChanged;
  let spoken;
  const voices = [
    { voiceURI: "ru-voice", lang: "ru-RU", default: true },
    { voiceURI: "en-voice", lang: "en-US", default: true }
  ];
  const context = {
    chrome: {
      storage: {
        local: {
          get(_keys, callback) {
            callback({
              tts: true,
              ttsSource: "translation",
              ttsProvider: "browser",
              browserVoice: "ru-voice",
              browserRate: 1.3,
              browserPitch: 0.8,
              browserVolume: 0.6
            });
          }
        },
        onChanged: { addListener(callback) { onStorageChanged = callback; } }
      }
    },
    SpeechSynthesisUtterance: class {
      constructor(text) {
        this.text = text;
      }
    },
    speechSynthesis: {
      cancel() {},
      getVoices() { return voices; },
      speak(utterance) { spoken = utterance; }
    }
  };
  context.self = context;
  vm.runInNewContext(
    fs.readFileSync("extension/caption-speech.js", "utf8"),
    context
  );

  context.CaptionSpeech.speak(
    { start: 0, text: "Hello", translation: "Привет" },
    null
  );

  assert.equal(spoken.text, "Привет");
  assert.equal(spoken.lang, "ru-RU");
  assert.equal(spoken.voice.voiceURI, "ru-voice");
  assert.equal(spoken.rate, 1.3);
  assert.equal(spoken.pitch, 0.8);
  assert.equal(spoken.volume, 0.6);
  assert.equal(typeof onStorageChanged, "function");
});
