from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"


class ReadmeContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = README.read_text(encoding="utf-8")

    def test_project_state_is_short_and_current(self) -> None:
        start = self.text.index("## Project state")
        end = self.text.index("## Acknowledgements", start)
        project_state = self.text[start:end]
        self.assertLess(len(project_state.split()), 100)
        self.assertIn("0.1.0-rc2", project_state)
        self.assertIn("untested Intel compatibility slice", project_state)
        self.assertNotIn("it is not a stable distribution channel", self.text)
        self.assertNotIn("Historical private RC evidence is preserved", self.text)

    def test_tectonic_acknowledgement_is_generous_and_linked(self) -> None:
        start = self.text.index("## Acknowledgements")
        end = self.text.index("## Installation channels", start)
        acknowledgements = " ".join(self.text[start:end].split())
        self.assertIn("only possible because of the amazing work", acknowledgements)
        self.assertIn("https://tectonic-typesetting.github.io/", acknowledgements)
        self.assertIn(
            "https://github.com/tectonic-typesetting/tectonic",
            acknowledgements,
        )
        self.assertIn("I am deeply grateful", acknowledgements)


if __name__ == "__main__":
    unittest.main()
