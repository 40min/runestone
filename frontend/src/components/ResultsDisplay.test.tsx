import { render, screen, fireEvent } from '@testing-library/react';
import ResultsDisplay from './ResultsDisplay';

const mockResult = {
  ocr_result: {
    text: 'Sample Swedish text',
    character_count: 18,
  },
  analysis: {
    grammar_focus: {
      topic: 'Present tense',
      explanation: 'Focus on present tense usage in sentences',
      has_explicit_rules: true,
    },
    vocabulary: [
      { swedish: 'hej', english: 'hello' },
      { swedish: 'bra', english: 'good' },
    ],
  },
  extra_info: 'Additional learning tips here',
  processing_successful: true,
};

describe('ResultsDisplay', () => {
  it('renders error state when error is provided', () => {
    const error = 'Processing failed';
    render(<ResultsDisplay result={null} error={error} />);

    expect(screen.getByText('Processing Error')).toBeInTheDocument();
    expect(screen.getByText(error)).toBeInTheDocument();
  });

  it('renders OCR tab content by default', () => {
    render(<ResultsDisplay result={mockResult} error={null} />);

    expect(screen.getByText('Analysis Results')).toBeInTheDocument();
    expect(screen.getByText('OCR Text')).toBeInTheDocument();
    expect(screen.getByText(mockResult.ocr_result.text)).toBeInTheDocument();
  });

  it('switches to grammar tab when clicked', () => {
    render(<ResultsDisplay result={mockResult} error={null} />);

    const grammarTab = screen.getByText('Grammar');
    fireEvent.click(grammarTab);

    expect(screen.getByText('Grammar Analysis')).toBeInTheDocument();
    expect(screen.getByText('Topic:')).toBeInTheDocument();
    expect(screen.getByText(mockResult.analysis.grammar_focus.topic)).toBeInTheDocument();
    expect(screen.getByText('Explanation:')).toBeInTheDocument();
    expect(screen.getByText(mockResult.analysis.grammar_focus.explanation)).toBeInTheDocument();
    expect(screen.getByText('Has Explicit Rules:')).toBeInTheDocument();
    expect(screen.getByText('Yes')).toBeInTheDocument();
  });

  it('switches to vocabulary tab when clicked', () => {
    render(<ResultsDisplay result={mockResult} error={null} />);

    const vocabularyTab = screen.getByText('Vocabulary');
    fireEvent.click(vocabularyTab);

    expect(screen.getByText('Vocabulary Analysis')).toBeInTheDocument();
    expect(screen.getByText('hej')).toBeInTheDocument();
    expect(screen.getByText('hello')).toBeInTheDocument();
    expect(screen.getByText('bra')).toBeInTheDocument();
    expect(screen.getByText('good')).toBeInTheDocument();
  });

  it('copies vocabulary to clipboard when copy button is clicked', async () => {
    const mockClipboard = {
      writeText: vi.fn().mockResolvedValue(undefined),
    };
    Object.assign(navigator, { clipboard: mockClipboard });

    render(<ResultsDisplay result={mockResult} error={null} />);

    const vocabularyTab = screen.getByText('Vocabulary');
    fireEvent.click(vocabularyTab);

    const copyButton = screen.getByText('Copy');
    fireEvent.click(copyButton);

    expect(mockClipboard.writeText).toHaveBeenCalledWith('hej - hello\nbra - good');
  });

  it('switches to extra info tab when clicked', () => {
    render(<ResultsDisplay result={mockResult} error={null} />);

    const extraInfoTab = screen.getByText('Extra info');
    fireEvent.click(extraInfoTab);

    expect(screen.getByRole('heading', { name: 'Extra info' })).toBeInTheDocument();
    expect(screen.getByText(mockResult.extra_info)).toBeInTheDocument();
  });

  it('shows default message when extra_info is not provided', () => {
    const resultWithoutExtraInfo = {
      ...mockResult,
      extra_info: undefined,
    };

    render(<ResultsDisplay result={resultWithoutExtraInfo} error={null} />);

    const extraInfoTab = screen.getByText('Extra info');
    fireEvent.click(extraInfoTab);

    expect(screen.getByText('Additional learning materials and resources will be displayed here.')).toBeInTheDocument();
  });

  it('does not render when neither result nor error is provided', () => {
    render(<ResultsDisplay result={null} error={null} />);

    expect(screen.queryByText('Analysis Results')).not.toBeInTheDocument();
  });

  it('renders all tabs correctly', () => {
    render(<ResultsDisplay result={mockResult} error={null} />);

    expect(screen.getByText('OCR Text')).toBeInTheDocument();
    expect(screen.getByText('Grammar')).toBeInTheDocument();
    expect(screen.getByText('Vocabulary')).toBeInTheDocument();
    expect(screen.getByText('Extra info')).toBeInTheDocument();
  });
});