import yaml
from copy import deepcopy


class NeedsRecommendation:
    def __init__(self, yaml_file, strace_file):
        self.yaml_file = yaml_file
        self.strace_file = strace_file
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
        Parse the strace log for shared resource access across jobs.
        """
        shared_resources = set()
        try:
            with open(self.strace_file, 'r') as file:
                for line in file:
                    if "open(" in line:
                        # Extract file paths or resources
                        parts = line.split('"')
                        if len(parts) > 1:
                            shared_resources.add(parts[1])
        except FileNotFoundError:
            print(f"Strace file '{self.strace_file}' not found.")
        return shared_resources

    def generate_recommendation(self):
        """
        Generate recommendations for adding 'needs' dependencies to the workflow YAML.
        """
        if not self.validate_yaml():
            return {"error": "Invalid YAML file"}

        shared_resources = self.parse_strace()
        updated_workflow = deepcopy(self.workflow)

        # Collect jobs that access shared resources
        job_dependencies = {}
        for job_id, job in updated_workflow.get('jobs', {}).items():
            job_dependencies[job_id] = []
            for step in job.get('steps', []):
                if 'run' in step:
                    for resource in shared_resources:
                        if resource in step['run']:
                            job_dependencies[job_id].append(resource)

        # Analyze inter-job dependencies and add 'needs'
        for job_id, dependencies in job_dependencies.items():
            if dependencies:
                dependent_jobs = [
                    dep_job_id for dep_job_id, dep_resources in job_dependencies.items()
                    if set(dependencies).intersection(set(dep_resources)) and dep_job_id != job_id
                ]
                if dependent_jobs:
                    updated_workflow['jobs'][job_id]['needs'] = dependent_jobs
                    self.recommendations.append({
                        "job_id": job_id,
                        "recommendation": f"Added 'needs' dependencies on jobs: {dependent_jobs}.",
                        "source": {
                            "shared_resources": list(shared_resources),
                            "strace_file": self.strace_file
                        }
                    })

        return {
            "updated_workflow": yaml.dump(updated_workflow, default_flow_style=False),
            "recommendations": self.recommendations
        }
