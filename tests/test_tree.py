# tests/test_tree.py
import unittest
import sys
import os

# Make sure the package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from pybro.tree import UINode, flatten_tree, find_node_by_id, build_tree_from_flat

class TestFlattenTree(unittest.TestCase):
    def setUp(self):
        # Build a simple tree: root -> page -> section -> input
        self.root = UINode('ROOT')
        page = UINode('PAGE_START', name="Test")
        section = UINode('SECTION_START', id="sec1", visible=True)
        inp = UINode('UI_INPUT', id="inp1", label="Name")
        # Build hierarchy
        self.root.children.append(page)
        page.children.append(section)
        section.children.append(inp)

    def test_flatten_preserves_structure(self):
        tokens = flatten_tree(self.root)
        types = [t['type'] for t in tokens]
        self.assertIn('PAGE_START', types)
        self.assertIn('PAGE_END', types)
        self.assertIn('SECTION_START', types)
        self.assertIn('SECTION_END', types)
        self.assertIn('UI_INPUT', types)

    def test_input_token_attributes(self):
        tokens = flatten_tree(self.root)
        inp_token = next(t for t in tokens if t['type'] == 'UI_INPUT')
        self.assertEqual(inp_token['id'], 'inp1')
        self.assertEqual(inp_token['label'], 'Name')

    def test_end_tokens_after_children(self):
        tokens = flatten_tree(self.root)
        # Find section_start position and ensure section_end comes after children
        start_idx = next(i for i, t in enumerate(tokens) if t['type'] == 'SECTION_START')
        input_idx = next(i for i, t in enumerate(tokens) if t['type'] == 'UI_INPUT')
        end_idx = next(i for i, t in enumerate(tokens) if t['type'] == 'SECTION_END')
        self.assertTrue(start_idx < input_idx < end_idx)


class TestFindNodeById(unittest.TestCase):
    def test_find_existing(self):
        root = UINode('ROOT')
        child = UINode('UI_TEXT_AREA', id="output", value="")
        root.children.append(child)
        node = find_node_by_id(root, "output")
        self.assertIsNotNone(node)
        self.assertEqual(node.attrs['value'], "")

    def test_not_found(self):
        root = UINode('ROOT')
        self.assertIsNone(find_node_by_id(root, "missing"))


class TestBuildTreeFromFlat(unittest.TestCase):
    def test_roundtrip(self):
        # Create a known flat list
        flat = [
            {'type': 'PAGE_START', 'name': 'Main'},
            {'type': 'UI_TITLE', 'text': 'Hello'},
            {'type': 'PAGE_END'}
        ]
        root = build_tree_from_flat(flat)
        self.assertEqual(root.children[0].type, 'PAGE_START')
        self.assertEqual(root.children[0].children[0].type, 'UI_TITLE')
        # After flattening back, should match original (excluding optional attrs)
        tokens_back = flatten_tree(root)
        self.assertEqual(tokens_back[0]['type'], 'PAGE_START')
        self.assertEqual(tokens_back[1]['type'], 'UI_TITLE')
        self.assertEqual(tokens_back[2]['type'], 'PAGE_END')


if __name__ == '__main__':
    unittest.main()