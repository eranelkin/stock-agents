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
import Alert from "@mui/material/Alert";
import CloseIcon from "@mui/icons-material/Close";
import { addWatchlistEntry, updateWatchlistEntry } from "../api/watchlist";
import type { WatchlistEntry } from "../types/watchlist";

interface WatchlistDialogProps {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  editEntry?: WatchlistEntry | null;
  env: "prod" | "test";
}

const EMPTY = { symbol: "", sec_type: "STK", exchange: "SMART", currency: "USD" };

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

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75 }}>
      <Typography sx={{ color: "#cdd1d9", fontWeight: 500, fontSize: "0.875rem" }}>
        {label}
      </Typography>
      {children}
    </Box>
  );
}

export default function WatchlistDialog({
  open,
  onClose,
  onSaved,
  editEntry,
  env,
}: WatchlistDialogProps) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEdit = Boolean(editEntry);

  useEffect(() => {
    if (editEntry) {
      setForm({
        symbol: editEntry.symbol,
        sec_type: editEntry.sec_type,
        exchange: editEntry.exchange,
        currency: editEntry.currency,
      });
    } else {
      setForm(EMPTY);
    }
    setError(null);
  }, [editEntry, open]);

  const set = (field: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async () => {
    if (!form.symbol.trim()) {
      setError("Symbol is required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (isEdit && editEntry) {
        await updateWatchlistEntry(editEntry.symbol, form, env);
      } else {
        await addWatchlistEntry(form, env);
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
      maxWidth="xs"
      fullWidth
      PaperProps={{
        sx: { bgcolor: "#000", borderRadius: 2, border: "1px solid rgba(255,255,255,0.12)" },
      }}
    >
      <DialogTitle
        sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", pt: 2.5, pb: 1.5, px: 3 }}
      >
        <Typography sx={{ color: "#fff", fontWeight: 600, fontSize: "1.05rem" }}>
          {isEdit ? "Edit Symbol" : "Add Symbol"}
        </Typography>
        <IconButton
          onClick={onClose}
          size="small"
          sx={{ color: "rgba(255,255,255,0.45)", "&:hover": { color: "#fff", bgcolor: "transparent" } }}
        >
          <CloseIcon sx={{ fontSize: 18 }} />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, px: 3, pb: 2, pt: 0.5 }}>
        {error && <Alert severity="error">{error}</Alert>}

        <Field label="Symbol">
          <TextField
            placeholder="e.g. AAPL"
            value={form.symbol}
            onChange={(e) => setForm((f) => ({ ...f, symbol: e.target.value.toUpperCase() }))}
            fullWidth
            size="small"
            sx={inputSx}
          />
        </Field>

        <Field label="Security Type">
          <TextField value={form.sec_type} onChange={set("sec_type")} fullWidth size="small" sx={inputSx} />
        </Field>

        <Field label="Exchange">
          <TextField value={form.exchange} onChange={set("exchange")} fullWidth size="small" sx={inputSx} />
        </Field>

        <Field label="Currency">
          <TextField value={form.currency} onChange={set("currency")} fullWidth size="small" sx={inputSx} />
        </Field>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2.5, gap: 1 }}>
        <Button
          onClick={onClose}
          sx={{ textTransform: "none", color: "text.secondary" }}
        >
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={saving}
          sx={{ textTransform: "none", fontWeight: 600 }}
        >
          {saving ? "Saving…" : isEdit ? "Save Changes" : "Add Symbol"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
