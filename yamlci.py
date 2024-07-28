from tracing import Tracing
import ruamel.yaml
from ruamel.yaml import YAML
from pathlib import Path

# Class that builds .yaml files for CI/CD environments
class YamlCI:
    def __init__(self, tracing: Tracing, name='Workflow'):
        self.yaml = {'name': name, 'on': 'push', 'jobs': {}}
        self.tracing = tracing
        self.construct()

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
    def add_step(self, job_id: str, name: str, run: list[str], has_py: bool = False):
        job = self.yaml['jobs'][job_id]
        if 'steps' not in job:
            job.update({'steps': [{'uses': 'actions/checkout@v4'}]})
        basic_dep = ['python -m pip install --upgrade pip wheel setuptools'] if has_py else []
        run_str = '; '.join(basic_dep + [' '.join(exps) for exps in run])
        job['steps'].append({'name': name, 'run': run_str})

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
    def construct(self):
        job_id = "job"
        if job_id not in self.yaml['jobs']:
            self.yaml['jobs'].update({job_id: {}})
        self.add_runner(job_id, 'ubuntu-latest')
        if len(self.tracing.versions) != 0:
            self.add_matrix(job_id, {'python-version': self.tracing.versions})
        if self.tracing.job_container['image'] is not None:
            self.add_container(job_id, self.tracing.job_container['image'], self.tracing.job_container['ports'])
        if len(self.tracing.scripts) != 0:
            has_py = len(self.tracing.versions) != 0
            self.add_step(job_id, 'Execute Test Scripts', self.tracing.scripts, has_py)
        for container in self.tracing.service_containers:
            name = container['image'] if ':' not in container['image'] else container['image'].split(':')[0]
            self.add_service(job_id, name, container['image'], container['ports'])

    # Dump the yaml file, as it has been built, to a file
    def dump(self, path: str):
        with open(path, 'w') as file:
            yaml = YAML(typ='full', pure=True)
            yaml.default_flow_style = False
            yaml.indent(sequence=4, offset=2)
            yaml.sort_base_mapping_type_on_output = False
            yaml.default_style = None
            yaml.width = 100
            yaml.ignore_aliases = lambda *args : True
            yaml.dump(data=self.yaml,
                      stream=file)
            
        # Remove aliases from yaml
        file = Path(path)  
        ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True
        yaml = YAML(pure=True)
        data = yaml.load(file)
        yaml.dump(data, file)