# BS TestReplay - Step Reproduction App

Flask web application for BrowserStack automation test management with two main features:
1. **Generate Test Reproduction Links** - Convert BS session URLs to shareable test replay links
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

## Version

- **Current Version:** 3.3
- **Last Updated:** April 2026

## File Structure

```
step_reproduction_app/
├── app.py                  # Main Flask application (3056 lines)
├── README.md               # This documentation file
└── __pycache__/            # Python cache directory
```

## Key Dependencies

- **Flask** - Web framework for the application
- **Requests** - HTTP library for BrowserStack API calls

## License

Internal tool for QA automation teams.

## Support

For issues or questions, contact the QA Automation team.

