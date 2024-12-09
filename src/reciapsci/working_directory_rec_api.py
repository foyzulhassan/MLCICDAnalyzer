import os
import yaml
from copy import deepcopy


class WorkingDirectoryRecommendation:
    def __init__(self, yaml_file, target_scripts_dir):
        self.yaml_file = yaml_file
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

    def parse_target_scripts(self):
        """
        Parse target scripts for paths.
        """
        script_paths = set()
        for root, dirs, files in os.walk(self.target_scripts_dir):
            for file in files:
                if file.endswith('.sh'):
                    script_path = os.path.join(root, file)
                    with open(script_path, 'r') as script_file:
                        for line in script_file:
                            if "cd " in line or "/" in line:
                                line = line.strip()
                                path = line.split("cd ")[-1].strip() if "cd " in line else line
                                if path.startswith('./') or '/' in path:
                                    script_paths.add(path)
        return script_paths

    def generate_recommendation(self):
        """
        Generate recommendations for working directories and update the YAML.
        """
        if not self.validate_yaml():
            return {"error": "Invalid YAML file"}

        script_paths = self.parse_target_scripts()
        updated_workflow = deepcopy(self.workflow)

        for job_id, job in updated_workflow.get('jobs', {}).items():
            for step in job.get('steps', []):
                if 'run' in step:
                    step_name = step.get('name', 'Unnamed Step')
                    for path in script_paths:
                        if path not in ['.', './', './root']:
                            if 'working-directory' not in step:
                                step['working-directory'] = path
                                self.recommendations.append({
                                    "job_id": job_id,
                                    "step_name": step_name,
                                    "recommendation": f"Added working-directory for '{path}' to the step.",
                                    "source": os.path.join(self.target_scripts_dir, 'target scripts')
                                })

        return {
            "updated_workflow": yaml.dump(updated_workflow, default_flow_style=False),
            "recommendations": self.recommendations
        }
