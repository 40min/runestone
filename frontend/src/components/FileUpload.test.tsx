import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FileUpload from './FileUpload';

const mockOnFileSelect = vi.fn();

describe('FileUpload', () => {
  beforeEach(() => {
    mockOnFileSelect.mockClear();
  });

  it('renders the file upload component', () => {
    render(<FileUpload onFileSelect={mockOnFileSelect} isProcessing={false} />);

    expect(screen.getByText('Drop your image here')).toBeInTheDocument();
    expect(screen.getByText('or')).toBeInTheDocument();
    expect(screen.getByText('browse files')).toBeInTheDocument();
  });

  it('shows drag active state when dragging over', async () => {
    render(<FileUpload onFileSelect={mockOnFileSelect} isProcessing={false} />);

    const dropzone = screen.getByText('Drop your image here').closest('.relative');
    act(() => {
      fireEvent.dragEnter(dropzone!);
    });

    await waitFor(() => {
      expect(dropzone).toHaveClass('border-blue-500 bg-blue-50');
    });
  });

  it('calls onFileSelect when a valid image file is selected', async () => {
    render(<FileUpload onFileSelect={mockOnFileSelect} isProcessing={false} />);

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    const input = screen.getByDisplayValue(''); // Hidden file input

    await userEvent.upload(input, file);

    expect(mockOnFileSelect).toHaveBeenCalledWith(file);
  });

  it('does not call onFileSelect for non-image files', async () => {
    render(<FileUpload onFileSelect={mockOnFileSelect} isProcessing={false} />);

    const file = new File(['test'], 'test.txt', { type: 'text/plain' });
    const input = screen.getByDisplayValue(''); // Hidden file input

    await userEvent.upload(input, file);

    expect(mockOnFileSelect).not.toHaveBeenCalled();
  });

  it('disables input when processing', () => {
    render(<FileUpload onFileSelect={mockOnFileSelect} isProcessing={true} />);

    const input = screen.getByDisplayValue(''); // Hidden file input
    expect(input).toBeDisabled();
  });

  it('shows file preview when file is selected', async () => {
    render(<FileUpload onFileSelect={mockOnFileSelect} isProcessing={false} />);

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    const input = screen.getByDisplayValue(''); // Hidden file input

    await userEvent.upload(input, file);

    expect(screen.getByAltText('Preview')).toBeInTheDocument();
  });
});