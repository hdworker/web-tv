self.CaptionTiming = (() => {
  const MAX_OFFSET = 3;

  function normalizeOffset(value) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return 0;
    const clamped = Math.max(-MAX_OFFSET, Math.min(MAX_OFFSET, parsed));
    return Math.round(clamped * 10) / 10;
  }

  function findCue(cues, videoTime, offset) {
    const adjustedTime = videoTime - normalizeOffset(offset);
    let low = 0;
    let high = cues.length - 1;
    let candidate = -1;
    while (low <= high) {
      const middle = (low + high) >> 1;
      if (cues[middle].start <= adjustedTime) {
        candidate = middle;
        low = middle + 1;
      } else {
        high = middle - 1;
      }
    }
    return candidate >= 0 && adjustedTime < cues[candidate].end ? candidate : -1;
  }

  return { findCue, normalizeOffset };
})();
