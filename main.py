import argparse
from tracing import Tracing
from yamlci import YamlCI


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', dest='target', type=str, help='path to target bash script to be traced', default='target.sh')
    parser.add_argument('--requirement', dest='requirement', type=str, help='path to, or for, a pip requirements file', default='requirement.txt')
    parser.add_argument('--template', dest='template', type=str, help='path to a workflow configuration template', default='dependencies.yaml')
    parser.add_argument('--workflow', dest='workflow', type=str, help='path to, or for, a workflow configuration', default='workflow.yaml')
    parser.add_argument('--workflow_name', dest='workflow_name', type=str, help='name for a new workflow configuration', default='workflow')
    parser.add_argument('--new_trace', dest='new_trace', type=bool, help='whether the target should be traced again', default=False)
    parser.add_argument('--dockerfile', dest='dockerfile', type=str, help='path to a dockerfile', default='Dockerfile')
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
    with open('requirements.txt', 'w') as file:
        file.write('\n'.join(requirements))
    scripts = dict()

    # Parse scripts from system trace
    scripts['pytest'] = tracing.parse_script('pytest')
    scripts['docker'] = {'exec': []}
    for parse in tracing.parse_script("docker"):
        if 'exec' in parse:
            scripts['docker']['exec'].append(parse)

    scripts['docker']['img'] = ''
    if len(scripts['docker']['exec']) != 0:
        with open(args.dockerfile, 'r') as file:
            dockerfile = file.readlines()
            for line in dockerfile:
                if line.startswith('FROM'):
                    scripts['docker']['img'] = line[5:]

    # Build CI/CD .yaml config from system tace information
    ciyaml = YamlCI()
    ciyaml.set_workflow_name(args.workflow_name)
    ciyaml.set_workflow_trigger_branches(['main'])
    ciyaml.set_jobs(versions, args.requirement, scripts)
    ciyaml.dump(f'{args.workflow_name}.yaml')


if __name__ == '__main__':
    main()