import CalculateRounded from '@mui/icons-material/CalculateRounded'
import CodeRounded from '@mui/icons-material/CodeRounded'
import HubRounded from '@mui/icons-material/HubRounded'
import MoreTimeRounded from '@mui/icons-material/MoreTimeRounded'
import RefreshRounded from '@mui/icons-material/RefreshRounded'
import {
  Alert,
  Box,
  Button,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Typography,
} from '@mui/material'
import { buildParticipants, minimumCalls } from '../config'
import type {
  Capabilities,
  ExecutionMode,
  Participant,
  ReasoningEffort,
  RunConfiguration,
} from '../types'

interface ConfigurationPanelProps {
  capabilities: Capabilities
  config: RunConfiguration
  onChange: (config: RunConfiguration) => void
}

export function ConfigurationPanel({
  capabilities,
  config,
  onChange,
}: ConfigurationPanelProps) {
  const reviewed = capabilities.execution_modes.find(
    (mode) => mode.id === config.execution_mode,
  )?.reviewed
  const debate = config.execution_mode.startsWith('debate')
  const jury = config.execution_mode === 'jury' || config.execution_mode === 'debate_jury'
  const estimate = minimumCalls(config)

  const updateShape = (changes: Partial<RunConfiguration>) => {
    const next = { ...config, ...changes }
    next.participants = buildParticipants(
      next.execution_mode,
      next.model_id,
      next.reasoning_effort,
      next.jury_size,
      next.debate_participants,
      config.participants,
    )
    onChange(next)
  }

  const updateParticipant = (id: string, changes: Partial<Participant>) => {
    onChange({
      ...config,
      participants: config.participants.map((participant) =>
        participant.id === id ? { ...participant, ...changes } : participant,
      ),
    })
  }

  const applyModelToAll = () => {
    onChange({
      ...config,
      participants: config.participants.map((participant) => ({
        ...participant,
        model_id: config.model_id,
        reasoning_effort: config.reasoning_effort,
      })),
    })
  }

  return (
    <Stack spacing={2.2}>
      {capabilities.models.length === 0 && (
        <Alert severity="warning">
          No models are currently available. Configure a provider or start an Ollama model.
        </Alert>
      )}
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
        <FormControl fullWidth size="small">
          <InputLabel id="mode-label">Execution mode</InputLabel>
          <Select
            labelId="mode-label"
            label="Execution mode"
            value={config.execution_mode}
            onChange={(event) =>
              updateShape({ execution_mode: event.target.value as ExecutionMode })
            }
          >
            {capabilities.execution_modes.map((mode) => (
              <MenuItem key={mode.id} value={mode.id}>
                {mode.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl fullWidth size="small">
          <InputLabel id="default-model-label">Default model</InputLabel>
          <Select
            labelId="default-model-label"
            label="Default model"
            value={config.model_id}
            onChange={(event) => updateShape({ model_id: event.target.value })}
          >
            {capabilities.models.map((model) => (
              <MenuItem key={model.id} value={model.id} disabled={!model.configured}>
                {model.label}{model.configured ? '' : ' · not configured'}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl fullWidth size="small">
          <InputLabel id="effort-label">Default effort</InputLabel>
          <Select
            labelId="effort-label"
            label="Default effort"
            value={config.reasoning_effort}
            onChange={(event) =>
              updateShape({ reasoning_effort: event.target.value as ReasoningEffort })
            }
          >
            {capabilities.reasoning_efforts.map((effort) => (
              <MenuItem key={effort} value={effort}>
                {effort}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Stack>

      <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap>
        {jury && (
          <FormControl size="small" sx={{ minWidth: 145 }}>
            <InputLabel id="jury-size-label">Jurors</InputLabel>
            <Select
              labelId="jury-size-label"
              label="Jurors"
              value={config.jury_size}
              onChange={(event) => updateShape({ jury_size: Number(event.target.value) })}
            >
              {[3, 5]
                .filter((size) => size <= capabilities.limits.max_jury_size)
                .map((size) => (
                  <MenuItem key={size} value={size}>
                    {size}
                  </MenuItem>
                ))}
            </Select>
          </FormControl>
        )}
        {debate && (
          <>
            <FormControl size="small" sx={{ minWidth: 145 }}>
              <InputLabel id="debaters-label">Debaters</InputLabel>
              <Select
                labelId="debaters-label"
                label="Debaters"
                value={config.debate_participants}
                onChange={(event) =>
                  updateShape({ debate_participants: Number(event.target.value) })
                }
              >
                {Array.from(
                  { length: capabilities.limits.max_debate_participants - 1 },
                  (_, index) => index + 2,
                ).map((size) => (
                  <MenuItem key={size} value={size}>
                    {size}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 145 }}>
              <InputLabel id="rounds-label">Debate rounds</InputLabel>
              <Select
                labelId="rounds-label"
                label="Debate rounds"
                value={config.debate_rounds}
                onChange={(event) => updateShape({ debate_rounds: Number(event.target.value) })}
              >
                {Array.from(
                  { length: capabilities.limits.max_debate_rounds - 1 },
                  (_, index) => index + 2,
                ).map((rounds) => (
                  <MenuItem key={rounds} value={rounds}>
                    {rounds}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </>
        )}
        {reviewed && (
          <FormControl size="small" sx={{ minWidth: 165 }}>
            <InputLabel id="attempts-label">Review attempts</InputLabel>
            <Select
              labelId="attempts-label"
              label="Review attempts"
              value={config.max_review_attempts}
              onChange={(event) =>
                updateShape({ max_review_attempts: Number(event.target.value) })
              }
            >
              {Array.from(
                { length: capabilities.limits.max_review_attempts },
                (_, index) => index + 1,
              ).map((attempts) => (
                <MenuItem key={attempts} value={attempts}>
                  {attempts}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
      </Stack>

      <Paper variant="outlined" className="estimate-card">
        <Stack direction="row" justifyContent="space-between" alignItems="center" gap={2}>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Estimated model passes
            </Typography>
            <Typography variant="h6">
              {estimate.minimum === estimate.maximum
                ? estimate.minimum
                : `${estimate.minimum}–${estimate.maximum}`}
            </Typography>
          </Box>
          <Button size="small" onClick={applyModelToAll} startIcon={<RefreshRounded />}>
            Apply defaults to all
          </Button>
        </Stack>
      </Paper>

      <Box>
        <Typography variant="overline" color="text.secondary">
          Participants
        </Typography>
        <Stack spacing={1} mt={0.5}>
          {config.participants.map((participant) => (
            <Paper key={participant.id} variant="outlined" className="participant-row">
              <Box minWidth={120}>
                <Typography variant="body2" fontWeight={700}>
                  {participant.id.replaceAll('_', ' ')}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {participant.role}
                </Typography>
              </Box>
              <FormControl size="small" sx={{ minWidth: 165, flex: 1 }}>
                <Select
                  aria-label={`${participant.id} model`}
                  value={participant.model_id}
                  onChange={(event) =>
                    updateParticipant(participant.id, { model_id: event.target.value })
                  }
                >
                  {capabilities.models.map((model) => (
                    <MenuItem key={model.id} value={model.id} disabled={!model.configured}>
                      {model.label}{model.configured ? '' : ' · not configured'}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 115 }}>
                <Select
                  aria-label={`${participant.id} reasoning effort`}
                  value={participant.reasoning_effort}
                  onChange={(event) =>
                    updateParticipant(participant.id, {
                      reasoning_effort: event.target.value as ReasoningEffort,
                    })
                  }
                >
                  {capabilities.reasoning_efforts.map((effort) => (
                    <MenuItem key={effort} value={effort}>
                      {effort}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Paper>
          ))}
        </Stack>
      </Box>

      <Box>
        <Typography variant="overline" color="text.secondary">
          Enabled tools
        </Typography>
        <Stack direction="row" spacing={1} mt={0.5} flexWrap="wrap" useFlexGap>
          {capabilities.tools.map((tool) => {
            const selected = config.enabled_tools.includes(tool.id)
            return (
              <Chip
                key={tool.id}
                clickable
                color={selected ? 'primary' : 'default'}
                variant={selected ? 'filled' : 'outlined'}
                icon={
                  tool.id === 'calculator'
                    ? <CalculateRounded />
                    : tool.id === 'execute_python'
                      ? <CodeRounded />
                      : <MoreTimeRounded />
                }
                label={tool.label}
                onClick={() =>
                  onChange({
                    ...config,
                    enabled_tools: selected
                      ? config.enabled_tools.filter((id) => id !== tool.id)
                      : [...config.enabled_tools, tool.id],
                  })
                }
              />
            )
          })}
        </Stack>
      </Box>
      {capabilities.mcp_servers.length > 0 && (
        <Box>
          <Typography variant="overline" color="text.secondary">
            Enabled MCP servers
          </Typography>
          <Stack direction="row" spacing={1} mt={0.5} flexWrap="wrap" useFlexGap>
            {capabilities.mcp_servers.map((server) => {
              const selected = config.enabled_mcp_servers.includes(server.id)
              return (
                <Chip
                  key={server.id}
                  clickable
                  color={selected ? 'secondary' : 'default'}
                  variant={selected ? 'filled' : 'outlined'}
                  icon={<HubRounded />}
                  label={server.label}
                  title={server.description}
                  onClick={() =>
                    onChange({
                      ...config,
                      enabled_mcp_servers: selected
                        ? config.enabled_mcp_servers.filter((id) => id !== server.id)
                        : [...config.enabled_mcp_servers, server.id],
                    })
                  }
                />
              )
            })}
          </Stack>
        </Box>
      )}
    </Stack>
  )
}
