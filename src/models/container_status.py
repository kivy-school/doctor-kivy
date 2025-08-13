from enum import Enum

class ContainerStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"

class ContainerInfo:
    def __init__(self, container_id: str):
        self.container_id = container_id
        self.status = ContainerStatus.IDLE

    def set_busy(self):
        self.status = ContainerStatus.BUSY

    def set_idle(self):
        self.status = ContainerStatus.IDLE

    def set_error(self):
        self.status = ContainerStatus.ERROR

    def __repr__(self):
        return f"ContainerInfo(container_id={self.container_id}, status={self.status})"