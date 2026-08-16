import type { Capabilities, Conversation, Run, RunConfiguration, Schedule } from '../types'

export const capabilitiesFixture: Capabilities = {
  models: [
    {
      id: 'gpt-test',
      label: 'GPT Test',
      provider: 'openai',
      reasoning_efforts: ['low', 'medium', 'high'],
      configured: true,
    },
    {
      id: 'ollama/gemma-test',
      label: 'Gemma Test',
      provider: 'ollama',
      reasoning_efforts: ['low', 'medium', 'high'],
      configured: true,
    },
  ],
  execution_modes: [
    { id: 'single', label: 'Single', description: 'One agent.', reviewed: false },
    { id: 'plan', label: 'Plan + Review', description: 'Reviewed plan.', reviewed: true },
    { id: 'judge', label: 'Judge', description: 'Judge review.', reviewed: true },
    { id: 'jury', label: 'Jury', description: 'Jury review.', reviewed: true },
    { id: 'debate', label: 'Debate', description: 'Agent debate.', reviewed: false },
    { id: 'debate_judge', label: 'Debate + Judge', description: 'Reviewed debate.', reviewed: true },
    { id: 'debate_jury', label: 'Debate + Jury', description: 'Jury-reviewed debate.', reviewed: true },
  ],
  reasoning_efforts: ['low', 'medium', 'high'],
  tools: [
    { id: 'current_time', label: 'Current time', description: 'Get time.', read_only: true, unattended: true },
    { id: 'calculator', label: 'Calculator', description: 'Calculate.', read_only: true, unattended: true },
    { id: 'execute_python', label: 'Python sandbox', description: 'Run Python.', read_only: true, unattended: true },
    { id: 'spawn_child_agent', label: 'Child agents', description: 'Delegate.', read_only: false, unattended: true },
  ],
  mcp_servers: [],
  model_providers: [
    { provider: 'openai', configured: true, available: true, model_count: 1, last_refreshed_at: null, error: null },
    { provider: 'gemini', configured: false, available: false, model_count: 0, last_refreshed_at: null, error: null },
    { provider: 'ollama', configured: true, available: true, model_count: 1, last_refreshed_at: null, error: null },
  ],
  defaults: {
    model_id: 'gpt-test',
    execution_mode: 'single',
    reasoning_effort: 'medium',
    enabled_tools: ['spawn_child_agent'],
    jury_size: 3,
    debate_participants: 3,
    debate_rounds: 2,
    max_review_attempts: 3,
  },
  limits: {
    max_jury_size: 5,
    max_debate_participants: 5,
    max_debate_rounds: 3,
    max_review_attempts: 5,
  },
}

export const conversationFixture: Conversation = {
  id: 'conversation-1',
  title: 'Test conversation',
  defaults: {},
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

export const runConfigFixture: RunConfiguration = {
  execution_mode: 'single',
  model_id: 'gpt-test',
  reasoning_effort: 'medium',
  participants: [
    { id: 'primary', role: 'primary', model_id: 'gpt-test', reasoning_effort: 'medium' },
  ],
  enabled_tools: [],
  enabled_mcp_servers: [],
  jury_size: 3,
  debate_participants: 3,
  debate_rounds: 2,
  max_review_attempts: 3,
}

export const runFixture: Run = {
  id: 'run-1',
  conversation_id: conversationFixture.id,
  schedule_id: null,
  parent_run_id: null,
  source_type: 'chat',
  status: 'succeeded',
  prompt: 'Question',
  config: runConfigFixture,
  final_output: 'Answer',
  error_code: null,
  error_message: null,
  created_at: '2026-01-01T00:00:00Z',
  started_at: '2026-01-01T00:00:01Z',
  finished_at: '2026-01-01T00:00:02Z',
  steps: [],
}

export const scheduleFixture: Schedule = {
  id: 'schedule-1',
  name: 'Morning brief',
  prompt: 'Plan my day',
  enabled: true,
  schedule_type: 'cron',
  schedule_config: { expression: '0 8 * * *' },
  timezone: 'America/Los_Angeles',
  conversation_id: null,
  run_config: runConfigFixture,
  next_run_at: null,
  last_run_at: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}
