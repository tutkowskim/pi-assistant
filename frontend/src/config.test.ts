import { describe, expect, it } from 'vitest'
import { buildParticipants, initialConfig, minimumCalls, reconcileConfig } from './config'
import { capabilitiesFixture } from './test/fixtures'

describe('participant layouts', () => {
  it('builds debate plus jury participants', () => {
    const participants = buildParticipants('debate_jury', 'model-a', 'medium', 3, 2)
    expect(participants.map((participant) => participant.id)).toEqual([
      'debater_1',
      'debater_2',
      'moderator',
      'juror_1',
      'juror_2',
      'juror_3',
    ])
  })

  it('preserves individual model overrides', () => {
    const original = buildParticipants('judge', 'model-a', 'medium', 3, 3)
    original[1].model_id = 'model-b'
    const rebuilt = buildParticipants('judge', 'model-a', 'medium', 3, 3, original)
    expect(rebuilt[1].model_id).toBe('model-b')
  })
})

describe('call estimates', () => {
  it('includes hybrid remediation attempts', () => {
    expect(
      minimumCalls({
        execution_mode: 'debate_judge',
        jury_size: 3,
        debate_participants: 3,
        debate_rounds: 2,
        max_review_attempts: 3,
      }),
    ).toEqual({ minimum: 8, maximum: 18 })
  })
})

describe('run configuration lifecycle', () => {
  it('initializes the default participant from capabilities', () => {
    const config = initialConfig(capabilitiesFixture)

    expect(config.model_id).toBe('gpt-test')
    expect(config.participants).toEqual([
      {
        id: 'primary',
        role: 'primary',
        model_id: 'gpt-test',
        reasoning_effort: 'medium',
      },
    ])
  })

  it('replaces models that disappear during provider refresh', () => {
    const config = initialConfig(capabilitiesFixture)
    config.model_id = 'removed-model'
    config.participants[0].model_id = 'removed-model'

    const reconciled = reconcileConfig(config, capabilitiesFixture)

    expect(reconciled.model_id).toBe('gpt-test')
    expect(reconciled.participants[0].model_id).toBe('gpt-test')
  })
})
