import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';import { ImageSidebar } from './ImageSidebar';

const images = [
  { id: 'img-1', url: 'blob:image-1' },
  { id: 'img-2', url: 'blob:image-2' },
];

describe('ImageSidebar', () => {
  it('renders nothing when there are no images', () => {
    const { container } = render(<ImageSidebar images={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders every thumbnail as a named button', () => {
    render(<ImageSidebar images={images} />);

    expect(
      screen.getByRole('button', { name: 'View uploaded image 1' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'View uploaded image 2' })
    ).toBeInTheDocument();
  });

  it('opens the image dialog when a thumbnail is activated with a click', async () => {
    render(<ImageSidebar images={images} />);

    await userEvent.click(
      screen.getByRole('button', { name: 'View uploaded image 2' })
    );

    const dialog = screen.getByLabelText('Uploaded image preview');
    expect(dialog).toBeInTheDocument();
    expect(screen.getByAltText('Full size')).toHaveAttribute(
      'src',
      'blob:image-2'
    );
  });

  it('opens the image dialog when a thumbnail is activated with the keyboard', async () => {
    render(<ImageSidebar images={images} />);

    await userEvent.tab();
    const thumbnail = screen.getByRole('button', {
      name: 'View uploaded image 1',
    });
    expect(thumbnail).toHaveFocus();
    await userEvent.keyboard('{Enter}');

    expect(
      screen.getByLabelText('Uploaded image preview')
    ).toBeInTheDocument();
  });

  it('closes the dialog through the labeled close button and returns focus to the thumbnail', async () => {
    const user = userEvent.setup();
    render(<ImageSidebar images={images} />);

    const thumbnail = screen.getByRole('button', {
      name: 'View uploaded image 1',
    });
    await user.click(thumbnail);

    const closeButton = screen.getByRole('button', {
      name: 'Close image preview',
    });
    await user.click(closeButton);

    await waitFor(() => {
      expect(
        screen.queryByLabelText('Uploaded image preview')
      ).not.toBeInTheDocument();
    });
    expect(thumbnail).toHaveFocus();
  });

  it('closes the dialog with Escape and returns focus to the thumbnail', async () => {
    const user = userEvent.setup();
    render(<ImageSidebar images={images} />);

    const thumbnail = screen.getByRole('button', {
      name: 'View uploaded image 1',
    });
    await user.click(thumbnail);

    await user.keyboard('{Escape}');

    await waitFor(() => {
      expect(
        screen.queryByLabelText('Uploaded image preview')
      ).not.toBeInTheDocument();
    });
    expect(thumbnail).toHaveFocus();
  });
});
