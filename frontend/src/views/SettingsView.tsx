import WarningAmberRounded from '@mui/icons-material/WarningAmberRounded'
import { Alert, Box, Chip, Paper, Stack, Typography } from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import type { Capabilities } from '../types'

export function SettingsView({ capabilities }: { capabilities: Capabilities }) {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })
  return (
    <Box className="page-view">
      <Typography variant="overline" color="primary.light">System</Typography>
      <Typography variant="h3">Small machine, clear controls.</Typography>
      <Typography color="text.secondary" mt={1} maxWidth={640}>
        This instance has no accounts and is intended for your trusted home network.
      </Typography>
      <Box className="settings-grid" mt={4}>
        <Paper variant="outlined" className="settings-card">
          <Typography variant="overline" color="text.secondary">Backend</Typography>
          <Typography variant="h5" mt={0.5}>{health.data?.status ?? 'Checking…'}</Typography>
          <Stack spacing={1} mt={2}>
            <Stack direction="row" justifyContent="space-between"><Typography color="text.secondary">Version</Typography><Typography>{String(health.data?.version ?? '—')}</Typography></Stack>
            <Stack direction="row" justifyContent="space-between"><Typography color="text.secondary">Timezone</Typography><Typography>{String(health.data?.timezone ?? '—')}</Typography></Stack>
            <Stack direction="row" justifyContent="space-between"><Typography color="text.secondary">OpenAI key</Typography><Chip size="small" color={health.data?.openai_configured ? 'success' : 'warning'} label={health.data?.openai_configured ? 'Configured' : 'Missing'} /></Stack>
            <Stack direction="row" justifyContent="space-between"><Typography color="text.secondary">Gemini key</Typography><Chip size="small" color={health.data?.gemini_configured ? 'success' : 'warning'} label={health.data?.gemini_configured ? 'Configured' : 'Missing'} /></Stack>
            <Stack direction="row" justifyContent="space-between"><Typography color="text.secondary">Ollama endpoint</Typography><Chip size="small" color={health.data?.ollama_configured ? 'success' : 'warning'} label={health.data?.ollama_configured ? 'Configured' : 'Missing'} /></Stack>
            <Stack direction="row" justifyContent="space-between"><Typography color="text.secondary">Discovered models</Typography><Typography>{String(health.data?.discovered_models ?? '—')}</Typography></Stack>
          </Stack>
        </Paper>
        <Paper variant="outlined" className="settings-card">
          <Typography variant="overline" color="text.secondary">Available models</Typography>
          <Stack spacing={1} mt={1}>
            {capabilities.models.map((model) => (
              <Chip
                key={model.id}
                variant="outlined"
                color={model.configured ? 'default' : 'warning'}
                label={`${model.label} · ${model.provider}${model.configured ? '' : ' · not configured'}`}
              />
            ))}
          </Stack>
        </Paper>
        <Paper variant="outlined" className="settings-card">
          <Typography variant="overline" color="text.secondary">Model discovery</Typography>
          <Stack spacing={1.5} mt={1}>
            {capabilities.model_providers.map((provider) => (
              <Stack key={provider.provider} direction="row" justifyContent="space-between" alignItems="center">
                <Box>
                  <Typography fontWeight={700}>{provider.provider}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {provider.model_count} available
                  </Typography>
                </Box>
                <Chip
                  size="small"
                  color={provider.error ? 'warning' : provider.available ? 'success' : 'default'}
                  label={provider.error ? 'Last refresh failed' : provider.available ? 'Connected' : 'Not configured'}
                />
              </Stack>
            ))}
          </Stack>
        </Paper>
        <Paper variant="outlined" className="settings-card">
          <Typography variant="overline" color="text.secondary">Local tools</Typography>
          <Stack spacing={1.5} mt={1}>
            {capabilities.tools.map((tool) => (
              <Box key={tool.id}>
                <Typography fontWeight={700}>{tool.label}</Typography>
                <Typography variant="body2" color="text.secondary">{tool.description}</Typography>
              </Box>
            ))}
          </Stack>
        </Paper>
        <Paper variant="outlined" className="settings-card">
          <Typography variant="overline" color="text.secondary">MCP servers</Typography>
          <Stack spacing={1.5} mt={1}>
            {capabilities.mcp_servers.length === 0 ? (
              <Typography variant="body2" color="text.secondary">None configured</Typography>
            ) : capabilities.mcp_servers.map((server) => (
              <Box key={server.id}>
                <Typography fontWeight={700}>{server.label}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {server.description || server.transport}
                </Typography>
              </Box>
            ))}
          </Stack>
        </Paper>
        <Alert severity="warning" icon={<WarningAmberRounded />}>
          Do not expose this no-authentication service directly to the public internet.
        </Alert>
      </Box>
    </Box>
  )
}
