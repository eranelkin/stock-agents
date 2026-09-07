import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Chip from "@mui/material/Chip";
import Tooltip from "@mui/material/Tooltip";
import CircularProgress from "@mui/material/CircularProgress";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import type { ScanResult } from "../types/scan";

interface ScanResultsTableProps {
  results: ScanResult[] | undefined;
  loading: boolean;
}

const HEADERS = [
  "Ticker",
  "Entry Range",
  "Entry Time",
  "SL Range",
  "TP Range",
  "Fill Status",
  "Exit Reason",
  "Fill Price",
  "Exit Price",
  "PnL %",
  "R-Multiple",
];

const headerCellSx = {
  color: "text.secondary",
  fontSize: "0.75rem",
  borderColor: "rgba(255,255,255,0.08)",
  fontWeight: 600,
  whiteSpace: "nowrap" as const,
};

const bodyCellSx = {
  borderColor: "rgba(255,255,255,0.06)",
  whiteSpace: "nowrap" as const,
  fontSize: "0.85rem",
};

const fmtRange = (low: number | null, high: number | null) =>
  low != null && high != null ? `${low} - ${high}` : "—";

const fmtNum = (n: number | null, digits = 2) => (n != null ? n.toFixed(digits) : "—");

const fillStatusTooltip = (r: ScanResult): string => {
  const entryZone = `$${fmtNum(r.entry_low)} - $${fmtNum(r.entry_high)}`;
  const window =
    r.entry_time_start && r.entry_time_end ? `${r.entry_time_start}-${r.entry_time_end}` : "the entry window";

  if (r.fill_status === "filled") {
    return (
      `Price entered the ${entryZone} entry zone during ${window}, filling at $${fmtNum(r.fill_price)}. ` +
      `Actual traded range in that window was $${fmtNum(r.entry_window_low)} - $${fmtNum(r.entry_window_high)}.`
    );
  }

  if (r.entry_window_low == null || r.entry_window_high == null) {
    return `No 1-minute market data was found during ${window} on this date, so the entry zone (${entryZone}) could never be tested.`;
  }

  return (
    `Price never reached the ${entryZone} entry zone during ${window}. ` +
    `It actually traded between $${fmtNum(r.entry_window_low)} and $${fmtNum(r.entry_window_high)} in that window.`
  );
};

export default function ScanResultsTable({ results, loading }: ScanResultsTableProps) {
  if (loading) {
    return (
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, py: 2, px: 1 }}>
        <CircularProgress size={16} color="inherit" />
        <Typography variant="body2" color="text.secondary">
          Loading scan results…
        </Typography>
      </Box>
    );
  }

  if (!results || results.length === 0) {
    return (
      <Box sx={{ py: 2, px: 1 }}>
        <Typography variant="body2" color="text.secondary">
          Not scanned yet — click the scan icon on this row to simulate its recommendations against real
          1-minute market data.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ py: 1.5, px: 1 }}>
      <TableContainer sx={{ overflowX: "auto", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 1 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              {HEADERS.map((h) => (
                <TableCell key={h} sx={headerCellSx}>
                  {h}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {results.map((r) => (
              <TableRow key={r.id} sx={{ "&:hover": { bgcolor: "rgba(255,255,255,0.03)" } }}>
                <TableCell sx={{ ...bodyCellSx, color: "#81d4fa", fontWeight: 700 }}>{r.ticker}</TableCell>
                {r.status === "error" ? (
                  <TableCell colSpan={HEADERS.length - 1} sx={bodyCellSx}>
                    <Chip
                      label="ERROR"
                      size="small"
                      sx={{
                        height: 18,
                        fontSize: "0.65rem",
                        fontWeight: 700,
                        bgcolor: "rgba(244,67,54,0.15)",
                        color: "#ef9a9a",
                        mr: 1,
                      }}
                    />
                    <Typography component="span" variant="body2" color="text.secondary" sx={{ fontSize: "0.8rem" }}>
                      {r.error_message ?? "Could not parse recommendation"}
                    </Typography>
                  </TableCell>
                ) : r.status === "no_data" ? (
                  <TableCell colSpan={HEADERS.length - 1} sx={bodyCellSx}>
                    <Chip
                      label="NO DATA"
                      size="small"
                      sx={{
                        height: 18,
                        fontSize: "0.65rem",
                        fontWeight: 700,
                        bgcolor: "rgba(255,193,7,0.15)",
                        color: "#ffd54f",
                        mr: 1,
                      }}
                    />
                    <Typography component="span" variant="body2" color="text.secondary" sx={{ fontSize: "0.8rem" }}>
                      {r.error_message ?? "Market data unavailable"}
                    </Typography>
                  </TableCell>
                ) : (
                  <>
                    <TableCell sx={bodyCellSx}>{fmtRange(r.entry_low, r.entry_high)}</TableCell>
                    <TableCell sx={bodyCellSx}>
                      {r.entry_time_start && r.entry_time_end
                        ? `${r.entry_time_start} - ${r.entry_time_end}`
                        : "—"}
                    </TableCell>
                    <TableCell sx={bodyCellSx}>{fmtRange(r.sl_low, r.sl_high)}</TableCell>
                    <TableCell sx={bodyCellSx}>{fmtRange(r.tp_low, r.tp_high)}</TableCell>
                    <TableCell sx={bodyCellSx}>
                      <Tooltip title={fillStatusTooltip(r)} arrow placement="top">
                        <Box sx={{ display: "inline-flex", alignItems: "center", gap: 0.5, cursor: "help" }}>
                          <Chip
                            label={r.fill_status === "filled" ? "FILLED" : "NO FILL"}
                            size="small"
                            sx={{
                              height: 18,
                              fontSize: "0.65rem",
                              fontWeight: 700,
                              bgcolor: r.fill_status === "filled" ? "rgba(76,175,80,0.15)" : "rgba(255,255,255,0.06)",
                              color: r.fill_status === "filled" ? "#81c784" : "#9e9e9e",
                            }}
                          />
                          {r.fill_status !== "filled" && (
                            <InfoOutlinedIcon sx={{ fontSize: 14, color: "#64b5f6" }} />
                          )}
                        </Box>
                      </Tooltip>
                    </TableCell>
                    <TableCell sx={bodyCellSx}>{r.exit_reason ? r.exit_reason.replace("_", " ") : "—"}</TableCell>
                    <TableCell sx={bodyCellSx}>{fmtNum(r.fill_price)}</TableCell>
                    <TableCell sx={bodyCellSx}>{fmtNum(r.exit_price)}</TableCell>
                    <TableCell
                      sx={{
                        ...bodyCellSx,
                        color: r.pnl_pct != null ? (r.pnl_pct >= 0 ? "#81c784" : "#ef9a9a") : "text.disabled",
                        fontWeight: 600,
                      }}
                    >
                      {r.pnl_pct != null ? `${r.pnl_pct >= 0 ? "+" : ""}${fmtNum(r.pnl_pct)}%` : "—"}
                    </TableCell>
                    <TableCell sx={bodyCellSx}>{fmtNum(r.r_multiple)}</TableCell>
                  </>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
