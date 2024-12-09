from flask import Flask, request, jsonify
from reciapsci.environment_rec_api import EnvironmentRecommendationAPI
# from reciapsci.output_rec_api import OutputRecommendationAPI
from reciapsci.parse_yaml_api import validate_yaml
from reciapsci.working_directory_rec_api import WorkingDirectoryRecommendation
from reciapsci.permissions_rec_api import PermissionsRecommendation
from reciapsci.outputs_rec_api import OutputsRecommendation
from reciapsci.needs_rec_api import NeedsRecommendation
from reciapsci.timeout_rec_api import TimeoutRecommendation
from reciapsci.docker_rec_api import DockerRecommendation

app = Flask(__name__)


@app.route('/validate_yaml', methods=['POST'])
def validate_yaml_endpoint():
    """
    Endpoint to validate a YAML file.
    Input: JSON with the 'yaml_file' path.
    """
    data = request.json
    yaml_file = data.get('yaml_file')

    if not yaml_file:
        return jsonify({"error": "yaml_file is required"}), 400

    is_valid = validate_yaml(yaml_file)
    return jsonify({"valid": is_valid})


@app.route('/recommend_environment', methods=['POST'])
def recommend_environment():
    """
    Endpoint to generate environment variable recommendations.
    Input: JSON with 'yaml_file', 'code_dir', and 'strace_file'.
    """
    data = request.json
    yaml_file = data.get('yaml_file')
    code_dir = data.get('code_dir')
    strace_file = data.get('strace_file')

    if not yaml_file or not code_dir or not strace_file:
        return jsonify({"error": "yaml_file, code_dir, and strace_file are required"}), 400

    env_rec = EnvironmentRecommendationAPI(yaml_file)

    if not env_rec.load_yaml():
        return jsonify({"error": "Invalid YAML file"}), 400

    env_rec.generate_recommendations(code_dir, strace_file)
    recommendations = env_rec.output_recommendations(return_as_dict=True)
    return jsonify({"recommendations": recommendations})

@app.route('/recommend_outputs', methods=['POST'])
def recommend_outputs():
    data = request.json
    yaml_file = data.get("yaml_file")
    strace_file = data.get("strace_file")
    target_scripts_dir = data.get("target_scripts_dir")

    if not yaml_file or not strace_file or not target_scripts_dir:
        return jsonify({"error": "All 'yaml_file', 'strace_file', and 'target_scripts_dir' are required."}), 400

    outputs_rec = OutputsRecommendation(yaml_file, strace_file, target_scripts_dir)
    result = outputs_rec.generate_recommendation()

    return jsonify(result)

# @app.route('/recommend_outputs', methods=['POST'])
# def recommend_outputs():
#     """
#     Endpoint to generate output recommendations.
#     Input: JSON with 'yaml_file', 'code_dir', and 'strace_file'.
#     """
#     data = request.json
#     yaml_file = data.get('yaml_file')
#     code_dir = data.get('code_dir')
#     strace_file = data.get('strace_file')

#     if not yaml_file or not code_dir or not strace_file:
#         return jsonify({"error": "yaml_file, code_dir, and strace_file are required"}), 400

#     output_rec = OutputRecommendationAPI(yaml_file)

#     if not output_rec.load_yaml():
#         return jsonify({"error": "Invalid YAML file"}), 400

#     output_rec.generate_recommendations(strace_file, code_dir)
#     recommendations = output_rec.output_recommendations(return_as_dict=True)
#     return jsonify({"recommendations": recommendations})


@app.route('/recommend_working_directory', methods=['POST'])
def recommend_working_directory():
    data = request.json
    yaml_file = data.get("yaml_file")
    target_scripts_dir = data.get("target_scripts_dir")

    if not yaml_file or not target_scripts_dir:
        return jsonify({"error": "Both 'yaml_file' and 'target_scripts_dir' are required."}), 400

    wd_rec = WorkingDirectoryRecommendation(yaml_file, target_scripts_dir)
    result = wd_rec.generate_recommendation()

    return jsonify(result)

@app.route('/recommend_permissions', methods=['POST'])
def recommend_permissions():
    data = request.json
    yaml_file = data.get("yaml_file")
    strace_file = data.get("strace_file")
    target_scripts_dir = data.get("target_scripts_dir")

    if not yaml_file or not strace_file or not target_scripts_dir:
        return jsonify({"error": "All 'yaml_file', 'strace_file', and 'target_scripts_dir' are required."}), 400

    perm_rec = PermissionsRecommendation(yaml_file, strace_file, target_scripts_dir)
    result = perm_rec.generate_recommendation()

    return jsonify(result)

@app.route('/recommend_needs', methods=['POST'])
def recommend_needs():
    data = request.json
    yaml_file = data.get("yaml_file")
    strace_file = data.get("strace_file")

    if not yaml_file or not strace_file:
        return jsonify({"error": "Both 'yaml_file' and 'strace_file' are required."}), 400

    needs_rec = NeedsRecommendation(yaml_file, strace_file)
    result = needs_rec.generate_recommendation()

    return jsonify(result)

@app.route('/recommend_timeout', methods=['POST'])
def recommend_timeout():
    data = request.json
    yaml_file = data.get("yaml_file")
    strace_file = data.get("strace_file")
    code_dir = data.get("code_dir")

    if not yaml_file or not strace_file or not code_dir:
        return jsonify({"error": "All 'yaml_file', 'strace_file', and 'code_dir' are required."}), 400

    timeout_rec = TimeoutRecommendation(yaml_file, strace_file, code_dir)
    result = timeout_rec.generate_recommendation()

    return jsonify(result)

@app.route('/recommend_docker', methods=['POST'])
def recommend_docker():
    data = request.json
    yaml_file = data.get('yaml_file')
    strace_file = data.get('strace_file')
    code_dir = data.get('code_dir')

    if not yaml_file or not strace_file or not code_dir:
        return jsonify({"error": "yaml_file, strace_file, and code_dir are required"}), 400

    docker_rec = DockerRecommendation(yaml_file, strace_file, code_dir)
    result = docker_rec.generate_recommendation()
    return jsonify(result)


if __name__ == '__main__':
    app.run(debug=True)
