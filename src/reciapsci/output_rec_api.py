import os
import re
import yaml
# old
class OutputRecommendationAPI:
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

    def extract_written_files_from_code(self, code_dir):
        """
        Extract written files from the provided code directory.
        """
        written_files = []
        pattern = r"open\(['\"](.*?)['\"], ['\"]w['\"]\)"
        for root, _, files in os.walk(code_dir):
            for file in files:
                if file.endswith(".py"):
                    with open(os.path.join(root, file), 'r') as f:
                        matches = re.findall(pattern, f.read())
                        written_files.extend(matches)
        return list(set(written_files))

    def extract_written_files_from_strace(self, strace_file):
        """
        Extract written files from the strace log.
        """
        written_files = []
        try:
            with open(strace_file, 'r') as file:
                content = file.read()
                matches = re.findall(r"open\(['\"](.*?)['\"], O_CREAT", content)
                written_files.extend(matches)
        except FileNotFoundError:
            print(f"Strace file '{strace_file}' not found.")
        return list(set(written_files))

    def generate_recommendations(self, strace_file, code_dir):
        """
        Generate recommendations for output artifacts.
        """
        files_from_code = self.extract_written_files_from_code(code_dir)
        files_from_strace = self.extract_written_files_from_strace(strace_file)
        matched_files = list(set(files_from_code + files_from_strace))

        if not matched_files:
            return

        for job_id, job in self.workflow.get('jobs', {}).items():
            self.recommendations.append({
                "job_id": job_id,
                "original_block": job,
                "recommended_block": {"outputs": matched_files},
                "sources": {"code": files_from_code, "strace": files_from_strace}
            })

    def output_recommendations(self, return_as_dict=False):
        """
        Output recommendations in JSON-friendly or console format.
        """
        if return_as_dict:
            return [
                {
                    "job_id": rec["job_id"],
                    "original_block": rec["original_block"],
                    "recommended_block": rec["recommended_block"],
                    "sources": rec["sources"]
                }
                for rec in self.recommendations
            ]
        else:
            for rec in self.recommendations:
                print(f"Job ID: {rec['job_id']}")
                print(f"Original Block: {rec['original_block']}")
                print(f"Recommended Block: {rec['recommended_block']}")
                print(f"Sources: {rec['sources']}")
