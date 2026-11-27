"""Compatibility entrypoint: all orchestration lives in the common module."""
from src.experiment_orchestrator import previous_segments,run,run_experiment

if __name__ == '__main__':
    import runpy
    runpy.run_module('src.experiment_orchestrator',run_name='__main__')
