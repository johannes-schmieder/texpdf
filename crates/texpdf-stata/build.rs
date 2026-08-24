use std::{env, fs, path::PathBuf};

use sha2::{Digest, Sha256};

fn main() {
    println!("cargo:rerun-if-env-changed=TEXPDF_HELPER_PATH");

    let out_dir = PathBuf::from(env::var_os("OUT_DIR").expect("OUT_DIR is set by Cargo"));
    let destination = out_dir.join("texpdf-helper.bin");
    let helper = env::var_os("TEXPDF_HELPER_PATH").map(PathBuf::from).unwrap_or_else(|| {
        panic!(
            "TEXPDF_HELPER_PATH must identify the target-matching texpdf-helper executable; build the helper before texpdf-stata"
        )
    });
    println!("cargo:rerun-if-changed={}", helper.display());
    let metadata = fs::metadata(&helper).unwrap_or_else(|error| {
        panic!(
            "cannot inspect TEXPDF_HELPER_PATH {}: {error}",
            helper.display()
        )
    });
    if !metadata.is_file() || metadata.len() == 0 {
        panic!(
            "TEXPDF_HELPER_PATH must identify a nonempty regular file: {}",
            helper.display()
        );
    }
    let bytes = fs::read(&helper).unwrap_or_else(|error| {
        panic!(
            "cannot read TEXPDF_HELPER_PATH {}: {error}",
            helper.display()
        )
    });
    let target = env::var("TARGET").expect("TARGET is set by Cargo");
    validate_architecture(&bytes, &target).unwrap_or_else(|error| {
        panic!(
            "TEXPDF_HELPER_PATH {} does not match target {target}: {error}",
            helper.display()
        )
    });
    fs::write(&destination, &bytes).unwrap_or_else(|error| {
        panic!("cannot embed helper at {}: {error}", destination.display())
    });
    println!(
        "cargo:rustc-env=TEXPDF_EMBEDDED_HELPER_SIZE={}",
        bytes.len()
    );
    println!(
        "cargo:rustc-env=TEXPDF_EMBEDDED_HELPER_SHA256={:x}",
        Sha256::digest(&bytes)
    );
}

fn validate_architecture(bytes: &[u8], target: &str) -> Result<(), &'static str> {
    if target.ends_with("-apple-darwin") {
        if bytes.len() < 8 || bytes[..4] != [0xcf, 0xfa, 0xed, 0xfe] {
            return Err("expected a thin 64-bit little-endian Mach-O executable");
        }
        let cpu = u32::from_le_bytes(bytes[4..8].try_into().expect("four-byte slice"));
        let expected = if target.starts_with("aarch64-") {
            0x0100_000c
        } else if target.starts_with("x86_64-") {
            0x0100_0007
        } else {
            return Err("unsupported macOS target architecture");
        };
        return (cpu == expected)
            .then_some(())
            .ok_or("Mach-O CPU type does not match Cargo TARGET");
    }

    if target.ends_with("-unknown-linux-gnu") {
        if bytes.len() < 20 || bytes[..4] != *b"\x7fELF" || bytes[4] != 2 {
            return Err("expected a 64-bit ELF executable");
        }
        let machine = u16::from_le_bytes(bytes[18..20].try_into().expect("two-byte slice"));
        let expected = if target.starts_with("x86_64-") {
            62
        } else if target.starts_with("aarch64-") {
            183
        } else {
            return Err("unsupported Linux target architecture");
        };
        return (machine == expected)
            .then_some(())
            .ok_or("ELF machine does not match Cargo TARGET");
    }

    if target.ends_with("-pc-windows-msvc") {
        if bytes.len() < 0x40 || bytes[..2] != *b"MZ" {
            return Err("expected a PE executable");
        }
        let offset =
            u32::from_le_bytes(bytes[0x3c..0x40].try_into().expect("four-byte slice")) as usize;
        if bytes.get(offset..offset + 4) != Some(b"PE\0\0") {
            return Err("invalid PE signature");
        }
        let machine_bytes = bytes
            .get(offset + 4..offset + 6)
            .ok_or("truncated PE COFF header")?;
        let machine = u16::from_le_bytes(machine_bytes.try_into().expect("two-byte slice"));
        let expected = if target.starts_with("x86_64-") {
            0x8664
        } else if target.starts_with("aarch64-") {
            0xaa64
        } else {
            return Err("unsupported Windows target architecture");
        };
        return (machine == expected)
            .then_some(())
            .ok_or("PE machine does not match Cargo TARGET");
    }

    Err("unsupported Cargo target")
}
