use std::{fs, io, path::Path};

use crate::TexPdfError;

/// Install a generated file, restoring an existing destination if installation
/// fails after replacement has begun.
pub(crate) fn install_file(
    generated: &Path,
    destination: &Path,
    context: &str,
) -> Result<(), TexPdfError> {
    if !destination.exists() {
        return fs::rename(generated, destination)
            .map_err(|error| TexPdfError::io(context, error));
    }

    let parent = destination.parent().ok_or_else(|| {
        TexPdfError::io(
            context,
            io::Error::new(io::ErrorKind::InvalidInput, "destination has no parent directory"),
        )
    })?;
    let backup = tempfile::Builder::new()
        .prefix(".texpdf-output-backup-")
        .tempfile_in(parent)
        .map_err(|error| TexPdfError::io("cannot reserve output rollback path", error))?;
    let backup_path = backup.into_temp_path();
    fs::remove_file(&backup_path)
        .map_err(|error| TexPdfError::io("cannot prepare output rollback path", error))?;
    fs::rename(destination, &backup_path)
        .map_err(|error| TexPdfError::io("cannot preserve existing output", error))?;

    match fs::rename(generated, destination) {
        Ok(()) => {
            // TempPath removes the preserved predecessor on drop. Failure to
            // clean a backup is not allowed to invalidate the newly installed
            // PDF; the OS will normally remove it here.
            drop(backup_path);
            Ok(())
        }
        Err(install_error) => {
            if let Err(restore_error) = fs::rename(&backup_path, destination) {
                let combined = io::Error::new(
                    install_error.kind(),
                    format!(
                        "{install_error}; rollback of the previous output also failed: {restore_error}"
                    ),
                );
                return Err(TexPdfError::io(context, combined));
            }
            Err(TexPdfError::io(context, install_error))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn installs_new_file() {
        let workspace = tempfile::tempdir().expect("tempdir");
        let generated = workspace.path().join("generated.pdf");
        let destination = workspace.path().join("output.pdf");
        fs::write(&generated, b"new").expect("write generated");
        install_file(&generated, &destination, "install").expect("install");
        assert_eq!(fs::read(destination).expect("read output"), b"new");
        assert!(!generated.exists());
    }

    #[test]
    fn replaces_existing_file() {
        let workspace = tempfile::tempdir().expect("tempdir");
        let generated = workspace.path().join("generated.pdf");
        let destination = workspace.path().join("output.pdf");
        fs::write(&generated, b"new").expect("write generated");
        fs::write(&destination, b"old").expect("write old output");
        install_file(&generated, &destination, "install").expect("replace");
        assert_eq!(fs::read(destination).expect("read output"), b"new");
    }

    #[test]
    fn restores_existing_file_when_installation_fails() {
        let workspace = tempfile::tempdir().expect("tempdir");
        let generated = workspace.path().join("missing.pdf");
        let destination = workspace.path().join("output.pdf");
        fs::write(&destination, b"old").expect("write old output");
        let error = install_file(&generated, &destination, "install")
            .expect_err("missing generated file must fail");
        assert!(matches!(error, TexPdfError::Io { .. }));
        assert_eq!(fs::read(destination).expect("read restored output"), b"old");
    }
}
