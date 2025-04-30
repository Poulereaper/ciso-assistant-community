"""
Script to find test files directly related to a list of Python files.

Usage:
    python find_related_test_files.py <file_with_list_of_files> <workspace_dir>

Example:
    python find_related_test_files.py backend_relevant_files.txt /path/to/workspace
"""

import os
import sys
import json
import re
from pathlib import Path


def normalize_path(path):
    """Normalize a file path to make it consistent for comparison."""
    return str(Path(path).resolve())


def is_test_file(file_path):
    """Check if the file is a test file."""
    file_name = os.path.basename(file_path)
    return file_name.startswith("test_") or file_name.endswith("_test.py") or "tests_" in file_name


def find_direct_test_file(file_path, workspace_dir):
    """Find the test file that directly tests the given file."""
    direct_test_files = []
    
    # Get the file name without extension
    file_path = file_path.strip()
    file_name = os.path.basename(file_path)
    name_without_ext = os.path.splitext(file_name)[0]
    
    # Resolve the file path - try both directly from workspace and from backend directory
    full_paths = [
        os.path.join(workspace_dir, file_path),  # Full path from workspace root
        os.path.join(workspace_dir, 'backend', file_path)  # Path relative to backend directory
    ]
    
    resolved_file_path = None
    for path in full_paths:
        if os.path.exists(path):
            resolved_file_path = path
            break
    
    # If we can't find the file at either location, return empty list
    if not resolved_file_path:
        print(f"Warning: Could not find source file at any of these locations:")
        for path in full_paths:
            print(f"  - {path}")
        return []
    
    # Common test file naming patterns
    test_patterns = [
        f"test_{name_without_ext}.py",
        f"{name_without_ext}_test.py",
        f"tests_{name_without_ext}.py",
        f"{name_without_ext}_tests.py"
    ]
    
    # Get directory structure for the resolved file
    file_dir = os.path.dirname(resolved_file_path)
    
    # Primary search locations for direct tests
    search_locations = [
        # Tests directory at the same level as the module directory
        os.path.join(file_dir, 'tests'),
        os.path.join(file_dir, 'test'),
    ]
    
    # If we're in a module structure, look for tests in specific locations
    module_parts = resolved_file_path.split(os.sep)
    
    # Handle specific project structure patterns
    if 'backend' in module_parts:
        backend_index = module_parts.index('backend')
        module_name = module_parts[backend_index+1] if backend_index + 1 < len(module_parts) else None
        
        if module_name:
            # Look for test in the module's test directory
            module_base_path = os.path.join(workspace_dir, 'backend', module_name)
            search_locations.append(os.path.join(module_base_path, 'tests'))
            search_locations.append(os.path.join(module_base_path, 'test'))
    
    # Search for test files in all potential locations
    for location in search_locations:
        if os.path.exists(location):
            for pattern in test_patterns:
                potential_test_file = os.path.join(location, pattern)
                if os.path.exists(potential_test_file):
                    direct_test_files.append(potential_test_file)
    
    # If we didn't find any direct tests in the primary locations, 
    # look in the parent directory's test folder
    if not direct_test_files:
        parent_dir = os.path.dirname(file_dir)
        parent_test_dirs = [
            os.path.join(parent_dir, 'tests'),
            os.path.join(parent_dir, 'test')
        ]
        
        for test_dir in parent_test_dirs:
            if os.path.exists(test_dir):
                for pattern in test_patterns:
                    potential_test_file = os.path.join(test_dir, pattern)
                    if os.path.exists(potential_test_file):
                        direct_test_files.append(potential_test_file)
    
    # Normalize paths and remove duplicates
    normalized_test_files = [normalize_path(p) for p in direct_test_files]
    return list(set(normalized_test_files))


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <file_with_list_of_files> <workspace_dir>")
        sys.exit(1)
    
    input_file_path = sys.argv[1]
    workspace_dir = sys.argv[2]
    
    all_test_files = []
    file_to_tests_map = {}
    
    try:
        # Read the list of files
        with open(input_file_path, 'r') as file_list:
            for line in file_list:
                file_path = line.strip()
                if file_path:
                    # Skip files that are already test files
                    if is_test_file(file_path):
                        # Resolve the test file path - try both workspace and backend paths
                        test_path_options = [
                            os.path.join(workspace_dir, file_path),
                            os.path.join(workspace_dir, 'backend', file_path)
                        ]
                        
                        resolved_test_path = None
                        for path in test_path_options:
                            if os.path.exists(path):
                                resolved_test_path = path
                                break
                        
                        if resolved_test_path:
                            all_test_files.append(resolved_test_path)
                        continue
                    
                    # Find direct test files
                    test_files = find_direct_test_file(file_path, workspace_dir)
                    if test_files:
                        file_to_tests_map[file_path] = test_files
                        all_test_files.extend(test_files)
        
        # Remove duplicates while preserving order
        unique_test_files = []
        for file in all_test_files:
            if file not in unique_test_files:
                unique_test_files.append(file)
        
        # Write the list of test files
        with open('all_test_files.txt', 'w') as output_file:
            for test_file in unique_test_files:
                output_file.write(f"{test_file}\n")
        
        # Write the mapping for debugging/reference
        with open('test_files_mapping.json', 'w') as mapping_file:
            json.dump(file_to_tests_map, mapping_file, indent=2)
        
        print(f"Found {len(unique_test_files)} direct test files.")
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()