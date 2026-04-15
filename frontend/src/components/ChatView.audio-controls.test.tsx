import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ChatView from "./ChatView";
import { appendTranscribedTextToInput } from "./chatInputText";

const mockUseChatState = {
  messages: [] as Array<{
    id: string;
    role: "user" | "assistant";
    content: string;
    responseTimeMs?: number;
    sources?: null;
  }>,
  isLoading: false,
  isFetchingHistory: false,
  isSyncingHistory: false,
  historySyncNotice: null as string | null,
  error: null as string | null,
  sendMessage: vi.fn(async () => null),
  startNewChat: vi.fn(async () => {}),
  clearError: vi.fn(),
  refreshHistory: vi.fn(async () => {}),
};

const mockAudioPlaybackState = {
  isPlaying: false,
  isPaused: true,
  isConnected: true,
  error: null as string | null,
  canReplay: true,
  playbackMessageId: null as string | null,
  pendingMessageId: null as string | null,
  play: vi.fn(async () => {}),
  pause: vi.fn(),
  replayLast: vi.fn(async () => {}),
  setExpectedMessageId: vi.fn(),
  clearPlayback: vi.fn(),
};

const mockChatImageUploadState = {
  uploadedImages: [],
  uploadImage: vi.fn(async () => null),
  isUploading: false,
  error: null as string | null,
  clearImages: vi.fn(),
};

const mockVoiceRecordingState = {
  isRecording: false,
  isProcessing: false,
  recordedDuration: 0,
  startRecording: vi.fn(async () => {}),
  stopRecording: vi.fn(async () => null),
  error: null as string | null,
  clearError: vi.fn(),
};

vi.mock("../hooks/useChat", () => ({
  useChat: () => mockUseChatState,
}));

vi.mock("../hooks/useAudioPlayback", () => ({
  useAudioPlayback: () => mockAudioPlaybackState,
}));

vi.mock("../hooks/useChatImageUpload", () => ({
  useChatImageUpload: () => mockChatImageUploadState,
}));

vi.mock("../hooks/useVoiceRecording", () => ({
  useVoiceRecording: () => mockVoiceRecordingState,
}));

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    userData: {
      mother_tongue: "Finnish",
    },
  }),
}));

vi.mock("./chat/AgentMemoryModal", () => ({
  default: () => null,
}));

describe("ChatView audio controls", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    mockUseChatState.messages = [];
    mockUseChatState.isLoading = false;
    mockUseChatState.isSyncingHistory = false;
    mockUseChatState.historySyncNotice = null;
    mockUseChatState.error = null;
    mockAudioPlaybackState.isPlaying = false;
    mockAudioPlaybackState.isPaused = true;
    mockAudioPlaybackState.canReplay = true;
    mockAudioPlaybackState.playbackMessageId = null;
    mockAudioPlaybackState.pendingMessageId = null;
    mockLocalStorage();
  });

  it("renders controls for the latest assistant message only", () => {
    mockUseChatState.messages = [
      { id: "user-1", role: "user", content: "Hej" },
      { id: "assistant-1", role: "assistant", content: "Older reply" },
      { id: "assistant-2", role: "assistant", content: "Latest reply" },
    ];
    mockAudioPlaybackState.playbackMessageId = "assistant-2";

    render(<ChatView />);

    expect(screen.getByText("Latest reply")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^play$/i })).toHaveLength(1);
    expect(screen.getByRole("button", { name: /^replay$/i })).toBeInTheDocument();
  });

  it("moves controls to a newer assistant reply", () => {
    mockUseChatState.messages = [
      { id: "user-1", role: "user", content: "Hej" },
      { id: "assistant-1", role: "assistant", content: "Older reply" },
      { id: "assistant-2", role: "assistant", content: "Current reply" },
    ];
    mockAudioPlaybackState.playbackMessageId = "assistant-2";

    const { rerender } = render(<ChatView />);
    expect(screen.getAllByRole("button", { name: /^play$/i })).toHaveLength(1);

    mockUseChatState.messages = [
      ...mockUseChatState.messages,
      { id: "assistant-3", role: "assistant", content: "Newest reply" },
    ];
    mockAudioPlaybackState.playbackMessageId = "assistant-3";

    rerender(<ChatView />);

    expect(screen.getByText("Newest reply")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^play$/i })).toHaveLength(1);
  });

  it("clears audio controls when starting a new chat", async () => {
    mockUseChatState.messages = [
      { id: "user-1", role: "user", content: "Hej" },
      { id: "assistant-1", role: "assistant", content: "Latest reply" },
    ];
    mockAudioPlaybackState.playbackMessageId = "assistant-1";

    const { rerender } = render(<ChatView />);
    expect(screen.getByRole("button", { name: /^play$/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /start new chat/i }));

    await Promise.resolve();

    expect(mockUseChatState.startNewChat).toHaveBeenCalledOnce();
    expect(mockChatImageUploadState.clearImages).toHaveBeenCalledOnce();
    expect(mockAudioPlaybackState.clearPlayback).toHaveBeenCalledOnce();

    mockUseChatState.messages = [];
    mockAudioPlaybackState.playbackMessageId = null;
    rerender(<ChatView />);

    expect(screen.queryByRole("button", { name: /^play$/i })).not.toBeInTheDocument();
  });

  it("appends transcribed text to an existing draft", () => {
    expect(appendTranscribedTextToInput("Hej", "hur mar du?")).toBe("Hej hur mar du?");
    expect(appendTranscribedTextToInput("Hej ", "hur mar du?")).toBe("Hej hur mar du?");
    expect(appendTranscribedTextToInput("", "hur mar du?")).toBe("hur mar du?");
  });
});

function mockLocalStorage() {
  const store = new Map<string, string>([
    ["runestone_voice_enabled", "true"],
  ]);

  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem: vi.fn((key: string) => store.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => {
        store.set(key, value);
      }),
      removeItem: vi.fn((key: string) => {
        store.delete(key);
      }),
      clear: vi.fn(() => {
        store.clear();
      }),
    },
  });
}
