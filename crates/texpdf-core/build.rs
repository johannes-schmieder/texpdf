use std::path::PathBuf;

fn main() {
    let root = PathBuf::from("../..").join("bundle").join("generated");
    println!(
        "cargo:rerun-if-changed={}",
        root.join("texpdf-bundle.zip").display()
    );
    println!(
        "cargo:rerun-if-changed={}",
        root.join("bundle-info.json").display()
    );
}
