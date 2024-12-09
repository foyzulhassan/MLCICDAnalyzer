import yaml
from copy import deepcopy
import os

class TimeoutRecommendation:
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

    def parse_strace_for_long_tasks(self):
        """
        Parse the strace log for long-running tasks.
        """
        long_running_tasks = []
        try:
            with open(self.strace_file, 'r') as file:
                for line in file:
                    if "connect(" in line or "write(" in line:
                        # Network/API calls or large file writes
                        long_running_tasks.append(line.strip())
        except FileNotFoundError:
            print(f"Strace file '{self.strace_file}' not found.")
        return long_running_tasks

    def analyze_code_for_long_operations(self):
        """
        Analyze code for long-running operations like I/O or API calls.
        """
        long_operations = []
        try:
            for root, _, files in os.walk(self.code_dir):
                for file in files:
                    if file.endswith(".py"):
                        with open(os.path.join(root, file), 'r') as f:
                            for line in f:
                                if "time.sleep(" in line or "requests.get(" in line:
                                    long_operations.append(line.strip())
        except FileNotFoundError:
            print(f"Code directory '{self.code_dir}' not found.")
        return long_operations

    def generate_recommendation(self):
        """
        Generate recommendations for adding 'timeout-minutes' to the workflow YAML.
        """
        if not self.validate_yaml():
            return {"error": "Invalid YAML file"}

        long_tasks = self.parse_strace_for_long_tasks()
        long_operations = self.analyze_code_for_long_operations()

        if not long_tasks and not long_operations:
            return {
                "updated_workflow": yaml.dump(self.workflow, default_flow_style=False),
                "recommendations": []
            }

        updated_workflow = deepcopy(self.workflow)

        # Add timeout-minutes to jobs with long-running steps
        for job_id, job in updated_workflow.get('jobs', {}).items():
            for step in job.get('steps', []):
                if 'run' in step:
                    # If step references long-running tasks or operations
                    if any(task in step['run'] for task in long_tasks) or any(op in step['run'] for op in long_operations):
                        step['timeout-minutes'] = 30  # Default timeout value
                        self.recommendations.append({
                            "job_id": job_id,
                            "step_name": step.get('name', 'Unnamed Step'),
                            "recommendation": "Added 'timeout-minutes' to avoid indefinite waits for long-running tasks.",
                            "source": {
                                "long_tasks": long_tasks,
                                "long_operations": long_operations
                            }
                        })

        return {
            "updated_workflow": yaml.dump(updated_workflow, default_flow_style=False),
            "recommendations": self.recommendations
        }
