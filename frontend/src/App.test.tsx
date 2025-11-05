import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
import { AuthProvider } from './context/AuthContext';

// Mock localStorage
const mockLocalStorage = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};
Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
});

// Wrapper component for tests - provides authenticated state
const wrapper = ({ children }: { children: React.ReactNode }) => {
  // Mock authenticated state
  mockLocalStorage.getItem.mockImplementation((key: string) => {
    if (key === 'runestone_token') return 'mock-token';
    if (key === 'runestone_user_data') return JSON.stringify({
      id: 1,
      email: 'test@example.com',
      name: 'Test',
      surname: 'User',
      timezone: 'UTC',
      pages_recognised_count: 0,
    });
    return null;
  });

  return <AuthProvider>{children}</AuthProvider>;
};

// Mock the useImageProcessing hook
const mockProcessImage = vi.fn();
const mockRecognizeImage = vi.fn();
const mockAnalyzeText = vi.fn();
const mockReset = vi.fn();

vi.mock('./hooks/useImageProcessing', () => ({
  default: () => ({
    processImage: mockProcessImage,
    recognizeImage: mockRecognizeImage,
    analyzeText: mockAnalyzeText,
    ocrResult: null,
    analysisResult: null,
    resourcesResult: null,
    processingStep: 'IDLE',
    error: null,
    isProcessing: false,
    reset: mockReset,
    currentImage: null,
    progress: 0,
  }),
}));

describe('App', () => {
  beforeEach(() => {
    mockProcessImage.mockClear();
    mockRecognizeImage.mockClear();
    mockAnalyzeText.mockClear();
    mockReset.mockClear();
  });

  it('renders the main application', () => {
    render(<App />, { wrapper });

    expect(screen.getByText('Analyze Your Swedish Textbook Page')).toBeInTheDocument();
    expect(screen.getByText('Upload an image to get an instant analysis of the text, grammar, and vocabulary.')).toBeInTheDocument();
    expect(screen.getByText('Drag & drop a file or click to upload')).toBeInTheDocument();
  });

  it('handles file selection and calls processImage', async () => {
    render(<App />, { wrapper });

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    await userEvent.upload(input, file);

    expect(mockProcessImage).toHaveBeenCalledWith(file, false); // Default is recognizeOnly: false
  });

  it('renders header component', () => {
    render(<App />, { wrapper });

    // Check for header element
    expect(document.querySelector('header')).toBeInTheDocument();
  });

  it('should call only recognizeImage when "Recognize only" is checked', async () => {
    mockRecognizeImage.mockResolvedValue({ text: 'OCR Text', character_count: 8 });
    render(<App />, { wrapper });

    const recognizeOnlyCheckbox = screen.getByLabelText('Recognize only');
    await userEvent.click(recognizeOnlyCheckbox);

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, file);

    await waitFor(() => {
      expect(mockProcessImage).toHaveBeenCalledWith(file, true);
    });
  });

  it('should call both recognizeImage and analyzeText when "Recognize only" is unchecked', async () => {
    mockRecognizeImage.mockResolvedValue({ text: 'OCR Text', character_count: 8 });
    render(<App />, { wrapper });

    // Ensure checkbox is unchecked (default state)
    const recognizeOnlyCheckbox = screen.getByLabelText('Recognize only');
    expect(recognizeOnlyCheckbox).not.toBeChecked();

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, file);

    await waitFor(() => {
      expect(mockProcessImage).toHaveBeenCalledWith(file, false);
    });
  });
});
