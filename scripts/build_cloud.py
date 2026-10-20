"""Optional build adapter for this proxy-backed cloud, not needed on a VPS.

Forwards standard proxy build args and resolves the proxy hostname for BuildKit.
Mounts the existing public CA bundle as an ephemeral BuildKit secret. Does not
copy credentials/certificates into the image or weaken certificate verification.
"""

import os
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


def main():
    command = ["docker", "build", "--network", "host"]
    proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    if proxy:
        host = urlsplit(proxy).hostname
        if not host:
            raise SystemExit("Invalid proxy configuration")
        command += ["--add-host", f"{host}:{socket.gethostbyname(host)}"]
        for key in [
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "NO_PROXY",
            "http_proxy",
            "https_proxy",
            "no_proxy",
        ]:
            if os.getenv(key):
                command += ["--build-arg", key]
        cert = Path(os.getenv("SSL_CERT_FILE", "/etc/ssl/certs/ca-certificates.crt"))
        if cert.is_file():
            command += ["--secret", f"id=build_ca,src={cert}"]
    command += ["-t", "business-pulse-pulse", "."]
    raise SystemExit(
        subprocess.run(
            command,
            env={
                **os.environ,
                "DOCKER_CONFIG": os.getenv("DOCKER_CONFIG", "/workspace/.docker-build"),
            },
        ).returncode
    )


if __name__ == "__main__":
    main()
