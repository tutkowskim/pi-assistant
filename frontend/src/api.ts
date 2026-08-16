import {
  cancelRunApiV1RunsRunIdCancelPost,
  capabilitiesApiV1CapabilitiesGet,
  createConversationApiV1ConversationsPost,
  createConversationRunApiV1ConversationsConversationIdRunsPost,
  createScheduleApiV1SchedulesPost,
  deleteConversationApiV1ConversationsConversationIdDelete,
  deleteScheduleApiV1SchedulesScheduleIdDelete,
  getRunApiV1RunsRunIdGet,
  listConversationsApiV1ConversationsGet,
  listMessagesApiV1ConversationsConversationIdMessagesGet,
  listSchedulesApiV1SchedulesGet,
  readyApiV1HealthReadyGet,
  runScheduleNowApiV1SchedulesScheduleIdRunNowPost,
} from './generated'
import type { ScheduleCreate } from './generated'
import type { Capabilities, Conversation, Message, Run, RunConfiguration, Schedule } from './types'

const API = '/api/v1'
const responseOptions = { responseStyle: 'data', throwOnError: true } as const

function errorMessage(cause: unknown): string {
  if (cause instanceof Error) return cause.message
  if (cause && typeof cause === 'object') {
    const body = cause as {
      detail?: string | Array<{ msg?: string }>
      error?: { message?: string }
      message?: string
    }
    if (body.error?.message) return body.error.message
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) {
      const messages = body.detail.flatMap((item) => item.msg ?? [])
      if (messages.length) return messages.join(', ')
    }
    if (body.message) return body.message
  }
  return 'The API request failed.'
}

async function apiData<T>(request: Promise<unknown>): Promise<T> {
  try {
    return await request as T
  } catch (cause) {
    throw new Error(errorMessage(cause), { cause })
  }
}

export const api = {
  capabilities: () =>
    apiData<Capabilities>(capabilitiesApiV1CapabilitiesGet(responseOptions)),
  conversations: () =>
    apiData<Conversation[]>(listConversationsApiV1ConversationsGet(responseOptions)),
  createConversation: (title = 'New conversation') =>
    apiData<Conversation>(
      createConversationApiV1ConversationsPost({
        ...responseOptions,
        body: { title },
      }),
    ),
  deleteConversation: (id: string) =>
    apiData<void>(
      deleteConversationApiV1ConversationsConversationIdDelete({
        ...responseOptions,
        path: { conversation_id: id },
      }),
    ),
  messages: (id: string) =>
    apiData<Message[]>(
      listMessagesApiV1ConversationsConversationIdMessagesGet({
        ...responseOptions,
        path: { conversation_id: id },
      }),
    ),
  createRun: (conversationId: string, prompt: string, config: RunConfiguration) =>
    apiData<{ id: string; status: string }>(
      createConversationRunApiV1ConversationsConversationIdRunsPost({
        ...responseOptions,
        path: { conversation_id: conversationId },
        body: { prompt, ...config },
      }),
    ),
  run: (id: string) =>
    apiData<Run>(
      getRunApiV1RunsRunIdGet({ ...responseOptions, path: { run_id: id } }),
    ),
  cancelRun: (id: string) =>
    apiData<{ id: string; status: string }>(
      cancelRunApiV1RunsRunIdCancelPost({
        ...responseOptions,
        path: { run_id: id },
      }),
    ),
  schedules: () =>
    apiData<Schedule[]>(listSchedulesApiV1SchedulesGet(responseOptions)),
  createSchedule: (payload: ScheduleCreate) =>
    apiData<Schedule>(
      createScheduleApiV1SchedulesPost({ ...responseOptions, body: payload }),
    ),
  deleteSchedule: (id: string) =>
    apiData<void>(
      deleteScheduleApiV1SchedulesScheduleIdDelete({
        ...responseOptions,
        path: { schedule_id: id },
      }),
    ),
  runSchedule: (id: string) =>
    apiData<{ id: string; status: string }>(
      runScheduleNowApiV1SchedulesScheduleIdRunNowPost({
        ...responseOptions,
        path: { schedule_id: id },
      }),
    ),
  health: () =>
    apiData<Record<string, string | boolean | number>>(readyApiV1HealthReadyGet(responseOptions)),
}

export function subscribeToRun(
  runId: string,
  onSnapshot: (run: Run) => void,
  onDone: () => void,
  onError: (error: Error) => void,
): () => void {
  const source = new EventSource(`${API}/runs/${runId}/events`)
  source.addEventListener('snapshot', (event) => {
    const run = JSON.parse((event as MessageEvent).data) as Run
    onSnapshot(run)
    if (['succeeded', 'review_failed', 'failed', 'cancelled'].includes(run.status)) {
      source.close()
      onDone()
    }
  })
  source.onerror = () => {
    source.close()
    onError(new Error('The live run connection was interrupted.'))
  }
  return () => source.close()
}
