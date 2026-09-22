"""Offline DDD model, architecture, comment and execution evidence checks."""

import argparse
import ast
from datetime import datetime, timezone
import io
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import tokenize


SKILL_ROOT = Path(__file__).resolve().parents[1]
CHECKS = ("package", "model", "architecture", "comments", "tests")
RULE_ID = re.compile(r"^[A-Z][A-Z0-9]*-\d{3,}$")
RULE_MARKER = re.compile(r"Rules:\s*([^\n]+)")


class InputError(ValueError):
    """An input cannot be interpreted reliably; do not report a clean check."""


def safe_path(root, value):
    if not isinstance(value, str) or not value.strip() or Path(value).is_absolute():
        raise InputError("Expected a nonempty project-relative path: %r" % value)
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        raise InputError("Path escapes project: " + value)
    return path


def read_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise InputError("%s: %s" % (path, exc))
    if not isinstance(value, dict):
        raise InputError("%s must contain a JSON object" % path)
    return value


def require_text(item, field, location):
    if not isinstance(item.get(field), str) or not item[field].strip():
        raise InputError("%s.%s must be a nonempty string" % (location, field))


def require_list(item, field, location, nonempty=False, strings=True):
    value = item.get(field)
    if not isinstance(value, list) or (nonempty and not value):
        raise InputError("%s.%s must be %sa list" % (location, field, "a nonempty " if nonempty else ""))
    if strings and any(not isinstance(v, str) or not v.strip() for v in value):
        raise InputError("%s.%s must contain nonempty strings" % (location, field))


def validate_shape(model, policy):
    if type(model.get("version")) is not int or model["version"] != 1:
        raise InputError("model.version must be integer 1")
    fields = {
        "contexts": (("id", "name", "responsibility"), (), ()),
        "aggregates": (("id", "context", "root"), ("invariants",), ()),
        "rules": (("id", "kind", "statement", "source", "status", "owner"), ("symbols", "tests"), ()),
        "decisions": (("id", "problem", "evidence", "choice", "reason", "consequences", "solid", "verification"), ("alternatives",), ("rules",)),
        "responsibilities": (("symbol", "responsibility"), (), ("rules", "decisions")),
    }
    for collection, (texts, required_lists, lists) in fields.items():
        require_list(model, collection, "model", nonempty=True, strings=False)
        for index, item in enumerate(model[collection]):
            location = "%s[%d]" % (collection, index)
            if not isinstance(item, dict):
                raise InputError(location + " must be an object")
            for field in texts:
                require_text(item, field, location)
            for field in required_lists:
                require_list(item, field, location, nonempty=True)
            for field in lists:
                require_list(item, field, location)
    require_list(model, "reviews", "model", nonempty=True)
    for rule in model["rules"]:
        if not RULE_ID.fullmatch(rule["id"]):
            raise InputError("Invalid business rule ID: " + rule["id"])
        if rule["status"] not in ("confirmed", "assumption"):
            raise InputError("Invalid rule status: " + rule["id"])
        if rule["kind"] not in ("invariant", "contract"):
            raise InputError("Invalid rule kind: " + rule["id"])
    require_list(policy, "source_roots", "architecture", nonempty=True)
    require_list(policy, "layers", "architecture", nonempty=True, strings=False)
    require_text(policy, "test_dir", "architecture")
    require_list(policy, "exceptions", "architecture", strings=False)
    prefixes = []
    for layer in policy["layers"]:
        if not isinstance(layer, dict):
            raise InputError("Layer must be an object")
        require_text(layer, "prefix", "layer")
        if not all(p.isidentifier() for p in layer["prefix"].split(".")):
            raise InputError("Invalid layer prefix")
        require_list(layer, "allow", "layer")
        require_list(layer, "forbidden", "layer")
        prefixes.append(layer["prefix"])
    if len(set(prefixes)) != len(prefixes):
        raise InputError("Duplicate layer prefix")
    for layer in policy["layers"]:
        if set(layer["allow"]) - set(prefixes):
            raise InputError("Allowed layer does not exist: " + layer["prefix"])
    for item in policy["exceptions"]:
        if not isinstance(item, dict):
            raise InputError("Exception must be an object")
        for field in ("from", "to", "reason", "decision"):
            require_text(item, field, "exception")


def prefix_match(name, prefix):
    return name == prefix or name.startswith(prefix + ".")


class SourceIndex:
    """Inspect syntax without importing the target project."""

    def __init__(self, root, directories):
        self.modules = {}
        self.symbols = {}
        self.root = root
        for directory in directories:
            path = safe_path(root, directory)
            if not path.is_dir():
                raise InputError("Missing source/test directory: " + str(path))
            for file in sorted(path.rglob("*.py")):
                safe_path(root, str(file.relative_to(root)))
                relative = file.relative_to(root).with_suffix("")
                parts = list(relative.parts)
                if parts[-1] == "__init__":
                    parts.pop()
                module = ".".join(parts)
                if module in self.modules:
                    if self.modules[module]["path"] == file:
                        continue
                    raise InputError("Ambiguous module: " + module)
                try:
                    source = file.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(file))
                except (SyntaxError, UnicodeError, OSError) as exc:
                    raise InputError(str(exc))
                self.modules[module] = {"path": file, "tree": tree, "source": source}
                self.symbols[module] = (tree, file, module)
                self._definitions(tree.body, module, file, module)

    def _definitions(self, body, prefix, file, module):
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol = prefix + "." + node.name
                self.symbols[symbol] = (node, file, module)
                if isinstance(node, ast.ClassDef):
                    self._definitions(node.body, symbol, file, module)

    def has_test(self, name, seen=None):
        if name in self.symbols:
            return isinstance(self.symbols[name][0], (ast.FunctionDef, ast.AsyncFunctionDef))
        seen = set() if seen is None else seen
        if name in seen:
            return False
        seen.add(name)
        parent, _, method = name.rpartition(".")
        if parent not in self.symbols:
            return False
        node, _, module = self.symbols[parent]
        if not isinstance(node, ast.ClassDef):
            return False
        # Local mixins are statically resolvable; dynamic loaders require execution.
        return any(self.has_test(module + "." + base.id + "." + method, seen)
                   for base in node.bases if isinstance(base, ast.Name))


class Audit:
    def __init__(self, root, selected):
        self.root = root
        self.report = {
            "version": 1,
            "project": str(root),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "checks": {name: "not_run" for name in CHECKS},
            "automated_status": "passed",
            "semantic_status": "needs_review",
            "findings": [],
            "test_results": None,
            "scope": {},
            "exit_code": 0,
        }
        self.selected = selected

    def issue(self, check, code, location, message, suggestion, status="failed"):
        self.report["findings"].append(dict(check=check, code=code, status=status,
                                             location=str(location), message=message, suggestion=suggestion))
        if status in ("failed", "error"):
            current = self.report["checks"].get(check)
            if check in CHECKS and current != "error":
                self.report["checks"][check] = status
            self.report["exit_code"] = max(self.report["exit_code"], 2 if status == "error" else 1)

    def begin(self, check):
        self.report["checks"][check] = "passed"

    def model(self, model, index):
        self.begin("model")
        maps = {}
        for collection in ("contexts", "aggregates", "rules", "decisions"):
            items = model[collection]
            maps[collection] = {item["id"]: item for item in items}
            if len(maps[collection]) != len(items):
                self.issue("model", "MODEL-DUPLICATE", collection, "Duplicate IDs", "Use unique IDs")

        def references(values, targets, location):
            for value in values:
                if value not in targets:
                    self.issue("model", "MODEL-REFERENCE", location, "Unknown reference: " + value, "Repair the reference or add its explicit definition")

        for aggregate in model["aggregates"]:
            references([aggregate["context"]], maps["contexts"], aggregate["id"])
            references(aggregate["invariants"], maps["rules"], aggregate["id"])
            root = index.symbols.get(aggregate["root"])
            if root is None or not isinstance(root[0], ast.ClassDef):
                self.issue("model", "MODEL-ROOT", aggregate["id"], "Aggregate root must resolve to a class", "Correct root symbol")
            for rule_id in aggregate["invariants"]:
                rule = maps["rules"].get(rule_id)
                if rule and rule["kind"] != "invariant":
                    self.issue("model", "MODEL-RULE-KIND", aggregate["id"], "Behavior contract listed as an invariant: " + rule_id, "Keep adapter contracts separate from domain invariants")
                if rule and rule["owner"] != aggregate["id"]:
                    self.issue("model", "MODEL-OWNERSHIP", aggregate["id"], "Invariant owner disagrees: " + rule_id, "Assign one explicit primary owner")
        for rule in model["rules"]:
            references([rule["owner"]], maps["aggregates"], rule["id"])
            references(rule["symbols"], index.symbols, rule["id"])
            owner = maps["aggregates"].get(rule["owner"])
            if owner and rule["kind"] == "invariant" and rule["id"] not in owner["invariants"]:
                self.issue("model", "MODEL-OWNERSHIP", rule["id"], "Owner does not list this invariant", "Repair both sides of the ownership link")
            for test in rule["tests"]:
                if not index.has_test(test):
                    self.issue("model", "MODEL-TEST", rule["id"], "Test symbol cannot be resolved: " + test, "Provide a discoverable test or review dynamic test generation")
            if rule["status"] == "assumption":
                self.issue("model", "BUSINESS-ASSUMPTION", rule["id"], rule["statement"], "Confirm with the business owner", "needs_review")
        for decision in model["decisions"]:
            references(decision["rules"], maps["rules"], decision["id"])
        seen = set()
        for responsibility in model["responsibilities"]:
            symbol = responsibility["symbol"]
            if symbol in seen:
                self.issue("model", "MODEL-DUPLICATE", symbol, "Duplicate responsibility", "Consolidate responsibility records")
            seen.add(symbol)
            references([symbol], index.symbols, symbol)
            references(responsibility["rules"], maps["rules"], symbol)
            references(responsibility["decisions"], maps["decisions"], symbol)
            if not responsibility["rules"] and not responsibility["decisions"]:
                self.issue("model", "MODEL-RESPONSIBILITY", symbol, "Responsibility lacks a business or architecture basis", "Link a rule or decision")
        for rule in model["rules"]:
            for symbol in rule["symbols"]:
                if not any(prefix_match(symbol, r["symbol"]) and rule["id"] in r["rules"] for r in model["responsibilities"]):
                    self.issue("model", "MODEL-TRACE", symbol, "No responsibility linked to " + rule["id"], "Record the object or method responsible for this rule")

    def architecture(self, model, policy, index, source_modules):
        self.begin("architecture")
        layers = sorted(policy["layers"], key=lambda x: len(x["prefix"]), reverse=True)
        layer_for = lambda name: next((l for l in layers if prefix_match(name, l["prefix"])), None)
        graph = {name: set() for name in source_modules}
        decisions = {d["id"] for d in model["decisions"]}
        exceptions = {}
        for item in policy["exceptions"]:
            if item["decision"] not in decisions or item["from"] not in graph or item["to"] not in graph:
                raise InputError("Architecture exception references missing decision or module")
            exceptions[(item["from"], item["to"])] = item
        used = set()
        for module in sorted(source_modules):
            record = index.modules[module]
            source_layer = layer_for(module)
            if not source_layer:
                self.issue("architecture", "ARCH-UNCLASSIFIED", record["path"], "Source module is not assigned to a layer", "Add an explicit layer policy")
            package = module if record["path"].name == "__init__.py" else module.rpartition(".")[0]
            imports = []
            for node in ast.walk(record["tree"]):
                if isinstance(node, ast.Call) and (isinstance(node.func, ast.Name) and node.func.id == "__import__" or isinstance(node.func, ast.Attribute) and node.func.attr == "import_module"):
                    self.issue("architecture", "ARCH-DYNAMIC", "%s:%s" % (record["path"], node.lineno), "Dynamic import is outside static guarantees", "Review runtime dependency behavior", "needs_review")
                if isinstance(node, ast.Import):
                    imports.extend((alias.name, node.lineno) for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    base = node.module or ""
                    if node.level:
                        parts = package.split(".") if package else []
                        if node.level > len(parts):
                            self.issue("architecture", "ARCH-RELATIVE", record["path"], "Relative import escapes the package", "Correct the import")
                            continue
                        base = ".".join(parts[:len(parts) - node.level + 1] + ([base] if base else []))
                    imports.append((base, node.lineno))
                    for alias in node.names:
                        child = base + "." + alias.name if base else alias.name
                        if child in index.modules:
                            imports.append((child, node.lineno))
            for imported, line in imports:
                target = next((m for m in sorted(index.modules, key=len, reverse=True) if prefix_match(imported, m)), None)
                if target in graph and target != module:
                    graph[module].add(target)
                target_layer = layer_for(imported)
                forbidden = source_layer and any(prefix_match(imported, f) for f in source_layer["forbidden"])
                denied = source_layer and target_layer and target_layer["prefix"] not in source_layer["allow"]
                # Importing project tests from production is always outside declared layers.
                if target and target not in graph:
                    denied = True
                if forbidden or denied:
                    edge = (module, target or imported)
                    location = "%s:%s" % (record["path"], line)
                    if edge in exceptions:
                        used.add(edge)
                        self.issue("architecture", "ARCH-EXCEPTION", location, exceptions[edge]["reason"], "Review decision " + exceptions[edge]["decision"], "needs_review")
                    else:
                        self.issue("architecture", "ARCH-DEPENDENCY", location, module + " imports " + imported, "Use the owning layer's port or record a justified composition-root exception")
        for edge in exceptions.keys() - used:
            self.issue("architecture", "ARCH-UNUSED-EXCEPTION", " -> ".join(edge), "Exception is not used by a forbidden edge", "Remove stale exceptions", "needs_review")
        visited, active, stack = set(), set(), []

        def visit(module):
            visited.add(module)
            active.add(module)
            stack.append(module)
            for target in sorted(graph[module]):
                if target in active:
                    cycle = stack[stack.index(target):] + [target]
                    self.issue("architecture", "ARCH-CYCLE", module, " -> ".join(cycle), "Break the cycle through responsibilities or a stable port")
                elif target not in visited:
                    visit(target)
            stack.pop()
            active.remove(module)

        for module in sorted(graph):
            if module not in visited:
                visit(module)

    def comments(self, model, index, source_modules):
        self.begin("comments")
        known_rules = {r["id"] for r in model["rules"]}
        for symbol, (node, path, module) in index.symbols.items():
            if module not in source_modules:
                continue
            doc = ast.get_docstring(node) or ""
            private = any(part.startswith("_") for part in symbol[len(module):].strip(".").split(".") if part)
            if not private and not doc.strip() and (not isinstance(node, ast.Module) or node.body):
                self.issue("comments", "DOC-MISSING", "%s:%s" % (path, getattr(node, "lineno", 1)), "Missing public contract documentation: " + symbol, "Document business responsibility or behavior")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args
                names = {arg.arg for arg in args.posonlyargs + args.args + args.kwonlyargs}
                names.update(arg.arg for arg in (args.vararg, args.kwarg) if arg)
                in_args = False
                for text in doc.splitlines():
                    if text.strip() == "Args:":
                        in_args = True
                    elif in_args and text.strip():
                        if not text.startswith((" ", "\t")):
                            in_args = False
                            continue
                        match = re.match(r"\s*\*{0,2}(\w+)(?:\s*\([^)]*\))?:", text)
                        if match and match.group(1) not in names:
                            self.issue("comments", "DOC-PARAMETER", "%s:%s" % (path, node.lineno), "Unknown documented parameter: " + match.group(1), "Synchronize docstring with signature")
        for module in source_modules:
            record = index.modules[module]
            for token in tokenize.generate_tokens(io.StringIO(record["source"]).readline):
                if token.type not in (tokenize.STRING, tokenize.COMMENT):
                    continue
                for marker in RULE_MARKER.findall(token.string):
                    for rule_id in re.findall(r"[A-Z][A-Z0-9]*-\d{3,}", marker):
                        if rule_id not in known_rules:
                            self.issue("comments", "DOC-RULE", "%s:%s" % (record["path"], token.start[0]), "Unknown rule: " + rule_id, "Repair the annotation or define the rule")
        for rule in model["rules"]:
            for symbol in rule["symbols"]:
                if symbol in index.symbols:
                    node, path, _ = index.symbols[symbol]
                    doc = ast.get_docstring(node) or ""
                    marked = set(re.findall(r"[A-Z][A-Z0-9]*-\d{3,}", " ".join(RULE_MARKER.findall(doc))))
                    if rule["id"] not in marked:
                        self.issue("comments", "DOC-TRACE", "%s:%s" % (path, getattr(node, "lineno", 1)), "Missing Rules marker for " + rule["id"] + " on " + symbol, "Keep implementation contract linked to its business rule")

    def tests(self, model, policy, timeout):
        self.begin("tests")
        payload = run_tests(self.root, policy["test_dir"], timeout)
        self.report["test_results"] = payload
        if payload.get("fatal"):
            self.issue("tests", "TEST-RUNNER", self.root, payload["fatal"], "Fix discovery/runtime configuration and rerun", "error")
            return
        if payload["count"] == 0:
            self.issue("tests", "TEST-EMPTY", policy["test_dir"], "No tests executed", "Provide discoverable test_*.py tests")
        for test_id, outcome in payload["outcomes"].items():
            if outcome["status"] != "passed":
                self.issue("tests", "TEST-OUTCOME", test_id, outcome["status"] + ": " + outcome["detail"], "Resolve the failure or explicitly report unavailable evidence")
        for rule in model["rules"]:
            for test_id in rule["tests"]:
                outcome = payload["outcomes"].get(test_id)
                if outcome is None or outcome["status"] != "passed":
                    self.issue("tests", "TEST-RULE-EVIDENCE", rule["id"], "Required test did not pass: " + test_id, "Run the associated business contract successfully")

    def package(self):
        self.begin("package")
        entry = SKILL_ROOT / "SKILL.md"
        source = entry.read_text(encoding="utf-8")
        if not source.startswith("---\n") or not re.search(r"^name: ddd-python$", source, re.M) or not re.search(r"^description: .+", source, re.M):
            self.issue("package", "PACKAGE-METADATA", entry, "Missing skill metadata", "Repair name and description")
        for required in ("scripts/check.py", "scripts/test_runner.py", "tests/test_checks.py", "agents/openai.yaml"):
            if not (SKILL_ROOT / required).is_file():
                self.issue("package", "PACKAGE-FILE", required, "Required file missing", "Restore package resource")
        for path in sorted(SKILL_ROOT.rglob("*.md")):
            for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                target = link.split("#", 1)[0]
                if not target or "://" in target:
                    continue
                resolved = (path.parent / target).resolve()
                try:
                    resolved.relative_to(SKILL_ROOT)
                except ValueError:
                    self.issue("package", "PACKAGE-EXTERNAL", path, "Reference escapes skill: " + target, "Bundle required resources inside the skill")
                    continue
                if not resolved.exists():
                    self.issue("package", "PACKAGE-LINK", path, "Missing reference: " + target, "Repair link or include the file")


def run_tests(root, start, timeout):
    if not math.isfinite(timeout) or timeout <= 0:
        raise InputError("Test timeout must be finite and positive")
    safe_path(root, start)
    with tempfile.TemporaryDirectory(prefix="ddd-test-") as directory:
        result_file = Path(directory) / "result.json"
        command = [sys.executable, "-B", str(SKILL_ROOT / "scripts/test_runner.py"),
                   "--root", str(root), "--start", start, "--result", str(result_file)]
        environment = os.environ.copy()
        # Assertions in target tests must not disappear under an inherited -O setting.
        environment.pop("PYTHONOPTIMIZE", None)
        process = subprocess.Popen(command, cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, env=environment, start_new_session=(os.name == "posix"))
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.communicate()
            return {"fatal": "Test execution timed out after %s seconds" % timeout, "count": 0, "outcomes": {}}
        if not result_file.exists():
            return {"fatal": "Runner did not produce results (exit %s): %s" % (process.returncode, stderr or stdout), "count": 0, "outcomes": {}}
        result = read_json(result_file)
        if process.returncode != 0 and not result.get("fatal"):
            result["fatal"] = "Runner exited with code " + str(process.returncode)
        return result


def run_checks(root, selected=None, timeout=60):
    root = Path(root).resolve()
    selected = set(CHECKS if selected is None else selected)
    audit = Audit(root, selected)
    current_check = None
    try:
        if "package" in selected:
            current_check = "package"
            audit.package()
            current_check = None
        if selected - {"package"}:
            model = read_json(root / "model.json")
            policy = read_json(root / "architecture.json")
            validate_shape(model, policy)
            index = SourceIndex(root, policy["source_roots"] + [policy["test_dir"]])
            source_dirs = [safe_path(root, p) for p in policy["source_roots"]]
            source_modules = {name for name, record in index.modules.items()
                              if any(directory in record["path"].parents for directory in source_dirs)}
            if not any(record["tree"].body for name, record in index.modules.items() if name in source_modules):
                raise InputError("No nonempty Python source in source_roots")
            audit.report["scope"] = {"source_roots": policy["source_roots"], "source_modules": sorted(source_modules), "test_dir": policy["test_dir"]}
            for question in model["reviews"]:
                audit.issue("semantic", "REVIEW-REQUIRED", "model.json", question, "Review domain meaning and design tradeoffs", "needs_review")
            for check in ("model", "architecture", "comments", "tests"):
                if check not in selected:
                    continue
                current_check = check
                if check == "model":
                    audit.model(model, index)
                elif check == "architecture":
                    audit.architecture(model, policy, index, source_modules)
                elif check == "comments":
                    audit.comments(model, index, source_modules)
                else:
                    audit.tests(model, policy, timeout)
                current_check = None
    except (InputError, OSError, tokenize.TokenError) as exc:
        audit.issue("input", "INPUT-ERROR", root, str(exc), "Correct inputs and rerun", "error")
        if current_check is not None:
            audit.report["checks"][current_check] = "error"
    code = audit.report["exit_code"]
    audit.report["automated_status"] = "error" if code == 2 else "failed" if code else "passed"
    return audit.report


def markdown_report(report):
    lines = ["# DDD Python 检查报告", "", "自动检查：**%s**；语义评审：**%s**。" % (report["automated_status"], report["semantic_status"]),
             "", "项目：`%s`" % report["project"], "", "| 检查 | 状态 |", "|---|---|"]
    lines.extend("| %s | %s |" % item for item in report["checks"].items())
    lines.extend(["", "覆盖目录：`%s`" % ", ".join(report["scope"].get("source_roots", [])), "", "## 发现", ""])
    for finding in report["findings"]:
        lines.extend(["- **%s / %s** — `%s`" % (finding["code"], finding["status"], finding["location"]),
                      "  " + finding["message"].replace("\n", "\n  "), "  建议：" + finding["suggestion"]])
    if report["test_results"] is not None:
        lines.extend(["", "实际测试数：%s。完整执行结果见 JSON 报告。" % report["test_results"]["count"]])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=SKILL_ROOT / "assets/order_example")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    for name in CHECKS:
        parser.add_argument("--" + name, action="store_true")
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be finite and positive")
    if args.self_test:
        if args.all or any(getattr(args, name) for name in CHECKS) or args.json or args.markdown:
            parser.error("--self-test is a separate mode; use --all for project reports")
        result = run_tests(SKILL_ROOT, "tests", args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get("fatal") else int(not result["count"] or any(x["status"] != "passed" for x in result["outcomes"].values()))
    selected = {name for name in CHECKS if getattr(args, name)}
    report = run_checks(args.project, None if args.all or not selected else selected, args.timeout)
    for destination, content in ((args.json, json.dumps(report, ensure_ascii=False, indent=2) + "\n"),
                                 (args.markdown, markdown_report(report))):
        if destination:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
    print("Automated: %s | Semantic: %s" % (report["automated_status"], report["semantic_status"]))
    for name, status in report["checks"].items():
        print("%s: %s" % (name, status))
    for finding in report["findings"]:
        if finding["status"] in ("failed", "error"):
            print("%s %s: %s" % (finding["code"], finding["location"], finding["message"]))
    if report["test_results"] is not None:
        print("Tests executed:", report["test_results"]["count"])
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
