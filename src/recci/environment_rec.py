# import os
# import re

# class EnvironmentRecommendation:
#     def __init__(self, workflow):
#         self.workflow = workflow
#         self.recommendations = []
#         self.env_var_sources = {}  # To store sources of environment variables

#     def clean_env_var_name(self, var):
#         # Clean and return the environment variable name
#         var = var.split(",")[0]
#         return var.strip().replace('"', '').replace("'", '')

#     def extract_env_vars_from_code(self, code_dir):
#         env_vars = {}

#         if code_dir:
#             try:
#                 for root, _, files in os.walk(code_dir):
#                     for file in files:
#                         if file.endswith('.py'):
#                             file_path = os.path.join(root, file)
#                             with open(file_path, 'r', errors='ignore') as f:
#                                 content = f.read()
#                                 matches = re.findall(r"os\.getenv\(['\"](.*?)['\"](?:, ['\"].*?['\"])?\)", content)
#                                 for match in matches:
#                                     clean_var = self.clean_env_var_name(match)
#                                     env_vars[clean_var] = f"Codebase: {file_path}"
#             except Exception as e:
#                 print(f"Error scanning code directory: {e}")
        
#         return env_vars

#     def extract_env_vars_from_strace(self, strace_file):
#         env_vars = {}

#         if strace_file and os.path.exists(strace_file):
#             try:
#                 with open(strace_file, 'r') as file:
#                     content = file.read()
#                     matches = re.findall(r"getenv\(['\"](.*?)['\"](?:, ['\"].*?['\"])?\)", content)
#                     for match in matches:
#                         clean_var = self.clean_env_var_name(match)
#                         env_vars[clean_var] = "Strace log"
#             except Exception as e:
#                 print(f"Error reading strace file: {e}")
        
#         return env_vars

#     def match_env_vars_to_jobs(self, env_vars):
#         """
#         Match environment variables to jobs where they are relevant.
#         """
#         job_env_map = {job_id: [] for job_id in self.workflow.get('jobs', {}).keys()}

#         for job_id, job in self.workflow.get('jobs', {}).items():
#             for step in job.get('steps', []):
#                 if 'run' in step:
#                     step_command = step['run']
#                     for var, source in env_vars.items():
#                         if var in step_command:
#                             job_env_map[job_id].append((var, source))
        
#         return job_env_map

#     def generate_recommendation(self, strace_file=None, code_dir=None):
#         env_vars_code = self.extract_env_vars_from_code(code_dir)
#         env_vars_strace = self.extract_env_vars_from_strace(strace_file)

#         all_env_vars = {**env_vars_strace, **env_vars_code}
#         self.env_var_sources = all_env_vars

#         job_env_map = self.match_env_vars_to_jobs(all_env_vars)

#         for job_id, vars_with_sources in job_env_map.items():
#             if vars_with_sources:
#                 recommendation = {
#                     "recommendation": (
#                         f"Define the following environment variables under 'jobs.{job_id}.environment' "
#                         "to ensure consistent access across steps."
#                     ),
#                     "yaml": f"jobs:\n  {job_id}:\n    environment:\n",
#                     "sources": {}
#                 }
#                 for var, source in vars_with_sources:
#                     recommendation["yaml"] += f"      {var}: <value>\n"
#                     recommendation["sources"][var] = source
#                 self.recommendations.append(recommendation)

#     def output_recommendations(self):
#         if not self.recommendations:
#             print("```yaml\n# No recommendations to provide. Your YAML looks good!\n```")
#             return

#         for rec in self.recommendations:
#             print("\nRecommendation:")
#             print(rec["recommendation"])
#             print("\nSuggested YAML Code Block:")
#             print("```yaml")
#             print(rec["yaml"])
#             print("```")
#             print("\nVariable Sources:")
#             for var, source in rec["sources"].items():
#                 print(f"  {var}: {source}")

# iNPUT:
# jobs:
#   Benchmarks:
#     steps:
#       - name: Run Benchmarks
#         run: |
#           python3 train.py --env COMET_LOG_PREDICTIONS
#   Tests:
#     steps:
#       - name: Run Tests
#         run: |
#           pytest tests/

# Output :

# Recommendation:
# Define the following environment variables under 'jobs.Benchmarks.environment' to ensure consistent access across steps.

# Suggested YAML Code Block:
# ```yaml
# jobs:
#   Benchmarks:
#     environment:
#       COMET_LOG_PREDICTIONS: <value>


import os
import re

class EnvironmentRecommendation:
    def __init__(self, workflow):
        self.workflow = workflow
        self.recommendations = []
        self.env_var_sources = {}  # To store sources of environment variables

    def clean_env_var_name(self, var):
        """
        Cleans up environment variable names by removing unwanted characters or default values.
        """
        # Remove any default values after a comma
        var = var.split(",")[0]
        # Strip surrounding quotes and spaces
        return var.strip().replace('"', '').replace("'", '')

    def extract_env_vars_from_code(self, code_dir):
        """
        Extract environment variable names from the codebase.
        Tracks the file where each variable is found.
        """
        env_vars = {}

        if code_dir:
            try:
                for root, _, files in os.walk(code_dir):
                    for file in files:
                        if file.endswith('.py'):
                            file_path = os.path.join(root, file)
                            with open(file_path, 'r', errors='ignore') as f:
                                content = f.read()
                                # Match os.getenv("VAR_NAME") or os.getenv('VAR_NAME', 'default_value')
                                matches = re.findall(r"os\.getenv\(['\"](.*?)['\"](?:, ['\"].*?['\"])?\)", content)
                                for match in matches:
                                    clean_var = self.clean_env_var_name(match)
                                    env_vars[clean_var] = f"Codebase: {file_path}"
            except Exception as e:
                print(f"Error scanning code directory: {e}")
        
        return env_vars

    def extract_env_vars_from_strace(self, strace_file):
        """
        Extract environment variable names from the strace output.
        Tracks that the variable came from strace.
        """
        env_vars = {}

        if strace_file and os.path.exists(strace_file):
            try:
                with open(strace_file, 'r') as file:
                    content = file.read()
                    # Match getenv("VAR_NAME") or getenv('VAR_NAME', 'default_value')
                    matches = re.findall(r"getenv\(['\"](.*?)['\"](?:, ['\"].*?['\"])?\)", content)
                    for match in matches:
                        clean_var = self.clean_env_var_name(match)
                        env_vars[clean_var] = "Strace log"
            except Exception as e:
                print(f"Error reading strace file: {e}")
        
        return env_vars

    def generate_recommendation(self, strace_file=None, code_dir=None):
        """
        Generate environment variable-related recommendations.
        """
        if not self.workflow:
            raise ValueError("Workflow not loaded.")

        # Extract environment variables from both sources
        env_vars_code = self.extract_env_vars_from_code(code_dir)
        env_vars_strace = self.extract_env_vars_from_strace(strace_file)

        # Combine all environment variables, preferring the source from the codebase
        all_env_vars = {**env_vars_strace, **env_vars_code}
        self.env_var_sources = all_env_vars

        if all_env_vars:
            for job_id, _ in self.workflow.get('jobs', {}).items():
                recommendation = {
                    "recommendation": (
                        f"Define the following environment variables under 'jobs.{job_id}.environment' "
                        "to ensure consistent access across steps."
                    ),
                    "yaml": f"jobs:\n  {job_id}:\n    environment:\n",
                    "sources": {}
                }
                for var, source in sorted(all_env_vars.items()):
                    recommendation["yaml"] += f"      {var}: <value>\n"
                    recommendation["sources"][var] = source
                self.recommendations.append(recommendation)

    def output_recommendations(self):
        """
        Output the recommendations in human-readable format.
        """
        if not self.recommendations:
            print("```yaml\n# No recommendations to provide. Your YAML looks good!\n```")
            return

        for rec in self.recommendations:
            print("\nRecommendation:")
            print(rec["recommendation"])
            print("\nSuggested YAML Code Block:")
            print("```yaml")
            print(rec["yaml"])
            print("```")
            print("\nVariable Sources:")
            for var, source in rec["sources"].items():
                print(f"  {var}: {source}")


# Recommendation:
# Define the following environment variables under 'jobs.Benchmarks.environment' to ensure consistent access across steps.

# Suggested YAML Code Block:
# ```yaml
# jobs:
#   Benchmarks:
#     environment:
#       COMET_LOG_PREDICTIONS", "true: <value>
#       COMET_LOG_PER_CLASS_METRICS", "false: <value>
#       COMET_PROJECT_NAME: <value>
#       COMET_LOG_BATCH_METRICS", "false: <value>
#       COMET_DEFAULT_CHECKPOINT_FILENAME", "last.pt: <value>
#       COMET_MODEL_NAME", "yolov5: <value>
#       COMET_LOG_CONFUSION_MATRIX", "true: <value>
#       COMET_OPTIMIZER_ID: <value>
#       COMET_UPLOAD_DATASET", "false: <value>
#       YOLOv5_DATASETS_DIR", ROOT.parent / "datasets: <value>
#       COMET_MODE", "online: <value>

# ```

# Recommendation:
# Define the following environment variables under 'jobs.Tests.environment' to ensure consistent access across steps.

# Suggested YAML Code Block:
# ```yaml
# jobs:
#   Tests:
#     environment:
#       COMET_LOG_PREDICTIONS", "true: <value>
#       COMET_LOG_PER_CLASS_METRICS", "false: <value>
#       COMET_PROJECT_NAME: <value>
#       COMET_LOG_BATCH_METRICS", "false: <value>
#       COMET_DEFAULT_CHECKPOINT_FILENAME", "last.pt: <value>
#       COMET_MODEL_NAME", "yolov5: <value>
#       COMET_LOG_CONFUSION_MATRIX", "true: <value>
#       COMET_OPTIMIZER_ID: <value>
#       COMET_UPLOAD_DATASET", "false: <value>
#       YOLOv5_DATASETS_DIR", ROOT.parent / "datasets: <value>
#       COMET_MODE", "online: <value>

# ```