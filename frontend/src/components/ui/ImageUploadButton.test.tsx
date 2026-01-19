import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ImageUploadButton from './ImageUploadButton';

// Mock window.alert
global.alert = vi.fn();

describe('ImageUploadButton', () => {
  const mockOnFileSelect = vi.fn();
  const mockOnError = vi.fn();

  beforeEach(() => {
    mockOnFileSelect.mockClear();
    mockOnError.mockClear();
    vi.clearAllMocks();
  });

  it('renders button correctly', () => {
    render(<ImageUploadButton onFileSelect={mockOnFileSelect} />);

    const button = screen.getByRole('button');
    expect(button).toBeInTheDocument();
    expect(button).not.toBeDisabled();
  });

  it('triggers file input when button is clicked', () => {
    const { container } = render(<ImageUploadButton onFileSelect={mockOnFileSelect} />);

    const button = screen.getByRole('button');
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;

    expect(fileInput).toBeInTheDocument();

    // Spy on the click method
    const clickSpy = vi.spyOn(fileInput, 'click');

    fireEvent.click(button);

    expect(clickSpy).toHaveBeenCalled();
  });

  it('calls onFileSelect with valid image file', () => {
    const { container } = render(<ImageUploadButton onFileSelect={mockOnFileSelect} />);

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['test'], 'test.png', { type: 'image/png' });

    fireEvent.change(fileInput, { target: { files: [file] } });

    expect(mockOnFileSelect).toHaveBeenCalledWith(file);
  });

  it('calls onError for non-image file', () => {
    const { container } = render(
      <ImageUploadButton onFileSelect={mockOnFileSelect} onError={mockOnError} />
    );

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['test'], 'test.txt', { type: 'text/plain' });

    fireEvent.change(fileInput, { target: { files: [file] } });

    expect(mockOnError).toHaveBeenCalledWith('Please select an image file');
    expect(mockOnFileSelect).not.toHaveBeenCalled();
    expect(global.alert).not.toHaveBeenCalled();
  });

  it('respects disabled state', () => {
    const { container } = render(
      <ImageUploadButton onFileSelect={mockOnFileSelect} disabled={true} />
    );

    const button = screen.getByRole('button');
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;

    expect(button).toBeDisabled();
    expect(fileInput).toBeDisabled();
  });

  it('resets input value after file selection', () => {
    const { container } = render(<ImageUploadButton onFileSelect={mockOnFileSelect} />);

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['test'], 'test.png', { type: 'image/png' });

    // Set initial value
    Object.defineProperty(fileInput, 'value', {
      writable: true,
      value: 'test.png',
    });

    fireEvent.change(fileInput, { target: { files: [file] } });

    // Value should be reset to allow selecting the same file again
    expect(fileInput.value).toBe('');
  });

  it('handles no file selected', () => {
    const { container } = render(
      <ImageUploadButton onFileSelect={mockOnFileSelect} onError={mockOnError} />
    );

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;

    // Trigger change with no files
    fireEvent.change(fileInput, { target: { files: [] } });

    expect(mockOnFileSelect).not.toHaveBeenCalled();
    expect(mockOnError).not.toHaveBeenCalled();
    expect(global.alert).not.toHaveBeenCalled();
  });

  it('accepts only image files via accept attribute', () => {
    const { container } = render(<ImageUploadButton onFileSelect={mockOnFileSelect} />);

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;

    expect(fileInput).toHaveAttribute('accept', 'image/*');
  });
});
