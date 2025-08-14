import subprocess

cmd = (
    "screen -dmS bot bash -lc "
    "'export PYTHONUNBUFFERED=1; "
    "cd /root/doctor-kivy; "
    "uv run bot.py 2>&1 | tee -a /var/log/doctor-kivy.log'"
)

subprocess.run(cmd, shell=True, check=True)