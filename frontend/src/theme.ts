import { createTheme } from '@mui/material/styles'

const theme = createTheme({
  palette: {
    mode: 'dark',
    background: {
      default: '#101010',
      paper: '#101010',
    },
    primary: {
      main: '#1976d2',
    },
    text: {
      primary: '#ffffff',
      secondary: '#9e9e9e',
    },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
  },
  components: {
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#101010',
          boxShadow: 'none',
          borderBottom: '1px solid #1e1e1e',
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          borderColor: '#1e1e1e',
        },
      },
    },
  },
})

export default theme
