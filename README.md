# ML CI/CD Generator
Automatically create robust CI/CD environments for applications that utilize machine learning.

# Dependencies
- **Linux-Based Environment** (e.g. Ubuntu)
- **Python3** (e.g. Python 3.11)
- **Target Dependencies** (i.e. Dependencies required to run the target script/executable)
- **ruamel.yaml** (i.e. pip install ruamel.yaml)

# Target Wrapper
Pathing issues can occur when selecting targets in directories other than this project's root. Because of this, **all targets must be enclosed within the wrapper provided below.** The "--target" argument should point to this wrapper.

```
# !/bin/bash
home=$PWD # Save the current directory
cd $(dirname "$0") # Navigate to the target's directory (this script must be in the same directory as the target)

INSERT_COMMAND(S)_TO_RUN_THE_TARGET_HERE > /dev/null 2>&1 # Run target, discard output

cd $home
```

# How to Run
1. Launch a Linux-based environment
2. Install Python3 (with tkinter) within the environment 
3. Install target dependencies within the environment
4. **Create the appropriate wrapper for the target within the environment**
5. Clone this project and navigate to its root directory
6. Run "python3 main.py --target \<PATH\> --requirement \<PATH\> --template \<PATH\> --workflow \<PATH\> --workflow_name \<NAME\> --new_trace"\
**Ex:** python3 main.py --new_trace --target target.sh --requirement requirement.txt --template dependencies.yaml --workflow workflow.yaml --workflow_name workflow

# Arguments
## --target PATH
**Description:** Path to target bash script to be traced\
**Type:** String (Path)\
**Default:** target.sh\
**Example:** python3 main.py --target run.sh

## --new_trace
**Description:** Whether the target should be traced again\
**Type:** N/A\
**Default:** False\
**Example:** python3 main.py --new_trace

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
**Default:** workflow\
**Example:** python3 main.py --template Workflow

## --dockerfile PATH
**Description:** Path to the dockerfile that the target uses\
**Type:** String\
**Default:** Dockerfile\
**Example:** python3 main.py --dockerfile docker/Dockerfile

# References
**Author:** Javid Ditty\
**Date:** 6/10/2024