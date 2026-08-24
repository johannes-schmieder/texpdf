use std::fmt::Arguments;

use tectonic_errors::Error;
use tectonic_status_base::{MessageKind, StatusBackend};

const MAX_DIAGNOSTICS: usize = 200;
const MAX_MESSAGE_CHARS: usize = 4096;
const MAX_LOG_CHARS: usize = 65_536;

/// Severity of one captured engine diagnostic.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DiagnosticKind {
    /// Informational engine note.
    Note,
    /// Nonfatal warning.
    Warning,
    /// Error-level message.
    Error,
    /// Bounded excerpt from an engine error log.
    Log,
}

/// One bounded diagnostic suitable for Stata-facing reporting.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Diagnostic {
    /// Diagnostic severity.
    pub kind: DiagnosticKind,
    /// UTF-8, single-record message text.
    pub message: String,
}

#[derive(Debug, Default)]
pub(crate) struct DiagnosticCollector {
    items: Vec<Diagnostic>,
}

impl DiagnosticCollector {
    pub(crate) fn into_items(self) -> Vec<Diagnostic> {
        self.items
    }

    pub(crate) fn snapshot(&self) -> Vec<Diagnostic> {
        self.items.clone()
    }

    fn push(&mut self, kind: DiagnosticKind, message: String, limit: usize) {
        if self.items.len() >= MAX_DIAGNOSTICS {
            return;
        }
        let normalized = message.replace('\0', "\\0");
        self.items.push(Diagnostic {
            kind,
            message: truncate_chars(normalized, limit),
        });
    }
}

impl StatusBackend for DiagnosticCollector {
    fn report(&mut self, kind: MessageKind, args: Arguments<'_>, err: Option<&Error>) {
        let kind = match kind {
            MessageKind::Note => DiagnosticKind::Note,
            MessageKind::Warning => DiagnosticKind::Warning,
            MessageKind::Error => DiagnosticKind::Error,
        };
        let mut message = args.to_string();
        if let Some(error) = err {
            if !message.is_empty() {
                message.push_str(": ");
            }
            message.push_str(&format!("{error:#}"));
        }
        self.push(kind, message, MAX_MESSAGE_CHARS);
    }

    fn dump_error_logs(&mut self, output: &[u8]) {
        self.push(
            DiagnosticKind::Log,
            String::from_utf8_lossy(output).into_owned(),
            MAX_LOG_CHARS,
        );
    }
}

fn truncate_chars(mut text: String, limit: usize) -> String {
    if text.chars().count() <= limit {
        return text;
    }
    let byte_index = text
        .char_indices()
        .nth(limit)
        .map(|(index, _)| index)
        .unwrap_or(text.len());
    text.truncate(byte_index);
    text.push('…');
    text
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn truncation_preserves_utf8() {
        let result = truncate_chars("ééé".to_owned(), 2);
        assert_eq!(result, "éé…");
    }
}
