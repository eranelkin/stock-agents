import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'

export default function RunPage() {
  return (
    <Box
      sx={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 'calc(100vh - 56px)',
      }}
    >
      <Typography variant="h5" color="text.secondary">
        Soon it would be ready
      </Typography>
    </Box>
  )
}
