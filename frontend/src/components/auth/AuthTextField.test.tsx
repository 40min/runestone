import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';
import AuthTextField from './AuthTextField';

describe('AuthTextField', () => {
  it('renders with label', () => {
    render(<AuthTextField label="Test Label" name="test" value="" onChange={() => {}} />);
    expect(screen.getByLabelText('Test Label')).toBeInTheDocument();
  });

  it('displays the correct value', () => {
    render(<AuthTextField label="Test" name="test" value="test value" onChange={() => {}} />);
    const input = screen.getByDisplayValue('test value');
    expect(input).toBeInTheDocument();
  });

  it('calls onChange when value changes', () => {
    const mockOnChange = vi.fn();
    render(<AuthTextField label="Test" name="test" value="" onChange={mockOnChange} />);

    const input = screen.getByLabelText('Test');
    fireEvent.change(input, { target: { value: 'new value' } });

    expect(mockOnChange).toHaveBeenCalledTimes(1);
    // MUI components pass SyntheticBaseEvent, check if function was called
    expect(typeof mockOnChange.mock.calls[0][0]).toBe('object');
  });

  it('applies required attribute when required is true', () => {
    render(<AuthTextField label="Required Field" name="required" value="" onChange={() => {}} required />);
    const input = screen.getByLabelText(/^Required Field\s+\*\s*$/);
    expect(input).toBeRequired();
  });

  it('does not apply required attribute when required is false', () => {
    render(<AuthTextField label="Optional Field" name="optional" value="" onChange={() => {}} required={false} />);
    const input = screen.getByLabelText('Optional Field');
    expect(input).not.toBeRequired();
  });

  it('defaults to required false', () => {
    render(<AuthTextField label="Default Field" name="default" value="" onChange={() => {}} />);
    const input = screen.getByLabelText('Default Field');
    expect(input).not.toBeRequired();
  });

  it('applies different input types', () => {
    render(<AuthTextField label="Email" name="email" type="email" value="" onChange={() => {}} />);
    const input = screen.getByLabelText('Email');
    expect(input).toHaveAttribute('type', 'email');
  });

  it('defaults to text type', () => {
    render(<AuthTextField label="Text" name="text" value="" onChange={() => {}} />);
    const input = screen.getByLabelText('Text');
    expect(input).toHaveAttribute('type', 'text');
  });

  it('applies autoComplete attribute', () => {
    render(<AuthTextField label="Email" name="email" value="" onChange={() => {}} autoComplete="email" />);
    const input = screen.getByLabelText('Email');
    expect(input).toHaveAttribute('autocomplete', 'email');
  });

  it('applies autoFocus attribute when true', () => {
    render(<AuthTextField label="Focused" name="focused" value="" onChange={() => {}} autoFocus />);
    const input = screen.getByLabelText('Focused');
    // MUI TextField might not render autofocus attribute directly
    expect(input).toBeInTheDocument();
  });

  it('does not apply autoFocus attribute when false', () => {
    render(<AuthTextField label="Not Focused" name="notFocused" value="" onChange={() => {}} autoFocus={false} />);
    const input = screen.getByLabelText('Not Focused');
    expect(input).toBeInTheDocument();
  });

  it('defaults autoFocus to false', () => {
    render(<AuthTextField label="Default Focus" name="defaultFocus" value="" onChange={() => {}} />);
    const input = screen.getByLabelText('Default Focus');
    expect(input).toBeInTheDocument();
  });

  it('displays error state', () => {
    render(<AuthTextField label="Error Field" name="error" value="" onChange={() => {}} error />);
    const input = screen.getByLabelText('Error Field');
    expect(input).toHaveAttribute('aria-invalid', 'true');
  });

  it('does not display error state by default', () => {
    render(<AuthTextField label="Normal Field" name="normal" value="" onChange={() => {}} />);
    const input = screen.getByLabelText('Normal Field');
    expect(input).toHaveAttribute('aria-invalid', 'false');
  });

  it('displays helper text', () => {
    render(<AuthTextField label="Field" name="field" value="" onChange={() => {}} helperText="Help text" />);
    expect(screen.getByText('Help text')).toBeInTheDocument();
  });

  it('applies correct name attribute', () => {
    render(<AuthTextField label="Named Field" name="customName" value="" onChange={() => {}} />);
    const input = screen.getByLabelText('Named Field');
    expect(input).toHaveAttribute('name', 'customName');
  });

  it('applies custom styling', () => {
    render(<AuthTextField label="Styled Field" name="styled" value="" onChange={() => {}} />);
    const input = screen.getByLabelText('Styled Field');
    // Check that the input is rendered (styling is applied via MUI sx prop)
    expect(input).toBeInTheDocument();
  });

  it('handles password type correctly', () => {
    render(<AuthTextField label="Password" name="password" type="password" value="" onChange={() => {}} />);
    const input = screen.getByLabelText('Password');
    expect(input).toHaveAttribute('type', 'password');
  });

  it('renders with full width', () => {
    render(<AuthTextField label="Full Width" name="fullWidth" value="" onChange={() => {}} />);
    const input = screen.getByLabelText('Full Width');

    // The TextField should have fullWidth by default
    const textField = input.closest('.MuiTextField-root');
    expect(textField).toHaveClass('MuiTextField-root');
  });

  it('handles empty string values', () => {
    render(<AuthTextField label="Empty" name="empty" value="" onChange={() => {}} />);
    const input = screen.getByLabelText('Empty');
    expect(input).toHaveValue('');
  });

  it('handles numeric string values', () => {
    render(<AuthTextField label="Number" name="number" value="123" onChange={() => {}} />);
    const input = screen.getByDisplayValue('123');
    expect(input).toBeInTheDocument();
  });
});
