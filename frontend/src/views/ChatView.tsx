import CloseRounded from '@mui/icons-material/CloseRounded'
import ForumRounded from '@mui/icons-material/ForumRounded'
import SendRounded from '@mui/icons-material/SendRounded'
import StopRounded from '@mui/icons-material/StopRounded'
import TuneRounded from '@mui/icons-material/TuneRounded'
import { Alert, Box, Button, Chip, IconButton, Paper, Stack, TextField, Tooltip, Typography } from '@mui/material'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { api, subscribeToRun } from '../api'
import { ConfigurationPanel } from '../components/ConfigurationPanel'
import { RunTimeline } from '../components/RunTimeline'
import { initialConfig, reconcileConfig } from '../config'
import type { Capabilities, Conversation, Message, Run, RunConfiguration } from '../types'
import { isTerminalRun } from '../utils'

interface ChatViewProps {
  capabilities: Capabilities
  conversation: Conversation | null
}

export function ChatView({ capabilities, conversation }: ChatViewProps) {
  const queryClient = useQueryClient()
  const [prompt, setPrompt] = useState('')
  const [config, setConfig] = useState<RunConfiguration>(() => initialConfig(capabilities))
  const [run, setRun] = useState<Run | null>(null)
  const [error, setError] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const messages = useQuery({
    queryKey: ['messages', conversation?.id],
    queryFn: () => api.messages(conversation!.id),
    enabled: Boolean(conversation),
  })

  useEffect(() => {
    setRun(null)
    setError('')
  }, [conversation?.id])

  useEffect(() => {
    setConfig((current) => reconcileConfig(current, capabilities))
  }, [capabilities])

  const running = run && !isTerminalRun(run.status)

  const send = async () => {
    if (!conversation || !prompt.trim() || running) return
    setError('')
    try {
      const accepted = await api.createRun(conversation.id, prompt.trim(), config)
      setPrompt('')
      void queryClient.invalidateQueries({ queryKey: ['conversations'] })
      const initial = await api.run(accepted.id)
      setRun(initial)
      subscribeToRun(
        accepted.id,
        setRun,
        () => {
          void queryClient.invalidateQueries({ queryKey: ['messages', conversation.id] })
          void queryClient.invalidateQueries({ queryKey: ['conversations'] })
        },
        (cause) => setError(cause.message),
      )
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to start run')
    }
  }

  if (!conversation) {
    return (
      <Box className="empty-state">
        <Box className="hero-orb"><ForumRounded /></Box>
        <Typography variant="h3">A private place to think.</Typography>
        <Typography color="text.secondary" maxWidth={520} textAlign="center">
          Start a conversation, choose how many perspectives you want, and keep every answer on
          your Raspberry Pi.
        </Typography>
      </Box>
    )
  }

  return (
    <Box className="chat-view">
      <Box className="chat-header">
        <Box>
          <Typography variant="overline" color="primary.light">
            Conversation
          </Typography>
          <Typography variant="h5" fontWeight={720}>
            {conversation.title}
          </Typography>
        </Box>
        <Button
          variant={showSettings ? 'contained' : 'outlined'}
          startIcon={showSettings ? <CloseRounded /> : <TuneRounded />}
          onClick={() => setShowSettings((value) => !value)}
        >
          {showSettings ? 'Close setup' : 'Run setup'}
        </Button>
      </Box>

      {showSettings && (
        <Paper variant="outlined" className="configuration-panel">
          <ConfigurationPanel capabilities={capabilities} config={config} onChange={setConfig} />
        </Paper>
      )}

      <Box className="message-list">
        {!messages.data?.length && (
          <Box className="welcome-card">
            <Typography variant="h4">What would you like to work through?</Typography>
            <Typography color="text.secondary">
              Use Single for speed, a review mode for verification, or Debate when competing
              perspectives will improve the answer.
            </Typography>
          </Box>
        )}
        {messages.data?.map((message: Message) => (
          <Box key={message.id} className={`message ${message.role}`}>
            <Typography variant="caption" color="text.secondary" className="message-label">
              {message.role === 'user' ? 'You' : 'Assistant'}
            </Typography>
            {message.role === 'assistant' ? (
              <ReactMarkdown>{message.content}</ReactMarkdown>
            ) : (
              <Typography whiteSpace="pre-wrap">{message.content}</Typography>
            )}
          </Box>
        ))}
        {run && <RunTimeline run={run} />}
        {run?.final_output && run.status === 'succeeded' &&
          !messages.data?.some((message) => message.run_id === run.id) && (
            <Box className="message assistant">
              <Typography variant="caption" color="text.secondary" className="message-label">
                Assistant
              </Typography>
              <ReactMarkdown>{run.final_output}</ReactMarkdown>
            </Box>
          )}
        {error && <Alert severity="error">{error}</Alert>}
      </Box>

      <Paper
        component="form"
        className="composer"
        onSubmit={(event) => {
          event.preventDefault()
          void send()
        }}
      >
        <TextField
          fullWidth
          multiline
          maxRows={7}
          placeholder="Ask anything…"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              void send()
            }
          }}
          slotProps={{ input: { disableUnderline: true } }}
          variant="standard"
        />
        <Stack direction="row" alignItems="center" justifyContent="space-between" mt={1}>
          <Stack direction="row" spacing={0.7} alignItems="center">
            <Chip size="small" label={config.execution_mode.replaceAll('_', ' + ')} />
            <Typography variant="caption" color="text.secondary">
              {config.participants.length} agents configured
            </Typography>
          </Stack>
          {running ? (
            <Tooltip title="Stop run">
              <IconButton color="warning" onClick={() => void api.cancelRun(run.id)}>
                <StopRounded />
              </IconButton>
            </Tooltip>
          ) : (
            <IconButton
              aria-label="Send message"
              type="submit"
              color="primary"
              disabled={!prompt.trim() || capabilities.models.length === 0}
              className="send-button"
            >
              <SendRounded />
            </IconButton>
          )}
        </Stack>
      </Paper>
    </Box>
  )
}
