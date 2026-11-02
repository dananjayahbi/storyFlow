import { render, screen } from '@testing-library/react';
import { ScriptViewer } from '@/components/ScriptViewer';

describe('ScriptViewer', () => {
  const script = {
    title: 'The Hidden River',
    segments: [
      { text_content: 'The river begins in the mountains.', image_prompt: 'Snowy peaks' },
      { text_content: 'It carves a path through the forest.', image_prompt: 'Green canyon' },
    ],
  };

  it('renders the script title and segment count', () => {
    render(<ScriptViewer script={script} />);
    expect(screen.getByText('The Hidden River')).toBeInTheDocument();
    expect(screen.getByText('2 narration segments')).toBeInTheDocument();
  });

  it('renders narration and image prompts for each segment', () => {
    render(<ScriptViewer script={script} />);
    expect(screen.getByText('The river begins in the mountains.')).toBeInTheDocument();
    expect(screen.getByText('Snowy peaks')).toBeInTheDocument();
    expect(screen.getByText('It carves a path through the forest.')).toBeInTheDocument();
    expect(screen.getByText('Green canyon')).toBeInTheDocument();
  });

  it('handles an empty script gracefully', () => {
    render(<ScriptViewer script={{ title: 'Empty', segments: [] }} />);
    expect(screen.getByText('Empty')).toBeInTheDocument();
    expect(screen.getByText('0 narration segments')).toBeInTheDocument();
  });
});
