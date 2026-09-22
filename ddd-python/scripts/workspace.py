"""Explicit multi-package mapping and conservative impact analysis; no target imports."""

import ast
import fnmatch
import hashlib
import json
from pathlib import Path
import sys
import sysconfig


class ProjectError(ValueError):
    """Configuration or evidence cannot be interpreted reliably."""


def read(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ProjectError(str(exc))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(root, name):
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ProjectError('Expected relative path: %r' % name)
    path = (root / name).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        raise ProjectError('Path escapes project: ' + name)
    return path


def match(name, patterns):
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


def prefix(name, parent):
    return name == parent or name.startswith(parent + '.')


def stdlib_names():
    """Locate standard library without importing project or installed packages."""
    names = set(sys.builtin_module_names) | set(getattr(sys, 'stdlib_module_names', ()))
    for path in Path(sysconfig.get_path('stdlib')).iterdir():
        if path.suffix == '.py' or (path.is_dir() and (path / '__init__.py').exists()):
            names.add(path.stem)
    for path in (Path(sysconfig.get_path('stdlib')) / 'lib-dynload').glob('*'):
        if path.suffix in ('.so', '.pyd', '.dylib'):
            names.add(path.name.split('.')[0])
    names.update({'__future__', 'typing', 'collections', 'importlib'})
    return names


def inventory(root, config):
    """Hash declared package/data/config paths; exclusions are visible in config."""
    root = Path(root).resolve()
    paths = [p['root'] for p in config['packages']] + config.get('tracked_paths', [])
    files = {}
    excludes = config.get('exclude', [])
    for item in paths:
        base = inside(root, item)
        if not base.exists():
            raise ProjectError('Missing tracked path: ' + item)
        for path in ([base] if base.is_file() else base.rglob('*')):
            relative = str(path.relative_to(root))
            if '.git' in path.parts or '__pycache__' in path.parts or path.suffix == '.pyc' or match(relative, excludes):
                continue
            if path.is_symlink():
                raise ProjectError('Symlink requires an explicit materialized source: ' + relative)
            if path.is_file():
                inside(root, relative)
                files[relative] = sha(path)
    return dict(sorted(files.items()))


def validate(config, root):
    if config.get('version') != 2 or not isinstance(config.get('packages'), list) or not config['packages']:
        raise ProjectError('Expected version 2 and nonempty packages')
    names = [p['name'] for p in config['packages']]
    if config.get('architecture_policy', 'strict') not in ('strict', 'no_new_violations'):
        raise ProjectError('Unknown architecture policy')
    if len(names) != len(set(names)):
        raise ProjectError('Duplicate package name')
    for package in config['packages']:
        if not isinstance(package['name'], str) or not package['name']:
            raise ProjectError('Invalid package name')
        inside(root, package['root'])
        if package.get('language', 'python') not in ('python', 'native'):
            raise ProjectError('Use python analysis or explicit native validation')
        if package.get('language', 'python') == 'python' and not package.get('imports'):
            raise ProjectError('Python package needs imports mappings')
        if set(package.get('allow', [])) - set(names):
            raise ProjectError('Unknown allowed package')
        for mapping in package.get('imports', []):
            source = inside(root, mapping['path'])
            package_root = inside(root, package['root'])
            if source != package_root and package_root not in source.parents:
                raise ProjectError('Import mapping is outside its package')
            if mapping.get('prefix') and not all(p.isidentifier() for p in mapping['prefix'].split('.')):
                raise ProjectError('Invalid import prefix')
    for edge in config.get('runtime_edges', []):
        if edge['from'] not in names or edge['to'] not in names or not edge.get('evidence') or edge.get('kind') not in ('event', 'rpc', 'config'):
            raise ProjectError('Runtime edges need known packages, kind and evidence')
    for resource in config.get('data_resources', []):
        if not resource.get('name') or not resource.get('evidence'):
            raise ProjectError('Data resource needs name and evidence')
        if set(resource.get('readers', []) + resource.get('writers', [])) - set(names):
            raise ProjectError('Unknown data resource participant')
        for path in resource.get('paths', []):
            inside(root, path)
    ids = [j['id'] for j in config.get('jobs', [])]
    if len(ids) != len(set(ids)) or any(not i or not all(c.isalnum() or c in '-_' for c in i) for i in ids):
        raise ProjectError('Invalid or duplicate job IDs')
    for job in config.get('jobs', []):
        if job.get('phase') not in ('both', 'after') or job.get('format') not in ('junit', 'unittest', 'checks'):
            raise ProjectError('Job requires phase and evidence format')
        if not isinstance(job.get('argv'), list) or not job['argv'] or not all(isinstance(x, str) for x in job['argv']):
            raise ProjectError('Job argv must be a nonempty string list')
        inside(root, job.get('cwd', '.'))
        if set(job.get('packages', names)) - set(names):
            raise ProjectError('Unknown job package')
    for entry in config.get('dynamic_import_exceptions', []):
        if not entry.get('reason') or not entry.get('module'):
            raise ProjectError('Dynamic import exception needs module and reason')
    return config


def cycles(graph):
    """Iterative DFS avoids recursion limits on large package/module graphs."""
    done, active, found = set(), set(), []
    for start in sorted(graph):
        if start in done:
            continue
        stack = [(start, iter(sorted(graph[start])))]; trail = [start]; active.add(start)
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                stack.pop(); trail.pop(); active.remove(node); done.add(node)
            elif child in active:
                found.append(trail[trail.index(child):] + [child])
            elif child not in done:
                active.add(child); trail.append(child); stack.append((child, iter(sorted(graph.get(child, [])))))
    return found


def analyze(root, config, changed=None):
    """Build static edges; declared runtime/data relationships widen impact."""
    root = Path(root).resolve()
    packages = {p['name']: p for p in config['packages']}
    modules, findings, notes = {}, [], []
    for package in packages.values():
        for mapping in package.get('imports', []):
            base = inside(root, mapping['path'])
            if not base.is_dir():
                raise ProjectError('Missing import root: ' + mapping['path'])
            for path in base.rglob('*.py'):
                relative = str(path.relative_to(root))
                if '__pycache__' in path.parts or match(relative, config.get('exclude', [])):
                    continue
                if path.is_symlink():
                    raise ProjectError('Symlink source: ' + relative)
                parts = list(path.relative_to(base).with_suffix('').parts)
                if parts[-1] == '__init__':
                    parts.pop()
                name = '.'.join(([mapping['prefix']] if mapping.get('prefix') else []) + parts)
                if not name:
                    continue
                if name in modules:
                    raise ProjectError('Ambiguous import name: ' + name)
                try:
                    tree = ast.parse(path.read_text(encoding='utf-8'), filename=relative)
                except (SyntaxError, UnicodeError) as exc:
                    findings.append({'code': 'SYNTAX', 'path': relative, 'detail': str(exc)})
                    continue
                modules[name] = dict(path=relative, tree=tree, package=package['name'], is_package=path.name == '__init__.py')
    if any(p.get('language', 'python') == 'python' for p in packages.values()) and not modules:
        raise ProjectError('No Python modules in configured mappings')
    graph = {name: set() for name in modules}
    package_graph = {name: set() for name in packages}
    edges, standard = [], stdlib_names()
    def resolve(name):
        while name:
            if name in modules:
                return name
            name = name.rpartition('.')[0]
        return None
    for name, record in modules.items():
        owner = packages[record['package']]
        imports = []
        scope = name if record['is_package'] else name.rpartition('.')[0]
        for node in ast.walk(record['tree']):
            if isinstance(node, ast.Call) and (isinstance(node.func, ast.Name) and node.func.id == '__import__' or isinstance(node.func, ast.Attribute) and node.func.attr == 'import_module'):
                exception = next((e for e in config.get('dynamic_import_exceptions', []) if e['module'] == name), None)
                item = dict(code='DYNAMIC_IMPORT', path=record['path'], line=node.lineno, detail='Runtime import needs declared edges and full validation')
                if exception:
                    item['reason'] = exception['reason']; notes.append(item)
                else:
                    findings.append(item)
            if isinstance(node, ast.Import):
                imports.extend((a.name, node.lineno) for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ''
                if node.level:
                    parts = scope.split('.') if scope else []
                    if node.level > len(parts):
                        findings.append(dict(code='RELATIVE_IMPORT', path=record['path'], detail='Escapes mapped package'))
                        continue
                    base = '.'.join(parts[:len(parts) - node.level + 1] + ([base] if base else []))
                imports.append((base, node.lineno))
                for alias in node.names:
                    child = base + '.' + alias.name
                    if child in modules:
                        imports.append((child, node.lineno))
                    if alias.name == '*':
                        findings.append(dict(code='STAR_IMPORT', path=record['path'], detail='Wildcard export resolution is not supported'))
        for imported, line in imports:
            target = resolve(imported)
            detail = dict(source=name, target=target or imported, line=line)
            if any(prefix(imported, p) for p in owner.get('forbidden', [])):
                findings.append(dict(code='FORBIDDEN_IMPORT', path=record['path'], detail=detail))
            if target:
                other = modules[target]['package']
                if target != name:
                    graph[name].add(target)
                if other != owner['name']:
                    package_graph[owner['name']].add(other)
                    edges.append(dict(detail, source_package=owner['name'], target_package=other))
                    if other not in owner.get('allow', []):
                        findings.append(dict(code='PACKAGE_DEPENDENCY', path=record['path'], detail=detail))
                    if not any(prefix(imported, public) for public in packages[other].get('public', [])):
                        findings.append(dict(code='PRIVATE_API', path=record['path'], detail=detail))
            elif imported.split('.')[0] not in standard and not any(prefix(imported, p) for p in owner.get('external', [])):
                findings.append(dict(code='UNRESOLVED_IMPORT', path=record['path'], detail=detail))
    for kind, values in (('MODULE_CYCLE', cycles(graph)), ('PACKAGE_CYCLE', cycles(package_graph))):
        findings.extend(dict(code=kind, detail=value) for value in values)
    impact_graph = {p: set(v) for p, v in package_graph.items()}
    for edge in config.get('runtime_edges', []):
        impact_graph[edge['from']].add(edge['to'])
    for resource in config.get('data_resources', []):
        participants = set(resource.get('readers', []) + resource.get('writers', []))
        for p in participants:
            impact_graph[p].update(participants - {p})
    changed = [] if changed is None else changed
    seeds, unknown = set(), []
    for filename in changed:
        assigned = {p['name'] for p in packages.values() if filename == p['root'].rstrip('/') or filename.startswith(p['root'].rstrip('/') + '/') or p['root'] == '.'}
        for resource in config.get('data_resources', []):
            if match(filename, resource.get('paths', [])):
                assigned.update(resource.get('readers', []) + resource.get('writers', []))
        seeds.update(assigned)
        if not assigned:
            unknown.append(filename)
    affected = set(seeds)
    while True:
        extra = {p for p, dependencies in impact_graph.items() if dependencies & affected} - affected
        if not extra:
            break
        affected.update(extra)
    # Unknown changes and dynamic imports defeat a reliable minimal test selection.
    full = bool(unknown or notes or any(f['code'] in ('DYNAMIC_IMPORT', 'UNRESOLVED_IMPORT', 'STAR_IMPORT') for f in findings))
    if full:
        affected = set(packages)
    return dict(result='FAIL' if findings else 'PASS', findings=findings, review_notes=notes,
                scope=dict(packages=list(packages), modules=len(modules), excludes=config.get('exclude', []),
                           native_packages=[p['name'] for p in packages.values() if p.get('language') == 'native']),
                package_edges=edges, runtime_edges=config.get('runtime_edges', []), data_resources=config.get('data_resources', []),
                impact=dict(changed=changed, directly_affected=sorted(seeds), affected=sorted(affected),
                            full_validation_required=full, unclassified_changes=unknown))


def goals(root, rules):
    """Check explicit syntactic goals; behavior remains the job of native tests."""
    result = []
    for rule in rules:
        kind = rule['kind']; path = inside(root, rule['path']); ok = False
        try:
            if kind in ('file_exists', 'file_absent'):
                ok = path.is_file() if kind == 'file_exists' else not path.exists()
            elif kind in ('symbol_exists', 'symbol_absent', 'calls', 'no_calls', 'docstring'):
                tree = ast.parse(path.read_text(encoding='utf-8'))
                node = tree
                for part in rule['symbol'].split('.'):
                    node = next((n for n in getattr(node, 'body', []) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == part), None)
                    if node is None:
                        break
                if kind == 'symbol_absent':
                    ok = node is None
                elif kind == 'symbol_exists':
                    ok = node is not None
                elif kind == 'docstring':
                    ok = node is not None and bool(ast.get_docstring(node))
                else:
                    def dotted(n):
                        return n.id if isinstance(n, ast.Name) else dotted(n.value) + '.' + n.attr if isinstance(n, ast.Attribute) else ''
                    observed = [dotted(n.func) for n in ast.walk(node) if isinstance(n, ast.Call)] if node else []
                    ok = node is not None and ((rule['callee'] in observed) == (kind == 'calls'))
            else:
                raise ProjectError('Unsupported goal kind: ' + kind)
            result.append(dict(id=rule['id'], result='PASS' if ok else 'FAIL', rule=rule))
        except (OSError, SyntaxError) as exc:
            result.append(dict(id=rule['id'], result='FAIL', reason=str(exc), rule=rule))
    return result
