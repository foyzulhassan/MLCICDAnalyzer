import argparse
import os
from tracing import Tracing
from yamlci import YamlCI
from improve_ci_with_llm import ImproveCIWithLLM

def parse_args():
    parser = argparse.ArgumentParser(description="Generate and improve CI YAML for a machine learning project.")
    parser.add_argument('--target', dest='targets', type=str,
                        help='path to a directory of target bash scripts or a comma-separated list of scripts', required=True)
    parser.add_argument('--host_container', dest='host_container', type=str,
                        help='id of the container that the target is running in', default=None)
    parser.add_argument('--requirements', dest='requirements_log', type=str,
                        help='path to a pip requirements file', required=True)
    parser.add_argument('--workflow', dest='workflow', type=str,
                        help='path to save the workflow configuration YAML', required=True)
    parser.add_argument('--trace_log', dest='trace_log', type=str,
                        help='path to, or for, a trace log', default='trace.log')
    parser.add_argument('--paths_log', dest='paths_log', type=str,
                        help='path to, or for, a path log', default='paths.log')
    parser.add_argument('--docker_log', dest='docker_log', type=str,
                        help='path to a log listing the docker containers on the machine', default='docker.log')
    parser.add_argument('--workflow_name', dest='workflow_name', type=str,
                        help='name for the workflow configuration', default='Workflow')
    parser.add_argument('--new_trace', dest='new_trace', help='whether the target should be traced again', action='store_true')
    parser.add_argument('--keep_log', dest='keep_log', help='whether trace logs should be preserved', action='store_true')
    parser.add_argument('--project_description', dest='project_description', type=str,
                        help='path to a project description file', required=True)
    parser.add_argument('--ci_instructions', dest='ci_instructions', type=str,
                        help='path to a file containing instructions to be performed on the CI script', required=True)
    parser.add_argument('--prompt_file', dest='prompt_file', type=str,
                        help='path to the prompt file with placeholders', required=True)
    parser.add_argument('--api_key', dest='api_key', type=str, help='OpenAI API key for LLM interaction', required=True)
    return parser.parse_args()

def main():
    args = parse_args()

    # Parse target scripts
    target_scripts = []
    if os.path.isdir(args.targets):
        target_scripts = [os.path.join(args.targets, script) for script in os.listdir(args.targets) if script.endswith('.sh')]
    else:
        target_scripts = args.targets.split(',')

    # Ensure output directory exists
    output_dir = os.path.dirname(args.workflow)
    os.makedirs(output_dir, exist_ok=True)

    # Generate initial CI YAML from all target scripts
    tracings = []
    for i, target in enumerate(target_scripts):
        tracings.append(Tracing(
            target=target.strip(),
            new_trace=args.new_trace,
            host_container=args.host_container,
            trace_log=args.trace_log,
            paths_log=args.paths_log,
            docker_log=args.docker_log,
            requirements_log=args.requirements_log
        ))
        if args.keep_log:
            os.renames(args.trace_log, f'logs/{i}_{os.path.basename(target.strip()).replace(".sh", ".log")}')

    ciyaml = YamlCI(tracings)
    tool_generated_yaml_path = os.path.join(output_dir, f"tool_generated_{args.workflow_name}.yaml")
    ciyaml.dump(tool_generated_yaml_path)

    print(f"Tool-generated CI YAML has been saved to {tool_generated_yaml_path}")

    # Improve CI YAML using the LLM
    llm = ImproveCIWithLLM(api_key=args.api_key)
    ciyaml_improved_by_llm = llm.improve_ci(
        requirements=args.requirements_log,
        generated_yaml=tool_generated_yaml_path,
        project_description=args.project_description,
        ci_instructions=args.ci_instructions,
        prompt_file=args.prompt_file
    )

    # Save the improved CI YAML
    llm_improved_yaml_path = os.path.join(output_dir, f"llm_improved_{args.workflow_name}.yaml")
    with open(llm_improved_yaml_path, 'w') as file:
        file.write(ciyaml_improved_by_llm)

    print(f"LLM-improved CI YAML has been saved to {llm_improved_yaml_path}")

if __name__ == '__main__':
    main()

#  python3 main.py \
#   --target /home/rchavan/ci_tool/test-projects/yolov5-scripts/targets \
#   --requirements /home/rchavan/ci_tool/test-projects/yolov5/requirements.txt \
#   --workflow /home/rchavan/ci_tool/test-projects/yolov5-scripts/generations/workflow.yaml \
#   --project_description /home/rchavan/ci_tool/test-projects/yolov5-scripts/project_description.txt \
#   --ci_instructions /home/rchavan/ci_tool/test-projects/yolov5-scripts/instructions.txt \
#   --prompt_file /home/rchavan/ci_tool/test-projects/yolov5-scripts/prompt.txt \
#   --workflow_name workflow \
#   --api_key <apikey> \
#   --new_trace
