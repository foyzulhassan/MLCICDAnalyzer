import os
import yaml
from copy import deepcopy


class PermissionsRecommendation:
    def __init__(self, yaml_file, strace_file, target_scripts_dir):
        self.yaml_file = yaml_file
        self.strace_file = strace_file
        self.target_scripts_dir = target_scripts_dir
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

    def parse_strace(self):
        """
        Parse the strace log for repository-related accesses.
        """
        repo_related_paths = set()
        try:
            with open(self.strace_file, 'r') as file:
                for line in file:
                    if any(repo_marker in line for repo_marker in ['.git/', 'HEAD', 'commits', 'config']):
                        repo_related_paths.add(line.strip())
        except FileNotFoundError:
            print(f"Strace file '{self.strace_file}' not found.")
        return repo_related_paths

    def parse_target_scripts(self):
        """
        Parse target scripts for repository-related mentions.
        """
        repo_related_paths = set()
        for root, dirs, files in os.walk(self.target_scripts_dir):
            for file in files:
                if file.endswith('.sh'):
                    script_path = os.path.join(root, file)
                    with open(script_path, 'r') as script_file:
                        for line in script_file:
                            if any(repo_marker in line for repo_marker in ['.git/', 'repo_name/']):
                                repo_related_paths.add(line.strip())
        return repo_related_paths

    def generate_recommendation(self):
        """
        Generate recommendations for adding permissions to the workflow YAML.
        """
        if not self.validate_yaml():
            return {"error": "Invalid YAML file"}

        repo_related_paths = self.parse_strace().union(self.parse_target_scripts())
        updated_workflow = deepcopy(self.workflow)

        for job_id, job in updated_workflow.get('jobs', {}).items():
            if 'permissions' not in job and repo_related_paths:
                job['permissions'] = {
                    'contents': 'read',
                    'pull-requests': 'write',
                }
                self.recommendations.append({
                    "job_id": job_id,
                    "recommendation": "Added repository permissions for read/write access.",
                    "source": {
                        "repo_related_paths": list(repo_related_paths),
                        "strace_file": self.strace_file,
                        "target_scripts_dir": self.target_scripts_dir
                    }
                })

        return {
            "updated_workflow": yaml.dump(updated_workflow, default_flow_style=False),
            "recommendations": self.recommendations
        }
