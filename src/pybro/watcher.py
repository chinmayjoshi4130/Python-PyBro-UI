# watcher.py
import os
import time
import ast
import importlib.util
import traceback
import json

from . import state
from .parser import PybroUIParser
from .tree import link_tree, flatten_tree, build_token_tree

logger = state.logger  # direct reference for readability

def watch_script(script_path, connectable=False):
    last_mtime = os.path.getmtime(script_path)
    while True:
        time.sleep(2)
        try:
            current_mtime = os.path.getmtime(script_path)
            if current_mtime != last_mtime:
                logger.info("Script change detected. Re‑compiling...")
                with open(script_path, "r") as f:
                    ast_tree = ast.parse(f.read())
                parser_obj = PybroUIParser()
                parser_obj.visit(ast_tree)
                new_root = parser_obj.root
                module_name = os.path.splitext(os.path.basename(script_path))[0]
                spec = importlib.util.spec_from_file_location(module_name, script_path)
                new_module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(new_module)
                except Exception as e:
                    logger.warn(f"Could not reload module: {e}")
                    logger.debug(traceback.format_exc())
                link_tree(new_root, new_module)
                with state.tree_lock:
                    state.UI_ROOT = new_root
                    state.TARGET_MODULE = new_module
                    flat = flatten_tree(state.UI_ROOT)
                if state.PROJECT_DIR and state.SESSION_KEY and connectable:
                    build_token_tree()
                state.broadcast_event("tokens_updated", json.dumps(flat))
                logger.info("Re‑compile successful. UI refreshed.")
                last_mtime = current_mtime
        except FileNotFoundError:
            logger.warn("Watched script disappeared.")
            break
        except Exception as e:
            logger.error(f"Error during re‑compile: {e}")
            logger.debug(traceback.format_exc())