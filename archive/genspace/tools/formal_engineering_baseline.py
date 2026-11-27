"""Repeat the existing seed-free ENGINEERING reference regression safely."""
from pathlib import Path
from tools import shadow_routing_engineering_regression as regression


if __name__ == '__main__':
    regression.OUT = (Path(__file__).resolve().parent.parent / 'results' /
                      'formal_orchestrator_engineering_regression.json')
    regression.main()
