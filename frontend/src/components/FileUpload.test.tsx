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

  it('opens the zoom dialog from the full-mode zoom control', async () => {
    render(<FileUpload onFileSelect={mockOnFileSelect} isProcessing={false} />);

    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    const input = screen.getByDisplayValue(''); // Hidden file input

    await userEvent.upload(input, file);

    const previewImage = screen.getByAltText('Preview');
    expect(previewImage).toBeInTheDocument();

    // Dialog should not be open initially
    expect(screen.queryByAltText('Enlarged Preview')).not.toBeInTheDocument();

    // Activate the named zoom control
    await userEvent.click(screen.getByRole('button', { name: 'Zoom preview image' }));

    // Enlarged image should be shown in Dialog
    const enlargedImage = screen.getByAltText('Enlarged Preview');
    expect(enlargedImage).toBeInTheDocument();
    expect(screen.getByLabelText('Image preview')).toBeInTheDocument();

    // Click close button to close dialog
    const closeBtn = screen.getByLabelText('close zoom');
    await userEvent.click(closeBtn);

    // Dialog should close
    await waitFor(() => {
      expect(screen.queryByAltText('Enlarged Preview')).not.toBeInTheDocument();
    });
  });

  it('opens the zoom dialog from the compact-mode zoom control', async () => {
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
    await userEvent.click(screen.getByRole('button', { name: 'Zoom preview image' }));

    // Enlarged image should be shown in Dialog
    const enlargedImage = screen.getByAltText('Enlarged Preview');
    expect(enlargedImage).toBeInTheDocument();
    expect(screen.getByLabelText('Image preview')).toBeInTheDocument();

    // Click close button to close dialog
    const closeBtn = screen.getByLabelText('close zoom');
    await userEvent.click(closeBtn);

    // Dialog should close
    await waitFor(() => {
      expect(screen.queryByAltText('Enlarged Preview')).not.toBeInTheDocument();
    });
  });

  it('closes the zoom dialog with Escape', async () => {
    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    render(
      <FileUpload
        onFileSelect={mockOnFileSelect}
        isProcessing={false}
        compact
        selectedFileOverride={file}
      />
    );

    await userEvent.click(screen.getByTestId('compact-preview-trigger'));

    expect(screen.getByAltText('Enlarged Preview')).toBeInTheDocument();

    await userEvent.keyboard('{Escape}');

    await waitFor(() => {
      expect(screen.queryByAltText('Enlarged Preview')).not.toBeInTheDocument();
    });
  });

  it('exposes a native zoom button with keyboard activation in compact mode', async () => {
    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    render(
      <FileUpload
        onFileSelect={mockOnFileSelect}
        isProcessing={false}
        compact
        selectedFileOverride={file}
      />
    );

    const zoomTrigger = screen.getByTestId('compact-preview-trigger');
    expect(zoomTrigger).toHaveAttribute('tabindex', '0');

    await userEvent.tab();
    expect(zoomTrigger).toHaveFocus();
    await userEvent.keyboard('{Enter}');

    expect(screen.getByAltText('Enlarged Preview')).toBeInTheDocument();
  });

  it('opens compact preview zoom with the spacebar', async () => {
    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' });
    render(
      <FileUpload
        onFileSelect={mockOnFileSelect}
        isProcessing={false}
        compact
        selectedFileOverride={file}
      />
    );

    const zoomTrigger = screen.getByTestId('compact-preview-trigger');
    expect(zoomTrigger.tagName).toBe('BUTTON');

    await userEvent.tab();
    expect(zoomTrigger).toHaveFocus();
    await userEvent.keyboard(' ');

    expect(screen.getByAltText('Enlarged Preview')).toBeInTheDocument();
  });

  it('does not expose a zoom trigger in compact mode without a file', () => {
    render(
      <FileUpload
        onFileSelect={mockOnFileSelect}
        isProcessing={false}
        compact
      />
    );

    const uploadPlaceholder = screen.getByTestId('compact-preview-trigger');
    expect(uploadPlaceholder).not.toHaveAttribute('role');
    expect(screen.queryByRole('button', { name: 'Zoom preview image' })).not.toBeInTheDocument();
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
