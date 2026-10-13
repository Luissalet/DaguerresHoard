// Modified for Daguerre: incorporated engine, own identity and historical import.
//! Native platform services: file dialogs (rfd), filesystem, codecs.

use daguerre_layers_codecs::{ChannelLayout, EncodeOptions, Image, SampleType as CS};
use daguerre_layers_color::{ColorMode, SampleType};
use daguerre_layers_doc::{Document, Layer, Size};
use daguerre_layers_format::Autosaver;
use daguerre_layers_geom::Rect;
use daguerre_layers_ui_egui::Services;
use std::cell::RefCell;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::rc::Rc;
use std::sync::Arc;

/// Everything File › Open reads: Daguerre Layers and Photoshop documents, flat images, and Photoshop
/// brushes (.abr) and gradients (.grd), which go to the preset libraries.
const OPEN_EXTS: &[&str] = &[
    "dglayers", "pcraft", "psd", "psb", "png", "jpg", "jpeg", "tif", "tiff", "webp", "gif", "bmp", "tga", "ico", "qoi", "exr", "hdr", "pbm", "pgm", "ppm", "pam", "pfm",
    "dng", "cr2", "cr3", "nef", "nrw", "arw", "pef", "orf", "rw2", "raf", "abr", "grd",
];

/// File › Save As formats: (filter name, extensions). The filter matching the suggested name's
/// extension comes first, so a .dglayers document saves as .dglayers by default and everything else
/// keeps defaulting to Photoshop.
const SAVE_FILTERS: &[(&str, &[&str])] =
    &[("Photoshop", &["psd", "psb"]), ("Daguerre Layers", &["dglayers"]), ("PNG", &["png"]), ("JPEG", &["jpg"]), ("TIFF", &["tif"]), ("OpenEXR", &["exr"])];

/// [`SAVE_FILTERS`] with the one for `suggested`'s extension first.
fn save_filters(suggested: &str) -> Vec<(&'static str, &'static [&'static str])> {
    let ext = Path::new(suggested).extension().map(|e| e.to_string_lossy().to_ascii_lowercase()).unwrap_or_default();
    let mut v = SAVE_FILTERS.to_vec();
    if let Some(i) = v.iter().position(|(_, exts)| exts.contains(&ext.as_str())) {
        let f = v.remove(i);
        v.insert(0, f);
    }
    v
}

/// Per-user settings directory: `DAGUERRE_LAYERS_CONFIG_DIR`, else the platform convention
/// (macOS `~/Library/Application Support/Photocraft`, Windows `%APPDATA%\Photocraft`, Linux
/// `$XDG_CONFIG_HOME/daguerre-layers` or `~/.config/daguerre-layers`).
pub fn config_dir() -> Option<PathBuf> {
    if let Some(d) = std::env::var_os("DAGUERRE_LAYERS_CONFIG_DIR") {
        return Some(PathBuf::from(d));
    }
    let home = std::env::var_os("HOME").map(PathBuf::from);
    if cfg!(target_os = "macos") {
        return home.map(|h| h.join("Library/Application Support/DaguerreLayers"));
    }
    if cfg!(windows) {
        return std::env::var_os("APPDATA").map(|a| PathBuf::from(a).join("DaguerreLayers"));
    }
    std::env::var_os("XDG_CONFIG_HOME").map(PathBuf::from).or_else(|| home.map(|h| h.join(".config"))).map(|c| c.join("daguerre-layers"))
}

fn prefs_file() -> Option<PathBuf> {
    config_dir().map(|d| d.join("preferences.json"))
}

/// The brush preset store (one file per preset group plus tip bitmaps; see
/// `daguerre_layers_engine::preset_store`).
pub fn presets_dir() -> Option<PathBuf> {
    config_dir().map(|d| d.join("Presets"))
}

fn recovery_dir() -> Option<PathBuf> {
    config_dir().map(|d| d.join("Recovery"))
}

/// Write `bytes` atomically (temp file + rename) so a crash never leaves half a preferences file.
fn write_atomic(path: &Path, bytes: &[u8]) -> Result<(), String> {
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
    }
    let tmp = path.with_extension("tmp");
    std::fs::write(&tmp, bytes).map_err(|e| e.to_string())?;
    std::fs::rename(&tmp, path).map_err(|e| e.to_string())
}

pub fn native(automation: Option<daguerre_layers_automation::AuthorizedWorkspace>) -> Services {
    let savers: Rc<RefCell<HashMap<u64, Autosaver>>> = Rc::default();
    let savers2 = savers.clone();
    let automation_read = automation.clone().map(|workspace| {
        Box::new(move |path: &str| {
            let bytes = workspace.read(path).map_err(|error| error.to_string())?;
            let name = Path::new(path).file_name().and_then(|name| name.to_str()).unwrap_or(path).to_string();
            Ok((name, bytes))
        }) as daguerre_layers_ui_egui::AutomationReadFn
    });
    let automation_write = automation.clone().map(|workspace| {
        Box::new(move |path: &str, bytes: &[u8]| workspace.write(path, bytes).map_err(|error| error.to_string())) as daguerre_layers_ui_egui::AutomationWriteFn
    });
    let automation_command = automation.map(|_| {
        Box::new(|id: &str, params: &serde_json::Value| {
            daguerre_layers_automation::workspace::authorize_desktop_engine_command(id, params).map_err(|error| error.to_string())
        }) as daguerre_layers_ui_egui::AutomationCommandFn
    });
    Services {
        import: Some(Box::new(|name: &str, bytes: &[u8]| {
            crate::crash_guard::guard("Open", || daguerre_layers_io::import(name, bytes).map(|r| (r.document, r.warnings)).map_err(|e| e.to_string()))
        })),
        export: Some(Box::new(|doc: &Document, path: &str, settings: &daguerre_layers_ui_egui::ExportSettings| {
            let mut opts = daguerre_layers_io::ExportOptions::default();
            if let Some(q) = settings.jpeg_quality {
                opts.encode.jpeg_quality = q;
            }
            crate::crash_guard::guard("Export", || daguerre_layers_io::export(doc, path, &opts).map(|r| (r.bytes, r.warnings)).map_err(|e| e.to_string()))
        })),
        pick_open: Some(Box::new(|| {
            let path = rfd::FileDialog::new().add_filter("All Formats", OPEN_EXTS).add_filter("Daguerre Layers", &["dglayers"]).pick_file()?;
            let bytes = std::fs::read(&path).ok()?;
            Some((path.to_string_lossy().to_string(), bytes))
        })),
        pick_save: Some(Box::new(|suggested: &str| {
            let p = std::path::Path::new(suggested);
            let mut d = rfd::FileDialog::new();
            for (name, exts) in save_filters(suggested) {
                d = d.add_filter(name, exts);
            }
            if let Some(name) = p.file_name() {
                d = d.set_file_name(name.to_string_lossy());
            }
            Some(d.save_file()?.to_string_lossy().to_string())
        })),
        write: Some(Box::new(|path: &str, bytes: &[u8]| std::fs::write(path, bytes).map_err(|e| e.to_string()))),
        automation_read,
        automation_write,
        automation_command,
        encode_png: Some(Box::new(|w, h, rgba| {
            let img = Image::from_u8(w, h, ChannelLayout::Rgba, rgba.to_vec()).map_err(|e| e.to_string())?;
            daguerre_layers_codecs::encode(&img, daguerre_layers_codecs::Format::Png, &EncodeOptions::default()).map_err(|e| e.to_string())
        })),
        inbox: None,
        open_url: Some(Box::new(|url: &str| open::that(url).map_err(|e| e.to_string()))),
        clipboard_set_image: Some(Box::new(|w: u32, h: u32, px: &[u8]| {
            let mut cb = arboard::Clipboard::new().map_err(|e| e.to_string())?;
            cb.set_image(arboard::ImageData { width: w as usize, height: h as usize, bytes: std::borrow::Cow::Borrowed(px) }).map_err(|e| e.to_string())
        })),
        clipboard_get_image: Some(Box::new(|| {
            let img = arboard::Clipboard::new().ok()?.get_image().ok()?;
            Some((img.width as u32, img.height as u32, img.bytes.into_owned()))
        })),
        load_prefs: Some(Box::new(|| std::fs::read_to_string(prefs_file()?).ok())),
        save_prefs: Some(Box::new(|text: &str| write_atomic(&prefs_file().ok_or("no config directory")?, text.as_bytes()))),
        // Crash recovery: background incremental .dglayers saves into the recovery directory.
        autosave: Some(Box::new(move |doc: &Arc<Document>, revision: u64, path: Option<&str>| {
            let dir = recovery_dir().ok_or("no config directory")?;
            let mut map = savers.borrow_mut();
            let saver = map.entry(doc.id.0).or_insert_with(|| Autosaver::new(&dir, &format!("doc-{}", doc.id.0)));
            saver.request(doc.clone(), revision, path.map(str::to_string), Default::default());
            Ok(())
        })),
        discard_autosave: Some(Box::new(move |id: u64| {
            if let Some(s) = savers2.borrow_mut().remove(&id) {
                let _ = s.discard();
            }
        })),
        recover: Some(Box::new(|| {
            let Some(dir) = recovery_dir() else { return Vec::new() };
            let mut out = Vec::new();
            for entry in daguerre_layers_format::list_recovery(&dir) {
                if let Ok(doc) = daguerre_layers_format::recover(&entry) {
                    out.push((entry.info.original_path.clone(), doc));
                }
                // Recovered documents autosave again under their new ids.
                let _ = daguerre_layers_format::discard_recovery(&dir, &entry);
            }
            out
        })),
        append_text: Some(Box::new(|path: &str, text: &str| {
            use std::io::Write;
            let mut f = std::fs::OpenOptions::new().create(true).append(true).open(path).map_err(|e| e.to_string())?;
            f.write_all(text.as_bytes()).map_err(|e| e.to_string())
        })),
        // Set by main once the Apple-event handlers are connected (macOS).
        os_events: None,
        // Set by main, which starts loading the store before the window opens.
        preset_store: None,
    }
}

/// Flat-image import via daguerre-layers-codecs (kept for reference/tests; the app uses daguerre-layers-io).
#[allow(dead_code)]
pub fn import_flat(name: &str, bytes: &[u8]) -> Result<Document, String> {
    let img = daguerre_layers_codecs::decode(bytes).map_err(|e| e.to_string())?;
    let (w, h) = (img.width(), img.height());
    let depth = match img.sample_type() {
        CS::U8 => SampleType::U8,
        CS::U16 => SampleType::U16,
        _ => SampleType::F32,
    };
    let gray = matches!(img.layout(), ChannelLayout::Gray | ChannelLayout::GrayA);
    let cmyk = matches!(img.layout(), ChannelLayout::Cmyk | ChannelLayout::CmykA);
    let mode = if gray {
        ColorMode::Grayscale
    } else if cmyk {
        ColorMode::Cmyk
    } else {
        ColorMode::Rgb
    };
    let target = match mode {
        ColorMode::Grayscale => ChannelLayout::GrayA,
        ColorMode::Cmyk => ChannelLayout::CmykA,
        _ => ChannelLayout::Rgba,
    };
    let sample = match depth {
        SampleType::U8 => CS::U8,
        SampleType::U16 => CS::U16,
        SampleType::F32 => CS::F32,
    };
    let conv = img.convert(target, sample);
    let stem = std::path::Path::new(name).file_stem().map(|s| s.to_string_lossy().to_string()).unwrap_or(name.to_string());
    let mut doc = Document::new(stem, Size::new(w, h), mode, depth);
    doc.icc_profile = img.icc.clone().map(std::sync::Arc::new);
    if let Some((x, _)) = img.meta.dpi {
        doc.resolution_dpi = x;
    }
    let mut layer = Layer::raster("Background", doc.pixel_format());
    let data = conv.to_normalized();
    layer.surface_mut().ok_or("new raster layer has no pixels")?.write_region(Rect::from_xywh(0, 0, w, h), &data);
    doc.layers.push(layer);
    Ok(doc)
}

#[allow(dead_code)]
pub fn export_flat(doc: &Document, path: &str) -> Result<Vec<u8>, String> {
    let format = daguerre_layers_codecs::from_extension(path).ok_or_else(|| format!("unknown file type for {path}"))?;
    let buf = daguerre_layers_compose::flatten(doc);
    let (w, h) = (buf.rect.width(), buf.rect.height());
    let data: Vec<f32> = buf.px.iter().flat_map(|p| *p).collect();
    let img = match doc.depth {
        SampleType::U8 => Image::from_u8(w, h, ChannelLayout::Rgba, buf.to_rgba8().pixels),
        SampleType::U16 => Image::from_u16(w, h, ChannelLayout::Rgba, &data.iter().map(|v| (v.clamp(0.0, 1.0) * 65535.0 + 0.5) as u16).collect::<Vec<_>>()),
        SampleType::F32 => Image::from_f32(w, h, ChannelLayout::Rgba, &data),
    }
    .map_err(|e| e.to_string())?;
    let img = match &doc.icc_profile {
        Some(icc) if doc.mode == ColorMode::Rgb => img.with_icc(Some((**icc).clone())),
        _ => img,
    };
    daguerre_layers_codecs::encode(&img, format, &EncodeOptions::default()).map_err(|e| e.to_string())
}
