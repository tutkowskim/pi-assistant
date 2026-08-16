import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Navigation } from './App'
import { conversationFixture } from './test/fixtures'
import { renderWithProviders } from './test/render'

vi.mock('./api', () => ({ api: {} }))

describe('Navigation', () => {
  it('routes between feature views and selects conversations', () => {
    const onNavigate = vi.fn()
    const onSelectConversation = vi.fn()
    renderWithProviders(
      <Navigation
        view="chat"
        conversations={[conversationFixture]}
        activeConversationId={conversationFixture.id}
        onNavigate={onNavigate}
        onSelectConversation={onSelectConversation}
        onCreateConversation={vi.fn()}
        onDeleteConversation={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByText('Automations'))
    fireEvent.click(screen.getByText(conversationFixture.title))

    expect(onNavigate).toHaveBeenCalledWith('automations')
    expect(onSelectConversation).toHaveBeenCalledWith(conversationFixture.id)
  })

  it('exposes create and delete actions', () => {
    const onCreateConversation = vi.fn()
    const onDeleteConversation = vi.fn()
    renderWithProviders(
      <Navigation
        view="chat"
        conversations={[conversationFixture]}
        activeConversationId={null}
        onNavigate={vi.fn()}
        onSelectConversation={vi.fn()}
        onCreateConversation={onCreateConversation}
        onDeleteConversation={onDeleteConversation}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'New conversation' }))
    fireEvent.click(screen.getByRole('button', { name: `Delete ${conversationFixture.title}` }))

    expect(onCreateConversation).toHaveBeenCalledOnce()
    expect(onDeleteConversation).toHaveBeenCalledWith(conversationFixture.id)
  })
})
