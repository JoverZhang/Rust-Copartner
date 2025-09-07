#[derive(Debug, Clone, Copy, PartialEq)]
struct Point3D {
    x: i32,
    y: i32,
}

impl Point {
    fn new(x: i32, y: i32) -> Self {
        Self { x, y }
    }
}

fn main() {
    let p = Point::new(1, 2);
    println!("p = {:?}", p);
}
