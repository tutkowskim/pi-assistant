import AutoAwesomeRounded from '@mui/icons-material/AutoAwesomeRounded'
import { Box, Stack, Typography } from '@mui/material'

export function Brand() {
  return (
    <Stack direction="row" spacing={1.4} alignItems="center">
      <Box className="brand-mark">
        <AutoAwesomeRounded fontSize="small" />
      </Box>
      <Box>
        <Typography variant="subtitle1" fontWeight={760} lineHeight={1.1}>
          Pi Assistant
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Private by design
        </Typography>
      </Box>
    </Stack>
  )
}
