import argparse
from tracing import Tracing
from yamlci import YamlCI


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', dest='target', type=str, help='path to target bash script to be traced', default='target.sh')
    parser.add_argument('--requirement', dest='requirement', type=str, help='path to, or for, a pip requirements file', default='requirement.txt')
    parser.add_argument('--template', dest='template', type=str, help='path to a workflow configuration template', default='dependencies.yaml')
    parser.add_argument('--workflow', dest='workflow', type=str, help='path to, or for, a workflow configuration', default='workflow.yaml')
    parser.add_argument('--workflow_name', dest='workflow_name', type=str, help='name for a new workflow configuration', default='Workflow')
    parser.add_argument('--new_trace', dest='new_trace', type=bool, help='whether the target should be traced again', default=False)
    return parser.parse_args()


def main():
    # Parse runtime arguments
    args = parse_args()

    # System trace a target program
    tracing = Tracing(new_trace=args.new_trace,
                      trace_log='trace.log',
                      paths_log='paths.log',
                      target=args.target)
    
    # Parse information from system trace
    versions = tracing.parse_versions()
    requirements = tracing.parse_requirements()
    scripts = tracing.parse_script("pytest")

    # Build CI/CD .yaml config from system tace information
    ciyaml = YamlCI()
    ciyaml.set_workflow_name(args.workflow_name)
    ciyaml.set_workflow_trigger_branches(['main'])
    ciyaml.set_jobs(versions, args.requirement, scripts)
    ciyaml.dump(f'{args.workflow_name}.yaml')


if __name__ == '__main__':
    main()