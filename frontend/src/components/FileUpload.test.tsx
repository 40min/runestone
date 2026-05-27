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

    expect(screen.getByText('Drag and drop an image here')).toBeInTheDocument();
    expect(screen.getByText('Choose File')).toBeInTheDocument();
  });

  it('handles drag events', async () => {
    render(<FileUpload onFileSelect={mockOnFileSelect} isProcessing={false} />);

    const dropzone = screen.getByText('Drag and drop an image here').closest('div');
    act(() => {
      fireEvent.dragEnter(dropzone!);
    });

    // Test passes if no errors occur during drag events
    expect(dropzone).toBeInTheDocument();
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

  it('shows a compact processing overlay while working', () => {
    render(
      <FileUpload
        onFileSelect={mockOnFileSelect}
        isProcessing={true}
        compact
        selectedFileOverride={new File(['test'], 'test.jpg', { type: 'image/jpeg' })}
      />
    );

    expect(screen.getByTestId('compact-processing-overlay')).toBeInTheDocument();
  });

  it('shows file preview when file is selected', async () => {
    render(<FileUpload onFileSelect={mockOnFileSelect} isProcessing={false} />);

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    const input = screen.getByDisplayValue(''); // Hidden file input

    await userEvent.upload(input, file);

    expect(screen.getByAltText('Preview')).toBeInTheDocument();
  });

  it('shows file name when file is selected', async () => {
    render(<FileUpload onFileSelect={mockOnFileSelect} isProcessing={false} />);

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    const input = screen.getByDisplayValue(''); // Hidden file input

    await userEvent.upload(input, file);

    expect(screen.getByText('test.jpg')).toBeInTheDocument();
  });

  it('allows zooming in and out of preview image', async () => {
    render(<FileUpload onFileSelect={mockOnFileSelect} isProcessing={false} />);

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    const input = screen.getByDisplayValue(''); // Hidden file input

    await userEvent.upload(input, file);

    const previewImage = screen.getByAltText('Preview');
    expect(previewImage).toBeInTheDocument();

    // Click to zoom in
    fireEvent.click(previewImage);
    expect(previewImage).toHaveClass('max-h-screen');

    // Click again to zoom out
    fireEvent.click(previewImage);
    expect(previewImage).toHaveClass('max-h-72');
  });

  it('allows enlarging the preview image in compact mode', async () => {
    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    render(
      <FileUpload
        onFileSelect={mockOnFileSelect}
        isProcessing={false}
        compact
        selectedFileOverride={file}
      />
    );

    const previewImage = screen.getByAltText('Preview');
    expect(previewImage).toBeInTheDocument();

    // Dialog should not be open initially
    expect(screen.queryByAltText('Enlarged Preview')).not.toBeInTheDocument();

    // Click preview to enlarge
    fireEvent.click(previewImage);

    // Enlarged image should be shown in Dialog
    const enlargedImage = screen.getByAltText('Enlarged Preview');
    expect(enlargedImage).toBeInTheDocument();
    expect(screen.getByLabelText('Image preview')).toBeInTheDocument();

    // Click close button to close dialog
    const closeBtn = screen.getByLabelText('close zoom');
    fireEvent.click(closeBtn);

    // Dialog should close
    await waitFor(() => {
      expect(screen.queryByAltText('Enlarged Preview')).not.toBeInTheDocument();
    });
  });

  it('supports keyboard interaction for compact preview zoom', async () => {
    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    render(
      <FileUpload
        onFileSelect={mockOnFileSelect}
        isProcessing={false}
        compact
        selectedFileOverride={file}
      />
    );

    const previewImage = screen.getByAltText('Preview');
    const zoomTrigger = previewImage.parentElement;
    expect(zoomTrigger).toHaveAttribute('role', 'button');
    expect(zoomTrigger).toHaveAttribute('tabindex', '0');

    zoomTrigger?.focus();
    fireEvent.keyDown(zoomTrigger!, { key: 'Enter' });
    expect(screen.getByAltText('Enlarged Preview')).toBeInTheDocument();
  });

  it('cleans up object URL on unmount', async () => {
    const revokeObjectURLSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});

    const { unmount } = render(<FileUpload onFileSelect={mockOnFileSelect} isProcessing={false} />);

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    const input = screen.getByDisplayValue(''); // Hidden file input

    await userEvent.upload(input, file);

    unmount();

    expect(revokeObjectURLSpy).toHaveBeenCalled();

    revokeObjectURLSpy.mockRestore();
  });
});
