import asyncio
import io
import logging
import os
import re
import shutil
import signal
import sys
import tarfile
import tempfile
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import aiodocker
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from metrics import Metrics

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Setup logging
discord.utils.setup_logging()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
metrics = Metrics("./metrics.db")

# Simple per-process memory: message_id -> dict(info)
PENDING_SNIPPETS: dict[int, dict] = {}

# Working directory where we will save the snippets
RUNS_DIR = Path("./runs")
RUNS_DIR.mkdir(parents=True, exist_ok=True)

# Container Pool Labels
POOL_LABELS = {"app": "doctor-kivy", "role": "kivy-pool"}


class KivyRenderMode(Enum):
    """Rendering modes for Kivy applications"""

    SCREENSHOT = "screenshot"
    VIDEO = "video"


class KivyTemplates:
    """Template manager that combines base template with mode-specific templates"""

    def __init__(self):
        """
        Initialize template manager.
        """
        self.templates_dir = Path("templates")
        self._template_cache = {}

    def _load_template(self, filename: str) -> str:
        """Load a template file and cache it"""
        if filename in self._template_cache:
            return self._template_cache[filename]

        template_path = self.templates_dir / filename

        if not template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path}")

        try:
            with open(template_path, "r", encoding="utf-8") as f:
                content = f.read()
            self._template_cache[filename] = content
            return content
        except Exception as e:
            raise RuntimeError(f"Failed to load template {filename}: {e}")

    def create_script(
        self, user_code: str, mode: KivyRenderMode = KivyRenderMode.SCREENSHOT
    ) -> str:
        """
        Create a complete Kivy script by combining base template with mode-specific code.

        Args:
            user_code: The user's Kivy application code
            mode: Rendering mode (screenshot, or video)

        Returns:
            Complete Python script ready for execution
        """
        # Load the base template
        base_template = self._load_template("base.py")

        # Load the mode-specific template
        if mode == KivyRenderMode.SCREENSHOT:
            mode_template = self._load_template("screenshot.py")
        elif mode == KivyRenderMode.VIDEO:
            mode_template = self._load_template("video.py")
        else:
            raise ValueError(f"Unknown render mode: {mode}")

        # Remove the import line from mode template since we're including base inline
        mode_template = re.sub(
            r"^from templates\.base import _install_bg\s*$",
            "",
            mode_template,
            flags=re.MULTILINE,
        )

        script = "\n\n".join(
            [
                base_template,
                mode_template,
                'print("🚀 Starting user code...")',
                user_code,
            ]
        )

        return script

    def clear_cache(self):
        """Clear template cache (useful for development)"""
        self._template_cache.clear()


templates = KivyTemplates()


# Pre-warmed Container Pool Implementation
class SimpleContainerPool:
    """Simple container pool for pre-warmed Kivy rendering containers"""

    def __init__(self, image: str, pool_size: int = 2):
        self.image = image
        self.pool_size = pool_size
        self.available_containers = asyncio.Queue()
        self.docker_client = None
        self.initialized = False

    async def _kill_existing_pool(self):
        # remove any leftover containers from previous runs
        existing = await self.docker_client.containers.list(
            all=True, filters={"label": ["app=doctor-kivy", "role=kivy-pool"]}
        )
        logging.info(f"🧹 Killing {len(existing)} existing containers in pool...")
        for c in existing:
            try:
                await c.kill()
            except Exception:
                pass
            try:
                await c.delete(force=True)
            except Exception:
                pass

    async def initialize(self):
        """Initialize the container pool"""
        try:
            self.docker_client = aiodocker.Docker()

            # Test if Docker is available
            await self.docker_client.version()

            # Kill any existing containers in the pool
            await self._kill_existing_pool()

            logging.info(f"🔥 Initializing {self.pool_size} pre-warmed containers...")

            for i in range(self.pool_size):
                try:
                    container = await self._create_prewarmed_container(f"kivy-pool-{i}")
                    await self.available_containers.put(container)
                    logging.info(
                        f"✅ Created pre-warmed container {i + 1}/{self.pool_size}"
                    )
                    await asyncio.sleep(1)  # Small delay between containers
                except Exception as e:
                    logging.error(f"❌ Failed to create container {i + 1}: {e}")

            self.initialized = True
            queue_size = self.available_containers.qsize()
            logging.info(f"🚀 Container pool initialized with {queue_size} containers!")

        except Exception as e:
            logging.error(f"❌ Failed to initialize container pool: {e}")
            self.initialized = False
            if self.docker_client:
                await self.docker_client.close()

    async def _create_prewarmed_container(self, name: str):
        """Create a pre-warmed container with Xvfb running"""
        container_config = {
            "Image": self.image,
            "Cmd": [
                "/bin/sh",
                "-c",
                "Xvfb :99 -screen 0 800x600x24 -nolisten tcp & "
                "sleep 3 && "  # Wait for Xvfb
                "export DISPLAY=:99 && "
                "echo 'Container ready for rendering!' && "
                "while true; do sleep 30; done",
            ],
            "Env": ["DISPLAY=:99", "PYTHONUNBUFFERED=1"],
            "WorkingDir": "/app",
            "Labels": POOL_LABELS,
            "HostConfig": {
                "Memory": 512 * 1024 * 1024,
                "CpuQuota": 50000,
                "NetworkMode": "none",
                "AutoRemove": True,
                "Tmpfs": {
                    "/tmp": "size=80m,noexec,nosuid,nodev",  # 80MB /tmp
                },
                "Ulimits": [
                    {
                        "Name": "fsize",
                        "Soft": 104857600,
                        "Hard": 104857600,
                    },  # 100MB file size limit
                    {"Name": "nofile", "Soft": 100, "Hard": 100},  # Limit open files
                ],
                "ReadonlyRootfs": False,
                "SecurityOpt": [
                    "no-new-privileges:true"
                ],  # Prevent privilege escalation
            },
        }

        container = await self.docker_client.containers.create(
            container_config, name=name
        )
        await container.start()

        # Wait for Xvfb to be ready
        await asyncio.sleep(5)

        return container

    async def get_container(self):
        """Get a container from the pool"""
        if not self.initialized or self.available_containers.empty():
            return None
        try:
            return await asyncio.wait_for(self.available_containers.get(), timeout=1.0)
        except asyncio.TimeoutError:
            return None

    async def return_container(self, container):
        """Return a container to the pool"""
        if self.initialized and container:
            await self.available_containers.put(container)

    async def cleanup(self):
        """Clean up all containers"""
        if self.docker_client:
            while not self.available_containers.empty():
                try:
                    container = await self.available_containers.get()
                    await container.kill()
                except Exception as e:
                    logging.error(f"Error cleaning up container: {e}")
            await self._kill_existing_pool()
            await self.docker_client.close()


# Global container pool
container_pool: Optional[SimpleContainerPool] = None


def _install_sigterm_cleanup():
    def _handler(signum, frame):
        try:
            metrics.close()
            if container_pool:
                asyncio.run(container_pool.cleanup())
        finally:
            os._exit(0)

    signal.signal(signal.SIGTERM, _handler)


class KivyRenderError(Exception):
    """Custom exception for Kivy rendering errors"""

    def __init__(self, message: str, logs: list = None):
        self.message = message
        self.logs = logs or []
        super().__init__(self.message)


def extract_codeblocks_py(text: str) -> list[str]:
    """
    Extracts all ```py / ```python code blocks from the text.
    Supports triple backticks with or without language, but filters only py/python.
    """
    if not text:
        return []

    # Gets blocks with explicitly marked language
    pattern_lang = re.compile(
        r"```(?:py|python)\n(.*?)```",
        flags=re.IGNORECASE | re.DOTALL,
    )
    matches_lang = pattern_lang.findall(text)

    # Here we stay only with py/python (as you requested)
    codeblocks = [m.strip() for m in matches_lang if m.strip()]
    return codeblocks


def looks_like_kivy(code: str) -> bool:
    """
    Checks if code contains actual Kivy imports.
    And if it runs a Kivy app.
    """
    runs = [".run()", "runTouchApp(", "async_runTouchApp", "trio.run"]

    if not any(run in code for run in runs):
        return False

    lowered = code.lower()
    # Check for standard Kivy imports
    if "from kivy" in lowered:
        return True
    if "import kivy" in lowered:
        return True

    # Check for Kivy reloader imports
    if "from kivy_reloader" in lowered:
        return True
    if "import kivy_reloader" in lowered:
        return True

    # Check for KivyMD imports
    if "from kivymd" in lowered:
        return True
    if "import kivymd" in lowered:
        return True

    return False


def validate_code(code: str) -> bool:
    """Basic validation to prevent malicious code execution"""
    dangerous_patterns = [
        "import os",
        "import subprocess",
        "import sys",
        "__import__",
        "eval(",
        "exec(",
        "open(",
        "file(",
        "input(",
        "raw_input(",
    ]

    code_lower = code.lower()
    for pattern in dangerous_patterns:
        if pattern in code_lower:
            return False
    return True


def ensure_clean_run_dir(message_id: int) -> Path:
    run_dir = RUNS_DIR / str(message_id)
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


async def cleanup_orphan_processes(container):
    """Clean up orphan processes in the container after successful rendering"""
    try:
        logging.info("🧹 Cleaning up orphan processes in container...")

        cleanup_cmd = [
            "/bin/sh",
            "-c",
            "for p in /proc/[0-9]*; do "
            "pid=${p#/proc/}; "
            '[ "$pid" -eq 1 ] && continue; '
            '[ "$pid" -eq "$$" ] && continue; '
            '[ ! -d "$p" ] && continue; '
            "cmd=$(tr '\\0' ' ' < \"$p/cmdline\" 2>/dev/null | sed 's/[[:space:]]*$//'); "
            '[ -z "$cmd" ] && cmd=$(cat "$p/comm" 2>/dev/null); '
            '[ -z "$cmd" ] && continue; '
            'if ! echo "$cmd" | grep -q -E "^(/bin/sh /entrypoint\\.sh.*Xvfb.*:99|Xvfb :99 -screen 0 800x600x24 -nolisten tcp.*|tail -f /dev/null|/bin/bash|sleep 30)$"; then '
            'kill "$pid" 2>/dev/null; '
            "fi; "
            "done 2>/dev/null",
        ]

        exec_instance = await container.exec(cmd=cleanup_cmd, stdout=True, stderr=True)

        # Execute and collect any output
        async with exec_instance.start() as stream:
            while True:
                try:
                    chunk = await stream.read_out()
                    if chunk is None:
                        break
                    if chunk.data:
                        log_line = chunk.data.decode("utf-8").strip()
                        if log_line:
                            logging.info(f"🧹 Cleanup: {log_line}")
                except Exception as e:
                    logging.debug(f"Cleanup stream read error: {e}")
                    break

        logging.info("✅ Orphan process cleanup completed")

    except Exception as e:
        logging.warning(f"⚠️ Failed to clean up orphan processes: {e}")
        # Don't fail the whole operation if cleanup fails


async def validate_screenshot_size(
    file_size: int,
    max_size: int = 50 * 1024 * 1024,
) -> bool:
    """Validate screenshot file size (default: 50MB max)"""
    try:
        if file_size > max_size:
            logging.warning(
                f"Screenshot too large: {file_size} bytes (max: {max_size})"
            )
            return False
        return True
    except Exception as e:
        logging.error(f"Failed to validate screenshot size: {e}")
        return False


_WINDOW_SIZE_RE = re.compile(
    r"Window\s*\.\s*size\s*=\s*(\([^\)]*\)|\[[^\]]*\])",
    flags=re.IGNORECASE,
)
_CONFIG_WIDTH_RE = re.compile(
    r"Config\s*\.\s*set\s*\(\s*['\"]graphics['\"]\s*,\s*['\"]width['\"]\s*,\s*['\"]?(\d+)['\"]?\s*\)",
    flags=re.IGNORECASE,
)
_CONFIG_HEIGHT_RE = re.compile(
    r"Config\s*\.\s*set\s*\(\s*['\"]graphics['\"]\s*,\s*['\"]height['\"]\s*,\s*['\"]?(\d+)['\"]?\s*\)",
    flags=re.IGNORECASE,
)


def _extract_first_two_numbers(s: str) -> Optional[Tuple[int, int]]:
    nums = re.findall(r"\d+(?:\.\d+)?", s)
    if len(nums) >= 2:
        try:
            w = int(float(nums[0]))
            h = int(float(nums[1]))
            if w > 0 and h > 0:
                return w, h
        except Exception:
            return None
    return None


def parse_requested_size(code: str) -> Tuple[Optional[int], Optional[int], str]:
    """
    Returns (width, height, source) where source in {'window','config','none'}.
    Prefers Window.size if both are present.
    """
    m = _WINDOW_SIZE_RE.search(code)
    if m:
        inner = m.group(1)
        pair = _extract_first_two_numbers(inner)
        if pair:
            return pair[0], pair[1], "window"

    w = None
    h = None
    for mw in _CONFIG_WIDTH_RE.finditer(code):
        w = int(mw.group(1))
    for mh in _CONFIG_HEIGHT_RE.finditer(code):
        h = int(mh.group(1))

    if w or h:
        return w, h, "config"

    return None, None, "none"


async def render_kivy_with_pool(
    interaction: discord.Interaction, code: str
) -> Dict[str, Any]:
    """Optimized render function using pre-warmed container pool"""
    if not container_pool or not container_pool.initialized:
        # Fallback to original method if pool not ready
        logging.warning(
            "⚠️ Container pool not available, falling back to original method"
        )
        return await render_kivy_snippet(interaction, code)

    logging.info("🚀 Using pre-warmed container from pool")
    container = await container_pool.get_container()

    if not container:
        logging.warning(
            "⚠️ No containers available in pool, falling back to original method"
        )
        return await render_kivy_snippet(interaction, code)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Clean old screenshot from container before starting
            cleanup_exec = await container.exec(
                cmd=[
                    "/bin/sh",
                    "-lc",
                    "set -e; rm -rf /work; mkdir -p /work; sync; ls -ld /work",
                ],
                stdout=True,
                stderr=True,
            )
            async with cleanup_exec.start() as stream:
                # Wait for cleanup to complete
                while True:
                    chunk = await stream.read_out()
                    if chunk is None:
                        break

            logging.info(
                "🧹 Cleaned old screenshot (deleted /work directory) from container"
            )

            # Prepare script
            script_path = Path(tmpdir) / "main.py"
            kivy_script = prepare_kivy_script(code)
            script_path.write_text(kivy_script, encoding="utf-8")

            logging.info(f"📝 Prepared script in {tmpdir}")

            # Create tar archive for Docker container
            tar_buffer = io.BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
                tar.add(script_path, arcname="main.py")
            tar_buffer.seek(0)

            # Copy script to container
            await container.put_archive("/work", tar_buffer.read())
            logging.info("📦 Uploaded script to container")

            # Execute in container with timeout
            exec_config = [
                "/bin/sh",
                "-c",
                "cd /work && timeout 25s /root/.local/bin/uv run python main.py",
            ]

            exec_instance = await container.exec(
                cmd=exec_config,
                stdout=True,
                stderr=True,
                environment=["DISPLAY=:99", "PYTHONUNBUFFERED=1"],
            )
            logs = []

            # Collect logs with timeout - using start() to get the stream
            try:

                async def collect_logs():
                    async with exec_instance.start() as stream:
                        while True:
                            try:
                                chunk = await stream.read_out()
                                if chunk is None:
                                    break
                                log_line = chunk.data.decode("utf-8").strip()
                                if log_line:
                                    logs.append(log_line)
                                    logging.info(f"📄 Container: {log_line}")
                            except Exception as e:
                                logging.debug(f"Stream read error: {e}")
                                break

                await asyncio.wait_for(collect_logs(), timeout=30.0)

            except asyncio.TimeoutError:
                logging.warning("⏰ Pre-warmed container execution timed out")
                return {
                    "content": "⏰ Rendering timed out after 30 seconds.",
                    "attachments": [],
                }

            # Get screenshot from container
            try:
                screenshot_tar = await container.get_archive(
                    "/work/kivy_screenshot.png"
                )

                # aiodocker returns TarFile directly, not async iterator
                screenshot_member = screenshot_tar.getmember("kivy_screenshot.png")
                screenshot_file = screenshot_tar.extractfile(screenshot_member)

                if screenshot_file:
                    screenshot_data = screenshot_file.read()
                    file_size = len(screenshot_data)
                    if not await validate_screenshot_size(file_size):
                        return {
                            "content": "Screenshot file is too large and may be malicious. Rendering aborted.",
                            "attachments": [],
                        }

                    if len(screenshot_data) > 0:
                        discord_file = discord.File(
                            io.BytesIO(screenshot_data), filename="kivy_screenshot.png"
                        )

                        logging.info(
                            f"✅ Pre-warmed container render successful! Screenshot: {len(screenshot_data)} bytes"
                        )
                        metrics.observe_screenshot_bytes(len(screenshot_data))

                        await cleanup_orphan_processes(container)

                        return {
                            "content": "🎉 Here's your Kivy app screenshot!",
                            "attachments": [discord_file],
                        }

            except Exception as e:
                logging.warning(f"Screenshot extraction failed: {e}")

            # Return logs if screenshot failed
            logs_content = "\n".join(logs[-50:]) if logs else "No logs collected"
            return {
                "content": "❌ Failed to generate screenshot (pre-warmed):",
                "attachments": [
                    discord.File(
                        fp=io.BytesIO(logs_content.encode("utf-8")),
                        filename="prewarmed_logs.txt",
                    )
                ],
            }

    except Exception as e:
        logging.error(f"💥 Pre-warmed container failed: {e}")
        # Fallback to original method
        logging.info("🔄 Falling back to original rendering method")
        return await render_kivy_snippet(interaction, code)
    finally:
        await container_pool.return_container(container)


async def render_kivy_snippet(
    interaction: discord.Interaction,
    code: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Renders Kivy code in a Docker container and returns the result.
    Similar to Manim's render_animation_snippet but for Kivy apps.
    Optional width/height override the Xvfb screen size.
    """
    logging.info("🚀 Starting Kivy snippet rendering")
    dockerclient = aiodocker.Docker()

    # Prepare the Kivy script
    kivy_script = prepare_kivy_script(code)
    logging.info(f"📝 Prepared Kivy script ({len(kivy_script)} chars)")

    with tempfile.TemporaryDirectory() as tmpdirname:
        logging.info(f"📁 Created temporary directory: {tmpdirname}")

        # Write script to temporary directory
        script_path = Path(tmpdirname) / "main.py"
        script_path.write_text(kivy_script, encoding="utf-8")
        logging.info(f"💾 Wrote script to: {script_path}")

        try:
            # Compute desired screen size (defaults if not provided)
            W = str(width if width and width > 0 else 800)
            H = str(height if height and height > 0 else 600)
            logging.info(f"🖥️ Xvfb size -> {W}x{H}")

            # Set up Docker container configuration
            container_config = {
                "Image": "kivy-renderer:latest",
                "Cmd": [
                    "/bin/sh",
                    "-lc",
                    # start Xvfb, wait for readiness, run, then clean up
                    "set -e; "
                    "Xvfb :99 -screen 0 ${WIDTH:-800}x${HEIGHT:-600}x24 -nolisten tcp & xp=$!; "
                    "for i in $(seq 1 50); do DISPLAY=:99 xdpyinfo >/dev/null 2>&1 && break; sleep 0.1; done; "
                    "DISPLAY=:99 timeout 25s /app/.venv/bin/python /work/main.py; "
                    'status=$?; kill "$xp"; wait "$xp" 2>/dev/null || true; exit $status',
                ],
                "WorkingDir": "/app",  # keep the project dir (with .venv) as CWD
                "Env": [
                    "PYTHONUNBUFFERED=1",
                    "OUT=/work/kivy_screenshot.png",
                    f"WIDTH={W}",
                    f"HEIGHT={H}",
                ],
                "HostConfig": {
                    "Binds": [f"{tmpdirname}:/work:rw"],
                    "AutoRemove": True,
                    "Memory": 512 * 1024 * 1024,
                    "CpuQuota": 50000,
                    "NetworkMode": "none",
                    "Ulimits": [
                        {
                            "Name": "fsize",
                            "Soft": 104857600,
                            "Hard": 104857600,
                        },  # 100MB file size limit
                        {
                            "Name": "nofile",
                            "Soft": 100,
                            "Hard": 100,
                        },  # Limit open files
                    ],
                    "ReadonlyRootfs": False,
                    "SecurityOpt": [
                        "no-new-privileges:true"
                    ],  # Prevent privilege escalation
                },
            }

            logging.info(f"🐳 Docker config: {container_config}")
            logging.info("🏃 Starting Docker container...")

            # Run the container with timeout
            container = await dockerclient.containers.run(config=container_config)
            logging.info(f"✅ Container started: {container.id}")

            # Collect output with timeout
            kivy_logs = []
            logging.info("📊 Collecting container logs...")

            try:
                # Add timeout to prevent hanging
                async def collect_logs():
                    async for line in container.log(
                        follow=True, stderr=True, stdout=True
                    ):
                        log_line = line.rstrip()
                        kivy_logs.append(log_line)
                        logging.info(f"📄 Container log: {log_line}")

                # Wait for logs with 30-second timeout
                await asyncio.wait_for(collect_logs(), timeout=30.0)
                logging.info(f"📋 Collected {len(kivy_logs)} log lines")

            except asyncio.TimeoutError:
                logging.warning("⏰ Container execution timed out after 30 seconds")
                # Force kill the container
                try:
                    await container.kill()
                    logging.info("🛑 Container killed due to timeout")
                except Exception as kill_error:
                    logging.error(f"❌ Failed to kill container: {kill_error}")

                # Return timeout error with collected logs
                logs_content = (
                    "\n".join(kivy_logs[-20:])
                    if kivy_logs
                    else "No logs collected before timeout"
                )
                await dockerclient.close()
                return {
                    "content": "⏰ Rendering timed out after 30 seconds. The Kivy app might be hanging.",
                    "attachments": [
                        discord.File(
                            fp=io.BytesIO(logs_content.encode("utf-8")),
                            filename="timeout_logs.txt",
                        )
                    ],
                }

            await dockerclient.close()

            # Check if screenshot was generated
            screenshot_path = Path(tmpdirname) / "kivy_screenshot.png"
            logging.info(f"🔍 Checking for screenshot at: {screenshot_path}")

            # Also check what files are actually in the temp directory
            temp_files = list(Path(tmpdirname).iterdir())
            logging.info(
                f"📂 All files in temp dir: {[(f.name, f.stat().st_size if f.is_file() else 'dir') for f in temp_files]}"
            )

            if screenshot_path.exists():
                file_size = screenshot_path.stat().st_size
                if not await validate_screenshot_size(file_size):
                    return {
                        "content": "Screenshot file is too large and may be malicious. Rendering aborted.",
                        "attachments": [],
                    }

                metrics.observe_screenshot_bytes(file_size)
                logging.info(f"✅ Screenshot found! Size: {file_size} bytes")
                return {
                    "content": "🎉 Here's your Kivy app screenshot!",
                    "attachments": [
                        discord.File(screenshot_path, filename="kivy_app.png")
                    ],
                }
            else:
                logging.warning("❌ No screenshot file found")

                # Return logs if no screenshot was generated
                logs_content = "\n".join(kivy_logs[-50:])  # Last 50 lines
                logging.info(f"📝 Returning logs ({len(logs_content)} chars)")
                return {
                    "content": "❌ No screenshot generated. Here are the logs:",
                    "attachments": [
                        discord.File(
                            fp=io.BytesIO(logs_content.encode("utf-8")),
                            filename="kivy_logs.txt",
                        )
                    ],
                }

        except Exception as e:
            logging.error(f"💥 Docker rendering error: {e}", exc_info=True)
            return {"content": f"❌ Rendering failed: {str(e)}", "attachments": []}


def prepare_kivy_script(
    user_code: str,
    mode: KivyRenderMode = KivyRenderMode.SCREENSHOT,
) -> str:
    """
    Prepares the Kivy script for execution in Docker.
    Uses Window.on_flip to detect first frame, then schedules screenshot after first frame
    Draws an opaque background using the user's Window.clearcolor
    """
    return templates.create_script(user_code, mode)


async def placeholder_render_call(
    interaction: discord.Interaction, code: str, run_dir: Path
):
    """
    Main render function that orchestrates the Kivy rendering process.
    Uses pre-warmed containers for better performance.
    Forces cold run with custom Xvfb size if user code specifies Window.size or Config graphics size.
    """
    logging.info(f"🎬 Starting render call for user {interaction.user.name}")
    logging.info(f"📝 Code length: {len(code)} characters")
    logging.info(f"📁 Run directory: {run_dir}")

    start = time.monotonic()
    metrics.inc_attempted()
    try:
        # Detect requested size from code
        req_w, req_h, src = parse_requested_size(code)
        force_cold = src != "none"
        if force_cold:
            logging.info(
                f"📐 Detected explicit size from {src}: width={req_w}, height={req_h}"
            )
            result = await render_kivy_snippet(
                interaction, code, width=req_w, height=req_h
            )
        else:
            # Try pre-warmed container first, fallback to original method
            if container_pool and container_pool.initialized:
                result = await render_kivy_with_pool(interaction, code)
            else:
                result = await render_kivy_snippet(interaction, code)

        success = bool(
            isinstance(result, dict)
            and result.get("attachments")
            and any(
                getattr(f, "filename", "").endswith(".png")
                for f in result["attachments"]
            )
        )
        if success:
            metrics.inc_success()
        else:
            metrics.inc_failure()

        metrics.observe_duration(time.monotonic() - start)

        logging.info(
            f"✅ Render {'successful' if success else 'failed'}, result: {result.get('content', 'No content')[:50]}..."
        )
        return result

    except Exception as e:
        metrics.inc_failure()
        metrics.observe_duration(time.monotonic() - start)
        logging.error(f"💥 Error in placeholder_render_call: {e}", exc_info=True)
        return {"content": f"❌ Something went wrong: {str(e)}", "attachments": []}


class KivyPromptView(discord.ui.View):
    def __init__(self, source_message_id: int, author_id: int, rendered: bool = False):
        super().__init__(timeout=180)
        self.source_message_id = source_message_id
        self.author_id = author_id
        self.message = None  # Store reference to the message
        self.rendered = rendered

        # adjust the label if this is a post-render view
        if self.rendered:
            for child in self.children:
                if (
                    isinstance(child, discord.ui.Button)
                    and child.label == "Yes, render"
                ):
                    child.label = "Render again"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data and interaction.data.get("custom_id") in {"go_away"}:
            return True
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the original author can use these buttons.", ephemeral=True
            )
            return False
        return True

    def _can_delete(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.author_id:
            return True
        if not interaction.guild:
            return False
        member = interaction.guild.get_member(interaction.user.id)
        if not member:
            return False
        perms = interaction.channel.permissions_for(member)
        return perms.manage_messages or perms.administrator

    async def on_timeout(self):
        """Called when the view times out"""
        if self.message:
            try:
                # Clear all buttons when timeout occurs
                await self.message.edit(view=self.clear_items())
            except discord.HTTPException:
                pass  # Message might be deleted already

    @discord.ui.button(label="Yes, render", style=discord.ButtonStyle.success)
    async def yes_render(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        logging.info(
            f"🎯 Render button clicked by {interaction.user.name} for message {self.source_message_id}"
        )

        # Disable buttons during processing
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        try:
            # Fetch the latest version of the message (in case it was edited)
            msg = await interaction.channel.fetch_message(self.source_message_id)
            blocks = extract_codeblocks_py(msg.content)

            code = None
            for b in blocks:
                if looks_like_kivy(b):
                    code = b
                    break

            if not code:
                logging.warning("❌ No valid Kivy snippet found in the current message")
                await interaction.followup.send(
                    "❌ Couldn't find a valid Kivy snippet in the message. Did you edit it incorrectly?",
                    ephemeral=True,
                )
                # Re-enable buttons
                for child in self.children:
                    child.disabled = False
                await interaction.edit_original_response(view=self)
                return

            logging.info(
                f"📝 Using latest code snippet from message {self.source_message_id}, length={len(code)}"
            )

            # Validate code for security
            # if not validate_code(code):
            #     logging.warning("🚨 Code validation failed - contains dangerous operations")
            #     await interaction.followup.send(
            #         "❌ This code contains potentially dangerous operations and cannot be rendered.",
            #         ephemeral=True
            #     )
            #     # Re-enable buttons
            #     for child in self.children:
            #         child.disabled = False
            #     await interaction.edit_original_response(view=self)
            #     return

            run_dir = ensure_clean_run_dir(self.source_message_id)
            result = await placeholder_render_call(interaction, code, run_dir)

            # Send new result with fresh buttons
            view = KivyPromptView(
                source_message_id=self.source_message_id,
                author_id=self.author_id,
                rendered=True,
            )
            await interaction.edit_original_response(**result, view=view)

        except Exception as e:
            # Failure: keep original message visible
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
            for child in self.children:
                child.disabled = False
            try:
                await interaction.edit_original_response(view=self)
            except discord.NotFound:
                # If original message was already deleted
                pass

    @discord.ui.button(label="Change settings", style=discord.ButtonStyle.secondary)
    async def change_settings(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_message(
            "⚙️ Settings are coming soon. This will allow you to configure Kivy rendering options.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Go away", style=discord.ButtonStyle.danger, custom_id="go_away"
    )
    async def go_away(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not self._can_delete(interaction):
            await interaction.response.send_message(
                "Only the original author or moderators can remove this.",
                ephemeral=True,
            )
            return
        try:
            await interaction.response.defer()
            await interaction.delete_original_response()
        except discord.Forbidden:
            await interaction.followup.send(
                "I couldn't delete my message (missing permission).", ephemeral=True
            )
        except discord.HTTPException:
            pass


@bot.event
async def on_ready():
    logging.info(f"✅ Bot {bot.user} is online!")
    logging.info(f"🏠 Connected to {len(bot.guilds)} servers")
    logging.info(f"🔧 Python version: {sys.version}")
    logging.info(f"📦 Discord.py version: {discord.__version__}")
    print(f"✅ Bot {bot.user} is online!")

    # Initialize container pool
    global container_pool
    try:
        logging.info("🔥 Initializing pre-warmed container pool...")
        container_pool = SimpleContainerPool("kivy-renderer:prewarmed", 2)
        await container_pool.initialize()

        if container_pool.initialized:
            queue_size = container_pool.available_containers.qsize()
            logging.info(
                f"🚀 Pre-warmed container pool ready with {queue_size} containers!"
            )
            print(f"🚀 Pre-warmed container pool ready with {queue_size} containers!")
        else:
            logging.warning(
                "⚠️ Container pool failed to initialize. Using fallback method."
            )
            print("⚠️ Container pool failed to initialize. Using fallback method.")
            container_pool = None

    except Exception as e:
        logging.warning(
            f"⚠️ Container pool initialization failed: {e}. Using fallback method."
        )
        print(f"⚠️ Container pool initialization failed: {e}. Using fallback method.")
        container_pool = None

    # Start cleanup task
    cleanup_old_snippets.start()


@tasks.loop(minutes=30)  # Clean up every 30 minutes
async def cleanup_old_snippets():
    """Clean up old snippets from memory to prevent memory leaks"""
    if not PENDING_SNIPPETS:
        return

    # Remove snippets older than 1 hour (Discord message IDs are snowflakes with timestamps)
    current_time = discord.utils.utcnow().timestamp()
    old_ids = []

    for message_id in PENDING_SNIPPETS:
        # Extract timestamp from Discord snowflake
        message_timestamp = ((message_id >> 22) + 1420070400000) / 1000
        if current_time - message_timestamp > 3600:  # 1 hour
            old_ids.append(message_id)

    for old_id in old_ids:
        PENDING_SNIPPETS.pop(old_id, None)

    if old_ids:
        logging.info(f"Cleaned up {len(old_ids)} old snippets from memory")


@bot.event
async def on_error(event, *args, **kwargs):
    """Handle uncaught exceptions"""
    logging.error(f"Error in event {event}: {args}, {kwargs}", exc_info=True)


@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    try:
        # Looks for ```py / ```python blocks
        blocks = extract_codeblocks_py(message.content)

        if blocks:
            logging.info(
                f"🔍 Found {len(blocks)} code blocks in message from {message.author.name}"
            )

            # Selects the first block that looks like Kivy; if none, takes the first one
            selected = None
            for i, b in enumerate(blocks):
                is_kivy = looks_like_kivy(b)
                logging.info(
                    f"📋 Block {i + 1}: {len(b)} chars, looks_like_kivy={is_kivy}"
                )
                if is_kivy:
                    selected = b
                    break
            if selected is None:
                logging.info("📌 No Kivy blocks found")
                return
            else:
                logging.info("✅ Selected Kivy block for rendering")

            # Stores context in memory for the "Yes, render" button
            PENDING_SNIPPETS[message.id] = {
                "author_id": message.author.id,
                "channel_id": message.channel.id,
                "code": selected,
            }

            logging.info(f"💾 Stored snippet {message.id} in memory")

            # Builds the message + view
            prefix = "This message looks like it contains a Kivy snippet, do you want me to render it?"

            view = KivyPromptView(
                source_message_id=message.id, author_id=message.author.id
            )
            reply_message = await message.reply(
                prefix,
                view=view,
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            view.message = reply_message  # Store reference for timeout handling

        # Keeps the commands
        await bot.process_commands(message)
    except Exception as e:
        logging.error(f"Error in on_message: {e}")
        # Don't let message processing errors crash the bot


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if after.author == bot.user:
        return

    blocks = extract_codeblocks_py(after.content)
    if blocks:
        # same logic as in on_message to pick a Kivy block
        selected = None
        for b in blocks:
            if looks_like_kivy(b):
                selected = b
                break
        if selected:
            logging.info(f"✏️ Updated snippet for message {after.id} after edit")
            PENDING_SNIPPETS[after.id] = {
                "author_id": after.author.id,
                "channel_id": after.channel.id,
                "code": selected,
            }


@bot.command()
async def ping(ctx: commands.Context):
    await ctx.send("🏓 Pong!")


@bot.command(name="stats")
async def stats_cmd(ctx: commands.Context):
    s = metrics.snapshot()
    c = s["counters"]
    d = s["render_duration_seconds"]
    b = s["screenshot_bytes"]

    def f6(x):
        return f"{x:.6f}" if isinstance(x, (int, float)) else "null"

    avg_dur = d["sum"] / d["count"] if d["count"] else 0.0
    avg_bytes = b["sum"] / b["count"] if b["count"] else 0.0

    text = (
        "doctor-kivy metrics\n"
        f"renders_attempted_total: {c.get('renders_attempted_total', 0)}\n"
        f"renders_success_total:  {c.get('renders_success_total', 0)}\n"
        f"renders_failure_total:  {c.get('renders_failure_total', 0)}\n"
        f"render_duration_seconds.count: {d.get('count', 0)}\n"
        f"render_duration_seconds.sum:   {f6(d.get('sum'))}\n"
        f"render_duration_seconds.min:   {f6(d.get('min'))}\n"
        f"render_duration_seconds.max:   {f6(d.get('max'))}\n"
        f"render_duration_seconds.avg:   {f6(avg_dur)}\n"
        f"screenshot_bytes.count: {int(b.get('count', 0))}\n"
        f"screenshot_bytes.sum:   {int(b.get('sum', 0))}\n"
        f"screenshot_bytes.min:   {('null' if b.get('min') is None else int(b['min']))}\n"
        f"screenshot_bytes.max:   {('null' if b.get('max') is None else int(b['max']))}\n"
        f"screenshot_bytes.avg:   {int(avg_bytes) if b.get('count', 0) else 0}\n"
        f"last_update_ts: {s.get('last_update_ts')}"
    )

    await ctx.send(f"```\n{text}\n```")


if __name__ == "__main__":
    try:
        _install_sigterm_cleanup()
        bot.run(TOKEN)
    except KeyboardInterrupt:
        logging.info("🛑 Bot shutdown requested")
        print("🛑 Bot shutdown requested")
        metrics.close()
        # Cleanup container pool if it exists
        if container_pool:
            logging.info("🧹 Cleaning up container pool...")
            asyncio.run(container_pool.cleanup())

    except Exception as e:
        logging.error(f"Failed to start bot: {e}")
        print(f"❌ Failed to start bot: {e}")
        metrics.close()
        # Cleanup on error too
        if container_pool:
            try:
                asyncio.run(container_pool.cleanup())
            except:
                pass
