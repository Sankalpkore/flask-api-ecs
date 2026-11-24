# Containerised Flask API on AWS (Docker, ECR, EC2)

A small Python (Flask) REST API packaged as a production-style Docker image, pushed to a private Amazon ECR repository, scanned for vulnerabilities, and deployed on an Amazon EC2 instance.

## Architecture

```
Code -> docker build -> Amazon ECR (scan on push) -> EC2 pulls via IAM role -> container on port 8000 -> browser
```

## What this project shows

- Writing a **Dockerfile** for a Python web app with layer caching, a non-root user and a production web server (gunicorn)
- Building, running and debugging containers locally (`docker build`, `run`, `logs`, `exec`)
- Pushing images to **Amazon ECR** with versioned tags
- **Vulnerability scanning** with ECR and reducing findings by patching the base image
- **Deploying on Amazon EC2** with an IAM instance role (no access keys on the server), a least-privilege security group and a Docker restart policy

## API endpoints

| Method | Path      | Returns                                                  |
|--------|-----------|----------------------------------------------------------|
| GET    | `/`       | Welcome message and app version                          |
| GET    | `/health` | `{"status": "ok"}`, used for container health checks     |
| GET    | `/info`   | Container hostname, app version and current UTC time     |

## Dockerfile design choices

- **`python:3.12-slim` base** keeps the image small (~45 MB compressed).
- **`apt-get upgrade` during the build** installs the latest Debian security patches.
- **`requirements.txt` is copied before the code**, so dependency installation is cached and rebuilds after code changes are fast.
- **Runs as a non-root user (`appuser`)** to limit damage if the app is compromised.
- **gunicorn** serves the app instead of Flask's development server.
- **`APP_VERSION` build argument** bakes a version label into the image, visible at `/info`.

## Run locally

```bash
docker build --provenance=false -t flask-api:v2 .
docker run -d -p 8000:8000 --name flask-api flask-api:v2
curl http://localhost:8000/info
```

Useful commands:

```bash
docker ps                     # running containers
docker logs flask-api         # gunicorn logs
docker exec -it flask-api sh  # shell inside the container (whoami -> appuser)
docker stop flask-api && docker rm flask-api
```

## Push to Amazon ECR

```bash
# One-time: create a private repository with scan-on-push enabled
aws ecr create-repository --repository-name flask-api-ecs --region ap-south-1 \
  --image-scanning-configuration scanOnPush=true

# Authenticate Docker to ECR (token valid for 12 hours)
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com

# Tag and push
docker tag flask-api:v2 <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/flask-api-ecs:v2
docker push <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/flask-api-ecs:v2
```

## Deploy on Amazon EC2

1. **IAM role** `ec2-ecr-pull-role` with the `AmazonEC2ContainerRegistryReadOnly` policy, attached to the instance as an instance profile. The server gets temporary credentials from the role, so no access keys are stored on it.
2. **EC2 instance:** Amazon Linux 2023 (x86_64), t3.micro, in ap-south-1.
3. **Security group:** SSH (22) from my IP only; TCP 8000 open for the demo.
4. **Install Docker on the server:**

```bash
sudo dnf update -y
sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user   # log out and back in afterwards
```

5. **Pull and run the image** (ECR login uses the instance role):

```bash
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com
docker run -d --name flask-api -p 8000:8000 --restart unless-stopped \
  <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/flask-api-ecs:v2
```

6. Open `http://<EC2_PUBLIC_IP>:8000/info`.

`--restart unless-stopped` means Docker starts the container again after a crash or a server reboot.

## Vulnerability scanning results

| Image | Change                                    | HIGH | MEDIUM | LOW |
|-------|-------------------------------------------|------|--------|-----|
| v1    | Base `python:3.12-slim`                   | 3    | 15     | 4   |
| v2    | Added Debian security updates in the build | 2    | 14     | 4   |

The remaining HIGH findings are in Debian OS packages (`glibc`) with no upstream fix available at the time of the scan. The app does not call the affected functions. The image will be rebuilt when Debian releases patches.

## Problems I hit and how I fixed them

**ECR scan returned `ScanNotFoundException` for my tag.**
Docker Desktop adds a provenance attestation to builds by default, which turns the pushed tag into an OCI *image index* (a list pointing to the real image plus an attestation). ECR basic scanning only scans image manifests, not indexes. Rebuilding with `--provenance=false` made the tag point directly to the image, and the scan results appeared.

**SSH to EC2 timed out.**
When I picked "My IP" in the security group, the console recorded my **IPv6** address, because my browser reached AWS over IPv6. The instance only had an IPv4 address and my SSH client connected over IPv4, so no rule matched and the traffic was silently dropped. AWS doesn't allow changing an existing rule from IPv6 to IPv4, so I deleted it and added a new SSH rule for my IPv4 address (`/32`).

**`aws: [ERROR]: Unknown output type: .json`**
The AWS CLI default output had been saved as `.json` instead of `json`. Fixed with `aws configure set output json`.

## Next steps

- Run the same image on **Amazon ECS Fargate** (no servers to manage)
- Automate build, scan and push with **GitHub Actions** using OIDC (no long-lived AWS keys)
- Replace SSH with **SSM Session Manager** so no inbound ports need to be open for admin access
