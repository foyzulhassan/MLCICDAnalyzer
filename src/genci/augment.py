import os
from openai import OpenAI

class ImproveCIWithLLM:
    def __init__(self, api_key=None):
        # Initialize the OpenAI client with the API key
        self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    def improve_ci(self, requirements, generated_yaml, project_description, ci_instructions, prompt_file, fallback_prompt_file):
        # Helper to read file content or return None if the file doesn't exist or is blank
        def read_file(file_path):
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                with open(file_path, 'r') as file:
                    return file.read()
            return None

        # Read files, using None if unavailable or empty
        requirements_content = read_file(requirements)
        generated_yaml_content = read_file(generated_yaml)
        project_description_content = read_file(project_description)
        ci_instructions_content = read_file(ci_instructions)

        with open(prompt_file, 'r') as file:
                prompt_template = file.read()

        # Prepare placeholders
        placeholders = {
            '{project_description}': project_description_content or "No project description provided.",
            '{ci_instructions}': ci_instructions_content or "No specific CI instructions provided.",
            '{requirements}': requirements_content or "No requirements.txt file provided.",
            '{generated_yaml}': generated_yaml_content or "No tool-generated CI YAML provided."
        }

        # Replace placeholders in the prompt
        for placeholder, content in placeholders.items():
            prompt_template = prompt_template.replace(placeholder, content)

        # Construct the message payload
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert CI/CD developer specializing in GitHub Actions workflows. "
                    "Your expertise includes creating, optimizing, and maintaining CI/CD scripts for software projects of varying complexity. "
                    "You understand best practices, industry standards, and effective methods for making CI workflows secure, efficient, and maintainable. "
                    "Your task is to ensure the CI script meets industry standards and is optimized for readability, performance, and security."
                )
            },
            {
                "role": "user",
                "content": (
                    f"{prompt_template}\n\n"
                    "### Important Considerations:\n"
                    "- Ensure all dependencies present in the YAML file but missing in `requirements.txt` are retained in the YAML file.\n"
                    "- Validate and enhance the YAML file for GitHub Actions compatibility, adhering to YAML syntax rules and best practices.\n"
                    "- Output **only** the final improved YAML file without any explanations or comments."
                )
            }
        ]

        # Call the OpenAI API
        chat_completion = self.client.chat.completions.create(
            messages=messages,
            model="gpt-4",
            temperature=0
        )

        # Extract and return the improved YAML
        ciyaml_improved_by_llm = chat_completion.choices[0].message.content
        return ciyaml_improved_by_llm
