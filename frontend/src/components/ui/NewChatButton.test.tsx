import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { NewChatButton } from './NewChatButton';
import React from 'react';

describe('NewChatButton', () => {
  it('renders correctly', () => {
    const onClick = vi.fn();
    render(<NewChatButton onClick={onClick} isLoading={false} hasMessages={true} />);

    expect(screen.getByText('Start New Chat')).toBeInTheDocument();
  });

  it('is disabled when isLoading is true', () => {
    const onClick = vi.fn();
    render(<NewChatButton onClick={onClick} isLoading={true} hasMessages={true} />);

    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
  });

  it('is disabled when hasMessages is false', () => {
    const onClick = vi.fn();
    render(<NewChatButton onClick={onClick} isLoading={false} hasMessages={false} />);

    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
  });

  it('calls onClick when clicked', () => {
    const onClick = vi.fn();
    render(<NewChatButton onClick={onClick} isLoading={false} hasMessages={true} />);

    const button = screen.getByRole('button');
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
