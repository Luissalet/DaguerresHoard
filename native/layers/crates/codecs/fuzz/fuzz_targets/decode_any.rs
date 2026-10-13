// Modified for Daguerre: incorporated engine, own identity and historical import.
#![no_main]
//! Detect + decode arbitrary bytes, then re-encode what decoded (symmetry
//! path) — neither may panic.

use libfuzzer_sys::fuzz_target;
use daguerre_layers_codecs::{decode_with, encode, DecodeOptions, EncodeOptions, Limits};

fuzz_target!(|data: &[u8]| {
    let opts = DecodeOptions {
        limits: Limits { max_width: 4096, max_height: 4096, max_pixels: 1 << 22, max_alloc: 256 << 20 },
    };
    if let Ok(img) = decode_with(data, &opts)
        && let Some(f) = daguerre_layers_codecs::detect(data)
    {
        let _ = encode(&img, f, &EncodeOptions::default());
    }
});
