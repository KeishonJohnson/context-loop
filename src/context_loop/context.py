"""Explicit governing context, Obsidian retrieval and persistent owner approval."""
import hashlib
import json
import re
from pathlib import Path
from .storage import ContextLoopError, read_json, write_json, now

ROLES = ("instructions", "roadmap", "decisions", "status", "index", "spec", "research")
CORE = set(ROLES[:5])
CONTROL = "Context Loop"


def safe_path(path):
    path = Path(path).absolute()
    if path.resolve() != path:
        raise ContextLoopError(f"Context path contains a symlink or traversal: {path}")
    return path


def text_file(path):
    path = safe_path(path)
    if not path.is_file() or path.suffix.lower() != ".md":
        raise ContextLoopError(f"Governing source must be an existing Markdown file: {path}")
    if path.stat().st_size > 200_000:
        raise ContextLoopError(f"Source is too large; explicitly split it before adoption: {path}")
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeError as exc:
        raise ContextLoopError(f"Source is not UTF-8 Markdown: {path}") from exc


def instruction_paths(root, write_paths):
    paths = []
    for directory in reversed([root, *root.parents]):
        for name in ("AGENTS.md", "CLAUDE.md", "AGENTS.override.md"):
            path = directory / name
            if path.exists():
                paths.append(safe_path(path))
    for relative in write_paths:
        path = root / relative
        if path.is_dir():
            for candidate in sorted(path.rglob("*.md")):
                if candidate.name in ("AGENTS.md", "CLAUDE.md", "AGENTS.override.md"):
                    paths.append(safe_path(candidate))
    return list(dict.fromkeys(paths))


def under(path, directory):
    return path == directory or directory in path.parents


def prepare(root, config):
    """Read complete selected sources; never silently truncate governing text."""
    settings = config.get("context")
    if not isinstance(settings, dict):
        raise ContextLoopError("Existing projects require an explicit context map")
    if settings.get("conflicts"):
        raise ContextLoopError("Unresolved owner-recorded context conflicts")
    budget = settings.get("max_context_bytes", 120_000)
    if type(budget) is not int or not 1000 <= budget <= 500_000:
        raise ContextLoopError("max_context_bytes must be between 1000 and 500000")
    roots = settings.get("obsidian_roots", [])
    if not isinstance(roots, list) or any(not isinstance(p, str) or not p for p in roots):
        raise ContextLoopError("obsidian_roots must contain explicit path strings")
    vaults = [safe_path(p) for p in roots]
    for vault in vaults:
        if not vault.is_dir():
            raise ContextLoopError(f"Missing Obsidian root: {vault}")
    allowed = [root, *vaults]
    sources = {}
    entries = settings.get("sources", [])
    if not isinstance(entries, list) or len(entries) > 100:
        raise ContextLoopError("Define at most 100 explicit governing sources")
    for source in entries:
        if not isinstance(source, dict):
            raise ContextLoopError("Source mappings must be objects")
        ident = source.get("id", "")
        if not isinstance(ident, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", ident) or ident in sources:
            raise ContextLoopError("Source IDs must be unique safe identifiers")
        role = source.get("role")
        if role not in ROLES:
            raise ContextLoopError(f"Invalid role for source {ident}")
        if not isinstance(source.get("path"), str) or not source["path"]:
            raise ContextLoopError("Each governing source needs an explicit file path")
        raw = Path(source["path"])
        path = safe_path(raw if raw.is_absolute() else root / raw)
        if path.parent == root / CONTROL and path.name in {"Tasks.md", "Progress.md", "Index.md"}:
            raise ContextLoopError("Generated output notes cannot govern their own run")
        # Ancestor instructions are automatically applicable, but arbitrary
        # external research must be inside an explicitly declared Obsidian root.
        ancestor_instruction = role == "instructions" and path in instruction_paths(root, [])
        if not any(under(path, base) for base in allowed) and not ancestor_instruction:
            raise ContextLoopError(f"External source outside declared Obsidian roots: {ident}")
        content = text_file(path)
        sources[ident] = {"id": ident, "role": role, "path": str(path), "text": content,
                          "sha256": hashlib.sha256(content.encode()).hexdigest()}
    mapped = {Path(s["path"]) for s in sources.values() if s["role"] == "instructions"}
    expected = set(instruction_paths(root, config.get("write_paths", [])))
    if not expected <= mapped:
        raise ContextLoopError("Unmapped applicable instructions: " + ", ".join(str(p) for p in sorted(expected - mapped)))
    roles = {source["role"] for source in sources.values()}
    if not {"instructions", "roadmap", "decisions", "status"} <= roles:
        raise ContextLoopError("Map instructions, roadmap, decisions/constraints, and current status sources")
    requirements = settings.get("requirements", {})
    if not isinstance(requirements, dict) or not requirements:
        raise ContextLoopError("Define requirements quoted from governing documents")
    for ident, requirement in requirements.items():
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", ident) or not isinstance(requirement, dict):
            raise ContextLoopError("Invalid requirement definition")
        source = sources.get(requirement.get("source"))
        quote = requirement.get("quote")
        if not source or source["role"] not in {"roadmap", "decisions", "spec"} or not isinstance(quote, str) or len(quote.strip()) < 8 or quote not in source["text"]:
            raise ContextLoopError(f"Requirement {ident} must quote exact text from a mapped source")
    for task in config.get("tasks", []):
        refs = task.get("requirements")
        if not isinstance(refs, list) or not refs or any(not isinstance(r, str) for r in refs) or len(refs) != len(set(refs)) or any(r not in requirements for r in refs):
            raise ContextLoopError(f"Task {task.get('id')} needs approved requirement IDs")
        selected = task.get("context_sources", [])
        if not isinstance(selected, list) or any(not isinstance(s, str) or s not in sources for s in selected):
            raise ContextLoopError("Task references an unknown context source")

    def resolve_note(target, origin):
        target = target.split("|", 1)[0].split("#", 1)[0].strip()
        if not target:
            return None
        raw = Path(target)
        if raw.is_absolute() or ".." in raw.parts or ":" in target:
            raise ContextLoopError(f"Unsafe Obsidian note reference: {target}")
        filename = target if target.endswith(".md") else target + ".md"
        candidates = {p.absolute() for base in [origin.parent, *allowed] if (p := base / filename).is_file()}
        if len(raw.parts) == 1 and not candidates:
            for base in allowed:
                candidates.update(p.absolute() for p in base.rglob(filename) if ".git" not in p.parts and ".context-loop" not in p.parts)
                if len(candidates) > 1:
                    break
        if len(candidates) != 1:
            raise ContextLoopError(f"Missing or ambiguous Obsidian note: {target}; use an explicit path")
        path = safe_path(next(iter(candidates)))
        if not any(under(path, base) for base in allowed):
            raise ContextLoopError("Note escaped declared roots")
        return path

    catalog = {}
    for source in sources.values():
        if source["role"] == "index":
            for target in re.findall(r"\[\[([^\]]+)\]\]", source["text"]):
                path = resolve_note(target, Path(source["path"]))
                if path:
                    key = target.split("|", 1)[0].split("#", 1)[0].strip()
                    if key in catalog and catalog[key] != path:
                        raise ContextLoopError(f"Ambiguous index reference: {key}")
                    catalog[key] = path
    task_notes = {}
    for task in config.get("tasks", []):
        requested = task.get("notes", [])
        if not isinstance(requested, list) or any(not isinstance(n, str) or n not in catalog for n in requested):
            raise ContextLoopError("Task notes must name exact links from a mapped Obsidian index")
        paths = set()
        for name in requested:
            parent = catalog[name]
            paths.add(parent)
            for target in re.findall(r"\[\[([^\]]+)\]\]", text_file(parent)):
                child = resolve_note(target, parent)
                if child:
                    paths.add(child)
        ids = []
        for path in sorted(paths):
            ident = "note-" + hashlib.sha256(str(path).encode()).hexdigest()[:16]
            content = text_file(path)
            sources[ident] = {"id": ident, "role": "research", "path": str(path), "text": content,
                              "sha256": hashlib.sha256(content.encode()).hexdigest()}
            ids.append(ident)
        task_notes[task["id"]] = ids
    ordered = sorted(sources.values(), key=lambda s: (ROLES.index(s["role"]), len(Path(s["path"]).parents) if s["role"] == "instructions" else 0, s["id"]))
    # Audit includes the union of selected task notes, not the whole vault.
    if sum(len(s["text"].encode()) for s in ordered) > budget:
        raise ContextLoopError("Governing context exceeds budget; narrow the explicit source selection")
    return {"sources": ordered, "requirements": requirements, "task_notes": task_notes,
            "catalog": {k: str(v) for k, v in catalog.items()}}


def for_task(context, task):
    wanted = set(task.get("context_sources", [])) | set(context["task_notes"].get(task["id"], []))
    return [s for s in context["sources"] if s["role"] in CORE or s["id"] in wanted]


def source_manifest(sources):
    return [{k: s[k] for k in ("id", "role", "path", "sha256")} for s in sources]


def approval_path(root):
    return root / CONTROL / "Approval.json"


def verify_approval(root, digest):
    path = approval_path(root)
    if not path.is_file() or path.is_symlink():
        raise ContextLoopError("Context has not been approved; review it and run context-loop approve")
    approved = read_json(path)
    if approved.get("digest") != digest:
        raise ContextLoopError("Approved context has drifted; review source/task changes and approve explicitly")
    return approved


def validate_citations(value, sources):
    expected = {s["id"]: s["sha256"] for s in sources}
    rows = value.get("sources")
    if not isinstance(rows, list) or any(not isinstance(row, dict) or set(row) != {"id", "sha256"} or not isinstance(row.get("id"), str) or not isinstance(row.get("sha256"), str) for row in rows):
        raise ContextLoopError("Missing governing-source citations")
    actual = {row.get("id"): row.get("sha256") for row in rows}
    if len(actual) != len(rows) or actual != expected:
        raise ContextLoopError("Source citations differ from the loaded governing context")
