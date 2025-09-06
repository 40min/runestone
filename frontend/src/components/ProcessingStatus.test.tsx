import { render, screen } from '@testing-library/react';
import ProcessingStatus from './ProcessingStatus';

describe('ProcessingStatus', () => {
  it('renders processing indicator when isProcessing is true', () => {
    render(<ProcessingStatus isProcessing={true} />);

    expect(screen.getByText('Processing...')).toBeInTheDocument();
    expect(screen.getByRole('status')).toBeInTheDocument(); // The spinner div
  });

  it('does not render when isProcessing is false', () => {
    render(<ProcessingStatus isProcessing={false} />);

    expect(screen.queryByText('Processing...')).not.toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('has correct spinner styling', () => {
    render(<ProcessingStatus isProcessing={true} />);

    const spinner = screen.getByRole('status');
    expect(spinner).toHaveClass('w-16', 'h-16', 'border-4', 'border-[#4d3c63]', 'border-t-[var(--primary-color)]', 'rounded-full', 'animate-spin');
  });

  it('has correct text styling', () => {
    render(<ProcessingStatus isProcessing={true} />);

    const text = screen.getByText('Processing...');
    expect(text).toHaveClass('text-lg', 'font-semibold', 'text-white');
  });
});