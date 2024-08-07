from tracing import Tracing
import ruamel.yaml
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString
import textwrap

# Class that builds .yaml files for CI/CD environments
class YamlCI:
    def __init__(self, tracings: list[Tracing], name='Workflow'):
        self.yaml = {'name': name, 'on': 'push', 'jobs': {}}
        for tracing in tracings:
            self.construct(tracing, tracing.target)

    # Specify the virtual machine that will be used to run the application
    def add_runner(self, job_id: str, runner: str):
        job = self.yaml['jobs'][job_id]
        job.update({'runs-on': runner})

    # Define different job configurations using variables
    def add_matrix(self, job_id: str, variables: dict[str, str]):
        job = self.yaml['jobs'][job_id]
        job.update({'strategy': {'matrix': variables}})

    # Specify container in which steps in a job should run
    def add_container(self, job_id: str, image: str, ports: list[str]):
        job = self.yaml['jobs'][job_id]
        job.update({'container': {'image': image, 'ports': ports}})

    # Add job steps to an existing job
    def add_step(self, job_id: str, name: str, run: list[str], has_py: bool = False, has_req_log: bool = False, requirements: dict[str, str] = []):
        job = self.yaml['jobs'][job_id]
        if 'steps' not in job:
            job.update({'steps': [{'uses': 'actions/checkout@v4'}]})

        dependency_run = []
        if has_py:
            job['steps'].append({'uses': 'actions/setup-python@v5', 'with': {'python-version': '${{ matrix.python-version }}', 'cache': 'pip'}})
            dependency_run.append('python -m pip install --upgrade pip wheel setuptools')
            if has_req_log:
                dependency_run.append(f'pip install -r requirements.txt')
            if len(requirements) > 0:
                requirements_str = ' '.join([f'{module}=={version}' for module, version in requirements.items()])
                dependency_run.append(f'pip install -I {requirements_str}')
        if len(dependency_run) > 0:
            job['steps'].append({'name': 'Install Python Dependencies', 'run': self.get_multiline_str(dependency_run)})
        job['steps'].append({'name': name, 'run': self.get_multiline_str(run)})

    # Specify a service container that an existing job should be able to use
    def add_service(self, job_id: str, name: str, image: str, ports: list[str]):
        job = self.yaml['jobs'][job_id]
        if 'services' not in job:
            job.update({'services': {}})
        if name not in job['services']:
            job['services'].update({name: {'image': image, 'ports': ports}})
        else:
            job['services'][name]['ports'].extend(ports)
    
    # Contrust the yaml file using trace information
    def construct(self, tracing: Tracing, job_id='job'):
        if job_id not in self.yaml['jobs']:
            self.yaml['jobs'].update({job_id: {}})
        self.add_runner(job_id, 'ubuntu-latest')
        if len(tracing.versions) != 0:
            self.add_matrix(job_id, {'python-version': tracing.versions})
        if tracing.job_container['image'] is not None:
            self.add_container(job_id, tracing.job_container['image'], tracing.job_container['ports'])
        if len(tracing.scripts) != 0:
            has_py = len(tracing.versions) != 0
            has_req_log = tracing.requirements_log is not None
            for i in range(len(tracing.scripts)):
                for container in tracing.service_containers:
                    if container['id'] in tracing.scripts[i]:
                        tracing.scripts[i] = tracing.scripts[i].replace(container['id'], container['name'])
                        break
            self.add_step(job_id, 'Execute Test Scripts', tracing.scripts, has_py, has_req_log, tracing.requirements)
        for container in tracing.service_containers:
            self.add_service(job_id, container['name'], container['image'], container['ports'])

    # Dump the yaml file, as it has been built, to a file
    def dump(self, path: str):
        with open(path, 'w') as file:
            ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True
            yaml = YAML()
            yaml.indent(sequence=4, offset=2)
            yaml.sort_base_mapping_type_on_output = False
            yaml.default_style = None
            yaml.width = 100
            yaml.ignore_aliases = lambda *args : True
            yaml.dump(data=self.yaml, stream=file)
    
    # Retrieve multiline string that will be rendered properly
    def get_multiline_str(self, strs: list[str]):
        newline_strs = '\n'.join(strs) + '\n'
        return LiteralScalarString(textwrap.dedent(f"""{newline_strs}"""))