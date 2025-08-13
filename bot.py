import os
import re
import shutil
import logging
import asyncio
import tempfile
import io
import sys
from pathlib import Path
from typing import Dict, Any
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import aiodocker

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Setup logging
logging.basicConfig(level=logging.INFO)
discord.utils.setup_logging()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Simple per-process memory: message_id -> dict(info)
PENDING_SNIPPETS: dict[int, dict] = {}

# Working directory where we will save the snippets
RUNS_DIR = Path("./runs")
RUNS_DIR.mkdir(parents=True, exist_ok=True)


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
    runs = ['.run()', 'runTouchApp(', 'async_runTouchApp', 'trio.run']

    if not any(run in code for run in runs):
        return False

    lowered = code.lower()
    # Check for standard Kivy imports
    if "from kivy.app" in lowered:
        return True
    if "import kivy" in lowered:
        return True
    
    # Check for Kivy reloader imports
    if "from kivy_reloader.app" in lowered:
        return True
    if "import kivy_reloader" in lowered:
        return True
        
    # Check for KivyMD imports
    if "from kivymd.app" in lowered:
        return True
    if "import kivymd" in lowered:
        return True
    
    return False


def validate_code(code: str) -> bool:
    """Basic validation to prevent malicious code execution"""
    dangerous_patterns = [
        'import os',
        'import subprocess', 
        'import sys',
        '__import__',
        'eval(',
        'exec(',
        'open(',
        'file(',
        'input(',
        'raw_input(',
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


async def render_kivy_snippet(interaction: discord.Interaction, code: str) -> Dict[str, Any]:
    """
    Renders Kivy code in a Docker container and returns the result.
    Similar to Manim's render_animation_snippet but for Kivy apps.
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
            # Set up Docker container configuration
            container_config = {
                "Image": "kivy-renderer:latest",
                "Cmd": [
                    "/bin/sh", "-lc",
                    # start Xvfb, wait for readiness, run, then clean up
                    'set -e; '
                    'Xvfb :99 -screen 0 ${WIDTH:-800}x${HEIGHT:-600}x24 -nolisten tcp & xp=$!; '
                    'for i in $(seq 1 50); do DISPLAY=:99 xdpyinfo >/dev/null 2>&1 && break; sleep 0.1; done; '
                    'DISPLAY=:99 timeout 25s /app/.venv/bin/python /work/main.py; '
                    'status=$?; kill "$xp"; wait "$xp" 2>/dev/null || true; exit $status'
                ],
                "WorkingDir": "/app",      # keep the project dir (with .venv) as CWD
                "Env": [
                    "PYTHONUNBUFFERED=1",
                    "OUT=/work/kivy_screenshot.png",
                    "WIDTH=800",
                    "HEIGHT=600"
                ],
                "HostConfig": {
                    "Binds": [f"{tmpdirname}:/work:rw"],
                    "AutoRemove": True,
                    "Memory": 512 * 1024 * 1024,
                    "CpuQuota": 50000,
                    "NetworkMode": "none"
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
                    async for line in container.log(follow=True, stderr=True, stdout=True):
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
                logs_content = "\n".join(kivy_logs[-20:]) if kivy_logs else "No logs collected before timeout"
                await dockerclient.close()
                return {
                    "content": "⏰ Rendering timed out after 30 seconds. The Kivy app might be hanging.",
                    "files": [
                        discord.File(
                            fp=io.BytesIO(logs_content.encode('utf-8')),
                            filename="timeout_logs.txt"
                        )
                    ]
                }
            
            await dockerclient.close()
            
            # Check if screenshot was generated
            screenshot_path = Path(tmpdirname) / "kivy_screenshot.png"
            logging.info(f"🔍 Checking for screenshot at: {screenshot_path}")
            
            # Also check what files are actually in the temp directory
            temp_files = list(Path(tmpdirname).iterdir())
            logging.info(f"📂 All files in temp dir: {[(f.name, f.stat().st_size if f.is_file() else 'dir') for f in temp_files]}")
            
            if screenshot_path.exists():
                file_size = screenshot_path.stat().st_size
                logging.info(f"✅ Screenshot found! Size: {file_size} bytes")
                return {
                    "content": "🎉 Here's your Kivy app screenshot!",
                    "files": [discord.File(screenshot_path, filename="kivy_app.png")]
                }
            else:
                logging.warning("❌ No screenshot file found")
                
                # Return logs if no screenshot was generated
                logs_content = "\n".join(kivy_logs[-50:])  # Last 50 lines
                logging.info(f"📝 Returning logs ({len(logs_content)} chars)")
                return {
                    "content": "❌ No screenshot generated. Here are the logs:",
                    "files": [
                        discord.File(
                            fp=io.BytesIO(logs_content.encode('utf-8')),
                            filename="kivy_logs.txt"
                        )
                    ]
                }
                
        except Exception as e:
            logging.error(f"💥 Docker rendering error: {e}", exc_info=True)
            return {
                "content": f"❌ Rendering failed: {str(e)}",
                "files": []
            }


def prepare_kivy_script(user_code: str) -> str:
    """
    Prepares the Kivy script for execution in Docker.
    Uses Window.on_flip to detect first frame, then schedules screenshot after 2 seconds.
    """
    template = '''
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.app import App
from kivy.app import stopTouchApp

def take_screenshot_and_exit(_dt):
    try:
        # Use absolute path to ensure file is saved in the right location
        screenshot_path = '/work/kivy_screenshot.png'
        print("Attempting to save screenshot to: ", screenshot_path)

        # Prefer exporting the root to keep exact filename:
        from kivy.base import EventLoop
        root = EventLoop.window.children[0] if EventLoop.window.children else None
        if root and hasattr(root, 'export_to_png'):
            print("Using root.export_to_png method")
            root.export_to_png(screenshot_path)
        else:
            # Window.screenshot may auto-number; returns the actual path used:
            print("Using Window.screenshot method")
            path = Window.screenshot(name=screenshot_path)
            print("Window.screenshot saved to: ", path)

        # Check if file was actually created
        import os
        if os.path.exists(screenshot_path):
            file_size = os.path.getsize(screenshot_path)
            print("Screenshot saved successfully! File size: ", file_size, "bytes")
        else:
            print("ERROR: Screenshot file not found at: ", screenshot_path)
            # List files in /work directory
            work_files = os.listdir('/work')
            print("Files in /work: ", work_files)

    except Exception as e:
        print("Screenshot failed: ", e)
        import traceback
        traceback.print_exc()
    finally:
        running_app = App.get_running_app()
        if running_app is not None:
            running_app.stop()
        else:
            stopTouchApp()
        exit()

def arm_once(*_):
    # IMPORTANT: unbind so we don't schedule every frame
    Window.unbind(on_flip=arm_once)
    Clock.schedule_once(take_screenshot_and_exit, 15)

Window.bind(on_flip=arm_once)

print("🚀 Starting user code...")
# User code starts here
{user_code}
'''

    return template.format(user_code=user_code)


async def placeholder_render_call(interaction: discord.Interaction, code: str, run_dir: Path):
    """
    Main render function that orchestrates the Kivy rendering process.
    """
    logging.info(f"🎬 Starting render call for user {interaction.user.name}")
    logging.info(f"📝 Code length: {len(code)} characters")
    logging.info(f"📁 Run directory: {run_dir}")
    
    try:
        # Use Docker rendering
        result = await render_kivy_snippet(interaction, code)
        logging.info(f"✅ Render successful, sending result: {result.get('content', 'No content')[:50]}...")
        await interaction.followup.send(**result, ephemeral=False)  # Make it visible to everyone
    except Exception as e:
        logging.error(f"💥 Error in placeholder_render_call: {e}", exc_info=True)
        await interaction.followup.send(
            f"❌ Something went wrong: {str(e)}",
            ephemeral=True,  # Keep error messages private
        )


class KivyPromptView(discord.ui.View):
    def __init__(self, source_message_id: int):
        super().__init__(timeout=180)
        self.source_message_id = source_message_id
        self.message = None  # Store reference to the message

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
        logging.info(f"🎯 Render button clicked by {interaction.user.name} for message {self.source_message_id}")
        
        # Disable all buttons during processing
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        
        data = PENDING_SNIPPETS.get(self.source_message_id)
        if not data:
            logging.warning(f"❌ No snippet data found for message {self.source_message_id}")
            await interaction.followup.send(
                "I couldn't find the original snippet (maybe I restarted). Try again.", 
                ephemeral=True
            )
            # Re-enable buttons
            for child in self.children:
                child.disabled = False
            await interaction.edit_original_response(view=self)
            return

        code = data["code"]
        logging.info(f"📝 Retrieved code snippet: {len(code)} chars")
        
        # Validate code for security
        if not validate_code(code):
            logging.warning("🚨 Code validation failed - contains dangerous operations")
            await interaction.followup.send(
                "❌ This code contains potentially dangerous operations and cannot be rendered.",
                ephemeral=True
            )
            # Re-enable buttons
            for child in self.children:
                child.disabled = False
            await interaction.edit_original_response(view=self)
            return

        try:
            run_dir = ensure_clean_run_dir(self.source_message_id)
            await placeholder_render_call(interaction, code, run_dir)
            
            # Change button label after successful render
            button.label = "Render again"
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
        finally:
            # Re-enable buttons
            for child in self.children:
                child.disabled = False
            await interaction.edit_original_response(view=self)

    @discord.ui.button(label="Change settings", style=discord.ButtonStyle.secondary)
    async def change_settings(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_message(
            "⚙️ Settings are coming soon. This will allow you to configure Kivy rendering options.", 
            ephemeral=True
        )

    @discord.ui.button(label="Go away", style=discord.ButtonStyle.danger)
    async def go_away(self, interaction: discord.Interaction, button: discord.ui.Button):
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
            logging.info(f"🔍 Found {len(blocks)} code blocks in message from {message.author.name}")
            
            # Selects the first block that looks like Kivy; if none, takes the first one
            selected = None
            for i, b in enumerate(blocks):
                is_kivy = looks_like_kivy(b)
                logging.info(f"📋 Block {i+1}: {len(b)} chars, looks_like_kivy={is_kivy}")
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

            view = KivyPromptView(source_message_id=message.id)
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


@bot.command()
async def ping(ctx: commands.Context):
    await ctx.send("🏓 Pong!")


if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except Exception as e:
        logging.error(f"Failed to start bot: {e}")
        print(f"❌ Failed to start bot: {e}")
