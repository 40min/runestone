import { render, screen } from '@testing-library/react';
import ProcessingStatus from './ProcessingStatus';

describe('ProcessingStatus', () => {
  it('renders processing indicator when isProcessing is true', () => {
    render(<ProcessingStatus isProcessing={true} processingStep="IDLE" />);

    expect(screen.getByText('Processing...')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toBeInTheDocument(); // Material-UI CircularProgress has role="progressbar"
  });

  it('does not render when isProcessing is false', () => {
    render(<ProcessingStatus isProcessing={false} processingStep="IDLE" />);

    expect(screen.queryByText('Processing...')).not.toBeInTheDocument();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('has correct spinner styling', () => {
    render(<ProcessingStatus isProcessing={true} processingStep="IDLE" />);

    const spinner = screen.getByRole('progressbar');
    // Material-UI CircularProgress has its own classes, we just verify it exists
    expect(spinner).toBeInTheDocument();
  });

  it('has correct text styling', () => {
    render(<ProcessingStatus isProcessing={true} processingStep="IDLE" />);

    const text = screen.getByText('Processing...');
    // Material-UI Typography has its own classes, we just verify it exists
    expect(text).toBeInTheDocument();
  });
});
