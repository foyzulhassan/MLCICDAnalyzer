import copy
import json
import os
from pathlib import Path

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

    def apply(self, dump: bool = False) -> dict:
        """Apply one or all recommendations to a workflow"""
        pass
    
    def recommendations(self, dump: bool = False) -> list:
        """Get all recommendations for a workflow"""
        recommendations = {}
        improved_workflow = self.__prompt() \
            .strip() \
            .replace('```', '') \
            .removeprefix('yaml') \
            .strip()
        pass

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
    
    def __parse_recommendations(self) -> list:
        """Parse individual requirements from Delta"""
        pass

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
                'Your job is to create and improve GitHub Actions workflows. '
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
                '# Background Knowledge\n'
                f'{self.__knowledge()}\n\n'
                '# Instructions\n'
                '- Improve the GitHub Actions Workflow.\n'
                '- Reflect on the Background Knowledge before making improvements.\n'
                '- Only output the improved GitHub Actions Workflow.\n'
                '- Do not explain the changes that were made.'
            )
        }
