import argparse
import json
import os
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

def analyze_script_for_paths(target_script_path):
    """Analyze the target script for specific paths and subdirectories."""
    if not os.path.exists(target_script_path):
        return []
    
    paths = []
    with open(target_script_path, 'r') as script_file:
        for line in script_file:
            if any(keyword in line for keyword in ('cd ', 'mkdir ', 'rm ', './')):
                paths.append(line.strip())
    return paths

def is_valid_github_actions_yml(yml_content):
    """Check if the YAML is valid for GitHub Actions."""
    required_keys = ['name', 'on', 'jobs']
    try:
        for key in required_keys:
            if key not in yml_content:
                return False, f"Missing key: {key}"
        return True, "YAML is valid and complete for GitHub Actions."
    except Exception as e:
        return False, f"YAML validation error: {str(e)}"

def split_yml_into_chunks(yml_content):
    """Split YAML into chunks like name, on, and jobs."""
    chunks = CommentedMap()
    chunks['name'] = yml_content.get('name', '')
    chunks['on'] = yml_content.get('on', {})
    chunks['jobs'] = yml_content.get('jobs', {})
    return chunks

def apply_recommendations(job_id, job_data, script_paths, strace_data):
    """Apply recommendations to a specific job."""
    recommendations = {}
    updated_job = job_data.copy()

    # Add `working-directory` recommendation
    if any('./' in path for path in script_paths):
        updated_job.setdefault('steps', [])
        for idx, step in enumerate(updated_job['steps']):
            if 'working-directory' not in step:
                recommendations[f'{job_id}_step_{idx}_working_directory'] = {
                    "recommendation": "Add 'working-directory' to avoid ambiguity.",
                    "status": "missing",
                    "original": step,
                    "updated": {**step, "working-directory": "./src"}
                }
                step['working-directory'] = './src'

    # Add `concurrency` recommendation
    if 'concurrency' not in updated_job:
        recommendations[f'{job_id}_concurrency'] = {
            "recommendation": "Add concurrency control to avoid job overlaps.",
            "status": "missing",
            "original": job_data,
            "updated": {**job_data, "concurrency": {"group": "${{ github.ref }}", "cancel-in-progress": True}}
        }
        updated_job['concurrency'] = {"group": "${{ github.ref }}", "cancel-in-progress": True}

    # Add `environment` recommendation
    if 'environment' not in updated_job:
        recommendations[f'{job_id}_environment'] = {
            "recommendation": "Add 'environment' variables for better control.",
            "status": "missing",
            "original": job_data,
            "updated": {**job_data, "environment": {"name": "production", "url": "https://api.example.com"}}
        }
        updated_job['environment'] = {"name": "production", "url": "https://api.example.com"}

    # Add `permissions` recommendation
    if 'permissions' not in updated_job:
        recommendations[f'{job_id}_permissions'] = {
            "recommendation": "Add permissions to control access to repository resources.",
            "status": "missing",
            "original": job_data,
            "updated": {**job_data, "permissions": {"contents": "write", "packages": "read"}}
        }
        updated_job['permissions'] = {"contents": "write", "packages": "read"}

    # Add `outputs` recommendation
    if 'outputs' not in updated_job:
        recommendations[f'{job_id}_outputs'] = {
            "recommendation": "Add outputs for artifact generation.",
            "status": "missing",
            "original": job_data,
            "updated": {**job_data, "outputs": {"artifacts": {"path": "./output.txt"}}}
        }
        updated_job['outputs'] = {"artifacts": {"path": "./output.txt"}}

    # Add `needs` recommendation
    if 'needs' not in updated_job:
        recommendations[f'{job_id}_needs'] = {
            "recommendation": "Add dependencies between jobs if needed.",
            "status": "missing",
            "original": job_data,
            "updated": {**job_data, "needs": ["job1", "job2"]}
        }
        updated_job['needs'] = ["job1", "job2"]

    return recommendations, updated_job

def analyze_yml_file(yml_path, target_script_path, strace_path):
    """Analyze the YAML file and apply recommendations."""
    recommendations = {}
    updated_yml = CommentedMap()

    try:
        yaml = YAML(typ='rt')
        with open(yml_path, 'r') as file:
            yml_content = yaml.load(file)

        is_valid, message = is_valid_github_actions_yml(yml_content)
        recommendations['validation'] = {
            "status": "valid" if is_valid else "invalid",
            "message": message
        }
        if not is_valid:
            return recommendations, updated_yml

        script_paths = analyze_script_for_paths(target_script_path)
        yml_chunks = split_yml_into_chunks(yml_content)
        updated_yml['name'] = yml_chunks['name']
        updated_yml['on'] = yml_chunks['on']
        updated_yml['jobs'] = CommentedMap()

        for job_id, job_data in yml_chunks['jobs'].items():
            job_recommendations, updated_job = apply_recommendations(
                job_id, job_data, script_paths, strace_path
            )
            recommendations[job_id] = job_recommendations
            updated_yml['jobs'][job_id] = updated_job

    except Exception as e:
        recommendations['error'] = str(e)

    return recommendations, updated_yml

def main():
    parser = argparse.ArgumentParser(description="Analyze GitHub Actions YAML file and provide recommendations.")
    parser.add_argument('--yml', type=str, help='Path to the YAML workflow file.')
    parser.add_argument('--target', type=str, help='Path to the target script.', required=True)
    parser.add_argument('--strace', type=str, help='Path to the strace log.', required=False)

    args = parser.parse_args()
    recommendations, updated_yml = analyze_yml_file(args.yml, args.target, args.strace)

    print("Recommendations:")
    print(json.dumps(recommendations, indent=4))

    with open('recommendations_output.json', 'w') as json_file:
        json.dump(recommendations, json_file, indent=4)

    with open('updated_workflow.yml', 'w') as yml_file:
        yaml = YAML()
        yaml.dump(updated_yml, yml_file)

if __name__ == "__main__":
    main()
