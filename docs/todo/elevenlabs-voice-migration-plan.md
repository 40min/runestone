# ElevenLabs Voice Migration Plan

## Summary

Runestone does **not** use Whisper for both speech directions today.

- Speech-to-text (voice recognition) currently uses OpenAI `whisper-1`.
- Text-to-speech currently uses OpenAI `gpt-4o-mini-tts`.
- The chat LLM flow itself is separate and does not depend on the voice provider.

Because of that, the safest migration path is:

1. Switch **TTS first** to ElevenLabs.
2. Keep transcription on OpenAI initially.
3. Evaluate whether moving STT to ElevenLabs is worth the added scope.

This gives us the user-facing quality win with the smallest architecture change.

## Verified Current State

### Backend

- `src/runestone/config.py`
  - `voice_transcription_model = "whisper-1"`
  - `tts_model = "gpt-4o-mini-tts"`
  - `tts_voice = "onyx"`
- `src/runestone/services/voice_service.py`
  - Uses `OpenAI.audio.transcriptions.create(...)`
  - Optionally runs a second OpenAI chat completion to clean up the transcript
- `src/runestone/services/tts_service.py`
  - Uses `AsyncOpenAI.audio.speech.with_streaming_response.create(...)`
  - Streams MP3 chunks to the client over WebSocket
- `src/runestone/api/chat_endpoints.py`
  - `POST /api/chat/transcribe-voice` handles uploaded voice recordings
- `src/runestone/api/audio_ws.py`
  - `/api/ws/audio` pushes assistant speech to the browser
- `src/runestone/services/chat_service.py`
  - When `tts_expected=True`, it triggers TTS after the assistant message is saved

### Frontend

- `frontend/src/hooks/useVoiceRecording.ts`
  - Records microphone audio with `MediaRecorder`
  - Uploads WebM audio to `/api/chat/transcribe-voice`
- `frontend/src/hooks/useAudioPlayback.ts`
  - Connects to `/api/ws/audio`
  - Plays streamed MP3 chunks with `MediaSource`
- `frontend/src/components/ChatView.tsx`
  - Controls voice toggle, playback speed, recording, autosend, and transcript cleanup

### Test surface

- `tests/services/test_voice_service.py`
- `tests/services/test_chat_service.py`
- `tests/api/test_chat_endpoints.py`

## ElevenLabs Capabilities Relevant To This Migration

Based on ElevenLabs documentation:

- ElevenLabs supports **text-to-speech** with REST and WebSocket streaming.
- ElevenLabs supports **speech-to-text** as a separate capability.
- TTS appears to be the stronger near-term fit for the current Runestone architecture because we already have a server-side streaming TTS pipeline.

Useful docs:

- Overview: <https://elevenlabs.io/docs/overview>
- TTS: <https://elevenlabs.io/docs/capabilities/text-to-speech>
- TTS API: <https://elevenlabs.io/docs/api-reference/text-to-speech/>
- TTS WebSocket: <https://elevenlabs.io/docs/api-reference/websocket>
- STT: <https://elevenlabs.io/docs/capabilities/speech-to-text/>

## Recommendation

### Recommended path: TTS-first migration

Move assistant speech generation to ElevenLabs first and leave transcription on OpenAI for now.

Why this is the best first step:

- It targets the part users hear directly, where ElevenLabs is likely to matter most.
- It avoids changing both upload transcription and reply playback at the same time.
- It preserves the current frontend contract if we keep sending MP3 chunks over the existing `/api/ws/audio` socket.
- It keeps rollback simple.

### Optional later path: STT migration

Only move transcription after we compare real user recordings for:

- Swedish accuracy
- mixed-language handling
- punctuation quality
- noisy microphone input
- latency
- cost

## Proposed Architecture

### Goal

Move vendor-specific API code out of `VoiceService` and `TTSService` without adding a new generic provider layer under `services/`.

### Recommended split

- Keep `VoiceService` as the orchestration layer for transcription, language mapping, errors, and optional transcript cleanup.
- Keep `TTSService` as the orchestration layer for concurrency limits, task cancellation, and WebSocket streaming to the browser.
- Keep `ChatService` unchanged at the workflow level.
- Move raw OpenAI and ElevenLabs API calls into a dedicated voice client package under `src/runestone/core/clients/voice/`.

Suggested structure:

- `src/runestone/core/clients/voice/__init__.py`
- `src/runestone/core/clients/voice/openai_voice_client.py`
- `src/runestone/core/clients/voice/elevenlabs_voice_client.py`
- `src/runestone/core/clients/voice/voice_factory.py`

Optional, only if it helps readability:

- small `Protocol` contracts for speech synthesis and transcription

Why this is a better fit for Runestone:

- The repo already keeps third-party integration details in `core/clients/`.
- A dedicated `voice/` package keeps speech integrations grouped together without mixing them into the generic LLM client files.
- `runestone.core.clients.base` is LLM-specific, so voice clients should not be forced into that inheritance tree.
- The current services already own orchestration concerns, so adding `services/providers/*` would split one feature across too many layers.
- A client seam is enough to switch vendors through config while keeping the current service responsibilities intact.

## Implementation Plan

### Phase 0: Prep and configuration

Add new settings:

- `voice_transcription_provider` with default `openai`
- `tts_provider` with default `openai`
- `elevenlabs_api_key`
- `elevenlabs_tts_model`
- `elevenlabs_tts_voice_id`
- optional tuning fields such as output format, stability, similarity, style, and speaker boost

Update:

- `src/runestone/config.py`
- `.env.example`
- `README.md`
- dependency list in `pyproject.toml`

### Phase 1: Add voice client seam

Refactor so vendor clients live behind a small voice-specific boundary:

- transcription client returns plain transcript text
- synthesis client yields audio chunks as `AsyncIterator[bytes]`
- service classes depend on those capabilities, not on a specific SDK

Recommended approach:

- extract the current OpenAI voice API calls out of `VoiceService` and `TTSService`
- create a small `voice_factory` inside the `voice/` package that selects OpenAI or ElevenLabs from config
- avoid a shared abstract base class for now; if we want a contract, prefer `typing.Protocol`

Update dependency wiring in:

- `src/runestone/dependencies.py`

Success criteria:

- Existing OpenAI behavior still works without product changes
- Unit tests still pass against the OpenAI path

### Phase 2: Implement ElevenLabs TTS client

Create an ElevenLabs voice client that:

- uses the configured voice ID
- returns MP3 chunks
- supports the current chat reply flow
- either maps the existing `speed` concept or documents that ElevenLabs voice settings are different

Important compatibility note:

- The current frontend expects MP3 chunks over `/api/ws/audio`.
- Preserve that contract in phase 1 of the migration to avoid unnecessary frontend changes.

Files most likely touched:

- `src/runestone/core/clients/voice/elevenlabs_voice_client.py`
- `src/runestone/core/clients/voice/voice_factory.py`
- `src/runestone/services/tts_service.py`
- `src/runestone/dependencies.py`
- `src/runestone/config.py`

### Phase 3: Validate TTS in production-like conditions

Test:

- short replies
- long replies
- rapid consecutive replies
- cancellation/interruption behavior
- concurrent users
- browser playback stability

Also verify:

- chunk ordering
- end-of-stream signaling
- reconnect behavior remains acceptable with the existing frontend hook

### Phase 4: Optional ElevenLabs STT spike

If we want a single vendor for voice, build a limited STT spike behind the same client seam.

Files most likely touched:

- `src/runestone/core/clients/voice/elevenlabs_voice_client.py`
- `src/runestone/core/clients/voice/openai_voice_client.py`
- `src/runestone/core/clients/voice/voice_factory.py`
- `src/runestone/services/voice_service.py`
- `src/runestone/api/chat_endpoints.py`
- tests for transcription behavior

Keep the current enhancement pass concept:

- provider transcribes audio
- Runestone optionally cleans up transcript text afterward

That cleanup step should remain ours even if STT vendor changes.

## Risks And Decisions

### 1. Voice identity is now a provider concern

OpenAI uses a simple voice name like `onyx`.
ElevenLabs is voice-ID based.

Decision:

- store a concrete ElevenLabs `voice_id`
- do not try to infer voice identity from the old `tts_voice` field

### 2. Speed control may not map one-to-one

The UI already exposes playback speed. ElevenLabs voice settings are not a drop-in copy of OpenAI's `speed` parameter.

Decision:

- keep the UI control for now
- map it approximately if supported
- otherwise reduce the set of exposed controls and document the behavior change

### 3. Streaming contract must stay stable

The browser currently expects MP3 chunks and a final JSON completion message.

Decision:

- keep `/api/ws/audio` unchanged for the first migration
- do not switch the frontend directly to ElevenLabs WebSocket unless there is a strong latency reason

### 4. STT and TTS should be independently swappable

There is no product reason to force both onto one vendor at once.

Decision:

- separate provider selection for transcription and synthesis

## Rollout Plan

### Option A: safest rollout

1. Add voice client seam.
2. Keep OpenAI as default.
3. Enable ElevenLabs TTS in development.
4. Add a config flag for staging or selected users.
5. Promote ElevenLabs TTS to default after validation.

### Option B: faster rollout

1. Add ElevenLabs TTS path.
2. Switch globally in one release.

I do **not** recommend Option B unless timeline matters more than rollback safety.

## Testing Plan

### Unit tests

Add tests for:

- provider selection by config
- ElevenLabs TTS chunk streaming
- provider error handling and fallback behavior
- transcript cleanup still running after STT

Update existing tests so they mock provider interfaces instead of concrete OpenAI clients.

### Integration tests

Verify:

- `/api/chat/message` still triggers TTS when `tts_expected=true`
- `/api/ws/audio` still delivers playable audio plus completion event
- `/api/chat/transcribe-voice` still accepts recorded WebM uploads

### Manual QA

Check in the browser:

- record voice -> transcript appears
- autosend still works
- assistant voice toggle still works
- multiple rapid sends do not interleave audio
- stopping one reply before the next still behaves correctly

## Suggested Work Breakdown

1. Add config and dependency scaffolding.
2. Introduce provider interfaces.
3. Move existing OpenAI TTS/STT behind those interfaces.
4. Implement ElevenLabs TTS.
5. Validate streaming contract end to end.
6. Decide whether STT should remain on OpenAI or move later.

## Bottom Line

Today:

- Whisper/OpenAI is used for **recognition**
- OpenAI TTS is used for **speech output**
- not Whisper for both

Best next move:

- migrate **assistant TTS to ElevenLabs first**
- keep **voice transcription on OpenAI** until we run a focused STT comparison

That gives the cleanest path to better voice quality without taking on unnecessary migration risk all at once.
