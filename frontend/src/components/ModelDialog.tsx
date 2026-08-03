import { useEffect, useState } from "react";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import DialogActions from "@mui/material/DialogActions";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import IconButton from "@mui/material/IconButton";
import Typography from "@mui/material/Typography";
import Box from "@mui/material/Box";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import CloseIcon from "@mui/icons-material/Close";
import { createModel, updateModel } from "../api/models";
import type { Model, ModelCreatePayload } from "../types/model";

interface ModelDialogProps {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  editModel?: Model | null;
}

const EMPTY = {
  name: "",
  model_id: "",
  provider: "openai_compatible",
  base_url: "",
  api_key: "",
  search_depth: "" as string,
};

const inputSx = {
  "& .MuiOutlinedInput-root": {
    backgroundColor: "rgba(255,255,255,0.05)",
    borderRadius: "6px",
    "& fieldset": { borderColor: "rgba(255,255,255,0.14)" },
    "&:hover fieldset": { borderColor: "rgba(255,255,255,0.28)" },
    "&.Mui-focused fieldset": { borderColor: "#1976d2", borderWidth: "1px" },
    "&.Mui-focused": { boxShadow: "0 0 0 3px rgba(25,118,210,0.18)" },
  },
  "& .MuiInputBase-input": {
    color: "#e8eaed",
    fontSize: "0.9rem",
    py: "10px",
    px: "14px",
  },
  "& input::placeholder": { color: "#555", opacity: 1 },
};

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75 }}>
      <Typography
        sx={{ color: "#cdd1d9", fontWeight: 500, fontSize: "0.875rem" }}
      >
        {label}
      </Typography>
      {children}
    </Box>
  );
}

export default function ModelDialog({
  open,
  onClose,
  onSaved,
  editModel,
}: ModelDialogProps) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEdit = Boolean(editModel);

  useEffect(() => {
    if (editModel) {
      setForm({
        name: editModel.name,
        model_id: editModel.model_id,
        provider: editModel.provider,
        base_url: editModel.base_url ?? "",
        api_key: "",
        search_depth: editModel.search_depth ?? "",
      });
    } else {
      setForm(EMPTY);
    }
    setError(null);
  }, [editModel, open]);

  const set =
    (field: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async () => {
    if (!form.name || !form.model_id || !form.provider) {
      setError("Name, Model ID and Provider are required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const searchDepth = form.search_depth || null;

      if (isEdit && editModel) {
        await updateModel(editModel.id, {
          name: form.name,
          model_id: form.model_id,
          provider: form.provider,
          base_url: form.base_url || null,
          api_key: form.api_key || null,
          search_depth: searchDepth,
        });
      } else {
        const payload: ModelCreatePayload = {
          name: form.name,
          model_id: form.model_id,
          provider: form.provider,
          base_url: form.base_url || null,
          api_key: form.api_key || null,
          search_depth: searchDepth,
        };
        await createModel(payload);
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: "#000",
          borderRadius: 2,
          border: "1px solid rgba(255,255,255,0.12)",
        },
      }}
    >
      <DialogTitle
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          pt: 2.5,
          pb: 1.5,
          px: 3,
        }}
      >
        <Typography
          sx={{ color: "#fff", fontWeight: 600, fontSize: "1.05rem" }}
        >
          {isEdit ? "Edit Model" : "Add Model"}
        </Typography>
        <IconButton
          onClick={onClose}
          size="small"
          sx={{
            color: "rgba(255,255,255,0.45)",
            "&:hover": { color: "#fff", bgcolor: "transparent" },
          }}
        >
          <CloseIcon sx={{ fontSize: 18 }} />
        </IconButton>
      </DialogTitle>

      <DialogContent
        sx={{
          display: "flex",
          flexDirection: "column",
          gap: 2,
          px: 3,
          pb: 2,
          pt: 0.5,
        }}
      >
        <Field label="Model ID">
          <TextField
            placeholder="e.g. gpt-4o, groq/llama-3.3-70b-versatile"
            value={form.model_id}
            onChange={set("model_id")}
            fullWidth
            size="small"
            sx={inputSx}
          />
        </Field>

        <Field label="Display Name">
          <TextField
            placeholder="e.g. GPT-4o"
            value={form.name}
            onChange={set("name")}
            fullWidth
            size="small"
            sx={inputSx}
          />
        </Field>

        <Field label="Provider">
          <TextField
            value={form.provider}
            onChange={set("provider")}
            fullWidth
            size="small"
            sx={inputSx}
          />
        </Field>

        <Field label="Base URL">
          <TextField
            placeholder="e.g. https://api.groq.com/openai/v1"
            value={form.base_url}
            onChange={set("base_url")}
            fullWidth
            size="small"
            sx={inputSx}
          />
        </Field>

        <Field label="API Key">
          <TextField
            type="password"
            placeholder={
              isEdit && editModel?.api_key_configured
                ? "••••••••  (leave blank to keep existing)"
                : "Paste your API key"
            }
            value={form.api_key}
            onChange={set("api_key")}
            fullWidth
            size="small"
            sx={inputSx}
          />
          <Typography sx={{ color: "#6b7280", fontSize: "0.78rem", mt: 0.25 }}>
            Stored securely — never shown after saving.
          </Typography>
        </Field>

        <Field label="Default Research Depth for All Prompts">
          <ToggleButtonGroup
            value={form.search_depth}
            exclusive
            onChange={(_e, val) => {
              if (val !== null) setForm((f) => ({ ...f, search_depth: val }));
            }}
            size="small"
            sx={{ gap: 1 }}
          >
            {(["", "basic", "advanced"] as const).map((val) => (
              <ToggleButton
                key={val}
                value={val}
                sx={{
                  color: "rgba(255,255,255,0.5)",
                  borderColor: "rgba(255,255,255,0.14)",
                  textTransform: "none",
                  fontSize: "0.82rem",
                  px: 2,
                  "&.Mui-selected": {
                    color: "#fff",
                    bgcolor: "rgba(25,118,210,0.25)",
                    borderColor: "#1976d2",
                  },
                  "&.Mui-selected:hover": { bgcolor: "rgba(25,118,210,0.35)" },
                }}
              >
                {val === "" ? "Default" : val === "basic" ? "Basic" : "Deep Research"}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
          <Box sx={{ display: "flex", gap: 1, mt: 0.5 }}>
            {[
              { desc: "Uses the global SEARCH_DEPTH from .env" },
              { desc: "Faster & lower cost. Good for most prompts." },
              { desc: "Tavily advanced mode — richer results, higher cost." },
            ].map(({ desc }, i) => (
              <Typography key={i} sx={{ flex: 1, color: "#4b5563", fontSize: "0.7rem", lineHeight: 1.4 }}>
                {desc}
              </Typography>
            ))}
          </Box>
          <Typography sx={{ color: "#6b7280", fontSize: "0.78rem", mt: 0.5 }}>
            Applied to all prompts using this model. Individual prompts can override this per-prompt.
          </Typography>
          <Typography sx={{ color: "#374151", fontSize: "0.72rem", mt: 0.25, fontStyle: "italic" }}>
            Hierarchy: .env global → Model default (this setting) → Prompt override (set per-prompt)
          </Typography>
        </Field>

        {error && (
          <Typography sx={{ color: "#f44336", fontSize: "0.85rem" }}>
            {error}
          </Typography>
        )}
      </DialogContent>

      <DialogActions
        sx={{ px: 3, pb: 3, pt: 1, gap: 1, justifyContent: "flex-end" }}
      >
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={saving}
          sx={{
            borderRadius: 1.5,
            px: 3,
            bgcolor: "#1976d2",
            textTransform: "none",
            fontWeight: 600,
            "&:hover": { bgcolor: "#1565c0" },
          }}
        >
          {saving ? "Saving…" : isEdit ? "Save Changes" : "Add Model"}
        </Button>
        <Button
          onClick={onClose}
          disabled={saving}
          sx={{
            color: "rgba(255,255,255,0.6)",
            textTransform: "none",
            "&:hover": { bgcolor: "transparent", color: "#fff" },
          }}
        >
          Cancel
        </Button>
      </DialogActions>
    </Dialog>
  );
}
