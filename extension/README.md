# UN Web TV Live Captions

Chrome Manifest V3 extension that asks the local `web-tv` API to prepare
timecoded English captions for a UN Web TV recording, then displays each cue
against the video player's current time.

## Install

1. Start the API with `start_api.cmd` from the repository root, or run:

   ```powershell
   uvicorn main:app --host 127.0.0.1 --port 8000
   ```

2. Open `chrome://extensions`, enable **Developer mode**, and choose
   **Load unpacked** with this `extension` directory.
3. Open a video on `https://webtv.un.org/`, open the extension, choose a
   recognition mode, and click **Подготовить субтитры**.
4. Start playback once the extension reports the first recognized block.
   Captions follow the player's timeline, including pause and seek.

The backend downloads the audio-only HLS rendition, writes a lossless FLAC
archive under `video/captions/`, and saves timecoded cues in SQLite. Temporary
TS segments and WAV files are removed after preparation. FLAC archives and cue
caches have no automatic expiration. Repeating the same URL with the same ASR
mode/model reuses both; changing the ASR mode/model reuses the audio archive and
only repeats transcription.

FLAC preserves the decoded HLS audio without another lossy encode; it cannot
restore information already lost in the source stream.

Preparation no longer has to finish before playback. The first ASR block covers
about 30 seconds of audio; as soon as it is recognized, the extension receives
those cues over WebSocket and can caption the video while later blocks are still
downloading and transcribing. Remaining blocks are roughly two minutes each.

## Local WhisperX

Install WhisperX separately and set the optional model name:

```powershell
$env:LIVE_WHISPER_MODEL = "small"
pip install whisperx
```

The local WhisperX model defaults to `small`; set `LIVE_WHISPER_MODEL` to
select another installed model. CPU inference time depends on the machine and
recording length.

## Cloud ASR

Configure an OpenAI-compatible audio transcription endpoint in the API process:

```powershell
$env:OPENAI_API_KEY = "<your key>"
$env:OPENAI_URL = "https://api.openai.com/v1"
$env:LIVE_ASR_MODEL = "whisper-1"
```

Then select **Облачный сервис** in the extension. The backend splits the
recording into two-minute WAV parts and sends them to the configured API. The
extension does not store provider credentials. The provider must support
`POST /audio/transcriptions` with `verbose_json` timestamps.

## Translation

Select a target language in the extension. Cues then carry an extra
`translation` field next to `text`, and the overlay shows the translation.

| Engine | Model | License | Notes |
|---|---|---|---|
| `opus` (default) | `Helsinki-NLP/opus-mt-en-ru` | Apache-2.0 | ~293 MB, better on news text |
| `argos` | `translate-en_ru` 1.9 | MIT / CC0 | ~187 MB, installs on first use |

Both run locally on CPU and translate sentence by sentence. The cache key
includes the target language and engine, so switching engines re-translates
instead of serving a stale result.

## Voiceover

Enable **Озвучка** and choose what to speak: the translation or the original.
Two providers are available:

- **Браузер** — `speechSynthesis` inside the page, no network, robotic voice.
- **Edge TTS** — neural voices via the backend (`edge-tts>=7.3`), cached as mp3
  in `video/tts/`. Requires internet access to Microsoft.

The video volume is ducked to 20% while a cue is spoken and restored afterwards.
Edge TTS occasionally returns an empty stream for a specific voice and phrase;
the backend then retries with another voice of the same locale, and the
extension falls back to browser speech if the request fails. The voice must
match the language of the spoken text.

## API

- `GET /api/videos/live-transcription/health?mode=local|cloud`
- `POST /api/videos/captions/prepare`
- `GET /api/videos/captions/jobs/{job_id}`
- `WS /api/videos/captions/jobs/{job_id}/ws`
- `GET /api/videos/captions/media/{asset_key}`
- `GET /api/videos/captions/tts/voices?lang=ru|en`
- `GET /api/videos/captions/tts/audio?text=&voice=`

The preparation API returns cue objects with `start`, `end`, and `text` fields.
Active job progress is held in memory. If the API restarts, the extension
restarts the job and reuses the saved FLAC when available. Completed cues and
FLAC metadata persist in SQLite; the file is at
`video/captions/<asset_key>.flac`.
