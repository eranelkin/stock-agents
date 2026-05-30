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
import Switch from "@mui/material/Switch";
import IconButton from "@mui/material/IconButton";
import Chip from "@mui/material/Chip";
import Tooltip from "@mui/material/Tooltip";
import CircularProgress from "@mui/material/CircularProgress";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import { deleteModel, fetchModels, toggleModelActive } from "../api/models";
import type { Model } from "../types/model";
import ModelDialog from "../components/ModelDialog";

interface ModelsPageProps {
  onModelsChange: () => void;
}

export default function ModelsPage({ onModelsChange }: ModelsPageProps) {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Model | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setModels(await fetchModels());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleSaved = () => {
    load();
    onModelsChange();
  };

  const handleAddClick = () => {
    setEditTarget(null);
    setDialogOpen(true);
  };
  const handleEditClick = (m: Model) => {
    setEditTarget(m);
    setDialogOpen(true);
  };

  const handleDelete = async (m: Model) => {
    if (!window.confirm(`Delete "${m.name}"?`)) return;
    await deleteModel(m.id);
    load();
    onModelsChange();
  };

  const handleToggleActive = async (m: Model) => {
    await toggleModelActive(m.id, !m.is_active);
    load();
    onModelsChange();
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
      <Box
        sx={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
        }}
      >
        <Box>
          <Typography variant="h4" fontWeight={700} color="text.primary">
            Models
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Configure AI providers and API keys. Keys are stored securely and
            never exposed.
          </Typography>
        </Box>
        <Button
          variant="contained"
          color="primary"
          startIcon={<AddIcon />}
          onClick={handleAddClick}
          sx={{ whiteSpace: "nowrap", mt: 0.5, borderRadius: 1.5 }}
        >
          Add Model
        </Button>
      </Box>

      <Divider />

      {/* Table */}
      <Box sx={{ flex: 1, overflow: "auto" }}>
        {loading ? (
          <Box sx={{ display: "flex", justifyContent: "center", pt: 6 }}>
            <CircularProgress size={28} />
          </Box>
        ) : models.length === 0 ? (
          <Box sx={{ display: "flex", justifyContent: "center", pt: 6 }}>
            <Typography variant="h6" color="text.secondary">
              No models configured yet
            </Typography>
          </Box>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  {[
                    "Name",
                    "Model ID",
                    "Provider",
                    "Base URL",
                    "API Key",
                    "Active",
                    "Actions",
                  ].map((h) => (
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
                </TableRow>
              </TableHead>
              <TableBody>
                {models.map((m) => (
                  <TableRow
                    key={m.id}
                    sx={{ "&:hover": { bgcolor: "rgba(255,255,255,0.03)" } }}
                  >
                    <TableCell
                      sx={{
                        color: "text.primary",
                        borderColor: "rgba(255,255,255,0.06)",
                        fontWeight: 500,
                      }}
                    >
                      {m.name}
                    </TableCell>
                    <TableCell sx={{ borderColor: "rgba(255,255,255,0.06)" }}>
                      <Typography
                        variant="body2"
                        sx={{
                          fontFamily: "monospace",
                          color: "#9e9e9e",
                          fontSize: "0.8rem",
                        }}
                      >
                        {m.model_id}
                      </Typography>
                    </TableCell>
                    <TableCell
                      sx={{
                        color: "text.secondary",
                        borderColor: "rgba(255,255,255,0.06)",
                        fontSize: "0.85rem",
                      }}
                    >
                      {m.provider}
                    </TableCell>
                    <TableCell
                      sx={{
                        borderColor: "rgba(255,255,255,0.06)",
                        maxWidth: 220,
                      }}
                    >
                      <Tooltip title={m.base_url ?? ""} placement="top">
                        <Typography
                          variant="body2"
                          sx={{
                            color: "#9e9e9e",
                            fontSize: "0.8rem",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                            maxWidth: 200,
                          }}
                        >
                          {m.base_url ?? "—"}
                        </Typography>
                      </Tooltip>
                    </TableCell>
                    <TableCell sx={{ borderColor: "rgba(255,255,255,0.06)" }}>
                      {m.api_key_configured ? (
                        <Chip
                          label="Configured"
                          size="small"
                          sx={{
                            bgcolor: "rgba(76,175,80,0.15)",
                            color: "#81c784",
                            fontSize: "0.75rem",
                          }}
                        />
                      ) : (
                        <Chip
                          label="Not set"
                          size="small"
                          sx={{
                            bgcolor: "rgba(255,255,255,0.06)",
                            color: "#757575",
                            fontSize: "0.75rem",
                          }}
                        />
                      )}
                    </TableCell>
                    <TableCell sx={{ borderColor: "rgba(255,255,255,0.06)" }}>
                      <Switch
                        checked={m.is_active}
                        onChange={() => handleToggleActive(m)}
                        size="small"
                        color="primary"
                      />
                    </TableCell>
                    <TableCell sx={{ borderColor: "rgba(255,255,255,0.06)" }}>
                      <Box sx={{ display: "flex", gap: 0.5 }}>
                        <Tooltip title="Edit">
                          <IconButton
                            size="small"
                            onClick={() => handleEditClick(m)}
                            sx={{ color: "text.secondary" }}
                          >
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete">
                          <IconButton
                            size="small"
                            onClick={() => handleDelete(m)}
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

      <ModelDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSaved={handleSaved}
        editModel={editTarget}
      />
    </Box>
  );
}
