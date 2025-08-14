# 🤖 Doctor Kivy - Discord Bot

A Discord bot that can render Kivy applications and take screenshots, similar to the Manim Discord bot.

> 🩺 I observe your code, inspect the widgets, and capture the diagnosis in a screenshot

https://github.com/user-attachments/assets/c8237d21-bdea-4869-9f2b-996ef2daf9d7

## 🚀 Features

- **Code Detection**: Automatically detects Python code blocks with Kivy imports
- **Docker Rendering**: Runs Kivy apps in isolated Docker containers
- **Screenshot Generation**: Automatically captures app screenshots

## 📋 Prerequisites

- Python 3.11+
- Docker installed and running
- Discord Bot Token

## 🛠️ Setup

### 1. Install Python

```bash
# Install Python 3.11
uv python install 3.11
```

### 2. Build Docker Image (Linux/Mac)

**Option 1: Manual Build**
```bash
docker build -t kivy-renderer:latest .
docker build -t kivy-renderer:prewarmed -f docker/Dockerfile.prewarmed .
```

**Option 2: Using setup script**
```bash
chmod +x setup_docker.sh
./setup_docker.sh
```

### 3. Environment Setup

Create a `.env` file:
```env
DISCORD_TOKEN=your_discord_bot_token_here
```

### 4. Run the Bot

```bash
uv run bot.py
```

## 🎯 Usage

After adding the bot to your Discord server:

1. **Post Kivy Code**: Send a message with Python code blocks containing Kivy imports:

````markdown
```python
from kivy.app import App
from kivy.uix.button import Button

class MyApp(App):
    def build(self):
        return Button(text="Hello, Kivy!")

MyApp().run()
```
````

2. **Bot Response**: The bot will detect Kivy code and offer to render it
3. **Rendering**: Click "Yes, render" to execute the code in Docker and get a screenshot

## Docker Environment

- **Base**: Python 3.11-slim
- **Display**: Xvfb (virtual framebuffer)
- **Libraries**: Kivy, Pillow, kivy-reloader
- **Limits**: 512MB RAM, 50% CPU, 30s timeout

## 🔒 Security Features

- Docker isolation prevents system access
- Resource limits prevent abuse
- Automatic cleanup of temporary files
- Memory leak prevention with periodic cleanup

## 🚨 Error Handling

- User-friendly error messages
- Detailed logging for debugging

## 📁 Project Structure

```
doctor-kivy/
├── bot.py                        # Main bot code
├── docker/                       # Docker configuration
│   ├── Dockerfile.prewarmed      # Pre-warmed container image
│   └── requirements.txt          # Python dependencies for containers
├── Dockerfile                    # Main Kivy rendering environment
└── setup_docker.sh               # Linux/Mac setup script
```

## 🔧 Configuration

The bot supports various configuration options:

- **Timeout**: 30 seconds per render
- **Memory Limit**: 512MB per container
- **CPU Limit**: 50% CPU quota
- **Cleanup Interval**: 60 minutes

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes
4. Test with Docker rendering
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Inspired by the [Manim Community Discord Bot](https://github.com/ManimCommunity/DiscordManimator)
- Built with [discord.py](https://github.com/Rapptz/discord.py)
- Rendering powered by [Kivy](https://github.com/kivy/kivy)
