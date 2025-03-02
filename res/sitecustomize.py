import csv
import inspect
import io
import os


PYENV_OUTPUT_PATH = os.getenv('PYENV_OUTPUT_PATH', None)
PYENV_REPOSITORY_DIR = os.getenv('PYENV_REPOSITORY_DIR', None)

if PYENV_OUTPUT_PATH is None:
    raise Exception('pyenv: environmental variable "PYENV_OUTPUT_PATH" must be set.') 
if PYENV_REPOSITORY_DIR is None:
    raise Exception('pyenv: environmental variable "PYENV_REPOSITORY_DIR" must be set.') 


def __get_monitored_getenv__(func):
    def __monitored_getenv__(*args, **kwargs):
        # Retrieve the caller and the environmental variable
        current = inspect.currentframe()
        filename = None
        while filename is None and current is not None:
            current = current.f_back
            filename = current.f_code.co_filename \
                if getattr(current, 'f_code', None) \
                and getattr(current.f_code, 'co_filename', None) \
                and current.f_code.co_filename.startswith(PYENV_REPOSITORY_DIR) \
                else filename
        key = args[1]
        value = args[0].decodekey(args[0]._data[args[0].encodekey(key)])

        # Construct the new output from the caller and environmental variable
        row = io.StringIO()
        writer = csv.writer(row, quoting=csv.QUOTE_MINIMAL)
        writer.writerow([filename, key, value])
        output = row.getvalue().strip()
        row.close()
        
        # Append the output to the output file
        with open(PYENV_OUTPUT_PATH, 'a') as file:
            file.write(f'{output}\n')
        return func(*args, **kwargs) 
    return __monitored_getenv__
os._Environ.__getitem__ = __get_monitored_getenv__(os._Environ.__getitem__)