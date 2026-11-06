//! Auswertbare Geometrie für das Gesichtsgitter.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Point {
    pub x: i32,
    pub y: i32,
}

impl Point {
    pub const fn new(x: i32, y: i32) -> Self {
        Self { x, y }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Rect {
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
}

impl Rect {
    pub const fn new(x: i32, y: i32, width: i32, height: i32) -> Self {
        Self {
            x,
            y,
            width,
            height,
        }
    }
}

/// Ein Punkt des Gitters in gesichtslokalen, normierten Koordinaten.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct NormalizedGridPoint {
    pub row: u32,
    pub column: u32,
    pub x: f32,
    pub y: f32,
}

/// Gleichmäßig verteiltes Messgitter innerhalb einer Gesichtsfläche.
#[derive(Debug, Clone, Copy)]
pub struct FaceGrid {
    pub bounds: Rect,
    pub rows: u32,
    pub columns: u32,
}

impl FaceGrid {
    pub fn new(bounds: Rect, rows: u32, columns: u32) -> Self {
        assert!(rows > 0 && columns > 0, "Das Gitter darf nicht leer sein");
        Self {
            bounds,
            rows,
            columns,
        }
    }

    /// Liefert stabile Werte zwischen 0 und 1, unabhängig von der Bildauflösung.
    pub fn normalized_points(&self) -> Vec<NormalizedGridPoint> {
        let mut points = Vec::with_capacity(((self.rows + 1) * (self.columns + 1)) as usize);

        for row in 0..=self.rows {
            for column in 0..=self.columns {
                points.push(NormalizedGridPoint {
                    row,
                    column,
                    x: column as f32 / self.columns as f32,
                    y: row as f32 / self.rows as f32,
                });
            }
        }

        points
    }

    /// Rechnet die normierten Punkte in Pixelkoordinaten des aktuellen Bildes um.
    pub fn pixel_points(&self) -> Vec<Point> {
        self.normalized_points()
            .into_iter()
            .map(|point| {
                Point::new(
                    self.bounds.x + (point.x * self.bounds.width as f32).round() as i32,
                    self.bounds.y + (point.y * self.bounds.height as f32).round() as i32,
                )
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn creates_normalized_grid_for_later_evaluation() {
        let grid = FaceGrid::new(Rect::new(100, 50, 200, 300), 2, 2);
        let points = grid.normalized_points();

        assert_eq!(points.len(), 9);
        assert_eq!(
            points.first().map(|point| (point.x, point.y)),
            Some((0.0, 0.0))
        );
        assert_eq!(
            points.last().map(|point| (point.x, point.y)),
            Some((1.0, 1.0))
        );
    }

    #[test]
    fn maps_grid_to_face_pixels() {
        let grid = FaceGrid::new(Rect::new(100, 50, 200, 300), 2, 2);
        let points = grid.pixel_points();

        assert_eq!(points[4], Point::new(200, 200));
    }
}
