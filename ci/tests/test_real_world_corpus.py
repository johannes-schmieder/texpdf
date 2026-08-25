import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ci/check_real_world_corpus.py"
SPEC = importlib.util.spec_from_file_location("check_real_world_corpus", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
CORPUS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CORPUS)

GENERATOR_PATH = ROOT / "tools/check_latexlog_fixture.py"
GENERATOR_SPEC = importlib.util.spec_from_file_location(
    "check_latexlog_fixture", GENERATOR_PATH
)
assert GENERATOR_SPEC is not None and GENERATOR_SPEC.loader is not None
GENERATOR = importlib.util.module_from_spec(GENERATOR_SPEC)
GENERATOR_SPEC.loader.exec_module(GENERATOR)


class RealWorldCorpusTests(unittest.TestCase):
    def test_repository_corpus_is_valid(self):
        result = CORPUS.validate_manifest(
            ROOT / "tests/fixtures/real-world/manifest.json",
            ROOT / "ci/stata_real_world_corpus.do",
        )
        self.assertEqual(result["fixture_count"], 3)

    def test_rejects_duplicate_ids_before_compilation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "one.tex").write_text("source", encoding="utf-8")
            manifest = {
                "schema_version": 1,
                "permitted_engine_diagnostics": [
                    {"kind": "note", "contains": "Running TeX"}
                ],
                "fixtures": [
                    {
                        "id": "same",
                        "entrypoint": "one.tex",
                        "assets": ["one.tex"],
                        "capabilities": ["test"],
                        "provenance": {
                            "kind": "synthetic-derivative",
                            "description": "test",
                        },
                        "permitted_diagnostics": [],
                    },
                    {
                        "id": "same",
                        "entrypoint": "one.tex",
                        "assets": ["one.tex"],
                        "capabilities": ["test"],
                        "provenance": {
                            "kind": "synthetic-derivative",
                            "description": "test",
                        },
                        "permitted_diagnostics": [],
                    },
                ],
            }
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            stata = root / "runner.do"
            stata.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(CORPUS.CorpusError, "duplicate fixture id"):
                CORPUS.validate_manifest(path, stata)

    def test_rejects_unsafe_relative_path(self):
        with self.assertRaisesRegex(CORPUS.CorpusError, "unsafe"):
            CORPUS.safe_relative("../outside.tex", "fixture")

    def test_latexlog_normalization_changes_only_timestamp(self):
        source = "% 25 Aug 2026 17:12:03\nline with 17:12:03\n"
        normalized = GENERATOR.normalize_tex(
            source, "% LATEXLOG GENERATED TIMESTAMP"
        )
        self.assertEqual(
            normalized,
            "% LATEXLOG GENERATED TIMESTAMP\nline with 17:12:03\n",
        )

    def test_latexlog_normalization_rejects_non_timestamp_header(self):
        with self.assertRaisesRegex(GENERATOR.ContractError, "timestamp"):
            GENERATOR.normalize_tex("% generated\nbody\n", "% normalized")


if __name__ == "__main__":
    unittest.main()
