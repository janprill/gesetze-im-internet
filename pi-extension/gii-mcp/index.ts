/**
 * gii-mcp — Pi-Extension, die den gii MCP-Server (stdio) bridge.
 *
 * Spawnt `gii mcp --transport stdio --repo-dir <abs>` als langes Kind,
 * macht den JSON-RPC-Handshake und registriert alle vom Server
 * annoncierten Tools per pi.registerTool(). Aufrufe werden 1:1 als
 * `tools/call` weitergereicht.
 *
 * Config (Env):
 *   GII_BIN        — Pfad zum gii-Binary (Default: ~/go/bin/gii)
 *   GII_MCP_REPO_DIR — lokaler Daten-Checkout (Default:
 *                    ~/age/gesetze-im-internet/.gii-data)
 *   GII_MCP_ARGS   — zusätzliche Args, leerzeichengetrennt (selten nötig)
 *
 * context-mode-Hinweis: law_text liefert ganze Gesetze als Plaintext
 * (z.B. BGB = sehr groß). Für Einzelfragen `norm_text` verwenden; für
 * Volltexte das Ergebnis per ctx_index ablegen und per ctx_search
 * abfragen, damit die Bytes nicht den Kontext fluten.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type, type TSchema } from "typebox";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";

// StringEnum aus pi-ai ist optional — keins der gii-Tools nutzt Enums.
// Lazy-Auflösung beim ersten Gebrauch, damit ein Export-Problem nie den
// Ladeprozess der Extension gefährdet.
let _stringEnum: ((
  vals: [string, ...string[]],
  opts?: { description?: string },
) => TSchema) | null | undefined = undefined;
async function getStringEnum() {
  if (_stringEnum !== undefined) return _stringEnum;
  try {
    const mod: any = await import("@earendil-works/pi-ai");
    _stringEnum = mod.StringEnum ?? null;
  } catch {
    _stringEnum = null;
  }
  return _stringEnum;
}

const GII_BIN = process.env.GII_BIN ?? join(homedir(), "go", "bin", "gii");
const REPO_DIR =
  process.env.GII_MCP_REPO_DIR ??
  join(homedir(), "age", "gesetze-im-internet", ".gii-data");
const EXTRA_ARGS = process.env.GII_MCP_ARGS
  ? process.env.GII_MCP_ARGS.split(/\s+/).filter(Boolean)
  : [];

type JsonRpcResponse = {
  jsonrpc: "2.0";
  id: number | string;
  result?: unknown;
  error?: { code: number; message: string; data?: unknown };
};
type JsonRpcNotification = { jsonrpc: "2.0"; method: string; params?: unknown };

type McpTool = {
  name: string;
  description?: string;
  inputSchema?: {
    type?: string;
    properties?: Record<string, unknown>;
    required?: string[];
  };
};

type McpCallResult = {
  content?: Array<{ type: string; text?: string } | Record<string, unknown>>;
  isError?: boolean;
};

class GiiMcpClient {
  private proc: ChildProcessWithoutNullStreams;
  private buf = "";
  private nextId = 1;
  private pending = new Map<
    number,
    { resolve: (v: unknown) => void; reject: (e: Error) => void }
  >();
  ready: Promise<void>;
  tools: McpTool[] = [];

  constructor() {
    const args = [
      "mcp",
      "--transport",
      "stdio",
      "--repo-dir",
      REPO_DIR,
      ...EXTRA_ARGS,
    ];
    this.proc = spawn(GII_BIN, args, { stdio: ["pipe", "pipe", "pipe"] });
    this.proc.stdout.setEncoding("utf-8");
    this.proc.stdout.on("data", this.onStdout);
    this.proc.stderr.on("data", (d) => {
      const s = d.toString().trim();
      if (s) process.stderr.write(`[gii-mcp] ${s}\n`);
    });
    this.proc.on("exit", (code, sig) => {
      if (!this.proc.killed) {
        process.stderr.write(
          `[gii-mcp] child exited unexpectedly code=${code} sig=${sig}\n`,
        );
      }
      const err = new Error(`gii mcp exited (code=${code} sig=${sig})`);
      for (const p of this.pending.values()) p.reject(err);
      this.pending.clear();
    });
    this.ready = this.handshake();
  }

  private onStdout = (chunk: string) => {
    this.buf += chunk;
    let nl: number;
    while ((nl = this.buf.indexOf("\n")) >= 0) {
      const line = this.buf.slice(0, nl).trim();
      this.buf = this.buf.slice(nl + 1);
      if (!line) continue;
      let msg: JsonRpcResponse | JsonRpcNotification;
      try {
        msg = JSON.parse(line);
      } catch {
        continue;
      }
      if ("id" in msg && msg.id !== undefined) {
        const id = typeof msg.id === "string" ? msg.id : msg.id;
        const p = this.pending.get(id as number);
        if (p) {
          this.pending.delete(id as number);
          if ((msg as JsonRpcResponse).error)
            p.reject(
              new Error(
                (msg as JsonRpcResponse).error!.message +
                  " (code " +
                  (msg as JsonRpcResponse).error!.code +
                  ")",
              ),
            );
          else p.resolve((msg as JsonRpcResponse).result);
        }
      }
    }
  };

  private send(payload: unknown) {
    this.proc.stdin.write(JSON.stringify(payload) + "\n");
  }

  private request(method: string, params?: unknown): Promise<unknown> {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.send({ jsonrpc: "2.0", id, method, params });
    });
  }

  private notify(method: string, params?: unknown) {
    this.send({ jsonrpc: "2.0", method, params });
  }

  private async handshake() {
    const initResult = (await this.request("initialize", {
      protocolVersion: "2024-11-05",
      capabilities: {},
      clientInfo: { name: "pi-gii-mcp", version: "0.1.0" },
    })) as { serverInfo?: { name: string; version: string } };
    this.notify("notifications/initialized");
    const list = (await this.request("tools/list", {})) as {
      tools?: McpTool[];
    };
    this.tools = list.tools ?? [];
    process.stderr.write(
      `[gii-mcp] ready: ${initResult?.serverInfo?.name ?? "?"} v${initResult?.serverInfo?.version ?? "?"} — ${this.tools.length} tools: ${this.tools.map((t) => t.name).join(", ")}\n`,
    );
  }

  async callTool(name: string, args: Record<string, unknown>): Promise<string> {
    const result = (await this.request("tools/call", {
      name,
      arguments: args,
    })) as McpCallResult;
    if (!result) return "";
    const parts: string[] = [];
    for (const c of result.content ?? []) {
      if (typeof c === "object" && c !== null && "text" in c) {
        const t = (c as { text?: string }).text;
        if (t) parts.push(t);
      }
    }
    const text = parts.join("\n");
    if (result.isError) throw new Error(text || `gii tool ${name} returned isError`);
    return text;
  }

  shutdown() {
    try {
      this.proc.kill("SIGTERM");
      setTimeout(() => {
        try {
          this.proc.kill("SIGKILL");
        } catch {
          /* already dead */
        }
      }, 1500);
    } catch {
      /* ignore */
    }
  }
}

// JSON-Schema → Typebox (abgedeckt: string/integer/number/boolean + string-enum)
async function propToTypebox(prop: Record<string, unknown>): Promise<TSchema> {
  const desc = (prop.description as string) ?? undefined;
  const type = prop.type as string | string[] | undefined;
  const t = Array.isArray(type) ? type[0] : type;
  if (
    Array.isArray(prop.enum) &&
    prop.enum.every((v) => typeof v === "string")
  ) {
    const SE = await getStringEnum();
    if (SE)
      return SE(prop.enum as [string, ...string[]], { description: desc });
    return Type.String({ description: desc, enum: prop.enum as string[] }) as TSchema;
  }
  switch (t) {
    case "integer":
      return Type.Integer({ description: desc });
    case "number":
      return Type.Number({ description: desc });
    case "boolean":
      return Type.Boolean({ description: desc });
    case "string":
    default:
      return Type.String({ description: desc });
  }
}

async function buildParameters(tool: McpTool) {
  const props = tool.inputSchema?.properties ?? {};
  const required = new Set(tool.inputSchema?.required ?? []);
  const out: Record<string, TSchema> = {};
  for (const [key, raw] of Object.entries(props)) {
    const schema = await propToTypebox(raw as Record<string, unknown>);
    out[key] = required.has(key) ? schema : Type.Optional(schema);
  }
  return Type.Object(out);
}

export default function (pi: ExtensionAPI) {
  let client: GiiMcpClient | null = null;

  const ensureClient = (): GiiMcpClient => {
    if (!client) client = new GiiMcpClient();
    return client;
  };

  pi.on("session_start", async () => {
    try {
      const c = ensureClient();
      await c.ready;
      for (const tool of c.tools) {
        const parameters = await buildParameters(tool);
        pi.registerTool({
          name: `gii_${tool.name}`,
          label: `gii: ${tool.name}`,
          description:
            tool.description ??
            `gii MCP tool ${tool.name} (Gesetze-im-Internet)`,
          promptSnippet: `gii_${tool.name}: ${tool.description?.slice(0, 120) ?? tool.name}`,
          promptGuidelines: [
            "Use gii_norm_text (not gii_law_text) when a single §/article is needed — it is token-sparse.",
            "For full law text via gii_law_text, pipe the result through ctx_index and query via ctx_search so the bytes stay out of context.",
            "If a gii tool reports local_cache_missing, call gii_update_cache once, then retry.",
          ],
          parameters,
          async execute(_id, params) {
            const text = await c.callTool(tool.name, params);
            return {
              content: [{ type: "text", text }],
              details: { tool: tool.name, bytes: text.length },
            };
          },
        });
      }
    } catch (e) {
      process.stderr.write(
        `[gii-mcp] startup failed: ${(e as Error).message}\n`,
      );
    }
  });

  pi.on("session_shutdown", () => {
    try {
      client?.shutdown();
    } catch {
      /* ignore */
    }
  });
}
