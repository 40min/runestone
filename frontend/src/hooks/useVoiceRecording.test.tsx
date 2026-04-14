import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useVoiceRecording } from "./useVoiceRecording";

const mockPost = vi.hoisted(() => vi.fn());

vi.mock("../utils/api", () => ({
  useApi: () => ({
    post: mockPost,
  }),
}));

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    token: "test-token",
  }),
}));

class MockMediaRecorder {
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;

  static isTypeSupported = vi.fn(() => true);

  start = vi.fn();

  stop = vi.fn(() => {
    this.ondataavailable?.({ data: new Blob(["audio"], { type: "audio/webm" }) });
    this.onstop?.();
  });
}

const stream = {
  getTracks: () => [
    {
      stop: vi.fn(),
    },
  ],
};

const TestComponent = () => {
  const { startRecording, stopRecording } = useVoiceRecording(true, "Finnish");

  return (
    <>
      <button type="button" onClick={() => void startRecording()}>
        Start
      </button>
      <button type="button" onClick={() => void stopRecording()}>
        Stop
      </button>
    </>
  );
};

describe("useVoiceRecording", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPost.mockResolvedValue({ text: "Hei" });

    Object.defineProperty(window, "isSecureContext", {
      configurable: true,
      value: true,
    });
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue(stream),
      },
    });
    Object.defineProperty(window, "MediaRecorder", {
      configurable: true,
      value: MockMediaRecorder,
    });
    Object.defineProperty(globalThis, "MediaRecorder", {
      configurable: true,
      value: MockMediaRecorder,
    });
  });

  it("includes selected language in the transcription form data", async () => {
    render(<TestComponent />);

    fireEvent.click(screen.getByRole("button", { name: "Start" }));

    await waitFor(() => {
      expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith({ audio: true });
    });

    fireEvent.click(screen.getByRole("button", { name: "Stop" }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        "/api/chat/transcribe-voice",
        expect.any(FormData),
      );
    });

    const formData = mockPost.mock.calls[0][1] as FormData;
    expect(formData.get("language")).toBe("Finnish");
    expect(formData.get("improve")).toBe("true");
    expect(formData.get("file")).toBeInstanceOf(Blob);
  });
});
