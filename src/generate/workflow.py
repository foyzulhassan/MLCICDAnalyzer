from io import StringIO
import os
import re
import textwrap

import ruamel.yaml
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString


class Workflow:
    def __init__(self, 
                 workflow_name: str,
                 output_dir: str,
                 job_parses: dict,
                 has_requirements: bool = True):
        self.workflow_name = workflow_name.split('.')[0]
        self.output_dir = output_dir
        self.job_parses = job_parses
        self.has_requirements = has_requirements

        self.job_ids = list(job_parses.keys())
        self.yaml_parser = self.__yaml_parser()
        self.workflow_path = os.path.join(self.output_dir, f'{self.workflow_name}.base.yaml')
        self.yaml = {'name': self.workflow_name, 'on': 'push', 'jobs': {job_id: {} for job_id in self.job_ids}}
        
    def construct(self, dump: bool = False) -> str:
        """Contrust the workflow using parsed information from traces"""
        self.__runner()
        self.__matrix()
        self.__checkout()
        self.__packages()
        self.__script()
        # self.__service()
        if dump:
            self.dump()
        return self.dumps()

    # ======================================================================= #
    #                                    STEPS                                #
    # ======================================================================= #

    def __runner(self):
        """Specify the virtual machine that will be used to run the application"""
        for job_id in self.job_ids:
            job = self.yaml['jobs'][job_id]
            job.update({'runs-on': '${{ matrix.os }}'})

    def __matrix(self):
        """Define different job configurations using variables"""
        for job_id in self.job_ids:
            job = self.yaml['jobs'][job_id]
            python_versions = self.job_parses[job_id]['versions']
            job.update({'strategy': {'matrix': {'os': 'ubuntu-latest', 'python-version': python_versions}}})

    def __checkout(self):
        """Add checkout action to job configurations"""
        for job_id in self.job_ids:
            job = self.yaml['jobs'][job_id]
            job.update({'steps': [{'uses': 'actions/checkout@v4'}]})
    
    def __packages(self):
        """Add python dependency installation to job configurations"""
        for job_id in self.job_ids:
            commands = []
            action = 'astral-sh/setup-uv@v6' if re.match(r'\buv\b', self.job_parses[job_id]['script']) else 'actions/setup-python@v5'
            steps = self.yaml['jobs'][job_id]['steps']
            steps.append({'uses': action, 'with': {'python-version': '${{ matrix.python-version }}'}})

            if self.job_parses[job_id]['apt']:
                apt_str = ' '.join(self.job_parses[job_id]['apt'])
                commands.append(f'apt install -y {apt_str}')

            if self.has_requirements:
                commands.append('if [ -f requirements.txt ]; then pip install -r requirements.txt; fi')
            if self.job_parses[job_id]['pip']:
                pip_str = ' '.join(f'{module}=={version}' if version is not None else f'{module}' for module, version in self.job_parses[job_id]['pip'].items())
                commands.append(f'pip install {pip_str}')
            if commands:
                steps.append({'name': 'Install Dependencies', 'run': self.__multiline(commands)})

    def __script(self):
        """Add target script commands (without comments) to a job"""
        for job_id in self.job_ids:
            steps = self.yaml['jobs'][job_id]['steps']
            script = self.job_parses[job_id]['script']
            steps.append({'name': 'Execute Tests', 'run': self.__multiline(script.strip().split('\n'))})
    
    def __service(self):
        """Specify a service container that an existing job should be able to use"""
        for job_id in self.job_ids:
            job = self.yaml['jobs'][job_id]
            services = self.job_parses[job_id]['services']
            if services:
                job.update({'services': {service['name']: {'image': service['image'], 'ports': service['ports']} for service in services}})

    # ======================================================================= #
    #                                   UTILITY                               #
    # ======================================================================= #

    def dump(self):
        """Dump the workflow, as it has been built, to a file"""
        with open(self.workflow_path, 'w') as file:
            self.yaml_parser.dump(data=self.yaml, stream=file)
    
    def dumps(self) -> str:
        """Dump the workflow, as it has been built, to a string"""
        workflow_stream = StringIO()
        self.yaml_parser.dump(self.yaml, workflow_stream)
        workflow_str = workflow_stream.getvalue()
        workflow_stream.close()
        return workflow_str

    def __multiline(self, strings: list[str]) -> str:
        """Retrieve multiline string that will be rendered properly"""
        newline_strings = '\n'.join(strings) + '\n'
        return LiteralScalarString(textwrap.dedent(f"""{newline_strings}"""))

    def __str__(self) -> str:
        """Get string representation of the workflow"""
        workflow_stream = StringIO()
        self.yaml_parser.dump(self.yaml, workflow_stream)
        workflow_str = workflow_stream.getvalue()
        workflow_stream.close()
        return workflow_str

    def __yaml_parser(self) -> YAML:
        """Get pre-configured yaml parser"""
        ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True
        yaml_parser = YAML(pure=True)
        yaml_parser.indent(sequence=4, offset=2)
        yaml_parser.sort_base_mapping_type_on_output = False
        yaml_parser.default_style = None
        yaml_parser.width = 100
        yaml_parser.ignore_aliases = lambda *args : True
        return yaml_parser
