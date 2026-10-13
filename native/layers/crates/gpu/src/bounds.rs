// Modified for Daguerre: incorporated engine, own identity and historical import.
//! Layer bounds exactly as `daguerre-layers-compose` computes them (`layer_bounds`), with the per-tile
//! content scan cached by copy-on-write tile identity, so an effect layer's region costs a hash
//! lookup per tile instead of a pixel scan per frame.

use daguerre_layers_doc::Layer;
use daguerre_layers_geom::Rect;
#[cfg(test)]
use daguerre_layers_raster::Surface;

pub use daguerre_layers_compose::bounds::content_bounds;

/// Bounds of a layer's own pixels: `daguerre_layers_compose::layer_bounds`.
pub fn layer_bounds(layer: &Layer, canvas: Rect) -> Rect {
    daguerre_layers_compose::layer_bounds(layer, canvas)
}

/// The region a layer's effect maps cover: its bounds grown by the effect reach, within the
/// canvas grown likewise (`daguerre_layers_compose::effect_maps`).
pub fn effect_region(layer: &Layer, canvas: Rect) -> Rect {
    let m = daguerre_layers_compose::effects::margin(layer);
    layer_bounds(layer, canvas).inflate(m).intersect(&canvas.inflate(m))
}

/// `daguerre_layers_compose::transparent_outside`.
pub fn transparent_outside(layer: &Layer) -> bool {
    daguerre_layers_compose::transparent_outside(layer)
}

#[cfg(test)]
mod tests {
    use super::*;
    use daguerre_layers_color::PixelFormat;

    #[test]
    fn matches_surface_content_bounds() {
        let mut s = Surface::new(PixelFormat::RGBA8);
        assert_eq!(content_bounds(&s), s.content_bounds());
        s.fill_rect(Rect::new(10, 300, 40, 700), &[1.0, 0.0, 0.0, 1.0]);
        s.fill_rect(Rect::new(-50, 5, -3, 9), &[0.0, 0.0, 1.0, 0.5]);
        assert_eq!(content_bounds(&s), s.content_bounds());
        // Cached a second time, and after a change.
        assert_eq!(content_bounds(&s), s.content_bounds());
        s.fill_rect(Rect::new(600, 600, 601, 601), &[0.0, 1.0, 0.0, 1.0]);
        assert_eq!(content_bounds(&s), s.content_bounds());
        let mut g = Surface::with_default(PixelFormat::GRAY8, &[1.0]);
        g.fill_rect(Rect::new(3, 3, 9, 9), &[0.5]);
        assert_eq!(content_bounds(&g), g.content_bounds());
    }
}
