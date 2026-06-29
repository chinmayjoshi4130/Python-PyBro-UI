# parser.py
import ast
from .tree import UINode


class PybroUIParser(ast.NodeVisitor):
    def __init__(self):
        self.root = UINode('ROOT')
        self.stack = [self.root]

    def _safe_literal(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Call):
            return None
        try:
            return ast.literal_eval(node)
        except (ValueError, TypeError):
            return None

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            if node.func.value.id == 'ui':
                func_name = node.func.attr
                args = []
                for arg in node.args:
                    val = self._safe_literal(arg)
                    args.append(val)

                kwargs = {}
                for kw in node.keywords:
                    if kw.arg == 'css':
                        try:
                            kwargs['css'] = ast.literal_eval(kw.value)
                        except Exception:
                            kwargs['css'] = {}
                    elif kw.arg == 'class_':
                        try:
                            kwargs['class'] = ast.literal_eval(kw.value)
                        except Exception:
                            kwargs['class'] = ''
                    elif kw.arg == 'target_id':
                        try:
                            kwargs['target_id'] = ast.literal_eval(kw.value)
                        except Exception:
                            kwargs['target_id'] = None
                    elif kw.arg == 'visible':
                        try:
                            kwargs['visible'] = ast.literal_eval(kw.value)
                        except Exception:
                            kwargs['visible'] = True
                    else:
                        try:
                            kwargs[kw.arg] = ast.literal_eval(kw.value)
                        except Exception:
                            kwargs[kw.arg] = None

                token_type = None
                attrs = {}

                # --- structural tokens ---
                if func_name == 'section_start' and args:
                    token_type = "SECTION_START"
                    attrs = {"id": args[0], "visible": kwargs.get("visible", True)}
                elif func_name == 'section_end':
                    token_type = "SECTION_END"
                elif func_name == 'page_start' and args:
                    token_type = "PAGE_START"
                    attrs = {"name": args[0]}
                elif func_name == 'page_end':
                    token_type = "PAGE_END"
                elif func_name == 'tab_group_start':
                    token_type = "TAB_GROUP_START"
                elif func_name == 'tab_start' and args:
                    token_type = "TAB_START"
                    attrs = {"name": args[0]}
                elif func_name == 'tab_end':
                    token_type = "TAB_END"
                elif func_name == 'tab_group_end':
                    token_type = "TAB_GROUP_END"

                # --- visual tokens ---
                elif func_name == 'title' and args:
                    token_type = "UI_TITLE"
                    attrs = {"text": args[0]}
                elif func_name == 'row_start':
                    token_type = "LAYOUT_ROW_START"
                elif func_name == 'row_end':
                    token_type = "LAYOUT_ROW_END"
                elif func_name == 'input_text' and len(args) >= 2:
                    token_type = "UI_INPUT"
                    attrs = {"id": args[0], "label": args[1]}
                elif func_name == 'checkbox' and len(args) >= 2:
                    token_type = "UI_CHECKBOX"
                    attrs = {"id": args[0], "label": args[1]}
                elif func_name == 'dropdown' and len(args) >= 3:
                    token_type = "UI_DROPDOWN"
                    attrs = {"id": args[0], "label": args[1], "options": args[2]}
                elif func_name == 'text_area' and len(args) >= 2:
                    token_type = "UI_TEXT_AREA"
                    attrs = {"id": args[0], "label": args[1], "value": ""}
                elif func_name == 'button_callback' and len(args) >= 2:
                    target = kwargs.get('target_id', None)
                    if target is None and len(args) >= 3:
                        target = args[2]
                    token_type = "UI_CALLBACK_BUTTON"
                    attrs = {"text": args[0], "callback_name": args[1], "target_id": target}
                elif func_name == 'math_compute' and len(args) >= 2:
                    token_type = "UI_MATH_COMPUTE"
                    attrs = {"target_id": args[0], "formula": args[1]}
                elif func_name == 'os_command' and len(args) >= 3:
                    token_type = "OS_GATEKEEPER"
                    attrs = {"cmd": args[0], "desc": args[1], "target_id": args[2]}
                elif func_name == 'table' and len(args) >= 2:
                    token_type = "UI_TABLE"
                    if isinstance(args[0], str) and not args[0].isdigit():
                        attrs["headers_ref"] = args[0]
                    else:
                        attrs["headers"] = args[0]
                    if len(args) >= 2:
                        if isinstance(args[1], str) and not args[1].isdigit():
                            attrs["rows_ref"] = args[1]
                        else:
                            attrs["rows"] = args[1]
                    table_id = kwargs.get('target_id', None)
                    if table_id is None and len(args) >= 3:
                        table_id = args[2]
                    if table_id:
                        attrs["id"] = table_id
                # --- Markdown block ---
                elif func_name == 'markdown' and args:
                    token_type = "UI_MARKDOWN"
                    attrs = {"text": args[0]}
                # --- Slider ---
                elif func_name == 'slider' and len(args) >= 3:
                    token_type = "UI_SLIDER"
                    attrs = {
                        "id": args[0],
                        "label": args[1],
                        "min": args[2] if len(args) >= 3 else 0,
                        "max": args[3] if len(args) >= 4 else 100,
                        "step": args[4] if len(args) >= 5 else 1
                    }
                elif func_name == 'password' and len(args) >= 2:
                    token_type = "UI_PASSWORD"
                    attrs = {"id": args[0], "label": args[1]}
                elif func_name == 'toggle' and len(args) >= 2:
                    token_type = "UI_TOGGLE"
                    attrs = {"id": args[0], "label": args[1], "checked": bool(args[2]) if len(args) >= 3 else False}
                elif func_name == 'progress' and len(args) >= 2:
                    token_type = "UI_PROGRESS"
                    attrs = {
                        "id": args[0],
                        "label": args[1],
                        "value": args[2] if len(args) >= 3 else 0,
                        "max": args[3] if len(args) >= 4 else 100
                    }
                elif func_name == 'date' and args:
                    token_type = "UI_DATE"
                    attrs = {"id": args[0], "label": args[1] if len(args) >= 2 else ""}
                elif func_name == 'input' and len(args) >= 2:
                    token_type = "UI_INPUT_GENERIC"
                    attrs = {"id": args[0], "label": args[1], "input_type": args[2] if len(args) >= 3 else "text"}
                elif func_name == 'root_css' and len(args) >= 1:
                    token_type = "UI_ROOT_CSS"
                    attrs = {"css_vars": args[0]}
                else:
                    token_type = None

                if token_type is not None:
                    if 'css' in kwargs:
                        attrs['css'] = kwargs['css']
                    if 'class' in kwargs:
                        attrs['class'] = kwargs['class']
                    new_node = UINode(token_type, **attrs)

                    if token_type in ('SECTION_START', 'LAYOUT_ROW_START', 'PAGE_START', 'TAB_START', 'TAB_GROUP_START'):
                        self.stack[-1].children.append(new_node)
                        self.stack.append(new_node)
                    elif token_type in ('SECTION_END', 'LAYOUT_ROW_END', 'PAGE_END', 'TAB_END', 'TAB_GROUP_END'):
                        if len(self.stack) > 1:
                            self.stack.pop()
                    else:
                        self.stack[-1].children.append(new_node)

        self.generic_visit(node)