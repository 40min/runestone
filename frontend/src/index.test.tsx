import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import App from './App';

describe('Font Loading', () => {
  it('should not load external Google Fonts', () => {
    // Render the app
    const { container } = render(<App />);

    // Check that no Google Fonts links are present in the document
    const googleFontLinks = document.querySelectorAll('link[href*="fonts.googleapis.com"]');
    expect(googleFontLinks.length).toBe(0);

    // Check that no Google Fonts preconnect links are present
    const preconnectLinks = document.querySelectorAll('link[href*="fonts.gstatic.com"]');
    expect(preconnectLinks.length).toBe(0);
  });

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
    const { container } = render(<App />);

    // Check that all stylesheets are local (relative paths or same origin)
    const styleLinks = document.querySelectorAll('link[rel="stylesheet"]');
    styleLinks.forEach(link => {
      const href = link.getAttribute('href');
      expect(href).not.toContain('http://');
      expect(href).not.toContain('https://');
      expect(href).not.toContain('fonts.googleapis.com');
    });
  });

  it('should not have external font references in HTML', () => {
    const { container } = render(<App />);

    // Check that the HTML doesn't contain external font references
    const html = document.documentElement.outerHTML;
    expect(html).not.toContain('fonts.googleapis.com');
    expect(html).not.toContain('fonts.gstatic.com');
  });
});