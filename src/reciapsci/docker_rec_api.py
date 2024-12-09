import os
import yaml
from copy import deepcopy

class DockerRecommendation:
    def __init__(self, yaml_file, strace_file, code_dir):
        self.yaml_file = yaml_file
        self.strace_file = strace_file
        self.code_dir = code_dir
        self.workflow = None
        self.recommendations = []

    def validate_yaml(self):
        """
        Validate the YAML file.
        """
        try:
            with open(self.yaml_file, 'r') as file:
                self.workflow = yaml.safe_load(file)
            return True
        except yaml.YAMLError as exc:
            print(f"Error parsing YAML file: {exc}")
            return False
        except FileNotFoundError:
            print(f"YAML file '{self.yaml_file}' not found.")
            return False

    def check_docker_in_code(self):
        """
        Check the codebase for Docker-related files or commands.
        """
        docker_files = []
        docker_commands = []
        try:
            for root, _, files in os.walk(self.code_dir):
                for file in files:
                    if file in ["Dockerfile", "docker-compose.yml"]:
                        docker_files.append(os.path.join(root, file))
                    elif file.endswith(".py") or file.endswith(".sh"):
                        with open(os.path.join(root, file), 'r') as f:
                            for line in f:
                                if "docker run" in line or "docker build" in line:
                                    docker_commands.append(line.strip())
        except FileNotFoundError:
            print(f"Code directory '{self.code_dir}' not found.")
        return docker_files, docker_commands

    def check_docker_in_strace(self):
        """
        Check the strace log for Docker-related system calls.
        """
        docker_calls = []
        try:
            with open(self.strace_file, 'r') as file:
                for line in file:
                    if "docker" in line:
                        docker_calls.append(line.strip())
        except FileNotFoundError:
            print(f"Strace file '{self.strace_file}' not found.")
        return docker_calls

    def generate_recommendation(self):
        """
        Generate recommendations for adding 'docker' commands to the workflow YAML.
        """
        if not self.validate_yaml():
            return {"error": "Invalid YAML file"}

        docker_files, docker_commands = self.check_docker_in_code()
        docker_calls = self.check_docker_in_strace()

        if not docker_files and not docker_commands and not docker_calls:
            return {
                "updated_workflow": yaml.dump(self.workflow, default_flow_style=False),
                "recommendations": []
            }

        updated_workflow = deepcopy(self.workflow)

        # Add docker-related recommendations
        for job_id, job in updated_workflow.get('jobs', {}).items():
            for step in job.get('steps', []):
                if 'run' in step:
                    if "docker" in step['run']:
                        step.setdefault('docker', True)
                        self.recommendations.append({
                            "job_id": job_id,
                            "step_name": step.get('name', 'Unnamed Step'),
                            "recommendation": "Detected Docker-related activity. Added 'docker: true' to the step.",
                            "source": {
                                "docker_files": docker_files,
                                "docker_commands": docker_commands,
                                "docker_calls": docker_calls
                            }
                        })

        return {
            "updated_workflow": yaml.dump(updated_workflow, default_flow_style=False),
            "recommendations": self.recommendations
        }
