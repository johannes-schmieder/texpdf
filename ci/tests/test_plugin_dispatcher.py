from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class PluginDispatcherTests(unittest.TestCase):
    def test_dispatcher_supports_verified_github_and_ssc_bindings(self) -> None:
        source = (ROOT / "stata/texpdf.ado").read_text(encoding="utf-8")
        for name in (
            "_texpdf_plugin_macosx.plugin",
            "_texpdf_plugin_unix.plugin",
            "_texpdf_plugin_windows.plugin",
        ):
            self.assertIn(name, source)
        self.assertIn('local generic_plugin "_texpdf_plugin.plugin"', source)
        self.assertIn('_texpdf_ssc_install.ado', source)
        self.assertIn("local marker_version `\"`r(package_version)'\"'", source)
        self.assertIn("`\"`marker_distribution'\"' != \"ssc-gh-v1\"", source)
        self.assertIn("files from both GitHub and SSC installations", source)
        self.assertIn("stale generic native plugin without an SSC marker", source)
        self.assertIn("incomplete SSC installation", source)
        self.assertNotIn("program drop _texpdf_plugin", source)
        self.assertIn("if `load_rc' == 110", source)
        self.assertIn("$TEXPDF_NATIVE_PLUGIN_FILE", source)
        self.assertIn("unknown or stale native plugin", source)

    def test_ssc_pkg_uses_exact_platform_selection_and_load_check(self) -> None:
        lines = (ROOT / "stata/texpdf.pkg").read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            [line for line in lines if line.startswith("g ")],
            [
                "g LINUX64 _texpdf_plugin_unix.plugin _texpdf_plugin.plugin",
                "g MACINTEL64 _texpdf_plugin_macosx.plugin _texpdf_plugin.plugin",
                "g OSX.X8664 _texpdf_plugin_macosx.plugin _texpdf_plugin.plugin",
                "g MACARM64 _texpdf_plugin_macosx.plugin _texpdf_plugin.plugin",
                "g OSX.ARM64 _texpdf_plugin_macosx.plugin _texpdf_plugin.plugin",
                "g WIN64 _texpdf_plugin_windows.plugin _texpdf_plugin.plugin",
            ],
        )
        self.assertEqual(lines.count("h _texpdf_plugin.plugin"), 1)
        self.assertEqual(lines.count("f _texpdf_ssc_install.ado"), 1)


if __name__ == "__main__":
    unittest.main()
