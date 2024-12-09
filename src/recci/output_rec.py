# import os
# import re

# class OutputRecommendation:
#     def __init__(self, workflow):
#         self.workflow = workflow
#         self.recommendations = []
#         self.output_sources = {}  # To store the sources of file/artifact writes

#     def extract_written_files_from_code(self, code_dir):
#         """
#         Extract files written by the codebase (e.g., open(file, 'w'), etc.).
#         """
#         written_files = {}

#         if code_dir:
#             try:
#                 for root, _, files in os.walk(code_dir):
#                     for file in files:
#                         if file.endswith('.py'):
#                             file_path = os.path.join(root, file)
#                             with open(file_path, 'r', errors='ignore') as f:
#                                 content = f.read()
#                                 # Match file writing patterns, e.g., open('filename', 'w')
#                                 matches = re.findall(r"open\(['\"](.*?)['\"], ['\"]w", content)
#                                 for match in matches:
#                                     written_files[match] = f"Codebase: {file_path}"
#             except Exception as e:
#                 print(f"Error scanning code directory for file writes: {e}")
        
#         return written_files

#     def extract_written_files_from_strace(self, strace_file):
#         """
#         Extract files modified or created based on strace logs (e.g., open(), write()).
#         """
#         written_files = {}

#         if strace_file and os.path.exists(strace_file):
#             try:
#                 with open(strace_file, 'r') as file:
#                     content = file.read()
#                     # Match system calls related to file creation/modification
#                     matches = re.findall(r'openat\([^,]+, "([^"]+)", O_CREAT|write\([^,]+, "([^"]+)",', content)
#                     for match in matches:
#                         file_path = match[0] or match[1]
#                         written_files[file_path] = "Strace log"
#             except Exception as e:
#                 print(f"Error reading strace file for file writes: {e}")
        
#         return written_files

#     def match_written_files_to_jobs(self, written_files):
#         """
#         Match files/artifacts written to jobs where relevant.
#         """
#         job_output_map = {job_id: [] for job_id in self.workflow.get('jobs', {}).keys()}

#         for job_id, job in self.workflow.get('jobs', {}).items():
#             for step in job.get('steps', []):
#                 if 'run' in step:
#                     step_command = step['run']
#                     for file_path, source in written_files.items():
#                         if file_path in step_command:
#                             job_output_map[job_id].append((file_path, source))
        
#         return job_output_map

#     def generate_recommendation(self, strace_file=None, code_dir=None):
#         """
#         Generate recommendations for file/artifact outputs.
#         """
#         files_from_code = self.extract_written_files_from_code(code_dir)
#         files_from_strace = self.extract_written_files_from_strace(strace_file)

#         # Combine all written files, preferring those from the codebase
#         all_written_files = {**files_from_strace, **files_from_code}
#         self.output_sources = all_written_files

#         job_output_map = self.match_written_files_to_jobs(all_written_files)

#         for job_id, files_with_sources in job_output_map.items():
#             if files_with_sources:
#                 recommendation = {
#                     "recommendation": (
#                         f"Define the following output files/artifacts under 'jobs.{job_id}.outputs' "
#                         "to ensure proper tracking and accessibility."
#                     ),
#                     "yaml": f"jobs:\n  {job_id}:\n    outputs:\n",
#                     "sources": {}
#                 }
#                 for file_path, source in files_with_sources:
#                     file_name = os.path.basename(file_path)  # Use the file name for the output key
#                     recommendation["yaml"] += f"      {file_name}: {file_path}\n"
#                     recommendation["sources"][file_path] = source
#                 self.recommendations.append(recommendation)

#     def output_recommendations(self):
#         """
#         Output the recommendations in human-readable format.
#         """
#         if not self.recommendations:
#             print("```yaml\n# No recommendations to provide for outputs. Your YAML looks good!\n```")
#             return

#         for rec in self.recommendations:
#             print("\nRecommendation:")
#             print(rec["recommendation"])
#             print("\nSuggested YAML Code Block:")
#             print("```yaml")
#             print(rec["yaml"])
#             print("```")
#             print("\nOutput Sources:")
#             for file_path, source in rec["sources"].items():
#                 print(f"  {file_path}: {source}")

import os
import re
import yaml

class OutputRecommendation:
    def __init__(self):
        self.recommendations = []

    def extract_written_files_from_code(self, code_dir):
        """
        Extract file paths that are being written to in the codebase using `open()` or similar calls.
        """
        written_files = {}

        if code_dir:
            try:
                for root, _, files in os.walk(code_dir):
                    for file in files:
                        if file.endswith('.py'):
                            file_path = os.path.join(root, file)
                            with open(file_path, 'r', errors='ignore') as f:
                                content = f.read()
                                # Match file write patterns using open("file_path", "w") or similar
                                matches = re.findall(r'open\(["\'](.*?)["\'], ["\']w', content)
                                for match in matches:
                                    written_files[match] = f"Codebase: {file_path}"
            except Exception as e:
                print(f"Error scanning code directory for written files: {e}")

        return written_files

    def extract_written_files_from_strace(self, strace_file):
        """
        Extract file paths being written to based on `strace` logs.
        """
        written_files = {}

        if strace_file and os.path.exists(strace_file):
            try:
                with open(strace_file, 'r') as file:
                    content = file.read()
                    # Match openat system calls with file creation/modification
                    matches = re.findall(r'openat\(.*?, "(.*?)", O_CREAT|O_WRONLY', content)
                    for match in matches:
                        written_files[match] = "Strace log"
            except Exception as e:
                print(f"Error reading strace file for written files: {e}")

        return written_files

    def generate_recommendation(self, job_id, job, strace_file=None, code_dir=None):
        """
        Generate recommendations for outputs for a specific job.
        """
        files_from_code = self.extract_written_files_from_code(code_dir)
        files_from_strace = self.extract_written_files_from_strace(strace_file)

        all_written_files = {**files_from_strace, **files_from_code}
        relevant_files = []

        # Check if the job's steps write to the files
        for step in job.get('steps', []):
            if 'run' in step:
                step_command = step['run']
                for file_path in all_written_files:
                    if file_path in step_command:
                        relevant_files.append((file_path, all_written_files[file_path]))

        # Skip recommendation if no relevant files found
        if not relevant_files:
            return

        recommendation = {
            "job_id": job_id,
            "original_block": job,
            "recommended_block": {
                "outputs": {os.path.basename(file_path): file_path for file_path, _ in relevant_files}
            },
            "sources": {file_path: source for file_path, source in relevant_files},
        }
        self.recommendations.append(recommendation)

    def output_recommendations(self):
        """
        Output recommendations for all jobs.
        """
        if not self.recommendations:
            print("No output recommendations available.")
            return

        for rec in self.recommendations:
            print("\n--- Output Recommendation ---")
            print(f"Job ID: {rec['job_id']}")
            print("\nOriginal Block:")
            print("```yaml")
            print(yaml.dump(rec["original_block"], default_flow_style=False))
            print("```")
            print("\nRecommended Block:")
            print("```yaml")
            print(yaml.dump(rec["recommended_block"], default_flow_style=False))
            print("```")
            print("\nSources Used:")
            for file_path, source in rec["sources"].items():
                print(f"  {file_path}: {source}")
