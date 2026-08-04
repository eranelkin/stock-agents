import { useState } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Dialog from '@mui/material/Dialog'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import IconButton from '@mui/material/IconButton'
import Stack from '@mui/material/Stack'
import Tab from '@mui/material/Tab'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Tabs from '@mui/material/Tabs'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import CloseIcon from '@mui/icons-material/Close'
import type { DataTestResult, DataTestSourceName } from '../types/dataTest'

interface DataTestDialogProps {
  open: boolean
  onClose: () => void
  result: DataTestResult | null
  error: string | null
}

const SOURCE_LABELS: Record<DataTestSourceName, string> = {
  interactive_service: 'Interactive Service',
  yahoo_finance: 'Yahoo Finance',
  finnhub: 'Finnhub',
  fmp: 'FMP',
}

const SOURCE_ORDER: DataTestSourceName[] = ['interactive_service', 'yahoo_finance', 'finnhub', 'fmp']

function formatValue(value: number | string | null | undefined): string {
  if (value === null || value === undefined) return 'N/A'
  if (typeof value === 'number') {
    const abs = Math.abs(value)
    const decimals = abs >= 1000 ? 2 : abs >= 1 ? 2 : 4
    return value.toLocaleString(undefined, { maximumFractionDigits: decimals })
  }
  return value
}

export default function DataTestDialog({ open, onClose, result, error }: DataTestDialogProps) {
  const [activeSymbol, setActiveSymbol] = useState<string | null>(null)

  const symbols = result?.symbols ?? []
  const currentSymbol = activeSymbol && symbols.includes(activeSymbol) ? activeSymbol : symbols[0]

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        Data Test — Interactive Service vs. External Sources
        <IconButton onClick={onClose} size="small">
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        {result && (
          <>
            <Stack spacing={1} sx={{ mb: 2 }}>
              {SOURCE_ORDER.filter((s) => result.source_errors[s]).map((s) => (
                <Alert key={s} severity="warning" sx={{ fontSize: '0.8rem' }}>
                  <strong>{SOURCE_LABELS[s]}:</strong> {result.source_errors[s]}
                </Alert>
              ))}
            </Stack>

            {symbols.length > 1 && (
              <Tabs
                value={currentSymbol}
                onChange={(_, val: string) => setActiveSymbol(val)}
                sx={{ mb: 1, minHeight: 36 }}
              >
                {symbols.map((s) => (
                  <Tab key={s} value={s} label={s} sx={{ minHeight: 36, textTransform: 'none' }} />
                ))}
              </Tabs>
            )}

            {currentSymbol && (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Field</TableCell>
                      {SOURCE_ORDER.map((s) => (
                        <TableCell key={s} align="right">
                          {SOURCE_LABELS[s]}
                        </TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {result.fields.map((field) => {
                      const row = result.values[currentSymbol]?.[field.key] ?? {}
                      return (
                        <TableRow key={field.key}>
                          <TableCell component="th" scope="row">
                            {field.label}
                          </TableCell>
                          {SOURCE_ORDER.map((s) => {
                            const value = row[s]
                            const na = value === null || value === undefined
                            return (
                              <TableCell key={s} align="right">
                                {na ? (
                                  <Tooltip title={result.source_errors[s] ?? 'Not available from this source'}>
                                    <Typography variant="body2" color="text.disabled" component="span">
                                      N/A
                                    </Typography>
                                  </Tooltip>
                                ) : (
                                  formatValue(value)
                                )}
                              </TableCell>
                            )
                          })}
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </>
        )}

        {!result && !error && (
          <Box sx={{ py: 4, textAlign: 'center' }}>
            <Typography color="text.secondary">No data yet.</Typography>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  )
}
