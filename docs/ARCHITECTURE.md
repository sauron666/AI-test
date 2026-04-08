# SAURON — Architecture

This document explains how SAURON is put together so contributors can
extend it without breaking the agent contract.

## High-level

```
┌──────────────────────────────────────────────────────────────────┐
│                        WEB DASHBOARD                             │
│    zero-build SPA · live terminal · graph · reports · settings  │
└───────────────────────────┬──────────────────────────────────────┘
                            │ REST + WebSocket
┌───────────────────────────▼──────────────────────────────────────┐
│                     FastAPI BACKEND                              │
│ auth · engagements · tools · llm · reports · websocket broadcast│
└─────┬─────────────────┬────────────────┬─────────────────────────┘
      │                 │                │
┌─────▼────────┐ ┌──────▼─────────┐ ┌────▼─────────────────────┐
│ LLM ROUTER   │ │ AGENT ORCHESTR │ │ MCP SERVER               │
│ claude/gpt/  │◄┤  ReAct loop +  │►│ exposes every tool       │
│ gemini/ollama│ │  sub-agents    │ │ over JSON-RPC/WebSocket  │
└──────────────┘ └──────┬─────────┘ └────┬─────────────────────┘
                        │                │
                 ┌──────▼────────────────▼───────────────────────┐
                 │            TOOL EXECUTOR                      │
                 │  sandbox · stdout/stderr capture · screenshot │
                 │  PTY record (asciinema) · banned-cmd filter   │
                 └──────┬────────────────────────────────────────┘
                        │
              ┌─────────▼──────────┐
              │    KALI ARSENAL    │
              │  500+ integrated   │
              │       tools        │
              └────────────────────┘
```

## Request flow (engagement start)

```
operator → POST /api/engagements/{id}/start
  → BackgroundTasks → Orchestrator.run_engagement(ctx)
      for phase in PHASE_SEQUENCE[profile]:
          agent = build_agent(phase)                     ← picks sub-agent class
          loop:
              llm_resp = router.for_role(...).complete(msgs, tools=mcp_tools)
              for tool_call in llm_resp.tool_calls:
                  result = mcp.call_tool(name, args)     ← runs Kali command
                  ctx.history.append(tool_result)
                  broadcast(event)                       ← WS to dashboard
              if reflection_enabled:
                  reflection = small_llm.complete(critique_prompt)
          emit phase.complete
      emit engagement.complete
```

## Module layout

| Path | Responsibility |
|---|---|
| `backend/main.py`          | FastAPI factory, lifespan, startup of MCP + static UI |
| `backend/settings.py`      | Typed env + YAML config |
| `backend/llm/*`            | Provider abstraction (Claude, OpenAI, Gemini, Ollama) + router |
| `backend/agents/*`         | Base agent + orchestrator + recon/scan/exploit/post-ex/red-team/report |
| `backend/mcp/server.py`    | MCP server — exposes every Kali tool + generic shell_exec |
| `backend/tools/executor.py`| THE place commands actually run — sandbox + capture |
| `backend/tools/kali_catalog.py` | Loads `config/kali_tools.yaml` → `ToolSpec` list |
| `backend/tools/stealth.py` | Stealth profiles (T1..T4, jitter, UA rotation) |
| `backend/pentest/*`        | High-level helper functions per domain |
| `backend/reporting/*`      | MD/HTML/PDF generator + synthetic terminal screenshot |
| `backend/database/*`       | SQLAlchemy models + session |
| `backend/api/*`            | HTTP routers + Pydantic schemas + WebSocket |
| `frontend/*`               | Zero-build cyberpunk SPA |
| `config/*.yaml`            | Tool catalog, LLM catalog, engagement profiles |
| `scripts/*.sh`             | install / start / ollama / bootstrap_kali |

## Extending

### Add a new LLM provider
1. Create `backend/llm/<name>_provider.py` subclassing `BaseLLMProvider`.
2. Register it in `backend/llm/router.py::PROVIDER_CLASSES`.
3. Add an entry to `config/llm_providers.yaml`.

### Add a new Kali tool
Just append to `config/kali_tools.yaml`. It becomes available to the
agent, the MCP server, and the dashboard automatically.

### Add a new pentest profile
Add to `config/pentest_profiles.yaml`. The orchestrator will auto-pick
it up. If the phase list differs from the default sequence, register
it in `PHASE_SEQUENCE` inside `backend/agents/orchestrator.py`.

## Safety by design
- `backend/utils/security.py::HARD_BANNED_PATTERNS` stops the executor
  from running destructive commands regardless of caller.
- `AGENT_AUTO_APPROVE_COMMANDS=false` pauses the agent on every action
  and waits for operator approval (wired into the WebSocket layer).
- No payload generators, no weaponised implants, no exfiltration.
- Every command is recorded with stdout, stderr, exit code, duration,
  screenshot and (optionally) an asciinema PTY cast.
