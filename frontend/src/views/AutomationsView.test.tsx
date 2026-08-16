import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import { capabilitiesFixture, scheduleFixture } from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { AutomationsView } from './AutomationsView'

vi.mock('../api', () => ({
  api: {
    schedules: vi.fn(),
    createSchedule: vi.fn(),
    runSchedule: vi.fn(),
    deleteSchedule: vi.fn(),
  },
}))

describe('AutomationsView', () => {
  beforeEach(() => {
    vi.mocked(api.schedules).mockResolvedValue([])
    vi.mocked(api.createSchedule).mockResolvedValue(scheduleFixture)
  })

  it('opens and closes the schedule form', async () => {
    renderWithProviders(<AutomationsView capabilities={capabilitiesFixture} />)
    await screen.findByText('No schedules yet')

    fireEvent.click(screen.getByRole('button', { name: 'New schedule' }))
    expect(screen.getByText('New scheduled prompt')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Close schedule form' }))
    expect(screen.queryByText('New scheduled prompt')).not.toBeInTheDocument()
  })

  it('saves a schedule with the current agent configuration', async () => {
    renderWithProviders(<AutomationsView capabilities={capabilitiesFixture} />)
    await screen.findByText('No schedules yet')
    fireEvent.click(screen.getByRole('button', { name: 'New schedule' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save schedule' }))

    await waitFor(() => {
      expect(api.createSchedule).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Morning brief',
          schedule_type: 'cron',
          schedule_config: { expression: '0 8 * * *' },
          run_config: expect.objectContaining({ model_id: 'gpt-test' }),
        }),
      )
    })
  })
})
