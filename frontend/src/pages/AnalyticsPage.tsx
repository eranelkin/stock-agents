import { useCallback, useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Divider from "@mui/material/Divider";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import CircularProgress from "@mui/material/CircularProgress";
import DeleteIcon from "@mui/icons-material/Delete";
import FlipIcon from "@mui/icons-material/Flip";
import { fetchAnalyticsRuns } from "../api/analytics";
import { deleteRun } from "../api/runs";
import type { Run } from "../types/run";
import { formatDateTime } from "../utils/date";

export default function AnalyticsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

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
                      color: "text.secondary",
                      fontSize: "0.8rem",
                      borderColor: "rgba(255,255,255,0.08)",
                      fontWeight: 600,
                    }}
                  >
                    Actions
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {runs.map((run) => (
                  <TableRow
                    key={run.id}
                    sx={{ "&:hover": { bgcolor: "rgba(255,255,255,0.03)" } }}
                  >
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
                      sx={{
                        borderColor: "rgba(255,255,255,0.06)",
                        whiteSpace: "nowrap",
                      }}
                    >
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "flex-end",
                          gap: 0.75,
                        }}
                      >
                        <Tooltip title="Scan — coming soon">
                          <span>
                            <IconButton
                              size="small"
                              disabled
                              sx={{
                                color: "text.secondary",
                                "&.Mui-disabled": { color: "text.disabled" },
                              }}
                            >
                              <FlipIcon fontSize="small" />
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
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>
    </Box>
  );
}
