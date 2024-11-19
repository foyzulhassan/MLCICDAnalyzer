# import argparse
# from tracing import Tracing
# from yamlci import YamlCI
# from improve_ci_with_llm import ImproveCIWithLLM
# import os

# def parse_args():
#     parser = argparse.ArgumentParser()
#     parser.add_argument('--target', dest='target', type=str, help='path to target bash script, or directory of scripts, to be traced', default='target.sh')
#     parser.add_argument('--host_container', dest='host_container', type=str, help='id of the container that the target is running in', default=None)
#     parser.add_argument('--requirements', dest='requirements_log', type=str, help='path to a pip requirements file', default='requirements.txt')
#     parser.add_argument('--workflow', dest='workflow', type=str, help='path to, or for, a workflow configuration', default='workflow.yaml')
#     parser.add_argument('--trace_log', dest='trace_log', type=str, help='path to, or for, a trace log', default='trace.log')
#     parser.add_argument('--paths_log', dest='paths_log', type=str, help='path to, or for, a path log', default='paths.log')
#     parser.add_argument('--docker_log', dest='docker_log', type=str, help='path to a log listing the docker containers on the machine', default='docker.log')
#     parser.add_argument('--workflow_name', dest='workflow_name', type=str, help='name for a new workflow configuration', default='Workflow')
#     parser.add_argument('--new_trace', dest='new_trace', help='whether the target should be traced again', action='store_true')
#     parser.add_argument('--keep_log', dest='keep_log', help='whether trace logs should be preserved', action='store_true')
#     #llm generations
#     parser.add_argument('--project_description', dest='project_description', type=str, help='path to a project description file', required=True)
#     parser.add_argument('--api_key', dest='api_key', type=str, help='OpenAI API key for LLM interaction', required=True)

#     return parser.parse_args()


# def main():
#     args = parse_args()
#     targets = [f'{args.target}/{path}' for path in os.listdir(args.target) if os.path.isfile(os.path.abspath(f'{args.target}/{path}'))] if os.path.isdir(args.target) else [args.target]
#     targets.reverse()
#     tracings = []
#     for i, target in enumerate(targets):
#         tracings.append(Tracing(target=target,
#                         new_trace=args.new_trace,
#                         host_container=args.host_container,
#                         trace_log=args.trace_log,
#                         paths_log=args.paths_log,
#                         docker_log=args.docker_log,
#                         requirements_log=args.requirements_log))
#         if args.keep_log:
#             os.renames(args.trace_log, f'logs/{i}_{os.path.basename(target).replace(".sh", ".log")}')
#     ciyaml = YamlCI(tracings)
#     tool_generated_yaml_path = f"tool_generated_{args.workflow}"
#     ciyaml.dump(args.workflow)

#     # Improve CI YAML using the LLM
#     llm = ImproveCIWithLLM(api_key=args.api_key)
#     ciyaml_improved_by_llm = llm.improve_ci(
#         target=args.target,
#         requirements=args.requirements_log,
#         ciyaml_tool_generated=tool_generated_yaml_path,
#         project_description=args.project_description,
#         output_file=f"improved_{args.workflow}"
#     )

#     # Save the LLM-improved CI YAML to a file
#     llm_improved_yaml_path = f"llm_improved_{args.workflow}"
#     with open(llm_improved_yaml_path, 'w') as file:
#         file.write(ciyaml_improved_by_llm)

#     print(f"LLM-improved CI YAML has been saved to {llm_improved_yaml_path}")


# if __name__ == '__main__':
#     main()

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
                        help='path to a project description file or instructions', required=True)
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
    target=args.targets,
    requirements=args.requirements_log,
    generated_yaml=tool_generated_yaml_path, 
    project_description=args.project_description
)

    # Save the improved CI YAML
    llm_improved_yaml_path = os.path.join(output_dir, f"llm_improved_{args.workflow_name}.yaml")
    with open(llm_improved_yaml_path, 'w') as file:
        file.write(ciyaml_improved_by_llm)

    print(f"LLM-improved CI YAML has been saved to {llm_improved_yaml_path}")

if __name__ == '__main__':
    main()
