import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, subscribeToRun } from '../api'
import { capabilitiesFixture, conversationFixture, runFixture } from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { ChatView } from './ChatView'

vi.mock('../api', () => ({
  api: {
    messages: vi.fn(),
    createRun: vi.fn(),
    run: vi.fn(),
    cancelRun: vi.fn(),
  },
  subscribeToRun: vi.fn(),
}))

describe('ChatView', () => {
  beforeEach(() => {
    vi.mocked(api.messages).mockResolvedValue([])
    vi.mocked(api.createRun).mockResolvedValue({ id: 'run-1', status: 'accepted' })
    vi.mocked(api.run).mockResolvedValue({ ...runFixture, status: 'running', final_output: null })
    vi.mocked(subscribeToRun).mockReturnValue(() => undefined)
  })

  it('shows the welcome state without a selected conversation', () => {
    renderWithProviders(<ChatView capabilities={capabilitiesFixture} conversation={null} />)

    expect(screen.getByText('A private place to think.')).toBeInTheDocument()
  })

  it('starts a configured run for a submitted prompt', async () => {
    renderWithProviders(
      <ChatView capabilities={capabilitiesFixture} conversation={conversationFixture} />,
    )
    await screen.findByText('What would you like to work through?')

    fireEvent.change(screen.getByPlaceholderText('Ask anything…'), {
      target: { value: 'Check this answer' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))

    await waitFor(() => {
      expect(api.createRun).toHaveBeenCalledWith(
        conversationFixture.id,
        'Check this answer',
        expect.objectContaining({ model_id: 'gpt-test', execution_mode: 'single' }),
      )
    })
    expect(api.run).toHaveBeenCalledWith('run-1')
    expect(subscribeToRun).toHaveBeenCalledWith(
      'run-1',
      expect.any(Function),
      expect.any(Function),
      expect.any(Function),
    )
  })
})
