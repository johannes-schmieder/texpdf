use std::{fs, path::Path};

use texpdf_core::{compile, CompileRequest};

fn crc32(data: &[u8]) -> u32 {
    let mut value = 0xffff_ffff_u32;
    for byte in data {
        value ^= u32::from(*byte);
        for _ in 0..8 {
            let mask = 0_u32.wrapping_sub(value & 1);
            value = (value >> 1) ^ (0xedb8_8320 & mask);
        }
    }
    !value
}

fn adler32(data: &[u8]) -> u32 {
    const MODULUS: u32 = 65_521;
    let mut first = 1_u32;
    let mut second = 0_u32;
    for byte in data {
        first = (first + u32::from(*byte)) % MODULUS;
        second = (second + first) % MODULUS;
    }
    (second << 16) | first
}

fn append_chunk(output: &mut Vec<u8>, kind: &[u8; 4], data: &[u8]) {
    output.extend_from_slice(&(data.len() as u32).to_be_bytes());
    output.extend_from_slice(kind);
    output.extend_from_slice(data);
    let mut checksum_input = Vec::with_capacity(kind.len() + data.len());
    checksum_input.extend_from_slice(kind);
    checksum_input.extend_from_slice(data);
    output.extend_from_slice(&crc32(&checksum_input).to_be_bytes());
}

fn write_one_pixel_png(path: &Path) {
    let mut output = b"\x89PNG\r\n\x1a\n".to_vec();
    let mut header = Vec::new();
    header.extend_from_slice(&1_u32.to_be_bytes());
    header.extend_from_slice(&1_u32.to_be_bytes());
    header.extend_from_slice(&[8, 2, 0, 0, 0]);
    append_chunk(&mut output, b"IHDR", &header);

    // One scanline: filter byte 0 followed by one red RGB pixel. The zlib
    // stream uses one uncompressed DEFLATE block so the fixture needs no image
    // or compression crate.
    let scanline = [0_u8, 255, 0, 0];
    let mut compressed = vec![0x78, 0x01, 0x01, 0x04, 0x00, 0xfb, 0xff];
    compressed.extend_from_slice(&scanline);
    compressed.extend_from_slice(&adler32(&scanline).to_be_bytes());
    append_chunk(&mut output, b"IDAT", &compressed);
    append_chunk(&mut output, b"IEND", &[]);
    fs::write(path, output).expect("write PNG fixture");
}

#[test]
fn embedded_engine_includes_a_png_figure() {
    let workspace = tempfile::tempdir().expect("temporary workspace");
    let input = workspace.path().join("figure.tex");
    let image = workspace.path().join("pixel.png");
    let output = workspace.path().join("figure.pdf");
    write_one_pixel_png(&image);
    fs::write(
        &input,
        r#"\documentclass{article}
\usepackage{graphicx}
\begin{document}
\includegraphics[width=10mm,height=10mm]{pixel.png}
\end{document}
"#,
    )
    .expect("write TeX fixture");

    let result = compile(&CompileRequest::new(&input, &output)).expect("compile PNG figure");
    assert!(fs::read(result.output)
        .expect("read generated PDF")
        .starts_with(b"%PDF-"));
}
