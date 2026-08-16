import CheckCircleRounded from '@mui/icons-material/CheckCircleRounded'
import ExpandMoreRounded from '@mui/icons-material/ExpandMoreRounded'
import WarningAmberRounded from '@mui/icons-material/WarningAmberRounded'
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Typography,
} from '@mui/material'
import { useMemo } from 'react'
import type { Run } from '../types'
import { isTerminalRun } from '../utils'

export function RunTimeline({ run }: { run: Run }) {
  const attempts = useMemo(
    () => Array.from(new Set(run.steps.map((step) => step.review_attempt))),
    [run.steps],
  )
  if (!run.steps.length && !isTerminalRun(run.status)) {
    return (
      <Paper variant="outlined" className="run-card">
        <Stack direction="row" alignItems="center" spacing={1.2}>
          <CircularProgress size={18} />
          <Typography variant="body2">Preparing agents…</Typography>
        </Stack>
      </Paper>
    )
  }
  return (
    <Paper variant="outlined" className="run-card">
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1}>
        <Stack direction="row" spacing={1} alignItems="center">
          {run.status === 'succeeded' ? (
            <CheckCircleRounded color="success" fontSize="small" />
          ) : run.status === 'review_failed' || run.status === 'failed' ? (
            <WarningAmberRounded color="warning" fontSize="small" />
          ) : (
            <CircularProgress size={17} />
          )}
          <Typography variant="subtitle2">
            {run.config.execution_mode.replaceAll('_', ' ')} · {run.status.replaceAll('_', ' ')}
          </Typography>
        </Stack>
        <Typography variant="caption" color="text.secondary">
          {run.steps.length} steps
        </Typography>
      </Stack>
      {attempts.map((attempt) => (
        <Accordion key={attempt} disableGutters elevation={0} className="attempt-accordion">
          <AccordionSummary expandIcon={<ExpandMoreRounded />}>
            <Typography variant="body2" fontWeight={650}>
              Attempt {attempt}
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Stack spacing={1}>
              {run.steps
                .filter((step) => step.review_attempt === attempt)
                .map((step) => (
                  <Box key={step.id} className="step-row">
                    <Stack direction="row" justifyContent="space-between" gap={1}>
                      <Typography variant="caption" fontWeight={750} color="primary.light">
                        {step.participant_id.replaceAll('_', ' ')}
                        {step.debate_round ? ` · round ${step.debate_round}` : ''}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {step.model_id} · {step.reasoning_effort}
                      </Typography>
                    </Stack>
                    {step.verdict ? (
                      <Box mt={0.5}>
                        <Chip
                          size="small"
                          color={step.verdict.verdict === 'correct' ? 'success' : 'warning'}
                          label={step.verdict.verdict}
                        />
                        <Typography variant="body2" mt={0.7}>
                          {step.verdict.summary}
                        </Typography>
                        {step.verdict.issues.map((issue) => (
                          <Typography
                            key={issue}
                            variant="caption"
                            display="block"
                            color="text.secondary"
                          >
                            • {issue}
                          </Typography>
                        ))}
                      </Box>
                    ) : (
                      step.output && (
                        <Typography variant="body2" mt={0.5} className="clamped-output">
                          {step.output}
                        </Typography>
                      )
                    )}
                  </Box>
                ))}
            </Stack>
          </AccordionDetails>
        </Accordion>
      ))}
      {run.error_message && (
        <Alert severity={run.status === 'review_failed' ? 'warning' : 'error'} sx={{ mt: 1 }}>
          {run.error_message}
        </Alert>
      )}
    </Paper>
  )
}
