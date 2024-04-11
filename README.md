# ML CI/CD Generator
Automatically create robust CI/CD environments for applications that utilize machine learning.

# Dependencies
- **Linux-Based Environment** (e.g. Ubuntu)
- **Python3** (e.g. Python 3.11)
- **Target Dependencies** (i.e. Dependencies required to run the target script/executable)

# Target Wrapper
Pathing issues can occur when selecting targets in directories other than this project's root. Because of this, **all targets must be enclosed within the wrapper provided below.** The "--target" argument should point to this wrapper.

```
# !/bin/bash
home=$PWD # Save the current directory
cd $(dirname "$0") # Navigate to the target's directory

# INSERT COMMAND TO RUN THE TARGET HERE

cd $home
```

# How to Run
1. Launch a Linux-based environment
2. Install Python3 (with tkinter) within the environment 
3. Install target dependencies within the environment
4. **Create the appropriate wrapper for the target within the environment**
5. Clone this project and navigate to its root directory
6. Run "python3 /<TARGET> --target /<PATH> --requirement /<PATH> --template /<PATH> --workflow /<PATH> --workflow_name /<NAME>"\
**Ex:** python3 main.py --target target.sh --requirement requirement.txt --template dependencies.yaml --workflow workflow.yaml --workflow_name Workflow

# Arguments
## --target PATH
**Description:** Path to target bash script to be traced\
**Type:** String (Path)\
**Default:** target.sh\
**Example:** python3 main.py --target run.sh

## --requirement PATH
**Description:** Path to, or for, a pip requirements file\
**Type:** String (Path)\
**Default:** requirement.txt\
**Example:** python3 main.py --requirement requirements.txt

## --template PATH
**Description:** Path to a workflow configuration template\
**Type:** String (Path)\
**Default:** dependencies.yaml\
**Example:** python3 main.py --template dependencies.yaml

## --workflow PATH
**Description:** Path to, or for, a workflow configuration\
**Type:** String (Path)\
**Default:** workflow.yaml\
**Example:** python3 main.py --workflow workflow.yaml

## --workflow_name NAME
**Description:** Name for a new workflow configuration\
**Type:** String\
**Default:** Workflow\
**Example:** python3 main.py --template Workflow

# References
**Author:** Javid Ditty\
**Date:** 4/11/2024