"""Tests for code parsing utilities."""

import unittest

from manim_generator.utils.parsing import parse_code_block


class TestParseCodeBlock(unittest.TestCase):
    """Test cases for parse_code_block."""

    def test_closed_fence(self):
        text = 'Here is code:\n```python\nfrom manim import *\n```'
        self.assertEqual(parse_code_block(text), "from manim import *")

    def test_unclosed_fence(self):
        text = "```python\nfrom manim import *\nclass Intro(Scene):\n    pass"
        self.assertEqual(
            parse_code_block(text),
            "from manim import *\nclass Intro(Scene):\n    pass",
        )

    def test_strips_thinking_blocks(self):
        text = "planning\n```python\nfrom manim import *\n```"
        self.assertEqual(parse_code_block(text), "from manim import *")

    def test_strips_trailing_prose_and_fixes_cyan(self):
        text = (
            "from manim import *\n\n"
            "class Intro(Scene):\n"
            "    def construct(self):\n"
            "        dot = Dot(ORIGIN, color=CYAN, glow_factor=2)\n"
            "        self.add(dot)\n\n"
            "I'll explain the animation next.\n"
        )
        parsed = parse_code_block(text)
        self.assertNotIn("I'll explain", parsed)
        self.assertIn("TEAL", parsed)
        self.assertNotIn("glow_factor", parsed)


if __name__ == "__main__":
    unittest.main()
