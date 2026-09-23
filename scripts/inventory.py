import ast
import os
import json
import subprocess

def run_inventory():
    errors = []
    warnings = []

    # 1. AST Syntax & Unused Imports
    for root, _, files in os.walk('backend'):
        for f in files:
            if not f.endswith('.py'):
                continue
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8') as file:
                src = file.read()
            try:
                tree = ast.parse(src, filename=path)
            except SyntaxError as e:
                errors.append({
                    'type': 'SYNTAX_ERROR',
                    'file': path,
                    'line': e.lineno,
                    'msg': f'SyntaxError: {e.msg}'
                })
                continue

            imported_names = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for n in node.names:
                        imported_names[n.asname or n.name] = (node.lineno, n.name)
                elif isinstance(node, ast.ImportFrom):
                    for n in node.names:
                        imported_names[n.asname or n.name] = (node.lineno, f'{node.module}.{n.name}')

            used_names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    used_names.add(node.id)

            for name, (line, full) in imported_names.items():
                if name not in used_names and not name.startswith('_') and name != '__all__':
                    if os.path.basename(path) != '__init__.py':
                        warnings.append({
                            'type': 'UNUSED_IMPORT',
                            'file': path,
                            'line': line,
                            'msg': f'Unused import: {name} ({full})'
                        })

    # 2. Pyright Diagnostics
    res = subprocess.run(['npx.cmd', 'pyright', '--outputjson'], capture_output=True, text=True)
    try:
        p_data = json.loads(res.stdout)
        for d in p_data.get('generalDiagnostics', []):
            rule = d.get('rule', 'unknown')
            f = d.get('file', '').replace('c:\\Users\\tst20\\Aegis software\\', '')
            l = d.get('range', {}).get('start', {}).get('line', 0) + 1
            m = d.get('message', '').split('\n')[0]
            
            if rule == 'reportUndefinedVariable':
                errors.append({'type': 'UNDEFINED_VARIABLE', 'file': f, 'line': l, 'msg': m})
            elif rule == 'reportOperatorIssue':
                errors.append({'type': 'INVALID_OPERATOR', 'file': f, 'line': l, 'msg': m})
            elif rule == 'reportAssignmentType':
                errors.append({'type': 'INVALID_ASSIGNMENT', 'file': f, 'line': l, 'msg': m})
            elif 'No overloads for "__init__"' in m:
                errors.append({'type': 'INVALID_CONSTRUCTOR_CALL', 'file': f, 'line': l, 'msg': m})
            elif rule in ['reportOptionalMemberAccess', 'reportCallIssue']:
                warnings.append({'type': rule, 'file': f, 'line': l, 'msg': m})
    except Exception as e:
        print('Pyright parse error:', e)

    print('====================================')
    print(f'TOTAL GENUINE ERRORS: {len(errors)}')
    print('====================================')
    for i, e in enumerate(errors):
        print(f'SOFTWARE-E{i+1:02d}: {e["file"]}:{e["line"]} [{e["type"]}] {e["msg"]}')

    print('\n====================================')
    print(f'TOTAL WARNINGS / LINTS: {len(warnings)}')
    print('====================================')
    for i, w in enumerate(warnings):
        print(f'SOFTWARE-W{i+1:02d}: {w["file"]}:{w["line"]} [{w["type"]}] {w["msg"]}')

if __name__ == '__main__':
    run_inventory()
