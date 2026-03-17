import docker
import tempfile
import logging

logger = logging.getLogger(__name__)

class DockerSandbox:
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as e:
            logger.error("Docker daemon is not running. Sandbox unavailable.")
            self.client = None

    def execute_code(self, code: str, language="python"):
        if not self.client:
            return "ERROR: Docker Sandbox offline."
            
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(code.encode())
            f.flush()
            
            try:
                # Runs a disposable Alpine python container, maps the script, executes, and destroys itself.
                container = self.client.containers.run(
                    "python:3.10-alpine",
                    command=f"python /mnt/{Path(f.name).name}",
                    volumes={Path(f.name).parent: {'bind': '/mnt', 'mode': 'ro'}},
                    mem_limit="512m",
                    cpu_period=100000,
                    cpu_quota=50000, # 50% of CPU
                    network_mode="none", # Totally isolated
                    remove=True,
                    detach=False
                )
                return container.decode('utf-8')
            except Exception as e:
                return f"Execution Error: {str(e)}"
