import { useCallback, useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Button from "@mui/material/Button";
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
import Alert from "@mui/material/Alert";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import { deleteWatchlistEntry, fetchWatchlist } from "../api/watchlist";
import type { WatchlistEntry } from "../types/watchlist";
import WatchlistDialog from "../components/WatchlistDialog";

export default function WatchlistPage() {
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<WatchlistEntry | null>(null);
  const [env, setEnv] = useState<"prod" | "test">(
    () => (localStorage.getItem("runEnv") as "prod" | "test") ?? "prod",
  );

  const load = useCallback(async (e: "prod" | "test") => {
    setLoading(true);
    setError(null);
    try {
      setEntries(await fetchWatchlist(e));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load watchlist");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(env);
  }, [env, load]);

  const handleDelete = async (symbol: string) => {
    if (!window.confirm(`Remove ${symbol} from the watchlist?`)) return;
    try {
      await deleteWatchlistEntry(symbol, env);
      setEntries((prev) => prev.filter((e) => e.symbol !== symbol));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete symbol");
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
      <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <Box>
          <Typography variant="h4" fontWeight={700} color="text.primary">
            Watchlist
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Stocks pulled from IBK when running the &ldquo;Watchlist&rdquo; run option.
          </Typography>
        </Box>

        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mt: 0.5 }}>
          <ToggleButtonGroup
            value={env}
            exclusive
            size="small"
            onChange={(_, v) => {
              if (v) {
                setEnv(v);
                localStorage.setItem("runEnv", v);
              }
            }}
            sx={{ height: 32 }}
          >
            <ToggleButton value="prod" sx={{ px: 1.5, textTransform: "none", fontWeight: 600, fontSize: 12 }}>
              Prod
            </ToggleButton>
            <ToggleButton
              value="test"
              sx={{
                px: 1.5, textTransform: "none", fontWeight: 600, fontSize: 12,
                "&.Mui-selected": { color: "#fbbf24", borderColor: "#fbbf24", bgcolor: "rgba(251,191,36,0.08)" },
              }}
            >
              Test
            </ToggleButton>
          </ToggleButtonGroup>

          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => { setEditTarget(null); setDialogOpen(true); }}
            sx={{ borderRadius: 1.5, textTransform: "none", fontWeight: 600, whiteSpace: "nowrap" }}
          >
            Add Symbol
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Divider />

      <Box sx={{ flex: 1, overflow: "auto" }}>
        {loading ? (
          <Box sx={{ display: "flex", justifyContent: "center", pt: 6 }}>
            <CircularProgress size={28} />
          </Box>
        ) : entries.length === 0 ? (
          <Box sx={{ display: "flex", justifyContent: "center", pt: 6 }}>
            <Typography variant="h6" color="text.secondary">
              Watchlist is empty
            </Typography>
          </Box>
        ) : (
          <TableContainer>
            <Table size="small" sx={{ width: "100%" }}>
              <TableHead>
                <TableRow>
                  {["Symbol", "Sec Type", "Exchange", "Currency"].map((h) => (
                    <TableCell
                      key={h}
                      sx={{
                        color: "text.secondary",
                        fontSize: "0.8rem",
                        borderColor: "rgba(255,255,255,0.08)",
                        fontWeight: 600,
                      }}
                    >
                      {h}
                    </TableCell>
                  ))}
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
                {entries.map((entry) => (
                  <TableRow
                    key={entry.symbol}
                    sx={{ "&:hover": { bgcolor: "rgba(255,255,255,0.03)" } }}
                  >
                    <TableCell sx={{ borderColor: "rgba(255,255,255,0.06)", color: "#fff", fontFamily: "monospace", fontWeight: 600 }}>
                      {entry.symbol}
                    </TableCell>
                    <TableCell sx={{ borderColor: "rgba(255,255,255,0.06)", color: "text.secondary", fontSize: "0.8rem" }}>
                      {entry.sec_type}
                    </TableCell>
                    <TableCell sx={{ borderColor: "rgba(255,255,255,0.06)", color: "text.secondary", fontSize: "0.8rem" }}>
                      {entry.exchange}
                    </TableCell>
                    <TableCell sx={{ borderColor: "rgba(255,255,255,0.06)", color: "text.secondary", fontSize: "0.8rem" }}>
                      {entry.currency}
                    </TableCell>
                    <TableCell align="right" sx={{ borderColor: "rgba(255,255,255,0.06)" }}>
                      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 0.5 }}>
                        <Tooltip title="Edit">
                          <IconButton
                            size="small"
                            onClick={() => { setEditTarget(entry); setDialogOpen(true); }}
                            sx={{ color: "text.secondary", "&:hover": { color: "#90caf9" } }}
                          >
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete">
                          <IconButton
                            size="small"
                            onClick={() => handleDelete(entry.symbol)}
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

      <WatchlistDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSaved={() => load(env)}
        editEntry={editTarget}
        env={env}
      />
    </Box>
  );
}
