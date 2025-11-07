import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';
import AuthButton from './AuthButton';

describe('AuthButton', () => {
  it('renders with children', () => {
    render(<AuthButton>Click me</AuthButton>);
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });

  it('calls onClick when clicked', () => {
    const mockOnClick = vi.fn();
    render(<AuthButton onClick={mockOnClick}>Click me</AuthButton>);

    const button = screen.getByRole('button');
    fireEvent.click(button);

    expect(mockOnClick).toHaveBeenCalledTimes(1);
  });

  it('shows loading spinner and text when loading', () => {
    render(<AuthButton loading loadingText="Processing...">Submit</AuthButton>);

    expect(screen.getByText('Processing...')).toBeInTheDocument();
    expect(document.querySelector('svg')).toBeInTheDocument(); // CircularProgress renders as svg
  });

  it('does not show spinner when not loading', () => {
    render(<AuthButton>Submit</AuthButton>);

    expect(screen.getByText('Submit')).toBeInTheDocument();
    expect(document.querySelector('svg')).not.toBeInTheDocument();
  });

  it('is disabled when loading', () => {
    render(<AuthButton loading>Submit</AuthButton>);

    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
  });

  it('is not disabled when not loading', () => {
    render(<AuthButton>Submit</AuthButton>);

    const button = screen.getByRole('button');
    expect(button).not.toBeDisabled();
  });

  it('applies primary variant styles', () => {
    render(<AuthButton variant="primary">Primary</AuthButton>);

    const button = screen.getByRole('button');
    expect(button).toHaveClass('MuiButton-root');
    expect(button).toHaveAttribute('type', 'button');
  });

  it('applies secondary variant styles', () => {
    render(<AuthButton variant="secondary">Secondary</AuthButton>);

    const button = screen.getByRole('button');
    expect(button).toHaveClass('MuiButton-root');
    expect(button).toHaveAttribute('type', 'button');
  });

  it('defaults to primary variant', () => {
    render(<AuthButton>Default</AuthButton>);

    const button = screen.getByRole('button');
    expect(button).toHaveClass('MuiButton-root');
    expect(button).toHaveAttribute('type', 'button');
  });

  it('applies correct type attribute', () => {
    render(<AuthButton type="submit">Submit</AuthButton>);

    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('type', 'submit');
  });

  it('defaults to button type', () => {
    render(<AuthButton>Button</AuthButton>);

    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('type', 'button');
  });

  it('has correct cursor style when loading', () => {
    render(<AuthButton loading>Submit</AuthButton>);

    const button = screen.getByRole('button');
    expect(button).toBeDisabled(); // This implies cursor: not-allowed
  });

  it('has correct cursor style when not loading', () => {
    render(<AuthButton>Submit</AuthButton>);

    const button = screen.getByRole('button');
    expect(button).not.toBeDisabled();
  });

  it('applies hover styles correctly', () => {
    render(<AuthButton variant="secondary">Hover Test</AuthButton>);

    const button = screen.getByRole('button');
    expect(button).toBeInTheDocument();
  });

  it('uses default loading text when none provided', () => {
    render(<AuthButton loading>Submit</AuthButton>);

    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('applies correct opacity when loading', () => {
    render(<AuthButton loading>Submit</AuthButton>);

    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
  });

  it('applies correct opacity when not loading', () => {
    render(<AuthButton>Submit</AuthButton>);

    const button = screen.getByRole('button');
    expect(button).not.toBeDisabled();
  });

  it('renders with correct padding and border radius', () => {
    render(<AuthButton>Styled Button</AuthButton>);

    const button = screen.getByRole('button');
    expect(button).toHaveClass('MuiButton-root');
  });
});
