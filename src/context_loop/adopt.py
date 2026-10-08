"""Additive adoption scaffolds; never rewrite an existing project's instructions."""
import hashlib
import json
import uuid
from pathlib import Path
from .context import CONTROL, ROLES, safe_path, instruction_paths, prepare, source_manifest
from .config import load, contract_digest, existing, validate_write_paths
from .storage import ContextLoopError, atomic_text, write_json, initial_state, save_state, now, lock
from .templates import starter


def inspect_project(project):
    root = safe_path(project)
    if not root.is_dir():
        raise ContextLoopError("Project must be an existing directory")
    candidates = []
    for folder in (root, root / "docs", root / "documentation"):
        if folder.is_dir():
            for path in sorted(folder.glob("*.md")):
                candidates.append(str(path.relative_to(root)))
    return {"project": str(root), "instructions": [str(p) for p in instruction_paths(root, [])],
            "document_candidates": list(dict.fromkeys(candidates)),
            "next": "Map actual source roles and requirements; inspection does not approve or modify anything"}


def attach(project, source_specs=(), write_paths=(), indexes=(), vaults=()):
    root = safe_path(project)
    if not root.is_dir() or root == Path.home() or root == Path(root.anchor):
        raise ContextLoopError("Choose a specific existing project directory")
    names = [root / "context-loop.json", root / CONTROL, root / ".context-loop"]
    if any(p.exists() or p.is_symlink() for p in names):
        raise ContextLoopError("Attachment paths already exist; refusing to overwrite anything")
    config, _ = starter(False)
    config.update(version=2, mode="existing", workspace=".", write_paths=list(write_paths), tasks=[])
    if write_paths:
        validate_write_paths(root, config)
    sources = []
    for spec in source_specs:
        parts = spec.split(":", 2)
        if len(parts) != 3 or parts[1] not in ROLES:
            raise ContextLoopError("Use --source ID:ROLE:PATH with an explicit source role")
        sources.append({"id": parts[0], "role": parts[1], "path": parts[2]})
    supplied = {safe_path(Path(s["path"]) if Path(s["path"]).is_absolute() else root / s["path"]) for s in sources if s["role"] == "instructions"}
    for path in instruction_paths(root, write_paths):
        if path not in supplied:
            sources.append({"id": "instruction-" + hashlib.sha256(str(path).encode()).hexdigest()[:12], "role": "instructions", "path": str(path)})
    roots = [str(safe_path(v)) for v in vaults]
    for index, name in enumerate(indexes):
        path = safe_path(name)
        sources.append({"id": f"obsidian-index-{index + 1}", "role": "index", "path": str(path)})
        if not any(Path(v) == path.parent or Path(v) in path.parents for v in roots):
            roots.append(str(path.parent))
    config["context"] = {"sources": sources, "requirements": {}, "obsidian_roots": roots,
                         "max_context_bytes": 120_000, "conflicts": []}
    # Only the dedicated new files are created. No original file is appended,
    # moved, or reformatted, including .gitignore and AGENTS.md.
    target = root / CONTROL
    target.mkdir()
    (target / "checks").mkdir()
    atomic_text(target / "Setup.md", "# Context Loop adoption\n\nThis is a context map, not a replacement build plan.\nMap actual instructions, roadmap, decisions and current status in ../context-loop.json.\nDefine exact requirement quotations and task checks before approval.\nReview source roles and explicit write paths. Then approve with an owner decision note.\nKeep governance changes separate from execution. Existing documents remain authoritative.\nNo project instructions or Git configuration were changed.\n")
    atomic_text(target / "Index.md", "# Context Loop project view\n\n- [[Tasks]]: task requirements and acceptance evidence.\n- [[Progress]]: progress, governing-source hashes and alignment review.\n- [[Setup]]: adoption instructions.\n\nGoverning sources are configured in ../context-loop.json.\n")
    write_json(root / "context-loop.json", config)
    state = initial_state(config)
    state["reason"] = "Attachment scaffold only; map sources, requirements, tasks and write paths, then approve"
    save_state(root, state, config)
    return root


def approve(project, note):
    if not note or not note.strip():
        raise ContextLoopError("Approval requires an explicit owner decision note")
    root, config = load(project)
    if not existing(config):
        raise ContextLoopError("Approval applies to attached existing projects")
    with lock(root):
        state_path = root / ".context-loop/state.json"
        from .storage import read_json
        state = read_json(state_path) if state_path.exists() else {}
        if state.get("child_pid"):
            import os
            try:
                os.kill(state["child_pid"], 0)
            except ProcessLookupError:
                pass
            else:
                raise ContextLoopError("Prior child is alive; inspect it before approving")
        context = prepare(root, config)
        value = {"version": 1, "id": uuid.uuid4().hex, "approved_at": now(), "note": note.strip(),
                 "digest": contract_digest(root, config), "sources": source_manifest(context["sources"])}
        write_json(root / CONTROL / "Approval.json", value)
        from urllib.parse import quote
        lines = ["# Context Loop project view", "", "- [[Tasks]]: requirements and acceptance evidence.", "- [[Progress]]: changes, source hashes and alignment review.", "- [[Setup]]: adoption instructions.", "", "## Approved governing sources", ""]
        for source in context["sources"]:
            path = Path(source["path"])
            link = quote("../" + path.relative_to(root).as_posix(), safe="/") if root in path.parents else path.as_uri()
            lines.append(f"- {source['role']} / [{source['id']}]({link})")
        lines += ["", "## Owner approval", "", value["note"], "", "Source edits require reviewed approval before another run."]
        atomic_text(root / CONTROL / "Index.md", "\n".join(lines) + "\n")
        return value
