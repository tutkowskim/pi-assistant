import AddRounded from '@mui/icons-material/AddRounded'
import CloseRounded from '@mui/icons-material/CloseRounded'
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded'
import ExpandMoreRounded from '@mui/icons-material/ExpandMoreRounded'
import PlayArrowRounded from '@mui/icons-material/PlayArrowRounded'
import ScheduleRounded from '@mui/icons-material/ScheduleRounded'
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { ConfigurationPanel } from '../components/ConfigurationPanel'
import { initialConfig, reconcileConfig } from '../config'
import type { Capabilities, RunConfiguration, Schedule } from '../types'
import { formatDate } from '../utils'

export function AutomationsView({ capabilities }: { capabilities: Capabilities }) {
  const queryClient = useQueryClient()
  const schedules = useQuery({ queryKey: ['schedules'], queryFn: api.schedules })
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('Morning brief')
  const [prompt, setPrompt] = useState('Summarize what I should focus on today.')
  const [scheduleType, setScheduleType] = useState<'once' | 'interval' | 'cron'>('cron')
  const [scheduleValue, setScheduleValue] = useState('0 8 * * *')
  const [timezone, setTimezone] = useState('America/Los_Angeles')
  const [config, setConfig] = useState<RunConfiguration>(() => initialConfig(capabilities))

  useEffect(() => {
    setConfig((current) => reconcileConfig(current, capabilities))
  }, [capabilities])

  const create = useMutation({
    mutationFn: () =>
      api.createSchedule({
        name,
        prompt,
        enabled: true,
        schedule_type: scheduleType,
        schedule_config:
          scheduleType === 'cron'
            ? { expression: scheduleValue }
            : scheduleType === 'interval'
              ? { seconds: Number(scheduleValue) }
              : { run_at: new Date(scheduleValue).toISOString() },
        timezone,
        conversation_id: null,
        run_config: config,
      }),
    onSuccess: () => {
      setShowForm(false)
      void queryClient.invalidateQueries({ queryKey: ['schedules'] })
    },
  })

  return (
    <Box className="page-view">
      <Stack direction="row" alignItems="flex-end" justifyContent="space-between" gap={2}>
        <Box>
          <Typography variant="overline" color="primary.light">Automations</Typography>
          <Typography variant="h3">Run on your time.</Typography>
          <Typography color="text.secondary" mt={1}>
            Saved prompts use the same agents, tools, reviews, and retry rules as chat.
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddRounded />} onClick={() => setShowForm(true)}>
          New schedule
        </Button>
      </Stack>

      {showForm && (
        <Paper variant="outlined" className="schedule-form">
          <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
            <Typography variant="h6">New scheduled prompt</Typography>
            <IconButton aria-label="Close schedule form" onClick={() => setShowForm(false)}>
              <CloseRounded />
            </IconButton>
          </Stack>
          <Stack spacing={2}>
            <TextField label="Name" value={name} onChange={(event) => setName(event.target.value)} />
            <TextField multiline minRows={3} label="Prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} />
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
              <FormControl fullWidth>
                <InputLabel id="schedule-type-label">Schedule type</InputLabel>
                <Select
                  labelId="schedule-type-label"
                  label="Schedule type"
                  value={scheduleType}
                  onChange={(event) => {
                    const next = event.target.value as typeof scheduleType
                    setScheduleType(next)
                    setScheduleValue(
                      next === 'cron'
                        ? '0 8 * * *'
                        : next === 'interval'
                          ? '3600'
                          : new Date(Date.now() + 3600000).toISOString().slice(0, 16),
                    )
                  }}
                >
                  <MenuItem value="once">Once</MenuItem>
                  <MenuItem value="interval">Interval</MenuItem>
                  <MenuItem value="cron">Cron</MenuItem>
                </Select>
              </FormControl>
              <TextField
                fullWidth
                label={scheduleType === 'cron' ? 'Cron expression' : scheduleType === 'interval' ? 'Seconds' : 'Run at'}
                type={scheduleType === 'once' ? 'datetime-local' : 'text'}
                value={scheduleValue}
                onChange={(event) => setScheduleValue(event.target.value)}
              />
              <TextField fullWidth label="Timezone" value={timezone} onChange={(event) => setTimezone(event.target.value)} />
            </Stack>
            <Accordion disableGutters elevation={0}>
              <AccordionSummary expandIcon={<ExpandMoreRounded />}>
                <Typography fontWeight={650}>Agent setup</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <ConfigurationPanel capabilities={capabilities} config={config} onChange={setConfig} />
              </AccordionDetails>
            </Accordion>
            {create.error && <Alert severity="error">{create.error.message}</Alert>}
            <Button
              variant="contained"
              size="large"
              disabled={create.isPending || capabilities.models.length === 0}
              onClick={() => create.mutate()}
            >
              Save schedule
            </Button>
          </Stack>
        </Paper>
      )}

      <Stack spacing={1.5} mt={4}>
        {schedules.isLoading && <CircularProgress />}
        {!schedules.data?.length && !schedules.isLoading && (
          <Paper variant="outlined" className="empty-list">
            <ScheduleRounded color="primary" />
            <Typography variant="h6">No schedules yet</Typography>
            <Typography color="text.secondary">Your automated prompts will appear here.</Typography>
          </Paper>
        )}
        {schedules.data?.map((schedule: Schedule) => (
          <Paper key={schedule.id} variant="outlined" className="schedule-card">
            <Stack direction={{ xs: 'column', md: 'row' }} alignItems={{ md: 'center' }} justifyContent="space-between" gap={2}>
              <Box>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="h6">{schedule.name}</Typography>
                  <Chip size="small" color={schedule.enabled ? 'success' : 'default'} label={schedule.enabled ? 'Active' : 'Paused'} />
                </Stack>
                <Typography color="text.secondary" mt={0.5}>{schedule.prompt}</Typography>
                <Typography variant="caption" color="text.secondary">
                  Next: {formatDate(schedule.next_run_at)} · {schedule.timezone} · {schedule.run_config.execution_mode.replaceAll('_', ' + ')}
                </Typography>
              </Box>
              <Stack direction="row" spacing={1}>
                <Button startIcon={<PlayArrowRounded />} onClick={() => void api.runSchedule(schedule.id)}>
                  Run now
                </Button>
                <IconButton
                  aria-label={`Delete ${schedule.name}`}
                  onClick={async () => {
                    await api.deleteSchedule(schedule.id)
                    void queryClient.invalidateQueries({ queryKey: ['schedules'] })
                  }}
                >
                  <DeleteOutlineRounded />
                </IconButton>
              </Stack>
            </Stack>
          </Paper>
        ))}
      </Stack>
    </Box>
  )
}
