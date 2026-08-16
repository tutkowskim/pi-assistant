export type ExecutionMode =
  | 'single'
  | 'judge'
  | 'jury'
  | 'debate'
  | 'debate_judge'
  | 'debate_jury'

export type ReasoningEffort = 'low' | 'medium' | 'high'

export interface Participant {
  id: string
  role: 'primary' | 'judge' | 'juror' | 'debater' | 'moderator'
  model_id: string
  reasoning_effort: ReasoningEffort
}

export interface Capabilities {
  models: {
    id: string
    label: string
    provider: 'openai' | 'gemini' | 'ollama'
    reasoning_efforts: ReasoningEffort[]
    configured: boolean
  }[]
  execution_modes: {
    id: ExecutionMode
    label: string
    description: string
    reviewed: boolean
  }[]
  reasoning_efforts: ReasoningEffort[]
  tools: {
    id: string
    label: string
    description: string
    read_only: boolean
    unattended: boolean
  }[]
  mcp_servers: {
    id: string
    label: string
    description: string
    transport: 'streamable_http'
  }[]
  model_providers: {
    provider: 'openai' | 'gemini' | 'ollama'
    configured: boolean
    available: boolean
    model_count: number
    last_refreshed_at: string | null
    error: string | null
  }[]
  defaults: {
    model_id: string
    execution_mode: ExecutionMode
    reasoning_effort: ReasoningEffort
    jury_size: number
    debate_participants: number
    debate_rounds: number
    max_review_attempts: number
  }
  limits: {
    max_jury_size: number
    max_debate_participants: number
    max_debate_rounds: number
    max_review_attempts: number
  }
}

export interface Conversation {
  id: string
  title: string
  defaults: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  conversation_id: string
  run_id: string | null
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface RunStep {
  id: string
  sequence: number
  participant_id: string
  role: string
  model_id: string
  reasoning_effort: ReasoningEffort
  review_attempt: number
  debate_round: number | null
  status: string
  output: string | null
  verdict: {
    verdict: 'correct' | 'incorrect'
    summary: string
    issues: string[]
    retry_instructions: string[]
  } | null
  usage: Record<string, number | null>
  created_at: string
}

export interface Run {
  id: string
  conversation_id: string | null
  schedule_id: string | null
  source_type: string
  status: string
  prompt: string
  config: RunConfiguration
  final_output: string | null
  error_code: string | null
  error_message: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  steps: RunStep[]
}

export interface RunConfiguration {
  execution_mode: ExecutionMode
  model_id: string
  reasoning_effort: ReasoningEffort
  participants: Participant[]
  enabled_tools: string[]
  enabled_mcp_servers: string[]
  jury_size: number
  debate_participants: number
  debate_rounds: number
  max_review_attempts: number
}

export interface Schedule {
  id: string
  name: string
  prompt: string
  enabled: boolean
  schedule_type: 'once' | 'interval' | 'cron'
  schedule_config: Record<string, unknown>
  timezone: string
  conversation_id: string | null
  run_config: RunConfiguration
  next_run_at: string | null
  last_run_at: string | null
  created_at: string
  updated_at: string
}
