import type {
  Capabilities,
  ExecutionMode,
  Participant,
  ReasoningEffort,
  RunConfiguration,
} from './types'

export function initialConfig(capabilities: Capabilities): RunConfiguration {
  const configuredDefault = capabilities.models.find(
    (model) => model.id === capabilities.defaults.model_id && model.configured,
  )
  const selectedModel =
    configuredDefault?.id ??
    capabilities.models.find((model) => model.configured)?.id ??
    capabilities.defaults.model_id
  const config: RunConfiguration = {
    execution_mode: capabilities.defaults.execution_mode,
    model_id: selectedModel,
    reasoning_effort: capabilities.defaults.reasoning_effort,
    participants: [],
    enabled_tools: [],
    enabled_mcp_servers: [],
    jury_size: capabilities.defaults.jury_size,
    debate_participants: capabilities.defaults.debate_participants,
    debate_rounds: capabilities.defaults.debate_rounds,
    max_review_attempts: capabilities.defaults.max_review_attempts,
  }
  config.participants = buildParticipants(
    config.execution_mode,
    config.model_id,
    config.reasoning_effort,
    config.jury_size,
    config.debate_participants,
  )
  return config
}

export function reconcileConfig(
  config: RunConfiguration,
  capabilities: Capabilities,
): RunConfiguration {
  const available = new Set(capabilities.models.map((model) => model.id))
  const fallback = available.has(capabilities.defaults.model_id)
    ? capabilities.defaults.model_id
    : capabilities.models[0]?.id
  if (!fallback) return config
  const modelId = available.has(config.model_id) ? config.model_id : fallback
  const participants = config.participants.map((participant) =>
    available.has(participant.model_id)
      ? participant
      : { ...participant, model_id: fallback },
  )
  const changed =
    modelId !== config.model_id ||
    participants.some((participant, index) => participant !== config.participants[index])
  return changed ? { ...config, model_id: modelId, participants } : config
}

export function buildParticipants(
  mode: ExecutionMode,
  modelId: string,
  reasoningEffort: ReasoningEffort,
  jurySize: number,
  debateParticipants: number,
  previous: Participant[] = [],
): Participant[] {
  const roles: Pick<Participant, 'id' | 'role'>[] = []
  if (mode === 'single' || mode === 'judge' || mode === 'jury') {
    roles.push({ id: 'primary', role: 'primary' })
  }
  if (mode === 'debate' || mode === 'debate_judge' || mode === 'debate_jury') {
    for (let index = 1; index <= debateParticipants; index += 1) {
      roles.push({ id: `debater_${index}`, role: 'debater' })
    }
    roles.push({ id: 'moderator', role: 'moderator' })
  }
  if (mode === 'judge' || mode === 'debate_judge') roles.push({ id: 'judge', role: 'judge' })
  if (mode === 'jury' || mode === 'debate_jury') {
    for (let index = 1; index <= jurySize; index += 1) {
      roles.push({ id: `juror_${index}`, role: 'juror' })
    }
  }
  return roles.map((role) => {
    const existing = previous.find((participant) => participant.id === role.id)
    return existing ?? { ...role, model_id: modelId, reasoning_effort: reasoningEffort }
  })
}

export function minimumCalls(config: {
  execution_mode: ExecutionMode
  jury_size: number
  debate_participants: number
  debate_rounds: number
  max_review_attempts: number
}): { minimum: number; maximum: number } {
  const debate = config.debate_participants * config.debate_rounds + 1
  const reviewers = config.execution_mode.endsWith('jury') || config.execution_mode === 'jury'
    ? config.jury_size
    : 1
  if (config.execution_mode === 'single') return { minimum: 1, maximum: 1 }
  if (config.execution_mode === 'debate') return { minimum: debate, maximum: debate }
  if (config.execution_mode === 'judge' || config.execution_mode === 'jury') {
    const perAttempt = 1 + reviewers
    return { minimum: perAttempt, maximum: perAttempt * config.max_review_attempts }
  }
  const remediation = config.debate_participants + 1 + reviewers
  return {
    minimum: debate + reviewers,
    maximum: debate + reviewers + remediation * (config.max_review_attempts - 1),
  }
}
