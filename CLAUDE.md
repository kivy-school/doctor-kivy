# Doctor Kivy - Claude Context File

## Project Overview

**Doctor Kivy** is a Discord bot that renders Kivy (Python GUI framework) applications in isolated Docker containers and captures their output as screenshots or videos. Users post Python code blocks containing Kivy apps in Discord, and the bot renders them automatically.

**Key Features:**
- Automatic detection of Kivy code in Discord messages
- Interactive UI with buttons for screenshot/video rendering
- Pre-warmed Docker container pool for sub-second rendering startup
- Security validation and resource isolation via Docker
- Metrics tracking for performance monitoring
- Widget interaction simulation for video recordings

## Architecture Overview

```
Discord User → Discord Message → Bot Detection → Validation →
Container Pool → Code Execution (Xvfb) → Screenshot/Video →
Discord Response
```

**Key Technologies:**
- Python 3.11+ with discord.py 2.5.2+
- uv (Python dependency manager and runner)
- Docker (aiodocker for async operations)
- Kivy + KivyMD + asynckivy
- Xvfb (headless X server for GUI rendering)
- ffmpeg (video encoding)
- SQLite (metrics storage)

## File Structure

```
/root/doctor-kivy/
├── bot.py                    # Main bot (1,296 lines) - core orchestration
├── metrics.py                # SQLite metrics tracking (162 lines)
├── templates/                # Kivy rendering templates
│   ├── base.py              # Common setup (background, colors)
│   ├── screenshot.py        # Screenshot capture logic
│   └── video.py             # Widget interaction & video recording (~9.4KB)
├── docker/
│   ├── Dockerfile.prewarmed # Pre-warmed image for container pooling
│   └── entrypoint.sh        # Container startup (starts Xvfb)
├── Dockerfile               # Main rendering environment
├── setup_docker.sh          # Setup script for building images
├── start_bot.py             # Helper to start bot in screen session
├── pyproject.toml           # Dependencies
├── uv.lock                  # Locked dependencies
├── .env                     # Discord token (secret)
└── runs/                    # Temporary execution directories
    └── {message_id}/        # One per Discord message
```

## Key Components

### 1. Main Bot (`bot.py`)

**Classes:**
- `KivyTemplates` - Manages rendering templates from `/templates/`
- `SimpleContainerPool` - Pre-warmed Docker containers (default: 2)
- `KivyPromptView` - Discord UI with interactive buttons
- `KivyRenderMode` - Enum: SCREENSHOT | VIDEO

**Critical Functions:**
- `extract_codeblocks_py()` - Parse Python code blocks from Discord
- `looks_like_kivy()` - Detect Kivy imports and `.run()` calls
- `validate_code()` - Security check (blocks `os`, `subprocess`, `eval`, `exec`, `open`, etc.)
- `parse_requested_size()` - Extract Window.size or Config.set from code
- `render_kivy_with_pool()` - Fast rendering using pre-warmed containers
- `render_kivy_snippet()` - Fallback creating containers on-demand
- `placeholder_render_call()` - Main rendering orchestrator

**Event Handlers:**
- `on_ready()` - Initializes container pool on bot startup
- `on_message()` - Detects Kivy code blocks
- `on_message_edit()` - Updates pending snippets when messages edited
- `on_error()` - Global error handler

**Commands:**
- `!ping` - Simple ping test
- `!stats` - Display rendering metrics

**Background Tasks:**
- `cleanup_old_snippets()` - Runs every 30 minutes, removes snippets >1 hour old

### 2. Metrics System (`metrics.py`)

SQLite database at `./metrics.db` with WAL mode for thread safety.

**Tables:**
- `counters` - Simple counters (renders_attempted, renders_successful, renders_failed)
- `aggs` - Aggregates with count/sum/min/max (render_duration_seconds, screenshot_bytes_size)
- `meta` - Key-value metadata

### 3. Rendering Templates

**base.py** - Common functionality:
- Sets up opaque background
- Respects user's Window.clearcolor or MDApp theme color
- Binds resize handler for background updates

**screenshot.py** - Screenshot rendering:
- Uses asynckivy for async operations
- Waits for first frame via `Window.on_flip`
- Captures using `Window.screenshot()`
- Saves to `/work/kivy_screenshot.png`
- Stops app after capture

**video.py** - Video recording:
- Discovers all widgets recursively
- Calculates optimal speed-up to fit within 15 seconds
- Triggers widget interactions:
  - Buttons: `trigger_action()`
  - Switches: toggle active state
  - TextInput: insert "Tested by Dr. Kivy"
  - ScrollView: animate scrolling
  - Video widgets: play for up to 3 seconds
- Exports frames to PNG at 60fps
- Compiles to MP4 using ffmpeg
- Saves to `/work/kivy_video.mp4`

### 4. Docker Configuration

**Container Resources:**
- Memory: 512MB
- CPU: 50% quota (0.5 cores)
- /tmp: 80MB
- File size limit: 100MB
- Execution timeout: 50 seconds

**Pre-warmed Container Labels:**
```python
{"app": "doctor-kivy", "role": "kivy-pool"}
```

**entrypoint.sh workflow:**
1. Start Xvfb on display :99
2. Wait for Xvfb readiness with xdpyinfo checks
3. Keep container alive with `tail -f /dev/null`

## User Workflow

1. User posts Kivy code in Discord (Python code block)
2. Bot detects code via `on_message` event
3. Bot sends reply with 4 buttons:
   - 📸 Screenshot
   - 🎬 Video
   - ⚙️ Change settings (placeholder)
   - ❌ Go away
4. User clicks button:
   - Bot validates code for security
   - Gets container from pool (or creates one)
   - Combines user code with appropriate template
   - Executes in container with timeout
   - Captures output (PNG or MP4)
   - Validates file size (max 50MB)
   - Sends to Discord
   - Returns container to pool
5. Buttons timeout after 3 minutes

## Important Constants & Configuration

**Environment Variables:**
- `DISCORD_TOKEN` - Bot authentication token (from `.env`)

**Directories:**
- `RUNS_DIR = ./runs/` - Stores snippet execution directories
- `TEMPLATES_DIR = ./templates/` - Kivy rendering templates

**In-Memory State:**
- `PENDING_SNIPPETS` - Dict storing detected Kivy code blocks
- `container_pool` - SimpleContainerPool instance

**Security Blacklist:**
```python
BAD_PATTERNS = ["os.", "subprocess", "eval(", "exec(",
                "open(", "__import__", "compile(",
                "socket", "sys.", "ctypes"]
```

**Container Pool:**
- Default size: 2 pre-warmed containers
- Startup time: <1 second (vs ~30 seconds cold start)

## Development Guidelines

### Code Patterns
- Full async/await for Discord and Docker operations
- Container pooling for performance
- Template composition for different render modes
- Security by isolation (Docker containers)
- Graceful degradation (pool → on-demand fallback)

### Adding New Features
1. **New render modes**: Add template to `/templates/`, add to `KivyRenderMode` enum
2. **New metrics**: Use `metrics.py` API (`inc_counter`, `record_agg`)
3. **New commands**: Add to bot.py using `@bot.command()` decorator
4. **New validations**: Add to `validate_code()` function

### Testing Locally
```bash
# Build Docker images
bash setup_docker.sh

# Set Discord token
echo "DISCORD_TOKEN=your_token" > .env

# Run bot (uses uv for dependency management)
uv run bot.py

# Or use screen session (recommended for production)
python3 start_bot.py
```

### Common Issues

**Container cleanup:**
- Orphan processes cleaned up after each render
- Old snippets cleaned every 30 minutes
- Containers removed on pool shutdown

**Memory management:**
- 512MB per container
- Max 50MB for output files
- Snippets >1 hour old purged

**Timeouts:**
- Container execution: 50 seconds
- Button interaction: 3 minutes
- Log collection: 3 minutes

## Git Status (at time of context creation)

Modified files:
- `setup_docker.sh`

Untracked files:
- `image.png`
- `metrics.db`, `metrics.db-shm`, `metrics.db-wal`
- `video.mp4`

Recent commits focus on:
- Container execution timeout fixes
- Video speed calculation adjustments
- Recording duration estimation
- ffmpeg command optimizations

## Entry Point

```bash
# Direct execution (requires uv)
uv run bot.py

# Production deployment (uses screen session)
python3 start_bot.py
```

**Initialization sequence:**
1. Load `.env` for DISCORD_TOKEN
2. Create Discord bot with `!` prefix
3. Initialize metrics DB
4. On `on_ready`: Initialize container pool (2 containers)
5. Start cleanup task (30min interval)
6. Listen for messages

**Note:** This project uses `uv` for Python dependency management. All bot execution commands should use `uv run` instead of plain `python`.

## Key Design Decisions

**Why container pooling?**
- Cold container start: ~30 seconds
- Pre-warmed container: <1 second
- Dramatically improves user experience

**Why Xvfb?**
- Headless X server for GUI rendering
- No physical display needed
- Standard for CI/CD GUI testing

**Why templates?**
- Separation of user code from rendering logic
- Easy to add new render modes
- Security boundary (user code doesn't control output)

**Why Docker?**
- Complete isolation from host system
- Resource limits (memory, CPU, disk)
- Easy cleanup and reproducibility

## Future Improvements (potential)

- Settings UI (currently placeholder)
- Custom window sizes beyond parsing
- Multiple render passes for animations
- Support for more widget types in video mode
- Caching frequently rendered snippets
- Rate limiting per user
- Better error messages to users
