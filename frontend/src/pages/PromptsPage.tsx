import { useCallback, useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Button from "@mui/material/Button";
import Divider from "@mui/material/Divider";
import Tabs from "@mui/material/Tabs";
import Tab from "@mui/material/Tab";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import CircularProgress from "@mui/material/CircularProgress";
import AddIcon from "@mui/icons-material/Add";
// import ChevronRightIcon from '@mui/icons-material/ChevronRight'
// import PlayIcon from '@mui/icons-material/PlayIcon'
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import Switch from "@mui/material/Switch";
import { fetchPrompts, deletePrompt, togglePromptActive } from "../api/prompts";
import type { Prompt } from "../types/prompt";
import PromptDialog from "../components/PromptDialog";

const CATEGORIES = ["system", "agents", "once", "market"] as const;
const CATEGORY_LABELS: Record<string, string> = {
  system: "System",
  agents: "Agents",
  once: "Once",
  market: "Market",
};

function PlayIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

interface PromptsPageProps {
  onRunPrompt: (content: string) => void
}

export default function PromptsPage({ onRunPrompt }: PromptsPageProps) {
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [innerTab, setInnerTab] = useState(0);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Prompt | null>(null);

  const currentCategory = CATEGORIES[innerTab];

  const load = useCallback(async (category: string) => {
    setLoading(true);
    try {
      setPrompts(await fetchPrompts(category));
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(currentCategory);
  }, [currentCategory, load]);

  const handleTabChange = (_: React.SyntheticEvent, v: number) => {
    setInnerTab(v);
  };

  const handleAddClick = () => {
    setEditTarget(null);
    setDialogOpen(true);
  };

  function handleRun(prompt: Prompt) {
    onRunPrompt(prompt.content)
  }

  const handleEditClick = (prompt: Prompt) => {
    setEditTarget(prompt);
    setDialogOpen(true);
  };

  const handleDelete = async (prompt: Prompt) => {
    if (!window.confirm(`Delete prompt "${prompt.title}"?`)) return;
    await deletePrompt(prompt.id);
    setPrompts((prev) => prev.filter((p) => p.id !== prompt.id));
  };

  const handleToggleActive = async (prompt: Prompt) => {
    await togglePromptActive(prompt.id, !prompt.is_active);
    load(currentCategory);
  };

  const handleSaved = () => {
    load(currentCategory);
  };

  const cellBorder = { borderColor: "rgba(255,255,255,0.06)" };

  return (
    <Box
      sx={{ px: 4, py: 3, display: "flex", flexDirection: "column", gap: 2, flex: 1, overflow: "hidden" }}
    >
      {/* Page header */}
      <Box
        sx={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
        }}
      >
        <Box>
          <Typography variant="h4" fontWeight={700} color="text.primary">
            Prompts Manager
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Create and manage AI agent prompts.
          </Typography>
        </Box>

        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={handleAddClick}
          sx={{
            borderRadius: 5,
            px: 2.5,
            textTransform: "none",
            fontWeight: 600,
            mt: 0.5,
            whiteSpace: "nowrap",
          }}
        >
          Add Prompt
        </Button>
      </Box>

      <Divider />

      {/* Inner tabs */}
      <Tabs
        value={innerTab}
        onChange={handleTabChange}
        TabIndicatorProps={{ style: { backgroundColor: "#1976d2", height: 2 } }}
        sx={{ minHeight: 40 }}
      >
        {CATEGORIES.map((cat) => (
          <Tab
            key={cat}
            label={CATEGORY_LABELS[cat]}
            sx={{
              minHeight: 40,
              textTransform: "none",
              fontWeight: 500,
              fontSize: "0.875rem",
              color: "text.secondary",
              px: 2,
              "&.Mui-selected": { color: "#1976d2" },
            }}
          />
        ))}
      </Tabs>

      {/* Table */}
      <Box sx={{ flex: 1, overflow: "auto" }}>
      {loading ? (
        <Box sx={{ display: "flex", justifyContent: "center", pt: 6 }}>
          <CircularProgress size={28} />
        </Box>
      ) : prompts.length === 0 ? (
        <Box sx={{ display: "flex", justifyContent: "center", pt: 6 }}>
          <Typography variant="h6" color="text.secondary">
            No {CATEGORY_LABELS[currentCategory]} prompts yet
          </Typography>
        </Box>
      ) : (
        <TableContainer>
          <Table size="small" sx={{ width: "100%" }}>
            <TableHead>
              <TableRow>
                {["Title", "Prompt", "Created"].map((h) => (
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
                  sx={{
                    color: "text.secondary",
                    fontSize: "0.8rem",
                    borderColor: "rgba(255,255,255,0.08)",
                    fontWeight: 600,
                  }}
                >
                  Active
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
              {prompts.map((prompt) => (
                <TableRow
                  key={prompt.id}
                  sx={{ "&:hover": { bgcolor: "rgba(255,255,255,0.03)" } }}
                >
                  <TableCell
                    sx={{
                      ...cellBorder,
                      color: "text.primary",
                      fontWeight: 500,
                      whiteSpace: "nowrap",
                      maxWidth: 200,
                    }}
                  >
                    {prompt.title}
                  </TableCell>
                  <TableCell
                    sx={{
                      ...cellBorder,
                      color: "text.secondary",
                      fontSize: "0.85rem",
                      maxWidth: 480,
                    }}
                  >
                    {prompt.content.length > 100
                      ? `${prompt.content.slice(0, 100)}…`
                      : prompt.content}
                  </TableCell>
                  <TableCell
                    sx={{
                      ...cellBorder,
                      color: "text.secondary",
                      fontSize: "0.85rem",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {new Date(prompt.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell sx={{ ...cellBorder }}>
                    <Switch
                      size="small"
                      checked={prompt.is_active}
                      onChange={() => handleToggleActive(prompt)}
                    />
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{ ...cellBorder, whiteSpace: "nowrap" }}
                  >
                    <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 0.5 }}>
                      <Tooltip title="Run">
                        <IconButton size="small" onClick={() => handleRun(prompt)}>
                          <PlayIcon />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Edit">
                        <IconButton
                          size="small"
                          onClick={() => handleEditClick(prompt)}
                          sx={{
                            color: "text.secondary",
                            "&:hover": { color: "#fff" },
                          }}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton
                          size="small"
                          onClick={() => handleDelete(prompt)}
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

      <PromptDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSaved={handleSaved}
        editPrompt={editTarget}
        defaultCategory={currentCategory}
      />
    </Box>
  );
}
