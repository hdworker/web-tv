# Feasibility: capturing live UN Web TV audio over HLS

**Assessment (2026-11-16): technically feasible, subject to playback access and rights.**
The current numbered-TS downloader is not a suitable live-HLS client. Prefer an HLS-aware
ingest path that follows the live playlist and selects an audio rendition; use Chrome tab
capture only when the page's player is the only authorized/reliable source. Research only:
no implementation or live media capture was performed.

## What was observed on the requested page

The public page
[`https://webtv.un.org/en/asset/k13/k13tn4gno5`](https://webtv.un.org/en/asset/k13/k13tn4gno5)
was inspected on 2026-11-16. Its HTML identifies the item as “1st Meeting, 7th Review
Conference of High Contracting Parties (CCW),” marks its schedule state as `Live`, and embeds
Kaltura Player with partner ID `2503451`, UI conf `49754663`, and entry ID `1_3tn4gno5`.
The open player displayed audio language options Arabic, Chinese, English, French, Russian,
Spanish, and Original.

**Empirical observation from the open tab:** playback requested HLS from `cflive.kaltura.com`.
The observed master playlist declared separate audio renditions (English `s100` default,
Spanish `s101`, French `s102`, Chinese `s105`, Arabic `s106`, Russian `s108`, and Interlingua)
and video variants `s34`, `s42`, and `s43`. A fetched media playlist showed
`EXT-X-TARGETDURATION:6`, `EXT-X-MEDIA-SEQUENCE:216981993`, six-second TS segments with
names in the `seg-<sequence>-s100.ts` form (sample: `seg-216981994-s100.ts`), and no
`EXT-X-ENDLIST` in the inspected head. No media was downloaded; only manifests/playback
requests from the open tab were inspected. **All signed query values are intentionally omitted:
do not log, store, share, or reproduce signed URLs/tokens.** These observations are specific
to the inspected live entry/time and may change.

The source page and player observation establish that this inspected item uses Kaltura live
HLS and exposes separate language audio renditions at that time. They do not prove that a
server-side client may reuse the browser's signed playback URL, that it remains valid, or that
the same rendition set is available on other events. [Observed page](https://webtv.un.org/en/asset/k13/k13tn4gno5)

## Why the existing numbered-segment flow differs

`downloader.py:39-47` recognizes only `seg-<n>-a1.ts` or `seg-<n>-v1-a1.ts`; it rejects the
observed `-s100.ts`/`-s108.ts` suffixes for both `audio_only=True` and video mode. A reproducible
local call with either observed sample path returned `None`. Its network-log discovery at
`downloader.py:94-102` also filters `cfvod.kaltura.com`, while this live stream was observed on
`cflive.kaltura.com`. In addition, `downloader.py:122-223` guesses local numbered filenames
(`a1` or `v1-a1`) instead of following a playlist.

The current caption path is separately numbered, not playlist-driven:
`api/services/caption_segmenter.py:39-58` starts at segment 1 and advances by a fixed window;
`:87-90,131-140` constructs `seg-<number>-a1.ts`; and `:109-120` interprets HTTP 404 as EOF.
This cannot correctly start at the observed live sequence (216981993), select a language
suffix such as `s100`, or distinguish an expired/missing live segment from stream completion.
The rolling playlist makes 404 especially unsafe as an end-of-stream signal.

HLS instead uses a playlist as the authority. A live media playlist is periodically updated;
its segment URIs can be added while older URIs are removed. `EXT-X-MEDIA-SEQUENCE` tracks
sequence position, but sequence numbers need not appear in filenames. A live playlist lacks
`EXT-X-ENDLIST` until it is no longer live. A downloader that guesses segment filenames can
miss URI changes, sliding-window advancement, discontinuities, alternate audio, or a changed
playlist base URL. On the inspected stream, `MEDIA-SEQUENCE` and `EXTINF`-listed TS URIs
provide the starting point and current available segment set; a live client should follow those
playlist updates, not construct URIs from a counter. [Apple: live sliding-window playlist](https://developer.apple.com/documentation/http-live-streaming/live-playlist-sliding-window-construction);
[RFC 8216 §6.2.2, §6.3.4](https://www.rfc-editor.org/rfc/rfc8216.html)

An HLS-aware client (for example, FFmpeg's HLS demuxer) reloads playlists and follows their
listed media resources. FFmpeg documents live playlist reload options, including limits for
reloading a playlist that has not yet gained segments. It can select streams with `-map`,
including audio-only output, rather than saving video and stripping it later.
[FFmpeg formats: HLS demuxer](https://ffmpeg.org/ffmpeg-formats.html#hls-1)

## Ingest options

### Server-side HLS pull — preferred where permitted

Resolve the player-authorized playback source/manifest, then have a supervised FFmpeg process
read the HLS input continuously and map the intended audio stream. Select an audio-only
rendition from the master playlist when one exists; otherwise map audio from the selected
audio/video variant and discard video. For transcription, produce bounded audio chunks (for
example, PCM/WAV at the ASR service's required sample rate/channels) or a single stream of
audio that is segmented downstream. The project already has FFmpeg-based audio conversion and
chunking patterns in `api/services/caption_ffmpeg.py`; those are downstream processing, not
live HLS acquisition.

**Advantages:** headless/server-operated, does not depend on a user's browser staying open,
avoids video transfer if the audio rendition is fetched directly, and the inspected master
playlist's separate renditions offer a path to a chosen language without decoding video.
**Tradeoffs:** a live playlist is not a finite file; the process needs reconnect/reload,
bounded buffering, explicit stop/end detection, and monitoring. Latency is at least the
playlist/segment publication delay plus ingest and ASR buffering. A six-second target duration
was observed on this playlist, but it does not by itself establish end-to-end latency. The
master playlist did provide separate audio renditions in this inspection; availability and
labels can vary by event.

Kaltura documents `playManifest` as a way to retrieve playback streams, including HLS, and
notes that playback access depends on delivery profiles and security/access-control settings.
It does not establish that this UN entry can be accessed through a guessed manifest URL or
without a Kaltura session. Use only the playback URL and permissions actually provided by the
player/service; do not bypass restrictions.
[Kaltura: playManifest](https://developer.kaltura.com/api-docs/Deliver-and-Distribute-Media/playManifest-streaming-api.html)

### Browser tab capture — fallback

Chrome's `chrome.tabCapture` obtains the audio/video `MediaStream` of a tab after a user
invokes the extension. An extension can pass audio to `MediaRecorder` and persist chunks;
Chrome documents using an offscreen document for background capture from Chrome 116 onward.
Capturing a tab suppresses its local audio unless the extension routes the stream back to an
`AudioContext` output. This captures what the player actually renders, including client-side
audio-language choice, but requires a logged-in/active browser session, user gesture, and the
tab/player to keep playing. It is less suitable for unattended server work and can add
browser scheduling and recorder chunk-boundary latency. `MediaRecorder` output is browser-
selected (commonly WebM/Opus where supported); check `MediaRecorder.isTypeSupported()` and
transcode/normalize through FFmpeg before ASR rather than assuming a fixed container/codec.
[Chrome: tabCapture API](https://developer.chrome.com/docs/extensions/reference/api/tabCapture);
[Chrome: recording and screen capture](https://developer.chrome.com/docs/extensions/how-to/web-platform/screen-capture);
[MDN: MediaRecorder](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder)

## Access, reliability, and policy constraints

- **Auth and expiring URLs:** Kaltura says `playManifest` may require a Kaltura Session (KS)
  where access-control or entitlement rules apply. URLs may also carry short-lived signed
  query parameters. Treat these as secrets: **do not store or share signed query tokens**, put
  them in logs, commit them, or persist them as media identifiers. Prefer reacquiring playback
  authorization through the official player/API flow.
- **CORS:** browser JavaScript fetching a manifest or segments is subject to cross-origin
  policy unless the server returns suitable CORS headers. Native player playback may work
  without exposing those resources to page scripts. Server-side FFmpeg is not governed by
  browser CORS, but still needs valid network access, authorization headers/cookies if
  legitimately provided, and permitted referrer/domain conditions. Kaltura documents referrer
  domain restriction as one access-control mechanism.
- **Latency:** HLS segment publication and player buffering make this near-live rather than
  sample-by-sample audio. Smaller segments/low-latency HLS can reduce delay only when the
  publisher serves those modes and the client supports them; no such mode was verified on the
  inspected page. Recorder chunk size and ASR chunk size add further delay.
- **Codec handling:** do not assume `.ts`, AAC, or a particular audio language. Inspect the
  authorized master/media playlist and probe the actual selected streams. FFmpeg can remux
  supported stream codecs without re-encoding; ASR often benefits from explicit mono PCM
  normalization, at a compute cost.
- **Rights/access policy:** technical availability is not permission to record, retain, or
  redistribute a UN broadcast. Confirm the applicable UN/Web TV terms, event-specific rights,
  retention requirements, and any organizational policy before collecting or sharing audio
  or transcripts. This research did not establish the permitted use for this meeting.

## Recommendation

Prototype only after confirming access/retention authority. The inspected playlist makes an
audio-only server-side HLS prototype technically promising: consume the authorized master and
select the desired audio rendition through an HLS-aware client (rather than guessing segment
URLs). Do not copy signed URLs out of the tab or treat a captured URL as durable authorization.
Build resilience around playlist refresh, discontinuities, stream changes, and process restarts.
If the source cannot be consumed server-side under its access policy, use explicit user-started
Chrome tab capture and clearly indicate capture state; do not reverse-engineer or bypass
player-side controls.

## Sources

- Observed UN Web TV page: https://webtv.un.org/en/asset/k13/k13tn4gno5
- Apple live playlist sliding-window construction:
  https://developer.apple.com/documentation/http-live-streaming/live-playlist-sliding-window-construction
- IETF RFC 8216, HTTP Live Streaming: https://www.rfc-editor.org/rfc/rfc8216.html
- Kaltura `playManifest` streaming API:
  https://developer.kaltura.com/api-docs/Deliver-and-Distribute-Media/playManifest-streaming-api.html
- FFmpeg formats documentation, HLS demuxer:
  https://ffmpeg.org/ffmpeg-formats.html#hls-1
- Chrome `tabCapture` reference:
  https://developer.chrome.com/docs/extensions/reference/api/tabCapture
- Chrome recording and screen capture guide:
  https://developer.chrome.com/docs/extensions/how-to/web-platform/screen-capture
- MDN `MediaRecorder` reference: https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder
- Repository comparison: `downloader.py:122-223`; audio processing:
  `api/services/caption_ffmpeg.py`. Current stream parsing:
  `downloader.py:39-47,94-102`; caption numbered-segment logic:
  `api/services/caption_segmenter.py:39-58,81-120,131-140`.
