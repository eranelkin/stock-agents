import { useEffect, useState } from "react";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import DialogActions from "@mui/material/DialogActions";
import TextField from "@mui/material/TextField";
import Select from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import Switch from "@mui/material/Switch";
import FormControlLabel from "@mui/material/FormControlLabel";
import Tooltip from "@mui/material/Tooltip";
import Button from "@mui/material/Button";
import IconButton from "@mui/material/IconButton";
import Typography from "@mui/material/Typography";
import Box from "@mui/material/Box";
import CloseIcon from "@mui/icons-material/Close";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import {
  createPrompt,
  updatePrompt,
  fetchActiveAgentPrompts,
  fetchTickerSchema,
  fetchSectorSchema,
  fetchMacroSchema,
} from "../api/prompts";
import type { Prompt } from "../types/prompt";

interface PromptDialogProps {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  editPrompt?: Prompt | null;
  defaultCategory: string;
}

const EMPTY = {
  title: "",
  content: "",
  search_mode: "",
  search_enabled: false,
  search_query_template: "",
  output_schema: "",
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
    fontSize: "0.85rem",
    fontFamily: "monospace",
  },
  "& textarea::placeholder": { color: "#555", opacity: 1 },
  "& input::placeholder": { color: "#555", opacity: 1 },
};

const regularInputSx = {
  ...inputSx,
  "& .MuiInputBase-input": {
    color: "#e8eaed",
    fontSize: "0.9rem",
    fontFamily: "inherit",
  },
};

function InfoTooltip({ content }: { content: React.ReactNode }) {
  return (
    <Tooltip
      title={content}
      placement="right"
      arrow
      slotProps={{
        tooltip: {
          sx: {
            bgcolor: "#1a1e2e",
            border: "1px solid rgba(255,255,255,0.12)",
            borderRadius: "10px",
            p: 2,
            maxWidth: 360,
            boxShadow: "0 12px 40px rgba(0,0,0,0.5)",
          },
        },
        arrow: { sx: { color: "#1a1e2e" } },
      }}
    >
      <InfoOutlinedIcon
        sx={{
          fontSize: 15,
          color: "rgba(255,255,255,0.3)",
          cursor: "help",
          flexShrink: 0,
          transition: "color 0.15s",
          "&:hover": { color: "#90caf9" },
        }}
      />
    </Tooltip>
  );
}

function Field({
  label,
  tooltip,
  children,
}: {
  label: string;
  tooltip?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
        <Typography
          sx={{ color: "#cdd1d9", fontWeight: 500, fontSize: "0.875rem" }}
        >
          {label}
        </Typography>
        {tooltip && <InfoTooltip content={tooltip} />}
      </Box>
      {children}
    </Box>
  );
}

/** Build the CEO input schema from the active agent prompts that have output schemas. */
function buildCeoInputSchema(
  agentPrompts: Prompt[],
): Record<string, unknown> | null {
  const agentProperties: Record<string, unknown> = {};
  for (const p of agentPrompts) {
    if (p.output_schema) {
      agentProperties[p.title] = p.output_schema;
    }
  }
  if (Object.keys(agentProperties).length === 0) return null;
  return {
    type: "object",
    properties: {
      name: { type: "string" },
      agents: {
        type: "object",
        properties: agentProperties,
      },
    },
    required: ["name", "agents"],
  };
}

export default function PromptDialog({
  open,
  onClose,
  onSaved,
  editPrompt,
  defaultCategory,
}: PromptDialogProps) {
  const [form, setForm] = useState(EMPTY);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ceoInputSchema, setCeoInputSchema] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [tickerInputSchema, setTickerInputSchema] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [sectorInputSchema, setSectorInputSchema] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [macroInputSchema, setMacroInputSchema] = useState<Record<
    string,
    unknown
  > | null>(null);

  const isEdit = Boolean(editPrompt);
  const isCeo = defaultCategory === "ceo";
  const isAgents = defaultCategory === "agents";
  const isSectors = defaultCategory === "sectors";
  const isMacro = defaultCategory === "macro";

  useEffect(() => {
    if (editPrompt) {
      setForm({
        title: editPrompt.title,
        content: editPrompt.content,
        search_mode: editPrompt.search_mode ?? "",
        search_enabled: editPrompt.search_enabled ?? false,
        search_query_template: editPrompt.search_query_template ?? "",
        output_schema: editPrompt.output_schema
          ? JSON.stringify(editPrompt.output_schema, null, 2)
          : "",
      });
    } else {
      setForm(EMPTY);
    }
    setError(null);
    setSchemaError(null);
  }, [editPrompt, open]);

  // When the dialog opens for a CEO prompt, fetch active agent prompts to build input schema
  useEffect(() => {
    if (!open || !isCeo) {
      setCeoInputSchema(null);
      return;
    }
    fetchActiveAgentPrompts()
      .then((prompts) => setCeoInputSchema(buildCeoInputSchema(prompts)))
      .catch(() => setCeoInputSchema(null));
  }, [open, isCeo]);

  // When the dialog opens for a stock agent prompt, fetch the global ticker input schema
  useEffect(() => {
    if (!open || !isAgents) {
      setTickerInputSchema(null);
      return;
    }
    fetchTickerSchema()
      .then((schema) =>
        setTickerInputSchema(Object.keys(schema).length ? schema : null),
      )
      .catch(() => setTickerInputSchema(null));
  }, [open, isAgents]);

  // When the dialog opens for a sector prompt, fetch the global sector input schema
  useEffect(() => {
    if (!open || !isSectors) {
      setSectorInputSchema(null);
      return;
    }
    fetchSectorSchema()
      .then((schema) =>
        setSectorInputSchema(Object.keys(schema).length ? schema : null),
      )
      .catch(() => setSectorInputSchema(null));
  }, [open, isSectors]);

  // When the dialog opens for a macro prompt, fetch the global macro input schema
  useEffect(() => {
    if (!open || !isMacro) {
      setMacroInputSchema(null);
      return;
    }
    fetchMacroSchema()
      .then((schema) =>
        setMacroInputSchema(Object.keys(schema).length ? schema : null),
      )
      .catch(() => setMacroInputSchema(null));
  }, [open, isMacro]);

  const set =
    (field: keyof typeof EMPTY) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleFormatJson = () => {
    if (!form.output_schema.trim()) return;
    try {
      const parsed = JSON.parse(form.output_schema);
      setForm((f) => ({
        ...f,
        output_schema: JSON.stringify(parsed, null, 2),
      }));
      setSchemaError(null);
    } catch {
      setSchemaError("Invalid JSON — cannot format");
    }
  };

  const parseOutputSchema = (): Record<string, unknown> | null | "invalid" => {
    const raw = form.output_schema.trim();
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return "invalid";
    }
  };

  const searchModeValue = form.search_mode || "";
  const resolvedSearchMode = searchModeValue === "" ? null : searchModeValue;

  const searchModeTooltip = (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
      <Typography
        sx={{ color: "#e2e8f0", fontWeight: 600, fontSize: "0.82rem" }}
      >
        Search Mode
      </Typography>
      <Typography
        sx={{ color: "#94a3b8", fontSize: "0.78rem", lineHeight: 1.6 }}
      >
        Controls how this prompt fetches real-time web data before the LLM
        processes it.
      </Typography>
      {[
        {
          label: "Use global setting",
          desc: "Inherits SEARCH_MODE from your .env file. Safe default — all prompts behave the same.",
        },
        {
          label: "Prefetch",
          desc: "Your system runs a Tavily search before the LLM call. Results are injected as context. Lower token usage, single clean LLM call.",
        },
        {
          label: "Tool call",
          desc: "The LLM decides when and what to search during its response, up to SEARCH_MAX_TOOL_ROUNDS. More flexible but uses significantly more tokens.",
        },
      ].map(({ label, desc }) => (
        <Box
          key={label}
          sx={{ display: "flex", flexDirection: "column", gap: 0.25 }}
        >
          <Typography
            sx={{ color: "#93c5fd", fontWeight: 600, fontSize: "0.78rem" }}
          >
            {label}
          </Typography>
          <Typography
            sx={{ color: "#94a3b8", fontSize: "0.76rem", lineHeight: 1.5 }}
          >
            {desc}
          </Typography>
        </Box>
      ))}
    </Box>
  );

  const enableSearchTooltip = (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
      <Typography
        sx={{ color: "#e2e8f0", fontWeight: 600, fontSize: "0.82rem" }}
      >
        Enable Search
      </Typography>
      <Typography
        sx={{ color: "#94a3b8", fontSize: "0.78rem", lineHeight: 1.6 }}
      >
        Gates whether a Tavily web search runs for this prompt in Prefetch mode.
      </Typography>
      {[
        {
          label: "ON",
          desc: "A search runs before the LLM call. Results are appended to the user message as a search_context block, giving the model fresh real-time data.",
        },
        {
          label: "OFF",
          desc: "No search is performed. The LLM relies only on the input data you provide (stock fields from your JSON/YAML file).",
        },
      ].map(({ label, desc }) => (
        <Box
          key={label}
          sx={{ display: "flex", flexDirection: "column", gap: 0.25 }}
        >
          <Typography
            sx={{ color: "#93c5fd", fontWeight: 600, fontSize: "0.78rem" }}
          >
            {label}
          </Typography>
          <Typography
            sx={{ color: "#94a3b8", fontSize: "0.76rem", lineHeight: 1.5 }}
          >
            {desc}
          </Typography>
        </Box>
      ))}
    </Box>
  );

  const queryTemplateTooltip = (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
      <Typography
        sx={{ color: "#e2e8f0", fontWeight: 600, fontSize: "0.82rem" }}
      >
        Search Query Template
      </Typography>
      <Typography
        sx={{ color: "#94a3b8", fontSize: "0.78rem", lineHeight: 1.6 }}
      >
        The exact query sent to Tavily. Use{" "}
        <Box
          component="span"
          sx={{ color: "#fbbf24", fontFamily: "monospace" }}
        >
          {"{ticker}"}
        </Box>{" "}
        as a placeholder — it's replaced with the stock symbol at runtime.
      </Typography>
      <Box
        sx={{ bgcolor: "rgba(255,255,255,0.06)", borderRadius: "6px", p: 1 }}
      >
        <Typography
          sx={{
            color: "#86efac",
            fontFamily: "monospace",
            fontSize: "0.75rem",
          }}
        >
          {"{ticker}"} pre-market price short interest today
        </Typography>
        <Typography sx={{ color: "#64748b", fontSize: "0.73rem", mt: 0.5 }}>
          → "POET pre-market price short interest today"
        </Typography>
      </Box>
      <Typography
        sx={{ color: "#94a3b8", fontSize: "0.76rem", lineHeight: 1.5 }}
      >
        If left empty, falls back to a default query:{" "}
        <Box
          component="span"
          sx={{
            color: "#fbbf24",
            fontFamily: "monospace",
            fontSize: "0.73rem",
          }}
        >
          {"{ticker}"} stock latest news research 2026
        </Box>
      </Typography>
      <Typography
        sx={{ color: "#64748b", fontSize: "0.75rem", fontStyle: "italic" }}
      >
        Tip: Include "today" or "pre-market" to prioritize fresh data from
        Tavily.
      </Typography>
    </Box>
  );

  const outputSchemaTooltip = (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
      <Typography
        sx={{ color: "#e2e8f0", fontWeight: 600, fontSize: "0.82rem" }}
      >
        Output Schema
      </Typography>
      <Typography
        sx={{ color: "#94a3b8", fontSize: "0.78rem", lineHeight: 1.6 }}
      >
        A strict JSON Schema that defines exactly what fields this agent must
        return. The system injects this into the agent's system prompt and
        validates every response against it.
      </Typography>
      <Typography
        sx={{ color: "#94a3b8", fontSize: "0.78rem", lineHeight: 1.6 }}
      >
        If the response doesn't match, the system retries the LLM call up to 3
        times before logging a warning.
      </Typography>
      <Box
        sx={{ bgcolor: "rgba(255,255,255,0.06)", borderRadius: "6px", p: 1 }}
      >
        <Typography
          sx={{
            color: "#86efac",
            fontFamily: "monospace",
            fontSize: "0.73rem",
            whiteSpace: "pre",
          }}
        >
          {`{
  "type": "object",
  "properties": {
    "ticker": { "type": "string" },
    "price":  { "type": ["number","null"] }
  },
  "required": ["ticker"]
}`}
        </Typography>
      </Box>
      <Typography
        sx={{ color: "#64748b", fontSize: "0.75rem", fontStyle: "italic" }}
      >
        Optional — leave empty to skip schema enforcement for this prompt.
      </Typography>
    </Box>
  );

  const handleSubmit = async () => {
    if (!form.title.trim() || !form.content.trim()) {
      setError("Title and Prompt are required.");
      return;
    }

    const parsedSchema = parseOutputSchema();
    if (parsedSchema === "invalid") {
      setSchemaError(
        "Output Schema contains invalid JSON — fix it before saving.",
      );
      return;
    }

    setSaving(true);
    setError(null);
    setSchemaError(null);
    try {
      const searchPayload = {
        search_mode: resolvedSearchMode,
        search_enabled:
          resolvedSearchMode === "prefetch" ? form.search_enabled : false,
        search_query_template:
          resolvedSearchMode === "prefetch" && form.search_enabled
            ? form.search_query_template.trim() || null
            : null,
      };
      if (isEdit && editPrompt) {
        await updatePrompt(editPrompt.id, {
          title: form.title,
          content: form.content,
          category: defaultCategory,
          output_schema: parsedSchema,
          ...searchPayload,
        });
      } else {
        await createPrompt({
          title: form.title,
          content: form.content,
          category: defaultCategory,
          output_schema: parsedSchema,
          ...searchPayload,
        });
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
          {isEdit ? "Edit Prompt" : "Add Prompt"}
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
        <Field label="Title">
          <TextField
            placeholder="e.g. Financial Data Collector"
            value={form.title}
            onChange={set("title")}
            fullWidth
            size="small"
            sx={regularInputSx}
          />
        </Field>

        <Field label="Prompt">
          <TextField
            placeholder="Enter the prompt text…"
            value={form.content}
            onChange={set("content")}
            fullWidth
            multiline
            rows={6}
            sx={regularInputSx}
          />
        </Field>

        <Field label="Search Mode" tooltip={searchModeTooltip}>
          <Select
            value={searchModeValue}
            onChange={(e) =>
              setForm((f) => ({ ...f, search_mode: e.target.value }))
            }
            size="small"
            displayEmpty
            sx={{
              bgcolor: "rgba(255,255,255,0.05)",
              borderRadius: "6px",
              color: "#e8eaed",
              fontSize: "0.9rem",
              "& .MuiOutlinedInput-notchedOutline": {
                borderColor: "rgba(255,255,255,0.14)",
              },
              "&:hover .MuiOutlinedInput-notchedOutline": {
                borderColor: "rgba(255,255,255,0.28)",
              },
              "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
                borderColor: "#1976d2",
                borderWidth: "1px",
              },
              "& .MuiSelect-icon": { color: "rgba(255,255,255,0.45)" },
            }}
            MenuProps={{
              PaperProps: {
                sx: {
                  bgcolor: "#1a1d27",
                  color: "#e8eaed",
                  border: "1px solid rgba(255,255,255,0.12)",
                },
              },
            }}
          >
            <MenuItem value="">Use global setting (.env)</MenuItem>
            <MenuItem value="prefetch">
              Prefetch — run search before LLM call
            </MenuItem>
            <MenuItem value="tool_call">
              Tool call — LLM drives searches (multi-round)
            </MenuItem>
          </Select>
        </Field>

        {searchModeValue === "prefetch" && (
          <>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={form.search_enabled}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        search_enabled: e.target.checked,
                      }))
                    }
                    size="small"
                    sx={{
                      "& .MuiSwitch-switchBase.Mui-checked": {
                        color: "#1976d2",
                      },
                      "& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track":
                        { bgcolor: "#1976d2" },
                    }}
                  />
                }
                label={
                  <Typography
                    sx={{
                      color: "#cdd1d9",
                      fontSize: "0.875rem",
                      fontWeight: 500,
                    }}
                  >
                    Enable Search
                  </Typography>
                }
                sx={{ ml: 0, mr: 0 }}
              />
              <InfoTooltip content={enableSearchTooltip} />
            </Box>

            {form.search_enabled && (
              <Field
                label="Search Query Template"
                tooltip={queryTemplateTooltip}
              >
                <TextField
                  placeholder="{ticker} pre-market price short interest today"
                  value={form.search_query_template}
                  onChange={set("search_query_template")}
                  fullWidth
                  size="small"
                  helperText="Use {ticker} as a placeholder — it will be replaced with the stock symbol at runtime"
                  FormHelperTextProps={{
                    sx: {
                      color: "rgba(255,255,255,0.35)",
                      fontSize: "0.78rem",
                      ml: 0,
                    },
                  }}
                  sx={regularInputSx}
                />
              </Field>
            )}
          </>
        )}

        {/* ── Output Schema ── */}
        <Field label="Output Schema" tooltip={outputSchemaTooltip}>
          <TextField
            placeholder={
              '{\n  "type": "object",\n  "properties": {\n    "ticker": { "type": "string" }\n  },\n  "required": ["ticker"]\n}'
            }
            value={form.output_schema}
            onChange={(e) => {
              set("output_schema")(e);
              setSchemaError(null);
            }}
            fullWidth
            multiline
            rows={7}
            sx={inputSx}
          />
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              mt: 0.25,
            }}
          >
            {schemaError ? (
              <Typography sx={{ color: "#f44336", fontSize: "0.78rem" }}>
                {schemaError}
              </Typography>
            ) : (
              <Typography
                sx={{ color: "rgba(255,255,255,0.3)", fontSize: "0.78rem" }}
              >
                Optional — leave empty to skip schema enforcement
              </Typography>
            )}
            <Button
              size="small"
              onClick={handleFormatJson}
              disabled={!form.output_schema.trim()}
              sx={{
                color: "#90caf9",
                textTransform: "none",
                fontSize: "0.75rem",
                minWidth: 0,
                px: 1,
                "&:hover": { bgcolor: "rgba(144,202,249,0.08)" },
                "&.Mui-disabled": { color: "rgba(255,255,255,0.2)" },
              }}
            >
              Format JSON
            </Button>
          </Box>
        </Field>

        {/* ── Ticker input schema (read-only, stock agent prompts only) ── */}
        {isAgents && (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
              <Typography
                sx={{ color: "#cdd1d9", fontWeight: 500, fontSize: "0.875rem" }}
              >
                What this agent receives
              </Typography>
              <InfoTooltip
                content={
                  <Box
                    sx={{ display: "flex", flexDirection: "column", gap: 1 }}
                  >
                    <Typography
                      sx={{
                        color: "#e2e8f0",
                        fontWeight: 600,
                        fontSize: "0.82rem",
                      }}
                    >
                      Ticker Input Schema
                    </Typography>
                    <Typography
                      sx={{
                        color: "#94a3b8",
                        fontSize: "0.78rem",
                        lineHeight: 1.6,
                      }}
                    >
                      The ticker data object this agent receives at runtime.
                      Each field is described so the AI understands exactly what
                      the values mean.
                    </Typography>
                    <Typography
                      sx={{
                        color: "#94a3b8",
                        fontSize: "0.78rem",
                        lineHeight: 1.6,
                      }}
                    >
                      Defined in backend/stock_schema.json — update that file
                      when new fields are added to Data.json.
                    </Typography>
                  </Box>
                }
              />
            </Box>
            <Box
              sx={{
                bgcolor: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: "6px",
                p: 1.5,
                maxHeight: 200,
                overflowY: "auto",
              }}
            >
              {tickerInputSchema ? (
                <Typography
                  component="pre"
                  sx={{
                    color: "#86efac",
                    fontFamily: "monospace",
                    fontSize: "0.75rem",
                    m: 0,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {JSON.stringify(tickerInputSchema, null, 2)}
                </Typography>
              ) : (
                <Typography
                  sx={{
                    color: "rgba(255,255,255,0.3)",
                    fontSize: "0.8rem",
                    fontStyle: "italic",
                  }}
                >
                  No ticker schema found. Create backend/stock_schema.json to
                  populate this field.
                </Typography>
              )}
            </Box>
          </Box>
        )}

        {/* ── Sector input schema (read-only, sector prompts only) ── */}
        {isSectors && (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
              <Typography
                sx={{ color: "#cdd1d9", fontWeight: 500, fontSize: "0.875rem" }}
              >
                What this agent receives
              </Typography>
              <InfoTooltip
                content={
                  <Box
                    sx={{ display: "flex", flexDirection: "column", gap: 1 }}
                  >
                    <Typography
                      sx={{
                        color: "#e2e8f0",
                        fontWeight: 600,
                        fontSize: "0.82rem",
                      }}
                    >
                      Sector Input Schema
                    </Typography>
                    <Typography
                      sx={{
                        color: "#94a3b8",
                        fontSize: "0.78rem",
                        lineHeight: 1.6,
                      }}
                    >
                      The sector data object this agent receives at runtime.
                      Each field is described so the AI understands exactly what
                      the values mean.
                    </Typography>
                    <Typography
                      sx={{
                        color: "#94a3b8",
                        fontSize: "0.78rem",
                        lineHeight: 1.6,
                      }}
                    >
                      Defined in backend/sector_schema.json — update that file
                      when new fields are added to Sectors.json.
                    </Typography>
                  </Box>
                }
              />
            </Box>
            <Box
              sx={{
                bgcolor: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: "6px",
                p: 1.5,
                maxHeight: 200,
                overflowY: "auto",
              }}
            >
              {sectorInputSchema ? (
                <Typography
                  component="pre"
                  sx={{
                    color: "#86efac",
                    fontFamily: "monospace",
                    fontSize: "0.75rem",
                    m: 0,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {JSON.stringify(sectorInputSchema, null, 2)}
                </Typography>
              ) : (
                <Typography
                  sx={{
                    color: "rgba(255,255,255,0.3)",
                    fontSize: "0.8rem",
                    fontStyle: "italic",
                  }}
                >
                  No sector schema found. Create backend/sector_schema.json to
                  populate this field.
                </Typography>
              )}
            </Box>
          </Box>
        )}

        {/* ── Macro input schema (read-only, macro prompts only) ── */}
        {isMacro && (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
              <Typography
                sx={{ color: "#cdd1d9", fontWeight: 500, fontSize: "0.875rem" }}
              >
                What this agent receives
              </Typography>
              <InfoTooltip
                content={
                  <Box
                    sx={{ display: "flex", flexDirection: "column", gap: 1 }}
                  >
                    <Typography
                      sx={{
                        color: "#e2e8f0",
                        fontWeight: 600,
                        fontSize: "0.82rem",
                      }}
                    >
                      Macro Input Schema
                    </Typography>
                    <Typography
                      sx={{
                        color: "#94a3b8",
                        fontSize: "0.78rem",
                        lineHeight: 1.6,
                      }}
                    >
                      The macro entity object this agent receives at runtime.
                      Each field is described so the AI understands exactly what
                      the values mean.
                    </Typography>
                    <Typography
                      sx={{
                        color: "#94a3b8",
                        fontSize: "0.78rem",
                        lineHeight: 1.6,
                      }}
                    >
                      Defined in backend/macro_schema.json — update that file
                      when new fields are added to Macro.json.
                    </Typography>
                  </Box>
                }
              />
            </Box>
            <Box
              sx={{
                bgcolor: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: "6px",
                p: 1.5,
                maxHeight: 200,
                overflowY: "auto",
              }}
            >
              {macroInputSchema ? (
                <Typography
                  component="pre"
                  sx={{
                    color: "#86efac",
                    fontFamily: "monospace",
                    fontSize: "0.75rem",
                    m: 0,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {JSON.stringify(macroInputSchema, null, 2)}
                </Typography>
              ) : (
                <Typography
                  sx={{
                    color: "rgba(255,255,255,0.3)",
                    fontSize: "0.8rem",
                    fontStyle: "italic",
                  }}
                >
                  No macro schema found. Create backend/macro_schema.json to
                  populate this field.
                </Typography>
              )}
            </Box>
          </Box>
        )}

        {/* ── CEO input schema (read-only, CEO prompts only) ── */}
        {isCeo && (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
              <Typography
                sx={{ color: "#cdd1d9", fontWeight: 500, fontSize: "0.875rem" }}
              >
                What this agent receives
              </Typography>
              <InfoTooltip
                content={
                  <Box
                    sx={{ display: "flex", flexDirection: "column", gap: 1 }}
                  >
                    <Typography
                      sx={{
                        color: "#e2e8f0",
                        fontWeight: 600,
                        fontSize: "0.82rem",
                      }}
                    >
                      CEO Input Schema
                    </Typography>
                    <Typography
                      sx={{
                        color: "#94a3b8",
                        fontSize: "0.78rem",
                        lineHeight: 1.6,
                      }}
                    >
                      Auto-computed from the output schemas of all currently
                      active stock agents. This is what the CEO agent receives
                      at runtime — use these field names in your prompt text.
                    </Typography>
                    <Typography
                      sx={{
                        color: "#94a3b8",
                        fontSize: "0.78rem",
                        lineHeight: 1.6,
                      }}
                    >
                      Updates automatically when you add, remove, or change
                      stock agent schemas.
                    </Typography>
                  </Box>
                }
              />
            </Box>
            <Box
              sx={{
                bgcolor: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: "6px",
                p: 1.5,
                maxHeight: 200,
                overflowY: "auto",
              }}
            >
              {ceoInputSchema ? (
                <Typography
                  component="pre"
                  sx={{
                    color: "#86efac",
                    fontFamily: "monospace",
                    fontSize: "0.75rem",
                    m: 0,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {JSON.stringify(ceoInputSchema, null, 2)}
                </Typography>
              ) : (
                <Typography
                  sx={{
                    color: "rgba(255,255,255,0.3)",
                    fontSize: "0.8rem",
                    fontStyle: "italic",
                  }}
                >
                  No active stock agents have output schemas defined yet. Add
                  output schemas to your stock agent prompts to see the CEO
                  input schema here.
                </Typography>
              )}
            </Box>
          </Box>
        )}

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
          {saving ? "Saving…" : isEdit ? "Save Changes" : "Add Prompt"}
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
