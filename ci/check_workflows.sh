#!/bin/bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
exec /usr/bin/ruby -rdate ci/check_workflows.rb
