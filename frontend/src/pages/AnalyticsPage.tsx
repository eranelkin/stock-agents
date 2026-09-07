import { Fragment, useCallback, useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Divider from "@mui/material/Divider";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Collapse from "@mui/material/Collapse";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import CircularProgress from "@mui/material/CircularProgress";
import Alert from "@mui/material/Alert";
import DeleteIcon from "@mui/icons-material/Delete";
import FlipIcon from "@mui/icons-material/Flip";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowRightIcon from "@mui/icons-material/KeyboardArrowRight";
import { fetchAnalyticsRuns } from "../api/analytics";
import { deleteRun } from "../api/runs";
import { runScan, fetchScanResults } from "../api/scan";
import type { Run } from "../types/run";
import type { ScanResult } from "../types/scan";
import { formatDateTime, isBeforeToday } from "../utils/date";
import ScanResultsTable from "../components/ScanResultsTable";

const STICKY_ACTIONS_SX = {
  position: "sticky" as const,
  right: 0,
  bgcolor: "#101010",
  borderLeft: "1px solid rgba(255,255,255,0.08)",
  zIndex: 2,
  px: 1,
  width: 88,
};

export default function AnalyticsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scanningId, setScanningId] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [loadingScanIds, setLoadingScanIds] = useState<Set<string>>(new Set());
  const [scanResultsByRun, setScanResultsByRun] = useState<Record<string, ScanResult[]>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRuns(await fetchAnalyticsRuns());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleDelete = async (run: Run) => {
    if (!window.confirm(`Delete run "${run.name ?? "Unnamed"}"?`)) return;
    await deleteRun(run.id);
    setRuns((prev) => prev.filter((r) => r.id !== run.id));
    setExpandedIds((prev) => {
      const next = new Set(prev);
      next.delete(run.id);
      return next;
    });
    setScanResultsByRun((prev) => {
      const { [run.id]: _omit, ...rest } = prev;
      return rest;
    });
  };

  const handleScan = async (run: Run) => {
    setError(null);
    setScanningId(run.id);
    try {
      const results = await runScan(run.id);
      setScanResultsByRun((prev) => ({ ...prev, [run.id]: results }));
      const lastScannedAt = results.reduce<string | null>(
        (max, r) => (max == null || r.scanned_at > max ? r.scanned_at : max),
        null
      );
      setRuns((prev) => prev.map((r) => (r.id === run.id ? { ...r, last_scanned_at: lastScannedAt } : r)));
      setExpandedIds((prev) => new Set(prev).add(run.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setScanningId(null);
    }
  };

  const toggleExpand = async (run: Run) => {
    const isExpanded = expandedIds.has(run.id);
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (isExpanded) {
        next.delete(run.id);
      } else {
        next.add(run.id);
      }
      return next;
    });

    if (!isExpanded && run.last_scanned_at && !scanResultsByRun[run.id]) {
      setLoadingScanIds((prev) => new Set(prev).add(run.id));
      try {
        const results = await fetchScanResults(run.id);
        setScanResultsByRun((prev) => ({ ...prev, [run.id]: results }));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load scan results");
      } finally {
        setLoadingScanIds((prev) => {
          const next = new Set(prev);
          next.delete(run.id);
          return next;
        });
      }
    }
  };

  return (
    <Box
      sx={{
        px: 4,
        py: 3,
        display: "flex",
        flexDirection: "column",
        gap: 2,
        flex: 1,
        overflow: "hidden",
      }}
    >
      {/* Title row */}
      <Box>
        <Typography variant="h4" fontWeight={700} color="text.primary">
          Analytics
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          History of completed runs available for analysis.
        </Typography>
      </Box>

      <Divider />

      {error && (
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Table */}
      <Box sx={{ flex: 1, overflow: "auto" }}>
        {loading ? (
          <Box sx={{ display: "flex", justifyContent: "center", pt: 6 }}>
            <CircularProgress size={28} />
          </Box>
        ) : runs.length === 0 ? (
          <Box sx={{ display: "flex", justifyContent: "center", pt: 6 }}>
            <Typography variant="h6" color="text.secondary">
              No completed runs yet
            </Typography>
          </Box>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell
                    sx={{
                      width: 40,
                      borderColor: "rgba(255,255,255,0.08)",
                    }}
                  />
                  <TableCell
                    sx={{
                      color: "text.secondary",
                      fontSize: "0.8rem",
                      borderColor: "rgba(255,255,255,0.08)",
                      fontWeight: 600,
                    }}
                  >
                    Date & Time
                  </TableCell>
                  <TableCell
                    sx={{
                      color: "text.secondary",
                      fontSize: "0.8rem",
                      borderColor: "rgba(255,255,255,0.08)",
                      fontWeight: 600,
                    }}
                  >
                    Stocks
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      ...STICKY_ACTIONS_SX,
                      color: "text.secondary",
                      fontSize: "0.8rem",
                      fontWeight: 600,
                    }}
                  >
                    Actions
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {runs.map((run) => {
                  const expanded = expandedIds.has(run.id);
                  const scanned = Boolean(run.last_scanned_at);
                  return (
                    <Fragment key={run.id}>
                      <TableRow
                        sx={{
                          "&:hover": { bgcolor: "rgba(255,255,255,0.03)" },
                          "&:hover .sticky-actions": { bgcolor: "#171717" },
                        }}
                      >
                        <TableCell sx={{ borderColor: "rgba(255,255,255,0.06)" }}>
                          <IconButton size="small" onClick={() => toggleExpand(run)} sx={{ color: "text.secondary" }}>
                            {expanded ? (
                              <KeyboardArrowDownIcon fontSize="small" />
                            ) : (
                              <KeyboardArrowRightIcon fontSize="small" />
                            )}
                          </IconButton>
                        </TableCell>
                        <TableCell
                          sx={{
                            color: "#ffffff",
                            borderColor: "rgba(255,255,255,0.06)",
                            fontSize: "0.85rem",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {formatDateTime(run.created_at)}
                        </TableCell>
                        <TableCell
                          sx={{
                            borderColor: "rgba(255,255,255,0.06)",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {run.ticker_count != null ? (
                            <Typography
                              variant="body2"
                              sx={{
                                fontFamily: "monospace",
                                fontSize: "0.8rem",
                                color: "text.secondary",
                              }}
                            >
                              {run.ticker_count}
                            </Typography>
                          ) : (
                            <Typography
                              variant="body2"
                              sx={{ fontSize: "0.8rem", color: "text.disabled" }}
                            >
                              —
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell
                          align="right"
                          className="sticky-actions"
                          sx={{
                            ...STICKY_ACTIONS_SX,
                            whiteSpace: "nowrap",
                          }}
                        >
                          <Box
                            sx={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "flex-end",
                              gap: 0.5,
                            }}
                          >
                            <Tooltip
                              title={
                                !isBeforeToday(run.created_at)
                                  ? "Available once this run's date is in the past"
                                  : scanned
                                    ? "Rescan (recompute against live market data)"
                                    : "Scan"
                              }
                            >
                              <span>
                                <IconButton
                                  size="small"
                                  disabled={!isBeforeToday(run.created_at) || scanningId === run.id}
                                  onClick={() => handleScan(run)}
                                  sx={{
                                    color: scanned ? "#81c784" : "text.secondary",
                                    "&:hover": { color: scanned ? "#81c784" : "#90caf9" },
                                    "&.Mui-disabled": { color: "text.disabled" },
                                  }}
                                >
                                  {scanningId === run.id ? (
                                    <CircularProgress size={16} color="inherit" />
                                  ) : (
                                    <FlipIcon fontSize="small" />
                                  )}
                                </IconButton>
                              </span>
                            </Tooltip>
                            <Tooltip title="Delete">
                              <IconButton
                                size="small"
                                onClick={() => handleDelete(run)}
                                sx={{ color: "#f44336" }}
                              >
                                <DeleteIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          </Box>
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell
                          colSpan={4}
                          sx={{ py: 0, borderColor: expanded ? "rgba(255,255,255,0.06)" : "transparent" }}
                        >
                          <Collapse in={expanded} timeout="auto" unmountOnExit>
                            <ScanResultsTable
                              results={scanResultsByRun[run.id]}
                              loading={loadingScanIds.has(run.id)}
                            />
                          </Collapse>
                        </TableCell>
                      </TableRow>
                    </Fragment>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>
    </Box>
  );
}
