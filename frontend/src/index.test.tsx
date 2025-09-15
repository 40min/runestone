import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import App from './App';

describe('Font Loading', () => {
  it('should not have @import statements for external fonts', () => {
    // Render the app to ensure styles are loaded
    render(<App />);

    // Check that no style elements contain @import statements
    const styleElements = document.querySelectorAll('style');
    styleElements.forEach(style => {
      const cssText = style.textContent || '';
      expect(cssText).not.toContain('@import');
      expect(cssText).not.toContain('fonts.googleapis.com');
    });
  });

  it('should not have external font imports in CSS', () => {
    // Get all style elements
    const styleElements = document.querySelectorAll('style');
    const linkElements = document.querySelectorAll('link[rel="stylesheet"]');

    // Check that no style elements contain Google Fonts imports
    styleElements.forEach(style => {
      expect(style.textContent).not.toContain('fonts.googleapis.com');
    });

    // Check that no link elements reference Google Fonts
    linkElements.forEach(link => {
      expect(link.getAttribute('href')).not.toContain('fonts.googleapis.com');
    });
  });
});

describe('CSP Compliance', () => {
  it('should only use local stylesheets', () => {
    render(<App />);

    // Check that all stylesheets are local (relative paths or same origin)
    const styleLinks = document.querySelectorAll('link[rel="stylesheet"]');
    styleLinks.forEach(link => {
      const href = link.getAttribute('href');
      expect(href).not.toContain('http://');
      expect(href).not.toContain('https://');
      expect(href).not.toContain('fonts.googleapis.com');
    });
  });
});