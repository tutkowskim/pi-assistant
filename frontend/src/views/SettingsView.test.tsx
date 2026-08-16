import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import { capabilitiesFixture } from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { SettingsView } from './SettingsView'

vi.mock('../api', () => ({
  api: {
    health: vi.fn().mockResolvedValue({
      status: 'ready',
      version: '1.2.3',
      timezone: 'America/Los_Angeles',
      openai_configured: true,
      gemini_configured: false,
      ollama_configured: true,
      discovered_models: 2,
    }),
  },
}))

describe('SettingsView', () => {
  it('renders backend health and discovered provider state', async () => {
    renderWithProviders(<SettingsView capabilities={capabilitiesFixture} />)

    expect(await screen.findByText('ready')).toBeInTheDocument()
    expect(screen.getByText('1.2.3')).toBeInTheDocument()
    expect(screen.getByText('GPT Test · openai')).toBeInTheDocument()
    expect(screen.getAllByText('Connected')).toHaveLength(2)
    expect(api.health).toHaveBeenCalledOnce()
  })
})
