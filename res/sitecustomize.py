import csv
import inspect
import io
import os


ENV_TRACE_OUTPUT_PATH = os.getenv('ENV_TRACE', None)
if ENV_TRACE_OUTPUT_PATH is None:
    raise Exception('pyenv: environmental variable "ENV_TRACE" must be set.') 
def __instrument_getenv__(func):
    def __new_getenv__(*args, **kwargs):
        try:
            canidates = []
            current = inspect.currentframe()
            while True:
                current = current.f_back
                filename = current.f_code.co_filename if getattr(current, 'f_code', None) and getattr(current.f_code, 'co_filename', None) else None
                canidates.append(filename) if filename else None
        except AttributeError:
            pass
        finally:
            filename = canidates[2] if '_collections_abc.py' in canidates[0] else canidates[0] # os.getenv('key') vs os.environ['key']
            key = args[1]
            value = args[0].decodekey(args[0]._data[args[0].encodekey(key)])

        row = io.StringIO()
        writer = csv.writer(row, quoting=csv.QUOTE_MINIMAL)
        writer.writerow([filename, key, value])
        output = row.getvalue().strip()
        row.close()

        with open(ENV_TRACE_OUTPUT_PATH, 'a') as file:
            file.write(f'{output}\n')
        return func(*args, **kwargs) 
    return __new_getenv__
os._Environ.__getitem__ = __instrument_getenv__(os._Environ.__getitem__)