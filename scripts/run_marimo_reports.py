#!/usr/bin/env python
"""
Script to run the Marimo attendance reports directly from the command line.
"""
import os
import sys
import argparse
import importlib.util
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance.settings')
import django
django.setup()


def list_notebooks():
    """List all available Marimo notebooks."""
    notebook_dir = project_root / 'notebooks'
    notebooks = []
    
    for file in notebook_dir.glob('*.py'):
        if file.name != '__init__.py' and file.name != 'viz-playground.py':
            notebooks.append(file.stem)
    
    return notebooks


def run_notebook(notebook_name):
    """Run a specific Marimo notebook."""
    notebook_path = project_root / 'notebooks' / f"{notebook_name}.py"
    
    if not notebook_path.exists():
        print(f"Notebook '{notebook_name}' not found")
        return False
    
    # Import the notebook module
    spec = importlib.util.spec_from_file_location(notebook_name, notebook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # Run the app if it exists
    if hasattr(module, 'app'):
        module.app.run()
        return True
    else:
        print(f"No Marimo app found in {notebook_name}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Marimo attendance reports")
    parser.add_argument("notebook", nargs="?", help="Name of the notebook to run")
    parser.add_argument("--list", action="store_true", help="List available notebooks")
    
    args = parser.parse_args()
    
    if args.list:
        notebooks = list_notebooks()
        if notebooks:
            print("Available notebooks:")
            for nb in notebooks:
                print(f"  - {nb}")
        else:
            print("No notebooks found")
    elif args.notebook:
        try:
            import marimo
            run_notebook(args.notebook)
        except ImportError:
            print("Marimo is not installed. Please install with 'pip install marimo[recommended]'")
    else:
        parser.print_help() 