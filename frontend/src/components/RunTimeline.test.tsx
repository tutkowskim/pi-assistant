import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { runFixture } from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { RunTimeline } from './RunTimeline'

describe('RunTimeline', () => {
  it('shows a preparing state before the first agent step', () => {
    renderWithProviders(<RunTimeline run={{ ...runFixture, status: 'running', steps: [] }} />)

    expect(screen.getByText('Preparing agents…')).toBeInTheDocument()
  })

  it('groups and expands review results by attempt', () => {
    const run = {
      ...runFixture,
      status: 'review_failed',
      error_message: 'The answer did not pass review.',
      steps: [
        {
          id: 'step-1',
          sequence: 1,
          participant_id: 'judge',
          role: 'judge',
          model_id: 'gpt-test',
          reasoning_effort: 'high' as const,
          review_attempt: 1,
          debate_round: null,
          status: 'succeeded',
          output: null,
          verdict: {
            verdict: 'incorrect' as const,
            summary: 'A key fact is unsupported.',
            issues: ['Missing evidence'],
            retry_instructions: ['Verify the claim'],
          },
          usage: {},
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
    }
    renderWithProviders(<RunTimeline run={run} />)

    expect(screen.getByText('Attempt 1')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Attempt 1'))
    expect(screen.getByText('A key fact is unsupported.')).toBeInTheDocument()
    expect(screen.getByText('The answer did not pass review.')).toBeInTheDocument()
  })
})
