// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAudioPlayback } from "./useAudioPlayback";

vi.mock("../config", () => ({
  API_BASE_URL: "http://localhost:8010",
}));

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    token: "test-token",
  }),
}));

class MockAudioElement {
  src = "";
  currentTime = 0;
  duration = 5;
  ended = false;
  paused = true;
  error: { message: string; code: number } | null = null;
  onplay: (() => void) | null = null;
  onpause: (() => void) | null = null;
  onended: (() => void) | null = null;
  onerror: (() => void) | null = null;
  play = vi.fn(async () => {
    this.paused = false;
    this.ended = false;
    this.onplay?.();
  });
  pause = vi.fn(() => {
    this.paused = true;
    this.onpause?.();
  });
  load = vi.fn();

  removeAttribute(name: string) {
    if (name === "src") {
      this.src = "";
    }
  }

  finish() {
    this.ended = true;
    this.paused = true;
    this.currentTime = this.duration;
    this.onended?.();
  }
}

class MockSourceBuffer {
  updating = false;
  private listeners = new Map<string, Set<() => void>>();

  addEventListener(type: string, listener: () => void) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    this.listeners.get(type)!.add(listener);
  }

  appendBuffer(chunk: ArrayBuffer) {
    void chunk;
    this.updating = true;
    this.updating = false;
    this.emit("updateend");
  }

  private emit(type: string) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener();
    }
  }
}

class MockMediaSource {
  readyState: "closed" | "open" | "ended" = "closed";
  private listeners = new Map<string, Set<() => void>>();

  constructor() {
    mediaSourceInstances.push(this);
  }

  addEventListener(type: string, listener: () => void) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    this.listeners.get(type)!.add(listener);
  }

  removeEventListener(type: string, listener: () => void) {
    this.listeners.get(type)?.delete(listener);
  }

  addSourceBuffer() {
    return new MockSourceBuffer() as unknown as SourceBuffer;
  }

  endOfStream() {
    this.readyState = "ended";
  }

  open() {
    this.readyState = "open";
    for (const listener of this.listeners.get("sourceopen") ?? []) {
      listener();
    }
  }
}

class MockWebSocket {
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: Blob | string }) => void | Promise<void>) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(public url: string) {
    webSocketInstances.push(this);
  }

  close() {
    this.onclose?.();
  }

  open() {
    this.onopen?.();
  }

  async emitBlob(blob: Blob) {
    await this.onmessage?.({ data: blob });
  }

  emitJson(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
}

const audioInstances: MockAudioElement[] = [];
const mediaSourceInstances: MockMediaSource[] = [];
const webSocketInstances: MockWebSocket[] = [];

describe("useAudioPlayback", () => {
  beforeEach(() => {
    audioInstances.length = 0;
    mediaSourceInstances.length = 0;
    webSocketInstances.length = 0;

    if (!Blob.prototype.arrayBuffer) {
      Blob.prototype.arrayBuffer = async function arrayBuffer() {
        return new Uint8Array([1, 2, 3]).buffer;
      };
    }

    vi.stubGlobal(
      "Audio",
      vi.fn(() => {
        const audio = new MockAudioElement();
        audioInstances.push(audio);
        return audio;
      }),
    );
    vi.stubGlobal("MediaSource", MockMediaSource);
    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps replayable audio available after playback ends", async () => {
    const { result } = renderHook(() => useAudioPlayback(true));
    const ws = webSocketInstances[0];

    act(() => {
      ws.open();
      result.current.setExpectedMessageId("assistant-1");
    });

    await act(async () => {
      await ws.emitBlob(new Blob([Uint8Array.from([1, 2, 3])]));
    });

    act(() => {
      mediaSourceInstances[0].open();
    });

    await waitFor(() => {
      expect(result.current.canReplay).toBe(true);
      expect(result.current.playbackMessageId).toBe("assistant-1");
    });

    act(() => {
      audioInstances[0].finish();
    });

    expect(result.current.isPlaying).toBe(false);
    expect(result.current.canReplay).toBe(true);

    await act(async () => {
      await result.current.replayLast();
    });

    expect(audioInstances[0].currentTime).toBe(0);
    expect(audioInstances[0].play).toHaveBeenCalledTimes(2);
  });

  it("pauses and resumes playback without clearing the buffered audio", async () => {
    const { result } = renderHook(() => useAudioPlayback(true));
    const ws = webSocketInstances[0];

    act(() => {
      ws.open();
      result.current.setExpectedMessageId("assistant-1");
    });

    await act(async () => {
      await ws.emitBlob(new Blob([Uint8Array.from([1, 2, 3])]));
    });

    act(() => {
      mediaSourceInstances[0].open();
    });

    await waitFor(() => {
      expect(result.current.isPlaying).toBe(true);
    });

    act(() => {
      result.current.pause();
    });

    expect(result.current.isPlaying).toBe(false);
    expect(result.current.canReplay).toBe(true);

    await act(async () => {
      await result.current.play();
    });

    expect(result.current.isPlaying).toBe(true);
  });

  it("replaces the replay target when a newer stream arrives", async () => {
    const { result } = renderHook(() => useAudioPlayback(true));
    const ws = webSocketInstances[0];

    act(() => {
      ws.open();
      result.current.setExpectedMessageId("assistant-1");
    });

    await act(async () => {
      await ws.emitBlob(new Blob([Uint8Array.from([1, 2, 3])]));
    });

    act(() => {
      mediaSourceInstances[0].open();
    });

    await waitFor(() => {
      expect(result.current.playbackMessageId).toBe("assistant-1");
    });

    act(() => {
      result.current.setExpectedMessageId("assistant-2");
    });

    await act(async () => {
      await ws.emitBlob(new Blob([Uint8Array.from([4, 5, 6])]));
    });

    act(() => {
      mediaSourceInstances[1].open();
    });

    await waitFor(() => {
      expect(result.current.playbackMessageId).toBe("assistant-2");
      expect(result.current.pendingMessageId).toBeNull();
    });

    expect(audioInstances[0].pause).toHaveBeenCalled();
  });

  it("clears replay state when voice playback is disabled", async () => {
    const { result, rerender } = renderHook(
      ({ enabled }) => useAudioPlayback(enabled),
      { initialProps: { enabled: true } },
    );
    const ws = webSocketInstances[0];

    act(() => {
      ws.open();
      result.current.setExpectedMessageId("assistant-1");
    });

    await act(async () => {
      await ws.emitBlob(new Blob([Uint8Array.from([1, 2, 3])]));
    });

    act(() => {
      mediaSourceInstances[0].open();
    });

    await waitFor(() => {
      expect(result.current.canReplay).toBe(true);
    });

    rerender({ enabled: false });

    await waitFor(() => {
      expect(result.current.canReplay).toBe(false);
      expect(result.current.playbackMessageId).toBeNull();
      expect(result.current.pendingMessageId).toBeNull();
    });
  });
});
