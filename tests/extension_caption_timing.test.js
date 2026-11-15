const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const test = require("node:test");

function loadTiming() {
  const context = { self: {} };
  vm.runInNewContext(
    fs.readFileSync("extension/caption-timing.js", "utf8"),
    context,
    { filename: "extension/caption-timing.js" }
  );
  return context.self.CaptionTiming;
}

function runCaptionsWithOffset(offset) {
  let onRuntimeMessage;
  let onTimeUpdate;
  const shown = [];
  let hidden = false;
  const video = {
    currentTime: 0,
    dataset: {},
    addEventListener(event, callback) {
      if (event === "timeupdate") onTimeUpdate = callback;
    }
  };
  const context = {
    chrome: {
      storage: {
        local: { get(_keys, callback) { callback({ captionOffset: offset }); } },
        onChanged: { addListener() {} }
      },
      runtime: { onMessage: { addListener(callback) { onRuntimeMessage = callback; } } }
    },
    CaptionPanel: {
      show(text) {
        shown.push(text);
        hidden = false;
      },
      hide() {
        hidden = true;
      }
    },
    CaptionSpeech: { speak() {}, stop() {} },
    document: {
      documentElement: {},
      querySelectorAll() { return [video]; },
      querySelector() { return video; }
    },
    MutationObserver: class {
      observe() {}
    }
  };
  context.self = context;
  vm.runInNewContext(
    fs.readFileSync("extension/caption-timing.js", "utf8"),
    context
  );
  vm.runInNewContext(
    fs.readFileSync("extension/captions.js", "utf8"),
    context
  );
  onRuntimeMessage({
    type: "captions:prepared",
    cues: [{ start: 10, end: 12, text: "caption" }]
  });
  return {
    setTime(time) {
      video.currentTime = time;
      onTimeUpdate();
      return { shown: shown.at(-1), hidden };
    }
  };
}

test("offset moves cue appearance and disappearance by the same amount", () => {
  const timing = loadTiming();
  const cues = [
    { start: 10, end: 12, text: "one" },
    { start: 12, end: 14, text: "two" }
  ];

  assert.equal(timing.findCue(cues, 9.5, -0.5), 0);
  assert.equal(timing.findCue(cues, 10, 0), 0);
  assert.equal(timing.findCue(cues, 10.4, 0.5), -1);
  assert.equal(timing.findCue(cues, 10.5, 0.5), 0);
  assert.equal(timing.findCue(cues, 12.5, 0.5), 1);
  assert.equal(timing.findCue(cues, 14.5, 0.5), -1);
});

test("offset is clamped to three seconds and rounded to tenths", () => {
  const timing = loadTiming();

  assert.equal(timing.normalizeOffset(-3.27), -3);
  assert.equal(timing.normalizeOffset(2.26), 2.3);
  assert.equal(timing.normalizeOffset(9), 3);
  assert.equal(timing.normalizeOffset("invalid"), 0);
});

test("caption text follows the configured timing offset", () => {
  const later = runCaptionsWithOffset(0.5);
  assert.equal(later.setTime(10.4).hidden, true);
  assert.equal(later.setTime(10.5).shown, "caption");

  const earlier = runCaptionsWithOffset(-0.5);
  assert.equal(earlier.setTime(9.5).shown, "caption");
});
