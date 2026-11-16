# Feasibility: YouTube timestamped transcripts via yt-dlp

**Assessment (2026-11-15): feasible, with availability and policy caveats.** yt-dlp can
discover and download YouTube-provided manual or automatic subtitle tracks without downloading
the video. Its WebVTT output carries timed cues that can be persisted against the existing
video record. This is a research note only; no implementation changes are included.

## Availability and timestamp quality

- yt-dlp separates uploaded/manual subtitles (`--write-subs`) from automatic captions
  (`--write-auto-subs`); `--list-subs` reports both groups. `--sub-langs` selects language
  codes and supports patterns; `--sub-format` selects a format, with VTT among the supported
  formats. The extractor metadata also exposes subtitle and automatic-caption track maps.
  [yt-dlp README: subtitle options](https://github.com/yt-dlp/yt-dlp#subtitle-options),
  [embedding yt-dlp](https://github.com/yt-dlp/yt-dlp#embedding-yt-dlp)
- Availability is per-video and track: do not assume that a video has manual captions, any
  captions, or a desired language. Automatic speech recognition and machine-translated tracks
  are distinct from human-provided captions; retain track language and provenance rather than
  presenting all tracks as equivalent. The YouTube Data API's caption download supports an
  optional machine-translated language (`tlang`), but that API requires edit permission on the
  video, so it is not a general public-video alternative.
  [YouTube captions.download](https://developers.google.com/youtube/v3/docs/captions/download)
- WebVTT stores cue start/end times and text, so it preserves timestamped segments; parse cues
  rather than flattening to a single string. Timing/transcription accuracy is not guaranteed
  by the extraction mechanism.
- **Requested public-page check:** on 2026-11-15, installed yt-dlp `2026.03.17` ran
  `yt-dlp --list-subs --no-warnings https://www.youtube.com/watch?v=pxFIjEOfTj4` successfully.
  Its regular “Available subtitles” section contained `live_chat` (not a spoken-caption
  transcript); its separate “Available automatic captions” section included `ru-orig`
  (Russian Original) and `ru` (Russian), among many other language codes. Listed formats
  included VTT, SRT, TTML, SRV3/SRV2/SRV1 and JSON3. Separately, browser player metadata for
  this same video exposed one Russian auto-generated track (`kind=asr`). These are one-time
  public observations, not a general guarantee of track availability or successful download.
  No media was downloaded. yt-dlp without `--no-warnings` had warned that no supported
  JavaScript runtime was available and some formats/features may be missing; install/configure
  a supported runtime and `yt-dlp-ejs` for full YouTube support per its
  [EJS guidance](https://github.com/yt-dlp/yt-dlp/wiki/EJS).

## Extraction examples

Discovery only (does not fetch a video):

```sh
yt-dlp --list-subs "https://www.youtube.com/watch?v=VIDEO_ID"
```

Fetch available English manual and automatic captions (when present) as VTT sidecar files:

```sh
yt-dlp --skip-download --write-subs --write-auto-subs \
  --sub-langs "en,en.*" --sub-format vtt \
  -o "%(id)s.%(ext)s" "https://www.youtube.com/watch?v=VIDEO_ID"
```

For Python integration, `YoutubeDL.extract_info(url, download=False)` returns metadata
including `subtitles` and `automatic_captions`; `YoutubeDL.download([url])` with equivalent
options writes selected sidecar files. Alternatively, inspect track URLs/metadata and use
yt-dlp's subtitle download flow. Track-map schema and extractor behavior can change, so pin
and update yt-dlp deliberately. The official README documents embedding and options:
https://github.com/yt-dlp/yt-dlp#embedding-yt-dlp .

## Persistence implications in this repository

- `database.py:11-30, 68-88` defines `Video` and the `videos` table, keyed by integer `id`;
  `un_video_url` is currently unique, so YouTube records can be represented there if the
  existing URL assumptions permit it.
- `database.py:43-51, 102-111` defines `Transcription` and `transcriptions`, already linked by
  `video_id` and carrying `language`, `transcript_text`, and `summary_text`. The CRUD methods at
  `database.py:273-315` insert and retrieve multiple transcripts per video.
- This is enough to store a flattened transcript associated with a video, but not enough to
  preserve cue boundaries/times, source-track identity, or whether a track was manual versus
  auto-generated. A durable timestamped implementation should store structured cue data
  (for example JSON containing start/end/text) and track provenance/language, either by
  extending the transcription model/table with migration or by a related cue/track table.
  Preserve source video ID/URL for deduplication and make no-caption / inaccessible states
  explicit rather than treating them as empty successful transcripts.
- Existing extraction in `transcript_extractor.py:60-88, 91-108` parses UN WebTV's
  `transcript__root` HTML into `[timestamp] text` lines. A YouTube VTT parser should be a
  separate source adapter, reusing shared persistence only after normalizing cue data.
- The caption subsystem uses JSON cue storage already: `api/services/caption_schema.py:24-34`
  has `caption_caches.cues_json` linked to `caption_media.asset_key`. It is specifically an
  audio-caption cache, not currently a durable YouTube transcript-to-`videos.id` relationship.

## Limits, risks, and operational constraints

- Private, age-restricted, members-only, geo-restricted, or otherwise gated material may
  require credentials or remain inaccessible. yt-dlp's official YouTube extractor guidance
  documents cookie requirements for account-gated content, warns of temporary/permanent
  account bans, explains request-rate limits, and notes PO-token-dependent feature gaps:
  [YouTube extractor guidance](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#youtube).
  Prefer public/no-cookie retrieval; never try to bypass access controls.
- YouTube's Terms restrict automated access/scraping and downloading/reproducing content except
  where expressly permitted, with permission, or allowed by law. Captions are content; obtain
  rights/legal review for the intended use and retention before deployment.
  [YouTube Terms, “Permissions and Restrictions”](https://www.youtube.com/t/terms).
- Operationally, YouTube changes can break extraction; yt-dlp notes stable releases can lag
  external site changes and recommends maintaining an up-to-date release. YouTube extraction
  currently recommends yt-dlp-ejs plus a supported JavaScript runtime. Add bounded retries,
  rate limiting, observability, and graceful “unavailable/no captions” results; avoid high
  request rates and do not depend on authenticated cookies as a default.

## Sources

- yt-dlp official README: https://github.com/yt-dlp/yt-dlp#subtitle-options
- yt-dlp official embedding docs: https://github.com/yt-dlp/yt-dlp#embedding-yt-dlp
- yt-dlp official YouTube extractor notes: https://github.com/yt-dlp/yt-dlp/wiki/Extractors#youtube
- yt-dlp JavaScript runtime guidance: https://github.com/yt-dlp/yt-dlp/wiki/EJS
- YouTube Data API `captions.download`: https://developers.google.com/youtube/v3/docs/captions/download
- YouTube Terms of Service: https://www.youtube.com/t/terms
- Repository facts: `database.py:11-30,43-51,68-111,273-315`;
  `transcript_extractor.py:60-108`; `api/services/caption_schema.py:24-34`.
