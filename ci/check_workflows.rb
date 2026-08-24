#!/usr/bin/env ruby
# frozen_string_literal: true

require "yaml"

root = File.expand_path("..", __dir__)
workflow_dir = File.join(root, ".github", "workflows")
paths = Dir.glob(File.join(workflow_dir, "*.{yml,yaml}")).sort
abort("no GitHub Actions workflows found") if paths.empty?

failures = []
paths.each do |path|
  begin
    payload = YAML.safe_load(
      File.read(path, encoding: "UTF-8"),
      permitted_classes: [Date, Time],
      aliases: true
    )
    failures << "#{path}: top-level YAML value is not a mapping" unless payload.is_a?(Hash)
  rescue StandardError => error
    failures << "#{path}: #{error.class}: #{error.message}"
  end
end

unless failures.empty?
  warn failures.join("\n")
  exit 1
end

puts "TEXPDF_WORKFLOW_YAML_PASS workflows=#{paths.length}"
