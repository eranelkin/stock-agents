import { useEffect, useRef, useState } from "react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import IconButton from "@mui/material/IconButton";
import Paper from "@mui/material/Paper";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

const ACCEPTED_TYPES = ".json,.csv,.txt,.md,.xml,.yaml,.yml,.toml,.log";
const MAX_FILE_BYTES = 512 * 1024;

interface Attachment {
  name: string;
  content: string;
  mime_type: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  attachments?: { name: string }[];
  streaming?: boolean;
  error?: boolean;
}

// ─── Icons ────────────────────────────────────────────────────────────────────

function PaperclipIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66L9.41 17.41a2 2 0 0 1-2.83-2.83l8.49-8.48" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
    </svg>
  );
}

function FileIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
      <polyline points="13 2 13 9 20 9" />
    </svg>
  );
}

// ─── Message bubble ───────────────────────────────────────────────────────────

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
        px: 2,
        py: 0.5,
      }}
    >
      <Paper
        elevation={0}
        sx={{
          maxWidth: "72%",
          px: 2,
          py: 1.25,
          bgcolor: isUser ? "rgba(25,118,210,0.18)" : "rgba(255,255,255,0.05)",
          border: "1px solid",
          borderColor: isUser
            ? "rgba(25,118,210,0.35)"
            : "rgba(255,255,255,0.08)",
          borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
        }}
      >
        <Typography
          variant="body2"
          sx={{
            whiteSpace: "pre-wrap",
            lineHeight: 1.7,
            color: message.error ? "#f44336" : "text.primary",
          }}
        >
          {message.content}
          {message.streaming && (
            <Box
              component="span"
              sx={{
                display: "inline-block",
                width: 7,
                height: 13,
                ml: 0.25,
                bgcolor: "text.primary",
                borderRadius: "1px",
                verticalAlign: "text-bottom",
                animation: "blink 1s step-end infinite",
                "@keyframes blink": {
                  "0%, 100%": { opacity: 1 },
                  "50%": { opacity: 0 },
                },
              }}
            />
          )}
        </Typography>

        {message.attachments && message.attachments.length > 0 && (
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, mt: 1 }}>
            {message.attachments.map((a) => (
              <Chip
                key={a.name}
                label={a.name}
                size="small"
                icon={
                  <Box sx={{ ml: 0.5 }}>
                    <FileIcon />
                  </Box>
                }
                variant="outlined"
                sx={{ fontSize: "0.7rem", height: 22 }}
              />
            ))}
          </Box>
        )}
      </Paper>
    </Box>
  );
}

// ─── Empty state ──────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <Box
      sx={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 1,
        opacity: 0.35,
        userSelect: "none",
      }}
    >
      <Typography variant="h4" fontWeight={700}>
        Stock Agents
      </Typography>
      <Typography variant="body2" color="text.secondary">
        Ask me to analyze a stock, or attach a file to get started.
      </Typography>
    </Box>
  );
}

// ─── Main chat page ───────────────────────────────────────────────────────────

interface ChatPageProps {
  selectedModelIds: string[];
  pendingInput?: string | null;
  onClearPendingInput?: () => void;
}

export default function ChatPage({ selectedModelIds, pendingInput, onClearPendingInput }: ChatPageProps) {
  const selectedModelId = selectedModelIds[0] ?? null;

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [fileError, setFileError] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (pendingInput) {
      setInput(pendingInput);
      onClearPendingInput?.();
    }
  }, [pendingInput, onClearPendingInput]);

  const scrollToBottom = () =>
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    setFileError("");
    const files = Array.from(e.target.files ?? []);
    e.target.value = "";

    const readers = files.map(
      (file) =>
        new Promise<Attachment>((resolve, reject) => {
          if (file.size > MAX_FILE_BYTES) {
            reject(`"${file.name}" exceeds the 512 KB limit.`);
            return;
          }
          const reader = new FileReader();
          reader.onload = () =>
            resolve({
              name: file.name,
              content: reader.result as string,
              mime_type: file.type || "text/plain",
            });
          reader.onerror = () => reject(`Failed to read "${file.name}".`);
          reader.readAsText(file);
        }),
    );

    Promise.allSettled(readers).then((results) => {
      const ok = results
        .filter((r) => r.status === "fulfilled")
        .map((r) => (r as PromiseFulfilledResult<Attachment>).value);
      const errors = results
        .filter((r) => r.status === "rejected")
        .map((r) => (r as PromiseRejectedResult).reason as string);

      if (errors.length) setFileError(errors.join(" "));

      setAttachments((prev) => {
        const existing = new Set(prev.map((a) => a.name));
        return [...prev, ...ok.filter((a) => !existing.has(a.name))];
      });
    });
  }

  function removeAttachment(name: string) {
    setAttachments((prev) => prev.filter((a) => a.name !== name));
  }

  async function sendMessage() {
    const text = input.trim();
    if ((!text && attachments.length === 0) || loading || !selectedModelId)
      return;

    const userMsg: Message = {
      role: "user",
      content: text || "(see attached files)",
      attachments: attachments.length > 0 ? attachments.map(({ name }) => ({ name })) : undefined,
    };
    const nextMessages = [...messages, userMsg];

    setMessages(nextMessages);
    setInput("");
    setAttachments([]);
    setFileError("");
    setLoading(true);

    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", streaming: true },
    ]);

    setTimeout(scrollToBottom, 50);

    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model_id: selectedModelId,
          messages: nextMessages.map(({ role, content }) => ({ role, content })),
          attachments,
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail ?? `Server error ${response.status}`);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop()!;

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6).trim();
          if (data === "[DONE]") continue;
          let parsed: { content?: string; error?: string };
          try {
            parsed = JSON.parse(data);
          } catch {
            continue;
          }
          if (parsed.error) throw new Error(parsed.error);
          if (parsed.content) {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = {
                ...last,
                content: last.content + parsed.content,
              };
              return updated;
            });
            scrollToBottom();
          }
        }
      }

      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          streaming: false,
        };
        return updated;
      });
    } catch (err) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          content: `Error: ${(err as Error).message}`,
          streaming: false,
          error: true,
        };
        return updated;
      });
    } finally {
      setLoading(false);
      setTimeout(scrollToBottom, 50);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  const canSend = input.trim().length > 0 && !!selectedModelId && !loading;

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        flex: 1,
        minHeight: 0,
        overflow: "hidden",
      }}
    >
      {/* Messages area */}
      <Box sx={{ flex: 1, minHeight: 0, overflowY: "auto", py: 2, display: "flex", flexDirection: "column" }}>
        {messages.length === 0 ? (
          <EmptyState />
        ) : (
          messages.map((msg, i) => <MessageBubble key={i} message={msg} />)
        )}
        <div ref={bottomRef} />
      </Box>

      {/* Input footer */}
      <Box
        sx={{
          borderTop: "1px solid rgba(255,255,255,0.08)",
          px: 2,
          pt: 1,
          pb: 1.5,
          bgcolor: "background.paper",
          flexShrink: 0,
        }}
      >
        {/* Pending attachment chips */}
        {attachments.length > 0 && (
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, mb: 1 }}>
            {attachments.map((a) => (
              <Chip
                key={a.name}
                label={a.name}
                size="small"
                onDelete={() => removeAttachment(a.name)}
                icon={
                  <Box sx={{ ml: 0.5 }}>
                    <FileIcon />
                  </Box>
                }
                variant="outlined"
                color="primary"
                sx={{ fontSize: "0.75rem" }}
              />
            ))}
          </Box>
        )}

        {fileError && (
          <Typography variant="caption" color="error" sx={{ display: "block", mb: 0.5 }}>
            {fileError}
          </Typography>
        )}

        {!selectedModelId && (
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
            Select a model in the header to start chatting.
          </Typography>
        )}

        <Box sx={{ display: "flex", gap: 1, alignItems: "flex-end" }}>
          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_TYPES}
            multiple
            style={{ display: "none" }}
            onChange={handleFileChange}
          />

          {/* Attach button */}
          <Tooltip title="Attach file (JSON, CSV, TXT…)" placement="top">
            <span>
              <IconButton
                size="small"
                onClick={() => fileInputRef.current?.click()}
                disabled={loading}
                sx={{
                  mb: 0.25,
                  color: "text.secondary",
                  "&:hover": { color: "#fff" },
                }}
              >
                <PaperclipIcon />
              </IconButton>
            </span>
          </Tooltip>

          {/* Multiline input */}
          <TextField
            multiline
            minRows={1}
            maxRows={6}
            fullWidth
            placeholder={
              selectedModelId
                ? "Ask about a stock… (Shift+Enter for new line)"
                : "Select a model to start…"
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading || !selectedModelId}
            size="small"
            sx={{
              "& .MuiOutlinedInput-root": {
                borderRadius: 2,
                fontSize: "0.9rem",
              },
              "& textarea": {
                overflow: "auto !important",
              },
            }}
          />

          {/* Send button */}
          <Tooltip title="Send (Enter)" placement="top">
            <span>
              <IconButton
                onClick={sendMessage}
                disabled={!canSend}
                sx={{
                  mb: 0.25,
                  bgcolor: canSend ? "#1976d2" : "rgba(255,255,255,0.08)",
                  color: canSend ? "#fff" : "text.disabled",
                  "&:hover": { bgcolor: canSend ? "#1565c0" : undefined },
                  transition: "background-color 0.2s",
                  width: 36,
                  height: 36,
                }}
              >
                {loading ? (
                  <CircularProgress size={16} sx={{ color: "inherit" }} />
                ) : (
                  <SendIcon />
                )}
              </IconButton>
            </span>
          </Tooltip>
        </Box>
      </Box>
    </Box>
  );
}
