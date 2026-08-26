from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class PluginDispatcherTests(unittest.TestCase):
    def test_dispatcher_is_platform_specific_and_reuses_verified_binding(self) -> None:
        source = (ROOT / "stata/texpdf.ado").read_text(encoding="utf-8")
        for name in (
            "_texpdf_plugin_macosx.plugin",
            "_texpdf_plugin_unix.plugin",
            "_texpdf_plugin_windows.plugin",
        ):
            self.assertIn(name, source)
        self.assertNotIn('using("_texpdf_plugin.plugin")', source)
        self.assertNotIn("program drop _texpdf_plugin", source)
        self.assertIn("if `load_rc' == 110", source)
        self.assertIn("$TEXPDF_NATIVE_PLUGIN_FILE", source)
        self.assertIn("unknown or stale native plugin", source)


if __name__ == "__main__":
    unittest.main()
