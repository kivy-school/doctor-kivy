# filepath: /kivy-discord-bot/kivy-discord-bot/src/utils/helpers.py
def get_container_status(container):
    """
    Returns the status of the given Docker container.
    """
    return {
        "id": container.id,
        "name": container.name,
        "status": container.status,
        "created": container.attrs['Created'],
        "image": container.attrs['Config']['Image'],
    }

def format_render_request(user_id, code):
    """
    Formats the render request data for logging or processing.
    """
    return {
        "user_id": user_id,
        "code_length": len(code),
        "timestamp": datetime.utcnow().isoformat(),
    }

def log_performance_metrics(start_time, end_time, request_details):
    """
    Logs the performance metrics for rendering requests.
    """
    duration = (end_time - start_time).total_seconds()
    logging.info(f"Render request completed in {duration:.2f} seconds. Details: {request_details}")

def sanitize_code(code):
    """
    Sanitizes the Kivy code to prevent potential security issues.
    """
    # Implement sanitization logic here
    return code.strip()  # Example: stripping whitespace

def handle_error(error):
    """
    Centralized error handling function.
    """
    logging.error(f"An error occurred: {error}")
    return str(error)  # Return a string representation of the error for user feedback