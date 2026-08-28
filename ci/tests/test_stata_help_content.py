import json
import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
HELP = ROOT / "stata/texpdf.sthlp"
CURATED_MANIFEST = ROOT / "bundle/curated-manifest.json"


def section(text: str, title: str, next_title: str) -> str:
    start = text.index(f"{{title:{title}}}")
    end = text.index(f"{{title:{next_title}}}", start)
    return text[start:end]


class StataHelpContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = HELP.read_text(encoding="utf-8")

    def test_example_two_names_texpdf_directly(self) -> None:
        self.assertIn(
            "the document. The document is compiled by {cmd:texpdf}.",
            self.text,
        )
        self.assertNotIn("rather than {cmd:latexlog: pdf}", self.text)

    def test_remarks_list_every_bundled_latex_interface(self) -> None:
        remarks = section(self.text, "Remarks", "Acknowledgements")
        manifest = json.loads(CURATED_MANIFEST.read_text(encoding="utf-8"))
        expected = {
            item["name"]
            for item in manifest["resources"]
            if item["name"].endswith((".sty", ".cls", ".bst"))
        }
        documented = set(re.findall(r"\{cmd:([^{}]+\.(?:sty|cls|bst))\}", remarks))
        self.assertEqual(documented, expected)
        self.assertIn("This version provides", remarks)
        self.assertNotIn("The private RC provides", remarks)
        for excluded_claim in ("Biber", "Beamer", "TikZ", "PSTricks", "unsupported"):
            self.assertNotIn(excluded_claim, remarks)

    def test_tectonic_acknowledgement_is_prominent_and_linked(self) -> None:
        acknowledgements = section(self.text, "Acknowledgements", "Also see")
        normalized = " ".join(acknowledgements.split())
        self.assertIn("only possible due to the amazing work", normalized)
        self.assertIn(
            '{browse "https://tectonic-typesetting.github.io/":Tectonic project}',
            acknowledgements,
        )
        self.assertIn("I am deeply grateful", normalized)

    def test_also_see_keeps_latexlog_and_etable_together(self) -> None:
        also_see = section(self.text, "Also see", "Author")
        self.assertIn("{help latexlog}, {help etable}", also_see)
        self.assertNotIn("{help latexlog}\n", also_see)
        self.assertEqual(also_see.count("{p_end}"), 1)

    def test_author_has_contact_links_and_invitation(self) -> None:
        author = self.text[self.text.index("{title:Author}") :]
        for required in (
            "Johannes Schmieder",
            'https://johannes-schmieder.com/',
            'https://github.com/johannes-schmieder',
            'mailto:johannes@bu.edu',
            "Suggestions welcome.",
        ):
            self.assertIn(required, author)


if __name__ == "__main__":
    unittest.main()
