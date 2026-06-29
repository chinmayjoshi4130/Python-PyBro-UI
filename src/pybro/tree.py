# tree.py
import os
import json
import hashlib
import hmac
from . import state
from .state import logger  # use the centralized logger

class UINode:
    __slots__ = ('type', 'attrs', 'children')
    def __init__(self, type_, **attrs):
        self.type = type_
        self.attrs = attrs
        self.children = []

    def to_dict(self):
        d = {'type': self.type}
        d.update(self.attrs)
        return d


def flatten_tree(node):
    tokens = []
    def walk(n):
        if n.type == 'ROOT':
            for child in n.children:
                walk(child)
            return
        tokens.append(n.to_dict())
        for child in n.children:
            walk(child)
        end_map = {
            'SECTION_START': 'SECTION_END',
            'LAYOUT_ROW_START': 'LAYOUT_ROW_END',
            'PAGE_START': 'PAGE_END',
            'TAB_START': 'TAB_END',
            'TAB_GROUP_START': 'TAB_GROUP_END',
        }
        if n.type in end_map:
            tokens.append({'type': end_map[n.type]})
    walk(node)
    logger.debug(f"Flattened tree to {len(tokens)} tokens")
    return tokens


def find_node_by_id(root, target_id):
    stack = [root]
    while stack:
        node = stack.pop()
        if node.attrs.get('id') == target_id:
            return node
        stack.extend(node.children)
    logger.debug(f"Node with id='{target_id}' not found in tree")
    return None


def build_tree_from_flat(tokens):
    root = UINode('ROOT')
    stack = [root]
    end_map = {
        'SECTION_END': 'SECTION_START',
        'LAYOUT_ROW_END': 'LAYOUT_ROW_START',
        'PAGE_END': 'PAGE_START',
        'TAB_END': 'TAB_START',
        'TAB_GROUP_END': 'TAB_GROUP_START',
    }
    for tok in tokens:
        ttype = tok['type']
        attrs = {k: v for k, v in tok.items() if k != 'type'}
        if ttype in ('SECTION_START', 'LAYOUT_ROW_START', 'PAGE_START', 'TAB_START', 'TAB_GROUP_START'):
            node = UINode(ttype, **attrs)
            stack[-1].children.append(node)
            stack.append(node)
        elif ttype in ('SECTION_END', 'LAYOUT_ROW_END', 'PAGE_END', 'TAB_END', 'TAB_GROUP_END'):
            expected_type = end_map[ttype]
            if stack[-1].type == expected_type:
                stack.pop()
            else:
                logger.warn(f"Mismatched end token: expected {expected_type}, got {stack[-1].type}")
        else:
            node = UINode(ttype, **attrs)
            stack[-1].children.append(node)
    logger.debug(f"Built tree from {len(tokens)} flat tokens")
    return root


def link_tree(node, module):
    if node.type == 'ROOT':
        for child in node.children:
            link_tree(child, module)
        return
    if node.type == 'UI_TABLE':
        headers_ref = node.attrs.pop('headers_ref', None)
        rows_ref = node.attrs.pop('rows_ref', None)
        if headers_ref and module and hasattr(module, headers_ref):
            node.attrs['headers'] = getattr(module, headers_ref)
        elif headers_ref:
            logger.warn(f"Could not resolve table headers reference '{headers_ref}'")
        if rows_ref and module and hasattr(module, rows_ref):
            node.attrs['rows'] = getattr(module, rows_ref)
        elif rows_ref:
            logger.warn(f"Could not resolve table rows reference '{rows_ref}'")
    for child in node.children:
        link_tree(child, module)
    logger.debug(f"Linking complete for node type={node.type}")


def get_bundle_info():
    try:
        import tomllib as _toml
    except ImportError:
        import tomli as _toml

    EXCLUDE_DIRS = {'.git', '__pycache__', 'venv', '.venv', 'env', 'node_modules', '.mypy_cache', '.pytest_cache'}
    def collect_project_files(project_dir):
        files = []
        for root, dirs, filenames in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')]
            for fname in filenames:
                if fname.endswith('.py'):
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, project_dir)
                    files.append(rel)
        logger.debug(f"Collected {len(files)} .py files from project directory")
        return files

    if not state.PROJECT_DIR:
        logger.info("No project directory set; bundle info empty")
        return {'files': [], 'requires': []}

    requires = []
    include = None
    manifest_path = os.path.join(state.PROJECT_DIR, 'pybro.toml')
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, 'rb') as f:
                config = _toml.load(f)
            distribute = config.get('distribute', {})
            include = distribute.get('include')
            requires = distribute.get('requires', [])
            logger.debug(f"Read pybro.toml: include={include}, requires={requires}")
        except Exception as e:
            logger.warn(f"Could not parse pybro.toml: {e}")

    if include:
        files = []
        for pattern in include:
            full = os.path.join(state.PROJECT_DIR, pattern)
            if os.path.isfile(full):
                files.append(pattern)
            elif os.path.isdir(full):
                for root, _, fnames in os.walk(full):
                    for fn in fnames:
                        if fn.endswith('.py'):
                            rel = os.path.relpath(os.path.join(root, fn), state.PROJECT_DIR)
                            files.append(rel)
            else:
                logger.warn(f"Include pattern '{pattern}' not found, skipping")
        logger.info(f"Bundle includes {len(files)} specified files")
        return {'files': files, 'requires': requires}

    collected = collect_project_files(state.PROJECT_DIR)
    logger.info(f"Auto-collected {len(collected)} files for bundle")
    return {'files': collected, 'requires': requires}


def build_token_tree():
    if not state.PROJECT_DIR or not state.SESSION_KEY:
        state.PROJECT_TOKEN_TREE = None
        logger.debug("Skipping token tree build: missing project dir or session key")
        return

    bundle_info = get_bundle_info()
    files_dict = {}
    for rel_path in bundle_info['files']:
        full_path = os.path.join(state.PROJECT_DIR, rel_path)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                files_dict[rel_path] = f.read()
        except Exception as e:
            logger.warn(f"Could not read file {rel_path}: {e}")

    with state.tree_lock:
        tokens_flat = flatten_tree(state.UI_ROOT)

    payload = {
        "ui_tokens": tokens_flat,
        "files": files_dict,
        "requires": bundle_info['requires']
    }
    payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    sig = hmac.new(state.SESSION_KEY.encode('utf-8'), payload_json, hashlib.sha256).hexdigest()
    payload['signature'] = sig
    state.PROJECT_TOKEN_TREE = payload
    logger.info(f"Token tree built: {len(tokens_flat)} tokens, {len(files_dict)} files, signature valid")