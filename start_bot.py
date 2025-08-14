import subprocess

cmd = (
    "screen -dmS bot bash -lc "
    "'export PYTHONUNBUFFERED=1; "
    "cd /root/doctor-kivy; "
    "uv run bot.py 2>&1 | tee -a /var/log/doctor-kivy.log'"
)

subprocess.run(cmd, shell=True, check=True)
print("Bot started in detached screen session named 'bot'.")
print("Run 'screen -r bot' to attach to the session. Press Ctrl+A D to detach.")
print("Run 'tail -f /var/log/doctor-kivy.log' to view the logs.")