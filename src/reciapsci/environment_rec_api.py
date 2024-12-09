import os
import re
import yaml
# old
class EnvironmentRecommendationAPI:
    def __init__(self, yaml_file):
        self.yaml_file = yaml_file
        self.workflow = None
        self.recommendations = []

    def load_yaml(self):
        """
        Load and validate the YAML file.
        """
        try:
            with open(self.yaml_file, 'r') as file:
                self.workflow = yaml.safe_load(file)
            return True
        except yaml.YAMLError as exc:
            print(f"Error parsing YAML file '{self.yaml_file}': {exc}")
            return False

    def extract_env_vars_from_code(self, code_dir):
        """
        Extract environment variables from the provided code directory.
        """
        env_vars = []
        pattern = r"os\.getenv\(['\"](.*?)['\"]\)"
        for root, _, files in os.walk(code_dir):
            for file in files:
                if file.endswith(".py"):
                    with open(os.path.join(root, file), 'r') as f:
                        matches = re.findall(pattern, f.read())
                        env_vars.extend(matches)
        return list(set(env_vars))

    def extract_env_vars_from_strace(self, strace_file):
        """
        Extract environment variables from the strace log.
        """
        env_vars = []
        try:
            with open(strace_file, 'r') as file:
                content = file.read()
                matches = re.findall(r"getenv\(['\"](.*?)['\"]\)", content)
                env_vars.extend(matches)
        except FileNotFoundError:
            print(f"Strace file '{strace_file}' not found.")
        return list(set(env_vars))

    def generate_recommendations(self, code_dir, strace_file):
        """
        Generate recommendations for environment variables.
        """
        env_vars_code = self.extract_env_vars_from_code(code_dir)
        env_vars_strace = self.extract_env_vars_from_strace(strace_file)
        matched_env_vars = list(set(env_vars_code + env_vars_strace))

        if not matched_env_vars:
            return

        for job_id, job in self.workflow.get('jobs', {}).items():
            self.recommendations.append({
                "job_id": job_id,
                "matched_vars": matched_env_vars,
                "source": {"code": env_vars_code, "strace": env_vars_strace}
            })

    def output_recommendations(self, return_as_dict=False):
        """
        Output recommendations in JSON-friendly or console format.
        """
        if return_as_dict:
            return [
                {
                    "job_id": rec["job_id"],
                    "matched_vars": rec["matched_vars"],
                    "sources": rec["source"]
                }
                for rec in self.recommendations
            ]
        else:
            for rec in self.recommendations:
                print(f"Job ID: {rec['job_id']}")
                print(f"Matched Variables: {rec['matched_vars']}")
                print(f"Sources: {rec['source']}")
