from logging import getLogger, StreamHandler, Formatter, INFO, DEBUG, FileHandler

def setup_logging(log_file='kivy_bot.log', level=INFO):
    logger = getLogger()
    logger.setLevel(level)

    # Console handler
    console_handler = StreamHandler()
    console_handler.setLevel(level)
    console_formatter = Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler
    file_handler = FileHandler(log_file)
    file_handler.setLevel(level)
    file_formatter = Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    logger.info("Logging is set up.")