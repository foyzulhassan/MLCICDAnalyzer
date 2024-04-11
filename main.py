import sys
import site
import platform
import subprocess
import importlib
import importlib.metadata
import argparse


# Trace paths that appear in system calls during the target bash script to be traced's runtime
def trace_paths(target):
    command = f"strace -fy -ttt -qqq -s 4096 -e trace=%file bash {target} 2>&1" + "| awk -F'\"' '{print $2}' | grep -v '^\s*$'"
    paths = str(subprocess.run(command, shell=True, capture_output=True).stdout, 'UTF-8').splitlines()
    command = f"strace -fy -ttt -qqq -s 4096 -e trace=%file bash {target} 2>&1" + "| awk -F'[<>]' '{print $2}' | grep -v '^\s*$'"
    paths += str(subprocess.run(command, shell=True, capture_output=True).stdout, 'UTF-8').strip().splitlines()
    return list(set(paths))


# Parse the module candidates found in the python package paths
def parse_modules(paths):
    module_paths = sys.path + [site.USER_BASE] + [site.USER_SITE]
    modules = []
    for path in paths:
        for module_path in module_paths:
            if module_path in path:
                try:
                    new_path = path.replace(module_path, '').split('/')[1].split('.')[0]
                except:
                    new_path = path.replace(module_path, '').split('/')[0].split('.')[0]
                if new_path != '':
                    modules.append(new_path)
                break
    modules = list(set(modules))
    return modules


# Select module candidates that are third-party python modules
def parse_requirements(modules):
    requirements = []
    for module in modules:
        try:
            # Third-Party Python Modules
            module_name = importlib.import_module(module).__name__
            module_version = importlib.metadata.version(module_name)
            requirements.append(f'{module_name}=={module_version}')
        except importlib.metadata.PackageNotFoundError:
            # Built-In Python Modules
            pass
        except ModuleNotFoundError:
            # Files that are not Python Modules
            pass
    requirements.sort()
    return requirements


 # Write requirements, or selected module candidates, to the requirements file
def write_requirements(requirements, requirements_file="requirements.txt"):
    with open(requirements_file, "w") as file:
        file.writelines([f'{requirement}\n' for requirement in requirements])


# Read a workflow configuration template, fill in its empty fields, and write it to workflow file
def fill_template(template_file, workflow_file, workflow_name, python_version, requirements_file):
    with open(template_file, "r") as file:
        yaml = file.read()
    yaml = yaml.format(workflow_name, python_version, requirements_file)

    with open(workflow_file, "w") as file:
        file.write(yaml)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', dest='target', type=str, help='path to target bash script to be traced', default='target.sh')
    parser.add_argument('--requirement', dest='requirement', type=str, help='path to, or for, a pip requirements file', default='requirement.txt')
    parser.add_argument('--template', dest='template', type=str, help='path to a workflow configuration template', default='dependencies.yaml')
    parser.add_argument('--workflow', dest='workflow', type=str, help='path to, or for, a workflow configuration', default='workflow.yaml')
    parser.add_argument('--workflow_name', dest='workflow_name', type=str, help='name for a new workflow configuration', default='Workflow')
    return parser.parse_args()


def main():
    PYTHON_VERSION = platform.python_version()
    args = parse_args()
    paths = trace_paths(target=args.target)
    modules = parse_modules(paths=paths)
    requirements = parse_requirements(modules=modules)
    write_requirements(requirements=requirements, 
                       requirements_file=args.requirement)
    fill_template(workflow_name=args.workflow_name, 
                  python_version=PYTHON_VERSION, 
                  template_file=args.template, 
                  workflow_file=args.workflow,
                  requirements_file=args.requirement)


if __name__ == '__main__':
    main()