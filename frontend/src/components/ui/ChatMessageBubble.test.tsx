import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import React from 'react';
import { ChatMessageBubble } from './ChatMessageBubble';

describe('ChatMessageBubble', () => {
  it('renders assistant sources with link and date', () => {
    render(
      <ChatMessageBubble
        role="assistant"
        content="Här är nyheterna"
        sources={[{ title: 'Nyhetstitel', url: 'https://example.com/news', date: '2026-02-05' }]}
      />
    );

    expect(screen.getByText('Sources')).toBeInTheDocument();
    const link = screen.getByRole('link', { name: 'Nyhetstitel' });
    expect(link).toHaveAttribute('href', 'https://example.com/news');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(screen.getByText('2026-02-05')).toBeInTheDocument();
  });

  it('does not render sources for user messages', () => {
    render(
      <ChatMessageBubble
        role="user"
        content="Hej!"
        sources={[{ title: 'Nyhetstitel', url: 'https://example.com/news', date: '2026-02-05' }]}
      />
    );

    expect(screen.queryByText('Sources')).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Nyhetstitel' })).not.toBeInTheDocument();
  });

  it('renders invalid source URLs as plain text', () => {
    render(
      <ChatMessageBubble
        role="assistant"
        content="Här är nyheterna"
        sources={[{ title: 'Skum länk', url: 'javascript:alert(1)', date: '2026-02-05' }]}
      />
    );

    expect(screen.getByText('Sources')).toBeInTheDocument();
    expect(screen.getByText('Skum länk')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Skum länk' })).not.toBeInTheDocument();
  });
});
