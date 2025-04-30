#!/usr/bin/env python3
"""
Script to analyze import dependencies in frontend files (JS, TS, Svelte).
Usage: python find_related_files.py <file_list> <project_root>
"""

import os
import sys
import json
import re
from collections import defaultdict

# Regular expressions for finding imports in different file types
JS_TS_IMPORT_REGEX = re.compile(r'''
    # Match ES6 imports
    (?:import|export)[\s\n]*
    (?:
        # import defaultExport from "module"
        # import * as name from "module"
        (?:[^'"{}]*)
        from[\s\n]+['"]([^'"]+)['"]|
        
        # import "module"
        ['"]([^'"]+)['"]|
        
        # export { x } from "module"
        (?:[^'"]*)\{[^}]*\}[\s\n]+from[\s\n]+['"]([^'"]+)['"]
    )
''', re.VERBOSE)

SVELTE_SCRIPT_REGEX = re.compile(r'<script[^>]*>(.*?)</script>', re.DOTALL)
SVELTE_MODULE_SCRIPT_REGEX = re.compile(r'<script\s+context="module"[^>]*>(.*?)</script>', re.DOTALL)

DYNAMIC_IMPORT_REGEX = re.compile(r'''
    # Match dynamic imports
    import\s*\(\s*['"]([^'"]+)['"]\s*\)
''', re.VERBOSE)

REQUIRE_IMPORT_REGEX = re.compile(r'''
    # Match CommonJS requires
    require\s*\(\s*['"]([^'"]+)['"]\s*\)
''', re.VERBOSE)

def find_imports(file_path):
    """Analyze a frontend file and find all imports."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        imports = []
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.svelte':
            # Extract script content from Svelte files
            script_matches = SVELTE_SCRIPT_REGEX.findall(content)
            module_script_matches = SVELTE_MODULE_SCRIPT_REGEX.findall(content)
            
            # Combine all script content
            script_content = '\n'.join(script_matches + module_script_matches)
            
            # Find imports in the script content
            imports.extend(find_imports_in_js_ts(script_content))
        else:
            # For JS/TS files
            imports.extend(find_imports_in_js_ts(content))
        
        return list(set(imports))  # Remove duplicates
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}", file=sys.stderr)
        return []

def find_imports_in_js_ts(content):
    """Extract import paths from JS/TS content."""
    imports = []
    
    # Find ES6 imports
    for match in JS_TS_IMPORT_REGEX.finditer(content):
        # Check each capture group and use the first non-None match
        for group in match.groups():
            if group is not None:
                imports.append(group)
                break
    
    # Find dynamic imports
    for match in DYNAMIC_IMPORT_REGEX.finditer(content):
        imports.append(match.group(1))
    
    # Find CommonJS requires
    for match in REQUIRE_IMPORT_REGEX.finditer(content):
        imports.append(match.group(1))
    
    return imports

def resolve_import_to_filepath(import_path, base_dir, file_with_import):
    """Try to convert an import path to an actual file path."""
    # Handle relative imports
    if import_path.startswith('.'):
        # Get the directory of the file containing the import
        parent_dir = os.path.dirname(file_with_import)
        # Resolve the relative path
        resolved_path = os.path.normpath(os.path.join(parent_dir, import_path))
        
        # Try common extensions
        for ext in ['', '.js', '.ts', '.tsx', '.jsx', '.svelte', '.mjs', '.cjs', '/index.js', '/index.ts', '/index.svelte']:
            file_path = f"{resolved_path}{ext}"
            if os.path.exists(file_path):
                return file_path
    
    # Handle non-relative imports (node_modules or aliases)
    else:
        # Check for path alias configurations (e.g., from tsconfig or vite config)
        alias_mappings = {
            # Common aliases, add more based on your project configuration
            '$lib': os.path.join(base_dir, 'src', 'lib'),
            '$components': os.path.join(base_dir, 'src', 'components'),
            '$routes': os.path.join(base_dir, 'src', 'routes'),
            '$assets': os.path.join(base_dir, 'src', 'assets'),
            '$stores': os.path.join(base_dir, 'src', 'stores'),
            '@': os.path.join(base_dir, 'src'),
            '~': os.path.join(base_dir, 'src')
        }
        
        # Check if the import starts with any of our aliases
        for alias, alias_path in alias_mappings.items():
            if import_path.startswith(alias + '/'):
                # Replace the alias with the actual path
                relative_path = import_path[len(alias) + 1:]
                absolute_path = os.path.join(alias_path, relative_path)
                
                # Try common extensions
                for ext in ['', '.js', '.ts', '.tsx', '.jsx', '.svelte', '.mjs', '.cjs', '/index.js', '/index.ts', '/index.svelte']:
                    file_path = f"{absolute_path}{ext}"
                    if os.path.exists(file_path):
                        return file_path
        
        # Handle node_modules imports or other non-relative imports
        # We don't typically need to track node_modules dependencies
        if import_path.startswith('@') or '/' in import_path:
            # This is likely a package import, we'll skip it
            return None
    
    # Could not resolve to a file
    return None

def find_related_files(file_path, project_root):
    """Find all files related to the given file through imports."""
    if not os.path.exists(file_path):
        print(f"Warning: File does not exist: {file_path}", file=sys.stderr)
        return set()
    
    direct_imports = find_imports(file_path)
    related_files = set()
    
    for import_path in direct_imports:
        resolved_file = resolve_import_to_filepath(import_path, project_root, file_path)
        if resolved_file:
            related_files.add(resolved_file)
    
    return related_files

def process_files_from_list(file_list_path, project_root):
    """Process a list of files and find all related files."""
    with open(file_list_path, 'r') as f:
        interesting_files = [line.strip() for line in f if line.strip()]
    
    # Dictionary to store each file and its dependencies
    dependencies_map = defaultdict(set)
    all_related_files = set()
    
    for file in interesting_files:
        # Normalize file path to be relative to project root
        if os.path.isabs(file):
            rel_file = os.path.relpath(file, project_root)
        else:
            rel_file = file
        full_path = os.path.join(project_root, rel_file)
        
        # Only process JS, TS, and Svelte files
        if os.path.exists(full_path) and os.path.splitext(full_path)[1].lower() in ['.js', '.ts', '.tsx', '.jsx', '.svelte', '.mjs', '.cjs']:
            related = find_related_files(full_path, project_root)
            # Store paths relative to project root
            relative_related_files = {os.path.relpath(r, project_root) for r in related if r}
            dependencies_map[rel_file] = relative_related_files
            all_related_files.update(relative_related_files)
    
    # Write results to a JSON file to maintain structure
    with open('dependencies_map.json', 'w') as f:
        json.dump({k: list(v) for k, v in dependencies_map.items()}, f, indent=2)
    
    # Write all related files to a text file
    with open('all_related_files.txt', 'w') as f:
        for file in sorted(all_related_files):
            f.write(f"{file}\n")
    
    # Write all files (original + related) to a file
    all_files = set(os.path.relpath(os.path.join(project_root, f), project_root) if not os.path.isabs(f) else f for f in interesting_files)
    all_files.update(all_related_files)
    with open('all_files.txt', 'w') as f:
        for file in sorted(all_files):
            f.write(f"{file}\n")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <file_list> <project_root>")
        sys.exit(1)
    
    file_list = sys.argv[1]
    project_root = sys.argv[2]
    process_files_from_list(file_list, project_root)
    print("Analysis completed. Results written to:")
    print("- dependencies_map.json: map of each file with its dependencies")
    print("- all_related_files.txt: list of all related files")
    print("- all_files.txt: combined list of original and related files")