//! Geometry primitives

/// A 2D point
pub struct Point {
    /// x coordinate
    pub x: i32,
    /// y coordinate
    pub y: i32,
}

/// Operations on `Point`
impl Point {
    /// Create a new Point
    pub fn new(x: i32, y: i32) -> Self {
        Self { x, y }
    }

    /// Sum coordinates
    pub fn sum(&self) -> i32 {
        self.x + self.y
    }
}

/// Free function example
pub fn origin() -> Point {
    Point { x: 0, y: 0 }
}

