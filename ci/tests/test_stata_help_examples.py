import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
HELP = ROOT / "stata/texpdf.sthlp"


def example_blocks(text: str) -> dict[str, str]:
    lines = text.splitlines()
    blocks: dict[str, str] = {}
    index = 0
    while index < len(lines):
        match = re.fullmatch(r"\{\* example_start - ([a-z0-9_-]+)\}\{\.\.\.\}", lines[index])
        if match is None:
            index += 1
            continue
        identifier = match.group(1)
        if identifier in blocks:
            raise AssertionError(f"duplicate example id: {identifier}")
        end = index + 1
        while end < len(lines) and lines[end] != "{* example_end}{...}":
            end += 1
        if end == len(lines):
            raise AssertionError(f"example has no end marker: {identifier}")
        block = "\n".join(lines[index + 1 : end])
        blocks[identifier] = block.replace("{c -(}", "{").replace("{c )-}", "}")
        index = end + 1
    return blocks


class StataHelpExampleTests(unittest.TestCase):
    def test_repository_help_has_three_runnable_examples(self) -> None:
        text = HELP.read_text(encoding="utf-8")
        blocks = example_blocks(text)
        self.assertEqual(set(blocks), {"manual", "latexlog", "etable"})
        links = re.findall(
            r"\{stata texpdf_run ([a-z0-9_-]+) using texpdf\.sthlp, preserve:",
            text,
        )
        self.assertEqual(links, ["manual", "latexlog", "etable"])
        self.assertEqual(text.count("{* example_end}{...}"), 3)
        self.assertLessEqual(max(map(len, text.splitlines())), 244)

    def test_manual_example_builds_table_figure_tex_and_pdf(self) -> None:
        block = example_blocks(HELP.read_text(encoding="utf-8"))["manual"]
        for required in (
            "table foreign",
            "collect export",
            "graph export",
            "file write",
            "texpdf using",
            "replace view",
        ):
            self.assertIn(required, block)
        self.assertIn("\\input{table.tex}", block)
        self.assertNotIn("\\begin{table}", block)
        self.assertNotIn("{c -(", block)
        self.assertNotIn("{c )-}", block)

    def test_latexlog_example_is_optional_and_compiles_with_texpdf(self) -> None:
        block = example_blocks(HELP.read_text(encoding="utf-8"))["latexlog"]
        self.assertIn("capture which latexlog", block)
        self.assertIn("latexlog/v0.5.0/", block)
        self.assertIn("table occupation union", block)
        self.assertIn("latexlog `report': collect export", block)
        self.assertIn("texpdf using", block)
        self.assertIn("replace view", block)
        self.assertNotIn("latexlog `report': pdf", block)

    def test_etable_example_builds_three_model_regression_table(self) -> None:
        block = example_blocks(HELP.read_text(encoding="utf-8"))["etable"]
        self.assertEqual(block.count("quietly regress price"), 3)
        self.assertEqual(block.count("estimates store model"), 3)
        for required in (
            "etable, estimates(model1 model2 model3) column(index)",
            "keep(mpg weight foreign _cons)",
            "cstat(_r_b, nformat(%9.2f))",
            "cstat(_r_se, nformat(%9.2f))",
            'mstat(N, label("Observations"))',
            'mstat(r2_a, label("Adjusted R-squared") nformat(%9.3f))',
            'stars(.10 "*" .05 "**" .01 "***") showstars showstarsnote',
            'title("Price regressions")',
            "regression-table.tex\", tableonly replace",
            "file write",
            "\\input{regression-table.tex}",
            "texpdf using",
            "replace view",
        ):
            self.assertIn(required, block)
        self.assertNotIn("ulem", block)
        self.assertNotIn("{c -(", block)
        self.assertNotIn("{c )-}", block)

    def test_runner_is_installable(self) -> None:
        self.assertTrue((ROOT / "stata/texpdf_run.ado").is_file())
        package = (ROOT / "stata/texpdf.pkg").read_text(encoding="utf-8")
        self.assertEqual(package.count("f texpdf_run.ado"), 1)


if __name__ == "__main__":
    unittest.main()
