import glob
import json
import logging
import os
from pathlib import Path
import subprocess
import time
import uuid

from openai import OpenAI
from openai.types import CreateEmbeddingResponse
from openai.types.chat import ChatCompletion
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.models import Distance, FieldCondition, Filter, MatchValue, ScoredPoint, VectorParams

import recommend.utils as utils


class HybridRecommendations:
    def __init__(
        self, 
        project_name: str,
        workflow_path: str,
        requirements_path: str,
        target_paths: list[str],
        assemble_prompt_path: str,
        job_prompt_path: str,
        output_dir: str,
        chat_model: str,
        chat_api_key: str,
        embedding_hostname: str,
        embedding_port: str,
        embedding_model: str,
        embedding_api_key: str,
        collection_name: str = 'sawra',
        max_chunks: int = 50,
        point_threshold: float = 0.60,
        max_attempts: int = 5,
    ) -> None:
        # Load and initialize a workflow and its metadata
        self.workflow_path = workflow_path
        self.workflow_name = Path(self.workflow_path).stem.split('.')[0]
        self.workflow = utils.load_workflow(self.workflow_path)
        self.workflow_str = utils.workflow_to_str(self.workflow)
        self.project_name = project_name
        self.target_paths = target_paths
        self.output_dir = output_dir
        self.scripts = self.__get_scripts()

        # Load the requirements file
        self.requirements_path = requirements_path
        with open(self.requirements_path, 'r') as file:
            self.requirements = file.read().strip().split('\n')

        # Initialize a chat model client and its metadata
        self.chat_model = chat_model
        self.client = OpenAI(api_key=chat_api_key)
        self.max_attempts = max_attempts
        
        # Initialize an embedding model client and its metadata
        self.embedding_model = embedding_model
        self.qdrant = QdrantClient(host=embedding_hostname, port=embedding_port, api_key=embedding_api_key, https=False)
        self.collection_name = collection_name
        self.version = 'hybrid'
        self.chunk_field = 'chunk_content'
        self.max_chunks = max_chunks
        self.point_threshold = point_threshold

        # Load job prompt
        self.job_prompt_path = job_prompt_path
        with open(self.job_prompt_path, 'r') as file:
            self.job_prompt = file.read().strip()

        # Load assemble prompt
        self.assemble_prompt_path = assemble_prompt_path
        with open(self.assemble_prompt_path, 'r') as file:
            self.assemble_prompt = file.read().strip()

        # Initialize miscellaneous paths
        self.output_dir = output_dir

    def __log_duration(func):
        """Decorator that logs the duration of the decorated function"""
        def wrapper(self, *args, **kwargs):
            # Calculate the duration of the caller
            start_time = time.time()
            result = func(self, *args, **kwargs) 
            end_time = time.time()
            duration = end_time - start_time

            # Get the qualified name of the caller
            filename = os.path.basename(__file__)
            classname = 'HybridRecommendations'
            qualname = f'{filename}.{classname}.{func.__name__}'

            # Log the qualname and duration of the decorated function
            message = f'"{qualname}","{start_time}","{end_time}","{duration}"'
            logging.getLogger('duration').info(message)
            return result
        return wrapper

    @__log_duration
    def apply(self) -> dict:
        """Apply model recommendations to a workflow"""

        # Get the blocks for each job (i.e. target script)
        job_blocks = []
        for script in self.scripts:
            job_name = Path(script['filename']).stem
            
            # Get the inputs and dump it
            job_input = self.__get_job_inputs(script=script, job_name=job_name)
            job_input_path = os.path.join(self.output_dir, f'{job_name}.job.hybrid.yaml')
            with open(job_input_path, 'w') as file:
                json.dump(job_input, file, indent=2)

            # Generate job blocks, or workflows for each job.
            job_block = self.__prompt(prompt=self.job_prompt, input=job_input)
            job_path = os.path.join(self.output_dir, f'{job_name}.job.hybrid.yaml')
            with open(job_path, 'w') as file:
                file.write(job_block)
            job_blocks.append(job_block)

        # Build the input for job block assembly
        assemble_input = \
        {
            'base_workflow': self.workflow,
            'bash_scripts': self.scripts,
            'python_requirements': self.requirements,
            'job_blocks': job_blocks,
            'actionlint_errors': [],
        }

        # Attempt to assemble the workflow blocks multiple times
        assembled_workflow = ''
        for _ in range(self.max_attempts):
            # Sanitize and dump the assembled workflow
            assembled_workflow = self.__prompt(prompt=self.assemble_prompt, input=assemble_input)
            assembled_workflow = utils.sanitize_workflow(assembled_workflow)
            assembled_path = os.path.join(self.output_dir, f'{self.workflow_name}.hybrid.yaml')
            with open(assembled_path, 'w') as file:
                file.write(assembled_workflow)

            # Add the lint errors to the input for the next iteration (if any)
            actionlint_error = self.__check_actionlint(assembled_path)
            if actionlint_error is not None:
                assemble_input['actionlint_errors'].append(actionlint_error)
            else:
                break
        return assembled_workflow

    @__log_duration
    def __get_job_inputs(self, script: dict[str, str], job_name: str) -> dict[str, str]:
        """Get the job input data that will be passed to the model"""

        # Get the embedding for the target script
        content = '\n'.join(script['content'])
        embedding = self.__get_embeddings(content)

        # Get the runtime chunks for a runtime script
        runtime_chunks = {}
        for chunk_type in ['apt', 'env', 'paths', 'pip', 'python_versions']:
            points = self.__get_top_chunks(project_name=self.project_name, job_name=job_name, chunk_type=chunk_type, embedding=embedding)
            filtered_points = [point for point in points if point.score >= self.point_threshold]
            if filtered_points:
                runtime_chunks[f"{job_name}.{chunk_type}"] = [point.payload[self.chunk_field] for point in filtered_points]

        # Build the input and return it
        return \
        {
            'bash_script': script, 
            'python_requirements': self.requirements, 
            'runtime_chunks': runtime_chunks,
        }
    
    @__log_duration
    def __get_top_chunks(self, project_name: str, job_name: str, chunk_type: str, embedding: list[float]) -> list[ScoredPoint]:
        """Fetch the top chunks within a qdrant"""
        return self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=embedding,
            query_filter=Filter(must=[
                FieldCondition(key='project_name', match=MatchValue(value=project_name)),
                FieldCondition(key='job_name', match=MatchValue(value=job_name)),
                FieldCondition(key='chunk_type', match=MatchValue(value=chunk_type))
            ]),
            limit=self.max_chunks,
            with_payload=True)

    @__log_duration
    def __prompt(self, prompt: str, input: dict) -> str:
        """Prompt the LLM and pass it input data"""
        response = self.client.chat.completions.create(
            model=self.chat_model,
            temperature=0,
            messages=[
                {'role': 'system', 'content': prompt},
                {'role': 'user', 'content': json.dumps(input, indent=2)},
            ])
        self.__log_costs('__prompt', response)
        return response.choices[0].message.content
    
    @__log_duration
    def __get_embeddings(self, text: str | list[str]) -> list[float]:
        """Get the vector embedding of text"""
        input = [text] if isinstance(text, str) else text
        response = self.client.embeddings.create(input=input, model=self.embedding_model)
        self.__log_costs('__get_embeddings', response)
        return response.data[0].embedding

    @__log_duration
    def __check_actionlint(self, workflow_path: str) -> str | None:
        """Determine whether a workflow is valid using actionlint"""
        result = subprocess.run(['actionlint', workflow_path], capture_output=True, text=True)
        return result.stderr if result.returncode != 0 else None

    @__log_duration
    def __get_scripts(self) -> list[dict[str, str]]:
        """Load target scripts and their metadata"""
        scripts = []
        for path in self.target_paths:
            with open(path, 'r') as file:
                content = file.read()
            script = \
            {
                'filename': Path(path).name, 
                'content': content.strip().split('\n'),
            }
            scripts.append(script)
        return scripts
    
    def __log_costs(self, funcname: str, response: ChatCompletion | CreateEmbeddingResponse) -> None:
        """Log the embedding/prompting costs that have been accumulated"""

        # Get the qualified name of the caller
        filename = os.path.basename(__file__)
        classname = 'HybridRecommendations'
        qualname = f'{filename}.{classname}.{funcname}'

        # Get the token usage statistics
        total_tokens = response.usage.total_tokens
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = total_tokens - prompt_tokens

        # Log the cost of the caller
        message = f'"{qualname}","{prompt_tokens}","{completion_tokens}","{total_tokens}"'
        logging.getLogger('cost').info(message)


class QdrantVectorizer:
    def __init__(
        self,
        project_name: str,
        output_dir: str,
        embedding_hostname: str,
        embedding_port: int,
        embedding_api_key: str,
        embedding_model: str,
        collection_name: str = 'sawra',
        chunk_size: int = 3000,
        vector_size: int = 1536,
    ) -> None:
        # Initialize project metadata
        self.project_name = project_name
        self.output_dir = output_dir

        # Initialize embedding vector
        self.openai_client = OpenAI(api_key=embedding_api_key)
        self.qdrant_client = QdrantClient(host=embedding_hostname, port=embedding_port, api_key=embedding_api_key, https=False)
        self.collection_name = collection_name
        self.chunk_size = chunk_size
        self.vector_size = vector_size
        self.embedding_model = embedding_model
        self.embedding_api_key = embedding_api_key
    
    def __log_duration(func):
        """Decorator that logs the duration of the decorated function"""
        def wrapper(self, *args, **kwargs):
            # Calculate the duration of the caller
            start_time = time.time()
            result = func(self, *args, **kwargs) 
            end_time = time.time()
            duration = end_time - start_time

            # Get the qualified name of the caller
            filename = os.path.basename(__file__)
            classname = 'QdrantVectorizer'
            qualname = f'{filename}.{classname}.{func.__name__}'

            # Log the qualname and duration of the decorated function
            message = f'"{qualname}","{start_time}","{end_time}","{duration}"'
            logging.getLogger('duration').info(message)
            return result
        return wrapper

    @__log_duration
    def vectorize(self) -> None:
        """Vectorize target traces and upload them"""
        if self.__has_points():
            return
        self.__ensure_collections()

        # Load and compile trace parses
        summary = {}
        paths = glob.glob(os.path.join(self.output_dir, '*.parse'))
        for path in paths:
            job_name = Path(path).stem
            with open(path, 'r') as file:
                parse = json.load(file)
            summary[f'{job_name}.apt'] = parse['apt']
            summary[f'{job_name}.env'] = parse['env']
            summary[f'{job_name}.pip'] = parse['pip']
            summary[f'{job_name}.python_versions'] = parse['versions']
            summary[f'{job_name}.paths'] = parse['paths']

        # Iterate through traces, chunk them, and embed them
        for trace_path, traced_values in summary.items():
            parsed = traced_values if isinstance(traced_values, list) else [f'"{k}": "{v}"' for k, v, in traced_values.items()]
            parsed = '\n'.join(parsed)
            chunks = self.__chunk_text(text=parsed, line_aware=True)

            # Iterate through chunks and embed them
            for i, chunk in enumerate(chunks):
                id = str(uuid.uuid4())
                embedding = self.__get_embeddings(chunk)
                payload = \
                {
                    'project_name': self.project_name,
                    'job_name': Path(trace_path).stem,
                    'chunk_id': i,
                    'chunk_type': Path(trace_path).suffix,
                    'chunk_content': chunk,   
                }
                self.qdrant_client.upsert \
                (
                    collection_name=self.collection_name,
                    points=[qmodels.PointStruct(id=id, vector=embedding, payload=payload)],
                )
    
    @__log_duration
    def __ensure_collections(self) -> None:
        """Ensure that all collections exist (and create them if they don't)"""
        if not self.qdrant_client.collection_exists(self.collection_name):
            self.qdrant_client.recreate_collection \
            (
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )

    @__log_duration
    def __has_points(self) -> bool:
        """Check whether the project already has points"""
        if not self.qdrant_client.collection_exists(self.collection_name):
            return False
        return self.qdrant_client.count(
            collection_name=self.collection_name,
            count_filter=Filter(must=[
                FieldCondition(
                    key='project_name', match=MatchValue(value=self.project_name)),
            ]),
        ).count > 0

    @__log_duration
    def __get_embeddings(self, text: str | list[str]) -> list[float]:
        """Get text embeddings from an embedding model"""
        input = [text] if isinstance(text, str) else text
        response = self.openai_client.embeddings.create(input=input, model=self.embedding_model)
        self.__log_costs('__get_embeddings', response)
        return response.data[0].embedding

    @__log_duration
    def __chunk_text(self, text: str, line_aware: bool = True) -> list[str]:
        """Chunk the provided text based on the maximum chunk size"""
        if line_aware:
            lines = text.splitlines()
            chunks, current = [], ''
            for line in lines:
                if len(current) + len(line) + 1 <= self.chunk_size:
                    current += line + '\n'
                else:
                    chunks.append(current.strip())
                    current = line + '\n'
            if current:
                chunks.append(current.strip())
            return chunks
        else:
            return [text[i : i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]

    def __log_costs(self, funcname: str, response: ChatCompletion | CreateEmbeddingResponse) -> None:
        """Log the embedding/prompting costs that have been accumulated"""

        # Get the qualified name of the caller
        filename = os.path.basename(__file__)
        classname = 'QdrantVectorizer'
        qualname = f'{filename}.{classname}.{funcname}'

        # Get the token usage statistics
        total_tokens = response.usage.total_tokens
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = total_tokens - prompt_tokens

        # Log the cost of the caller
        message = f'"{qualname}","{prompt_tokens}","{completion_tokens}","{total_tokens}"'
        logging.getLogger('cost').info(message)
