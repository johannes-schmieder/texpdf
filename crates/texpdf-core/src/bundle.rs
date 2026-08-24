use std::{io::Cursor, sync::OnceLock};

use serde::Deserialize;
use tectonic_bundles::{zip::ZipBundle, Bundle};

use crate::TexPdfError;

static BUNDLE_BYTES: &[u8] = include_bytes!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../bundle/generated/texpdf-bundle.zip"
));
static BUNDLE_INFO_TEXT: &str = include_str!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../bundle/generated/bundle-info.json"
));
static BUNDLE_INFO: OnceLock<Result<BundleInfo, String>> = OnceLock::new();

/// Build-time provenance for the embedded resource bundle.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
pub struct BundleInfo {
    /// Metadata schema version.
    pub schema_version: u32,
    /// Source bundle identifier.
    pub bundle_name: String,
    /// Source bundle version.
    pub bundle_version: String,
    /// Transformer version.
    pub transform_version: String,
    /// SHA-256 of the raw indexed-tar stream, if a full stream was downloaded.
    pub source_sha256: String,
    /// SHA-256 of the compressed index.
    pub index_sha256: String,
    /// Tectonic content digest carried inside the bundle.
    pub tectonic_bundle_digest: String,
    /// SHA-256 of the deterministic embedded ZIP.
    pub zip_sha256: String,
    /// Number of logical files.
    pub file_count: usize,
    /// Compressed ZIP size.
    pub zip_size_bytes: u64,
}

/// Return validated metadata for the embedded bundle.
pub fn bundle_info() -> Result<&'static BundleInfo, TexPdfError> {
    match BUNDLE_INFO.get_or_init(|| {
        serde_json::from_str(BUNDLE_INFO_TEXT)
            .map_err(|error| format!("cannot parse bundle-info.json: {error}"))
    }) {
        Ok(info) => Ok(info),
        Err(message) => Err(TexPdfError::Bundle(message.clone())),
    }
}

pub(crate) fn open_bundle() -> Result<Box<dyn Bundle>, TexPdfError> {
    let cursor = Cursor::new(BUNDLE_BYTES);
    let bundle = ZipBundle::new(cursor)
        .map_err(|error| TexPdfError::Bundle(format!("cannot open embedded ZIP: {error:#}")))?;
    Ok(Box::new(bundle))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn embedded_bundle_opens_and_has_expected_digest() {
        let info = bundle_info().expect("bundle metadata");
        assert_eq!(info.schema_version, 1);
        assert!(info.file_count > 100);
        assert_eq!(info.tectonic_bundle_digest.len(), 64);
        let mut bundle = open_bundle().expect("open embedded bundle");
        let digest = bundle.get_digest().expect("bundle digest").to_string();
        assert_eq!(digest, info.tectonic_bundle_digest);
    }
}
