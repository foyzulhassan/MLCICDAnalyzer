import os


ENV_TRACE_OUTPUT_PATH = os.getenv('ENV_TRACE', None)
if ENV_TRACE_OUTPUT_PATH is None:
    raise Exception('pyenv: environmental variable "ENV_TRACE" must be set.') 
def __instrument_getenv__(func):
    def __new_getenv__(*args, **kwargs):
        key = args[1]
        value = args[0].decodekey(args[0]._data[args[0].encodekey(key)])
        with open(ENV_TRACE_OUTPUT_PATH, 'a') as file:
            file.write(f'{key}={value}\n')
        return func(*args, **kwargs) 
    return __new_getenv__
os._Environ.__getitem__ = __instrument_getenv__(os._Environ.__getitem__)
