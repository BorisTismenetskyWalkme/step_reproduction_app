# Repro - Step Reproduction App

Flask web application for BrowserStack automation test management with two main features:
1. **Generate Test Reproduction Links** - Convert BS session URLs to shareable Repro report links
2. **Delete Failed Sessions** - Bulk delete failed test sessions from BrowserStack builds

## Features

### 1. Generate Test Reproduction Link
- Paste a BrowserStack session URL
- Generates a shareable HTML file with test step reproduction
- Downloads automatically for easy sharing

### 2. Cleanup Failed Sessions
- Delete all failed test sessions from a BrowserStack build
- Smart build selection (prefers builds with status "failed")
- Supports both build names and hashed IDs
- Full pagination support (fetches all sessions)
- Retry logic (3 attempts per session)
- Real-time progress feedback

## Setup

### Prerequisites
- Python 3.8+
- BrowserStack account with API access

### Installation

1. Navigate to the step_reproduction_app directory
2. Install dependencies:
   ```bash
   pip install flask requests
   ```

3. Set environment variables:
   ```powershell
   # PowerShell
   $env:AUTOMATION_BS_USER = "your_browserstack_username"
   $env:AUTOMATION_BS_PASS = "your_browserstack_access_key"
   ```


## Usage

### Start the Application

```bash
python app.py
```

Open your browser to `http://127.0.0.1:5000`

### Generate Test Reproduction Link

1. Go to BrowserStack dashboard
2. Copy a session URL like:
   ```
   https://automate.browserstack.com/dashboard/v2/sessions/abc123...
   ```
3. Paste it into the "Generate Link" form
4. Click "Generate Link"
5. Download the generated HTML file

### Delete Failed Sessions

Two methods:

#### Method A: Use Build Name (Smart Auto-Select)
1. Enter build name: `20260412-064121-6903a`
2. Click "Delete Failed Sessions"
3. Tool automatically selects builds with status "failed"

#### Method B: Use Hashed ID (100% Precise)
1. Go to BrowserStack dashboard, find your build
2. Copy hashed ID from URL:
   ```
   https://automate.browserstack.com/dashboard/v2/builds/910d848cde11c50835c0537c3b8899552067f48c
   ```
3. Paste the 40-character hashed ID: `910d848cde11c50835c0537c3b8899552067f48c`
4. Click "Delete Failed Sessions"

### Smart Build Selection

When multiple builds have the same name, the tool:
- ✅ Automatically prefers builds with status "failed"
- ✅ Shows all matching builds with details
- ✅ Provides helpful tips for precise targeting
- ✅ Uses the most recent "failed" build by default

Example output:
```
⚠️  WARNING: Found 6 builds with name '20260412-064121-6903a'
Build matches:
  1. hashed_id: 5b54a..., status: done, duration: 69345s
  2. hashed_id: 910d8..., status: failed, duration: 701052s

✓ Auto-selected most recent FAILED build: 910d8...
  (Reason: Build status is 'failed', likely contains failed sessions)
```

## Tips for Finding Build IDs

To find your build's hashed ID:
1. Go to BrowserStack dashboard: https://automate.browserstack.com/dashboard
2. Click on a build
3. Copy the 40-character hash from the URL:
   ```
   https://automate.browserstack.com/dashboard/v2/builds/[THIS_40_CHAR_HASH]
   ```

## How It Works

### Cleanup Process

1. **Build Lookup**
   - Searches 300 recent builds
   - Matches by name or uses hashed ID directly
   - Prefers "failed" builds when multiple matches

2. **Session Fetching**
   - Fetches all sessions with pagination
   - Handles up to 1000+ sessions per build
   - Shows progress for each page

3. **Session Filtering**
   - Deletes sessions with status: `error`, `failed`, `timeout`
   - Keeps sessions with status: `passed`, `running`
   - Shows status breakdown

4. **Deletion with Retry**
   - 3 retry attempts per session
   - Exponential backoff (1s, 2s, 4s)
   - Handles rate limiting (429 errors)
   - Shows progress: "Deleted 50/120 sessions..."

## API Endpoints

- `GET /` - Main page
- `POST /` - Process form submissions
  - Generate link: `session_url` parameter
  - Cleanup sessions: `build_id` parameter

## Environment Variables

| Variable              | Description               | Required |
|-----------------------|---------------------------|----------|
| `AUTOMATION_BS_USER`  | BrowserStack username     | Yes      |
| `AUTOMATION_BS_PASS`  | BrowserStack access key   | Yes      |

Get your credentials at: https://automate.browserstack.com/dashboard

## Troubleshooting

### "Invalid build ID format or build not found"

**Solution 1:** Use the hashed ID directly from the BrowserStack URL
```
https://automate.browserstack.com/dashboard/v2/builds/[COPY_THIS_40_CHAR_STRING]
```

**Solution 2:** Check your BrowserStack dashboard to verify the build exists

### "Found 0 failed sessions"

**Possible reasons:**
- Build genuinely has no failed tests
- Wrong build selected (use hashed ID for precision)
- All sessions already deleted

**Solution:** Verify in BrowserStack dashboard that the build has failed sessions

### Multiple Builds with Same Name

The tool automatically handles this by:
- Showing all matches
- Preferring builds with status "failed"
- Suggesting hashed ID for precision

For exact targeting, always use the hashed ID.

## Tips

### Best Practices

1. **Use hashed ID for precision** - Eliminates ambiguity
2. **Check browser console** - See detailed progress and selection logic
3. **Verify build first** - Check BrowserStack dashboard before deletion
4. **Let smart selection work** - It prefers failed builds automatically

### Common Scenarios

**Scenario 1: Quick cleanup of latest failed build**
- Enter build name
- Tool auto-selects the most recent failed build
- Done!

**Scenario 2: Cleanup specific build**
- Copy hashed ID from BS dashboard URL
- Paste it into the form
- Guaranteed to target exact build

**Scenario 3: Not sure which build**
- Check BrowserStack dashboard
- Look at recent builds list
- Copy the correct build name or hashed ID

## BrowserStack MCP Server

`browserstack_mcp_server.py` exposes BrowserStack Automate data and actions as
MCP tools, so an AI agent (Claude Desktop, a claude.ai custom connector, etc.)
can inspect and manage builds/sessions directly in chat instead of through
this web UI.

It reuses the fetching/parsing functions already defined in `app.py`
(`fetch_session`, `fetch_logs`, `parse_steps`, `extract_eux_bo_url`,
`get_all_hashed_build_ids`, `delete_failed_sessions`, etc.) by importing the
module directly, so behavior stays in sync with this app rather than drifting
in a second copy. Importing `app.py` does not start its Flask server.

### What it can NOT do

There is intentionally no "stop a running build/session" tool. BrowserStack's
public Automate REST API has no documented endpoint to forcibly terminate an
in-progress session or build -- a live Selenium session only ends when the
test's own WebDriver calls `quit()`, or BrowserStack's own idle/session
timeout fires. The dashboard's own "stop" behavior isn't part of the public
API.

### Tools

| Tool | Purpose |
|---|---|
| `list_builds` | List recent builds, optionally filtered by status (`running`, `done`, `failed`, `timeout`) |
| `resolve_build_id` | Resolve a build name to its hashed ID(s) |
| `list_build_sessions` | List sessions inside a build |
| `get_session` | Full session details + cleaned error reason |
| `get_session_logs` | Raw text/selenium/console/appium logs |
| `get_walkme_network_logs` | HAR network log filtered to WalkMe requests |
| `find_last_successful_run` | Last passing run of the same test |
| `get_reproduction_summary` | One-shot debugging summary (status, steps, error, EUX BO link, network) -- the JSON equivalent of the HTML page this app generates |
| `update_session_status` | Tag a session `passed`/`failed` + reason (metadata only, doesn't affect execution) |
| `delete_session` | Delete one session record |
| `delete_failed_sessions_in_build` | Bulk-delete failed/error/timeout sessions in a build (wraps this app's cleanup feature) |
| `delete_build` | Delete a build + all its sessions (`confirm=true` required) |
| `delete_builds` | Delete up to 5 builds at once (`confirm=true` required) |

### Running it

**Locally, as a Claude Desktop Extension (recommended):**

`browserstack-qa.mcpb` in this folder is a ready-to-install
[Desktop Extension](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop).
It uses the `uv` server type, so Claude Desktop manages the Python
environment and dependencies itself -- no manual venv, no pip install, and
no hand-edited `claude_desktop_config.json` (which on some installs,
including MSIX/Store-packaged ones, isn't at the path you'd expect anyway).

1. In Claude Desktop: **Settings > Extensions > Advanced settings >
   Extension Developer > "Install Extension..."**, and pick
   `browserstack-qa.mcpb`.
2. When prompted, enter your BrowserStack username and access key. Claude
   Desktop stores the access key in the OS's secure credential store
   (Credential Manager on Windows), not in a plaintext config file.
3. Restart Claude Desktop if the tools don't show up immediately in a new
   chat's connector list.

Source for this bundle lives in `browserstack-qa-mcpb/`. See
`browserstack-qa-mcpb/BUILD.md` for how to rebuild it (needed if `app.py`
changes in a way you want reflected in the extension -- it bundles a
snapshot copy of `app.py`, not a live import, since `.mcpb` bundles are
meant to be self-contained).

**Locally, via manual stdio config (alternative, if your Claude Desktop
build supports hand-editing an MCP config file):**
```bash
pip install -r requirements-mcp.txt
python browserstack_mcp_server.py --stdio
```
```json
{
  "mcpServers": {
    "browserstack-qa": {
      "command": "python",
      "args": ["/absolute/path/to/step_reproduction_app/browserstack_mcp_server.py", "--stdio"],
      "env": {
        "AUTOMATION_BS_USER": "your_browserstack_username",
        "AUTOMATION_BS_PASS": "your_browserstack_access_key"
      }
    }
  }
}
```
Credentials sit in plaintext in this file, so prefer the extension above
when it's available to you.

**Remote/hosted (Streamable HTTP), e.g. on Render:**
The `browserstack-mcp` service in `render.yaml` runs it as its own web service
alongside this app. Set `AUTOMATION_BS_USER`, `AUTOMATION_BS_PASS`, and
`MCP_API_KEY` (a secret you choose) in Render's dashboard. Then register it
as a custom/remote connector wherever your MCP client supports one, pointing
at `https://<your-render-service>.onrender.com/mcp` with header
`Authorization: Bearer <MCP_API_KEY>`.

**MCP_API_KEY is effectively required once this is public.** Without it,
anyone who finds the URL can list, tag, and delete your BrowserStack builds
and sessions. If it's unset, the server logs a loud warning and runs with no
auth -- fine for a quick local test over `localhost`, not for a public URL.

## Version

- **Current Version:** 4.0
- **Last Updated:** October 2026

## File Structure

```
step_reproduction_app/
├── app.py                       # Main Flask application (3056 lines)
├── browserstack_mcp_server.py   # MCP server exposing BrowserStack tools (stdio --stdio flag / remote HTTP)
├── browserstack-qa.mcpb         # Packaged Desktop Extension (install via Claude Desktop Settings > Extensions)
├── browserstack-qa-mcpb/        # Source for the .mcpb above -- see BUILD.md to rebuild it
│   ├── manifest.json
│   ├── pyproject.toml
│   ├── src/server.py
│   ├── src/app.py                 # snapshot copy, see BUILD.md
│   └── BUILD.md
├── requirements.txt             # Deps for app.py
├── requirements-mcp.txt         # Deps for browserstack_mcp_server.py
├── render.yaml                  # Render deploy config (both services)
├── README.md                    # This documentation file
└── __pycache__/                 # Python cache directory
```

## Key Dependencies

- **Flask** - Web framework for the application
- **Requests** - HTTP library for BrowserStack API calls
- **mcp** (pinned `<2.0`) - MCP server SDK (FastMCP), used by `browserstack_mcp_server.py`
- **Starlette / uvicorn** - ASGI app + server for the remote MCP transport

## License

Internal tool for QA automation teams.

## Support

For issues or questions, contact the QA Automation team.

