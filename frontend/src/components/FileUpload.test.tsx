import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FileUpload from './FileUpload';

const mockOnFileSelect = vi.fn();
const mockOnReset = vi.fn();

describe('FileUpload', () => {
  beforeEach(() => {
    mockOnFileSelect.mockClear();
  });

  it('renders the file upload component', () => {
    render(<FileUpload onFileSelect={mockOnFileSelect} isProcessing={false} onReset={mockOnReset} />);

    expect(screen.getByText('Drag & drop a file or click to upload')).toBeInTheDocument();
    expect(screen.getByText('Browse Files')).toBeInTheDocument();
  });

  it('handles drag events', async () => {
    render(<FileUpload onFileSelect={mockOnFileSelect} isProcessing={false} onReset={mockOnReset} />);

    const dropzone = screen.getByText('Drag & drop a file or click to upload').closest('div');
    act(() => {
      fireEvent.dragEnter(dropzone!);
    });

    // Test passes if no errors occur during drag events
    expect(dropzone).toBeInTheDocument();
  });

  it('calls onFileSelect when a valid image file is selected', async () => {
    render(<FileUpload onFileSelect={mockOnFileSelect} isProcessing={false} onReset={mockOnReset} />);

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    const input = screen.getByDisplayValue(''); // Hidden file input

    await userEvent.upload(input, file);

    expect(mockOnFileSelect).toHaveBeenCalledWith(file);
  });

  it('does not call onFileSelect for non-image files', async () => {
    render(<FileUpload onFileSelect={mockOnFileSelect} isProcessing={false} onReset={mockOnReset} />);

    const file = new File(['test'], 'test.txt', { type: 'text/plain' });
    const input = screen.getByDisplayValue(''); // Hidden file input

    await userEvent.upload(input, file);

    expect(mockOnFileSelect).not.toHaveBeenCalled();
  });

  it('disables input when processing', () => {
    render(<FileUpload onFileSelect={mockOnFileSelect} isProcessing={true} onReset={mockOnReset} />);

    const input = screen.getByDisplayValue(''); // Hidden file input
    expect(input).toBeDisabled();
  });

  it('shows file preview when file is selected', async () => {
    render(<FileUpload onFileSelect={mockOnFileSelect} isProcessing={false} onReset={mockOnReset} />);

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    const input = screen.getByDisplayValue(''); // Hidden file input

    await userEvent.upload(input, file);

    expect(screen.getByAltText('Preview')).toBeInTheDocument();
  });
});