use std::{env, path::PathBuf, sync::mpsc, time::Duration};

use gesichtserkennung::{FaceGrid, Point, Rect};
use image::RgbImage;
use minifb::{Key, ScaleMode, Window, WindowOptions};
use nokhwa::{
    Camera,
    pixel_format::RgbFormat,
    utils::{ApiBackend, CameraIndex, RequestedFormat, RequestedFormatType},
};
use rustface::{Detector, ImageData};

const WINDOW_TITLE: &str = "Gesichtsdetektion – Q oder Esc beendet";
const MODEL_PATH: &str = "models/seeta_fd_frontal_v1.0.bin";
const GRID_ROWS: u32 = 6;
const GRID_COLUMNS: u32 = 6;
const SMOOTHING: f64 = 0.35;
const MAX_MISSED_DETECTIONS: u32 = 3;
const DETECTION_INTERVAL: u64 = 3;
const GRID_COLOR: u32 = 0x00_32_E6_5A;
const GRID_POINT_COLOR: u32 = 0x00_28_BE_FF;

#[derive(Debug, Clone, Copy)]
struct SmoothedFace {
    x: f64,
    y: f64,
    width: f64,
    height: f64,
    missed_detections: u32,
}

impl SmoothedFace {
    fn from_rect(rect: Rect) -> Self {
        Self {
            x: f64::from(rect.x),
            y: f64::from(rect.y),
            width: f64::from(rect.width),
            height: f64::from(rect.height),
            missed_detections: 0,
        }
    }

    fn update(&mut self, rect: Rect) {
        self.x = lerp(self.x, f64::from(rect.x), SMOOTHING);
        self.y = lerp(self.y, f64::from(rect.y), SMOOTHING);
        self.width = lerp(self.width, f64::from(rect.width), SMOOTHING);
        self.height = lerp(self.height, f64::from(rect.height), SMOOTHING);
        self.missed_detections = 0;
    }

    fn rect(self) -> Rect {
        Rect::new(
            self.x.round() as i32,
            self.y.round() as i32,
            self.width.round() as i32,
            self.height.round() as i32,
        )
    }
}

fn lerp(current: f64, target: f64, amount: f64) -> f64 {
    current + (target - current) * amount
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Rustface skaliert auf diesem Intel-Mac mit zwei Threads meist besser als mit allen Kernen.
    let _ = rayon::ThreadPoolBuilder::new()
        .num_threads(2)
        .build_global();

    request_camera_permission()?;
    print_available_cameras()?;

    let camera_index = camera_index_from_args()?;
    // AVFoundation wählt ein tatsächlich von der jeweiligen Kamera angebotenes Format.
    let requested = RequestedFormat::new::<RgbFormat>(RequestedFormatType::None);
    let mut camera = Camera::new(CameraIndex::Index(camera_index), requested)?;
    camera.open_stream()?;

    let model_path = project_path(MODEL_PATH);
    let mut detector = rustface::create_detector(&model_path.to_string_lossy())?;
    configure_detector(&mut *detector);

    let first_frame = camera.frame()?.decode_image::<RgbFormat>()?;
    let (width, height) = first_frame.dimensions();
    let mut window = Window::new(
        WINDOW_TITLE,
        width as usize,
        height as usize,
        WindowOptions {
            resize: true,
            scale_mode: ScaleMode::AspectRatioStretch,
            ..WindowOptions::default()
        },
    )?;
    window.set_target_fps(30);

    println!("Kamera {camera_index}: {} × {height} Pixel", width);
    println!("Das Bild bleibt lokal. Beenden mit Q oder Esc.");

    let mut tracked_face: Option<SmoothedFace> = None;
    let mut last_reported_detection: Option<bool> = None;
    let mut frame_number = 0_u64;
    let mut rgb_frame = first_frame;

    while window.is_open() && !window.is_key_down(Key::Escape) && !window.is_key_down(Key::Q) {
        let (frame_width, frame_height) = rgb_frame.dimensions();
        if (frame_width, frame_height) != (width, height) {
            return Err("Die Kameraauflösung hat sich während der Aufnahme geändert.".into());
        }

        let mut display = mirrored_rgb_buffer(&rgb_frame);

        if frame_number.is_multiple_of(DETECTION_INTERVAL) {
            let detection = detect_largest_face(&mut *detector, &rgb_frame);
            update_tracking(&mut tracked_face, detection);

            let face_detected = tracked_face.is_some();
            if last_reported_detection != Some(face_detected) {
                println!(
                    "{}",
                    if face_detected {
                        "Gesicht erkannt – Messgitter aktiv."
                    } else {
                        "Kein Gesicht erkannt."
                    }
                );
                last_reported_detection = Some(face_detected);
            }
        }

        if let Some(face) = tracked_face {
            draw_face_grid(
                &mut display,
                width as usize,
                height as usize,
                FaceGrid::new(face.rect(), GRID_ROWS, GRID_COLUMNS),
            );
            window.set_title("Gesicht erkannt – Q oder Esc beendet");
        } else {
            window.set_title("Suche Gesicht … – Q oder Esc beendet");
        }

        window.update_with_buffer(&display, width as usize, height as usize)?;
        frame_number += 1;
        rgb_frame = camera.frame()?.decode_image::<RgbFormat>()?;
    }

    camera.stop_stream()?;
    Ok(())
}

fn request_camera_permission() -> Result<(), Box<dyn std::error::Error>> {
    if nokhwa::nokhwa_check() {
        return Ok(());
    }

    let (sender, receiver) = mpsc::channel();
    nokhwa::nokhwa_initialize(move |granted| {
        let _ = sender.send(granted);
    });

    match receiver.recv_timeout(Duration::from_secs(60)) {
        Ok(true) => Ok(()),
        Ok(false) => Err(
            "Der Kamerazugriff wurde abgelehnt. Bitte in Systemeinstellungen > Datenschutz & Sicherheit > Kamera freigeben."
                .into(),
        ),
        Err(_) => Err("Zeitüberschreitung beim Anfordern des Kamerazugriffs.".into()),
    }
}

fn print_available_cameras() -> Result<(), Box<dyn std::error::Error>> {
    let cameras = nokhwa::query(ApiBackend::AVFoundation)?;
    println!("Verfügbare Kameras:");
    for camera in cameras {
        println!("  {}: {}", camera.index(), camera.human_name());
    }
    Ok(())
}

fn camera_index_from_args() -> Result<u32, Box<dyn std::error::Error>> {
    match env::args().nth(1) {
        Some(value) => value
            .parse::<u32>()
            .map_err(|_| format!("Ungültiger Kameraindex: {value}").into()),
        None => Ok(0),
    }
}

fn project_path(relative: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(relative)
}

fn configure_detector(detector: &mut dyn Detector) {
    detector.set_min_face_size(40);
    detector.set_score_thresh(2.0);
    detector.set_pyramid_scale_factor(0.8);
    detector.set_slide_window_step(4, 4);
}

fn detect_largest_face(detector: &mut dyn Detector, frame: &RgbImage) -> Option<Rect> {
    // Halbe Auflösung hält die Erkennung flüssig. Die Koordinaten werden zurückskaliert.
    let (width, height) = frame.dimensions();
    let detect_width = width / 2;
    let detect_height = height / 2;
    let mut gray = Vec::with_capacity((detect_width * detect_height) as usize);

    for y in 0..detect_height {
        for x in 0..detect_width {
            let source_x = width - 1 - x * 2;
            let pixel = frame.get_pixel(source_x, y * 2).0;
            let luminance =
                (u32::from(pixel[0]) * 77 + u32::from(pixel[1]) * 150 + u32::from(pixel[2]) * 29)
                    >> 8;
            gray.push(luminance as u8);
        }
    }

    let image = ImageData::new(&gray, detect_width, detect_height);
    detector
        .detect(&image)
        .into_iter()
        .max_by_key(|face| face.bbox().width() * face.bbox().height())
        .map(|face| {
            let bounds = face.bbox();
            Rect::new(
                bounds.x() * 2,
                bounds.y() * 2,
                (bounds.width() * 2) as i32,
                (bounds.height() * 2) as i32,
            )
        })
}

fn update_tracking(tracked: &mut Option<SmoothedFace>, detection: Option<Rect>) {
    match (tracked.as_mut(), detection) {
        (Some(current), Some(rect)) => current.update(rect),
        (None, Some(rect)) => *tracked = Some(SmoothedFace::from_rect(rect)),
        (Some(current), None) if current.missed_detections < MAX_MISSED_DETECTIONS => {
            current.missed_detections += 1;
        }
        (Some(_), None) => *tracked = None,
        (None, None) => {}
    }
}

fn mirrored_rgb_buffer(frame: &RgbImage) -> Vec<u32> {
    let (width, height) = frame.dimensions();
    let mut output = vec![0_u32; (width * height) as usize];

    for y in 0..height {
        for x in 0..width {
            let pixel = frame.get_pixel(width - 1 - x, y).0;
            output[(y * width + x) as usize] =
                (u32::from(pixel[0]) << 16) | (u32::from(pixel[1]) << 8) | u32::from(pixel[2]);
        }
    }

    output
}

fn draw_face_grid(buffer: &mut [u32], width: usize, height: usize, grid: FaceGrid) {
    let left = grid.bounds.x;
    let right = grid.bounds.x + grid.bounds.width;
    let top = grid.bounds.y;
    let bottom = grid.bounds.y + grid.bounds.height;

    for row in 0..=grid.rows {
        let y = top + ((row as f32 / grid.rows as f32) * grid.bounds.height as f32).round() as i32;
        draw_horizontal(buffer, width, height, left, right, y, GRID_COLOR);
    }

    for column in 0..=grid.columns {
        let x = left
            + ((column as f32 / grid.columns as f32) * grid.bounds.width as f32).round() as i32;
        draw_vertical(buffer, width, height, x, top, bottom, GRID_COLOR);
    }

    for point in grid.pixel_points() {
        draw_square(buffer, width, height, point, 2, GRID_POINT_COLOR);
    }
}

fn draw_horizontal(
    buffer: &mut [u32],
    width: usize,
    height: usize,
    from_x: i32,
    to_x: i32,
    y: i32,
    color: u32,
) {
    let start = from_x.max(0);
    let end = to_x.min(width.saturating_sub(1) as i32);
    for x in start..=end {
        set_pixel(buffer, width, height, Point::new(x, y), color);
    }
}

fn draw_vertical(
    buffer: &mut [u32],
    width: usize,
    height: usize,
    x: i32,
    from_y: i32,
    to_y: i32,
    color: u32,
) {
    let start = from_y.max(0);
    let end = to_y.min(height.saturating_sub(1) as i32);
    for y in start..=end {
        set_pixel(buffer, width, height, Point::new(x, y), color);
    }
}

fn draw_square(
    buffer: &mut [u32],
    width: usize,
    height: usize,
    center: Point,
    radius: i32,
    color: u32,
) {
    for y in (center.y - radius)..=(center.y + radius) {
        for x in (center.x - radius)..=(center.x + radius) {
            set_pixel(buffer, width, height, Point::new(x, y), color);
        }
    }
}

fn set_pixel(buffer: &mut [u32], width: usize, height: usize, point: Point, color: u32) {
    if point.x >= 0 && point.y >= 0 && point.x < width as i32 && point.y < height as i32 {
        buffer[point.y as usize * width + point.x as usize] = color;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn smoothes_a_moving_face() {
        let mut face = SmoothedFace::from_rect(Rect::new(0, 0, 100, 100));
        face.update(Rect::new(100, 100, 200, 200));
        assert_eq!(face.rect(), Rect::new(35, 35, 135, 135));
    }

    #[test]
    fn keeps_face_briefly_when_detection_flickers() {
        let mut tracked = Some(SmoothedFace::from_rect(Rect::new(0, 0, 100, 100)));
        update_tracking(&mut tracked, None);
        assert!(tracked.is_some());
        assert_eq!(tracked.map(|face| face.missed_detections), Some(1));
    }

    #[test]
    fn draws_only_inside_the_frame() {
        let mut pixels = vec![0; 10 * 10];
        draw_face_grid(
            &mut pixels,
            10,
            10,
            FaceGrid::new(Rect::new(-5, -5, 20, 20), 2, 2),
        );
        assert!(pixels.iter().any(|pixel| *pixel != 0));
    }
}
