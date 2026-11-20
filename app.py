"""Small Flask API used to practise Docker, ECR, ECS Fargate and GitHub Actions."""
import os
import socket
from datetime import datetime, timezone

from flask import Flask, jsonify

app = Flask(__name__)

# Set at build time (GitHub Actions passes the git commit SHA) so you can see
# which version of the image is running after each deploy.
APP_VERSION = os.environ.get("APP_VERSION", "local")


@app.get("/")
def index():
    return jsonify(message="Hello from a container on AWS!", version=APP_VERSION)


@app.get("/health")
def health():
    # ECS and load balancers call this to check the container is alive.
    return jsonify(status="ok"), 200


@app.get("/info")
def info():
    return jsonify(
        hostname=socket.gethostname(),  # container ID locally, task ID on ECS
        version=APP_VERSION,
        time_utc=datetime.now(timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    # Only used for quick local runs without Docker. In the container, gunicorn runs the app.
    app.run(host="0.0.0.0", port=8000, debug=True)
