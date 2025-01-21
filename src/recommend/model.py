import copy
import json
import os
from pathlib import Path

from deepdiff import DeepDiff, Delta
from deepdiff.serialization import json_dumps, json_loads
from openai import OpenAI
import recommend.utils as utils


class ModelRecommendations():
    def __init__(self,
                 workflow_path: str,
                 output_dir: str,
                 schema_path: str,
                 api_key: str, 
                 model: str = 'gpt-4'):
        # Load and initialize workflow and its metadata
        self.workflow_path = workflow_path
        self.workflow = utils.load_workflow(self.workflow_path)
        self.workflow_name = Path(self.workflow_path).stem.split('.')[0]
        self.workflow_str = utils.workflow_to_str(self.workflow)
        
        # Load and initialize workflow validation schema
        self.schema_path = schema_path
        with open(self.schema_path, 'r') as schema_file:
            self.schema = json.load(schema_file)
        self.output_dir = output_dir

        # Initialize model client and its metadata
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(api_key=self.api_key)

    def apply(self, id: int = None, dump: bool = False) -> dict:
        """Apply one or all recommendations to a workflow"""
        workflow = copy.deepcopy(self.workflow)
        model_path = os.path.join(self.output_dir, f'{self.workflow_name}.model.recommendations')
        if os.path.isfile(model_path):
            delta = Delta(delta_path=model_path, deserializer=json_loads)
            edit_actions = self.__parse_recommendations(delta)
            if id is not None:
                workflow += Delta(edit_actions[id], serializer=json_dumps, always_include_values=True)
            else:
                for action in edit_actions:
                    workflow += Delta(action, serializer=json_dumps, always_include_values=True)
            if dump:
                workflow_path = os.path.join(self.output_dir, f'{self.workflow_name}.model.yaml')
                utils.dump_workflow(workflow, workflow_path)
        return workflow
    
    def recommendations(self, dump: bool = False) -> list:
        """Get all recommendations for a workflow"""
        recommendations = {}
        improved_workflow = self.__prompt() \
            .strip() \
            .replace('```', '') \
            .removeprefix('yaml') \
            .strip()

        # Find the differences between the old and new workflows
        if utils.validate_workflow(improved_workflow, self.schema):
            improved_workflow = utils.workflow_to_dict(improved_workflow)
            diff = DeepDiff(self.workflow, improved_workflow)
            delta = Delta(diff, serializer=json_dumps, always_include_values=True)
            recommendations = delta.to_dict()

        # Dump edit actions to a file
        if dump:
            model_path = os.path.join(self.output_dir, f'{self.workflow_name}.model.recommendations')
            with open(model_path, 'w') as file:
                delta.dump(file) if recommendations != {} else json.dump(recommendations)         
        return recommendations

    def __prompt(self) -> str:
        """Send messages to the model and receive a response"""
        response = self.client.chat.completions.create \
        (
            messages = self.__messages(),
            model = self.model,
            temperature = 0,
            n = 1
        )
        return response.choices[0].message.content
    
    def __parse_recommendations(self, delta: Delta) -> list:
        """Parse individual requirements from Delta"""
        edit_actions = []
        for group, actions in delta.to_dict().items():
            for name, action in actions.items():
                edit_actions.append({group: {name: action}})
        return edit_actions

    def __messages(self) -> list:
        """Get the messages that will be sent to the model"""
        return \
        [
            self.__system(),
            self.__user()
        ]
    
    def __system(self) -> dict:
        """Get a message that defines the context for the expected model behavior"""
        return \
        {
            'role': 'system',
            'content': (
                'You are a senior devops engineer. '
                'You are an expert in GitHub Actions workflows. '
                'Your job is to improve GitHub Actions workflows. '
                'Your GitHub Actions workflows must have valid syntax.'
            )
        }

    def __user(self) -> dict:
        """Get a message that defines the expected behavior of the model"""
        return \
        {
            'role': 'user',
            'content': (
                '# Workflow\n'
                f'{self.workflow_str}\n\n'
                '# Instructions\n'
                '- Improve the GitHub Actions Workflow.\n'
                '- Only output the improved GitHub Actions Workflow.\n'
                '- Do not explain the changes that were made.'
            )
        }
