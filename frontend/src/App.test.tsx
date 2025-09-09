import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';

// Mock the useImageProcessing hook
const mockProcessImage = vi.fn();
const mockReset = vi.fn();

vi.mock('./hooks/useImageProcessing', () => ({
  default: () => ({
    processImage: mockProcessImage,
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
    mockReset.mockClear();
  });

  it('renders the main application', () => {
    render(<App />);

    expect(screen.getByText('Analyze Your Swedish Textbook Page')).toBeInTheDocument();
    expect(screen.getByText('Upload an image to get an instant analysis of the text, grammar, and vocabulary.')).toBeInTheDocument();
    expect(screen.getByText('Drag & drop a file or click to upload')).toBeInTheDocument();
  });

  it('handles file selection and calls processImage', async () => {
    render(<App />);

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    const input = screen.getByDisplayValue(''); // Hidden file input

    await userEvent.upload(input, file);

    expect(mockProcessImage).toHaveBeenCalledWith(file);
  });

  it('renders header component', () => {
    render(<App />);

    // Check for header element
    expect(document.querySelector('header')).toBeInTheDocument();
  });
});