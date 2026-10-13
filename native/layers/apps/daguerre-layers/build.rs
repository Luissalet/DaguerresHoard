// Modified for Daguerre: incorporated engine, own identity and historical import.
//! Windows only: embed the app icon and version info (VERSIONINFO) into `daguerre-layers.exe`.
//!
//! On every other target this does nothing. A missing resource compiler is a warning, so a
//! cross-compile from macOS or Linux still links, unless `DAGUERRE_LAYERS_REQUIRE_WINRES=1` (set by the
//! release workflow) turns it into an error.

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=../../assets/app-icon/daguerre-layers.ico");
    println!("cargo:rerun-if-env-changed=DAGUERRE_LAYERS_REQUIRE_WINRES");
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() != Ok("windows") {
        return;
    }
    let mut res = winresource::WindowsResource::new();
    res.set_icon("../../assets/app-icon/daguerre-layers.ico")
        .set("ProductName", "Daguerre Layers")
        .set("FileDescription", "Daguerre Layers image editor")
        .set("CompanyName", "Daguerre's Hoard")
        .set("LegalCopyright", "Copyright (c) the PhotoCraft authors. MIT OR Apache-2.0.")
        .set("OriginalFilename", "daguerre-layers.exe")
        .set("InternalName", "daguerre-layers");
    if let Err(e) = res.compile() {
        if std::env::var_os("DAGUERRE_LAYERS_REQUIRE_WINRES").is_some() {
            panic!("embedding Windows resources failed: {e}");
        }
        println!("cargo:warning=daguerre-layers.exe built without icon/version resources: {e}");
    }
}
