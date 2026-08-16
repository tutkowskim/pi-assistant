import { createTheme } from '@mui/material/styles'

export const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#69d7c4' },
    secondary: { main: '#ffbd70' },
    background: { default: '#0b111d', paper: '#111b2b' },
    success: { main: '#72db9c' },
    warning: { main: '#f6c76f' },
    error: { main: '#ff7d8c' },
  },
  typography: {
    fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    h1: { fontWeight: 720, letterSpacing: '-0.04em' },
    h2: { fontWeight: 680, letterSpacing: '-0.03em' },
    h3: { fontWeight: 650, letterSpacing: '-0.02em' },
    button: { textTransform: 'none', fontWeight: 650 },
  },
  shape: { borderRadius: 14 },
  components: {
    MuiPaper: { styleOverrides: { root: { backgroundImage: 'none' } } },
    MuiButton: { defaultProps: { disableElevation: true } },
  },
})

