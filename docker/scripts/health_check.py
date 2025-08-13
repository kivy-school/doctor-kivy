import os
import requests

HEALTH_CHECK_URL = "http://localhost:8080/health"  # Adjust based on your container's health check endpoint

def check_container_health():
    try:
        response = requests.get(HEALTH_CHECK_URL)
        if response.status_code == 200:
            print("✅ Container is healthy.")
            return True
        else:
            print(f"❌ Container health check failed with status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Error during health check: {e}")
        return False

if __name__ == "__main__":
    check_container_health()