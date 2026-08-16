import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { initialConfig } from '../config'
import { capabilitiesFixture } from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { ConfigurationPanel } from './ConfigurationPanel'

describe('ConfigurationPanel', () => {
  it('enables and disables tools', () => {
    const onChange = vi.fn()
    const config = initialConfig(capabilitiesFixture)
    renderWithProviders(
      <ConfigurationPanel capabilities={capabilitiesFixture} config={config} onChange={onChange} />,
    )

    fireEvent.click(screen.getByText('Calculator'))

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ enabled_tools: ['spawn_child_agent', 'calculator'] }),
    )
  })

  it('applies the default model and effort to every participant', () => {
    const onChange = vi.fn()
    const config = initialConfig(capabilitiesFixture)
    config.execution_mode = 'judge'
    config.participants = [
      { id: 'primary', role: 'primary', model_id: 'ollama/gemma-test', reasoning_effort: 'high' },
      { id: 'judge', role: 'judge', model_id: 'ollama/gemma-test', reasoning_effort: 'low' },
    ]
    renderWithProviders(
      <ConfigurationPanel capabilities={capabilitiesFixture} config={config} onChange={onChange} />,
    )

    fireEvent.click(screen.getByRole('button', { name: /apply defaults to all/i }))

    const next = onChange.mock.calls[0][0]
    expect(next.participants).toHaveLength(2)
    expect(next.participants).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ model_id: 'gpt-test', reasoning_effort: 'medium' }),
      ]),
    )
    expect(next.participants.every((participant: { model_id: string }) => participant.model_id === 'gpt-test')).toBe(true)
  })
})
