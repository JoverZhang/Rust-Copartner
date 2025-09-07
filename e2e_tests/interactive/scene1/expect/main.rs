#[derive(Debug, Clone, Copy, PartialEq)]
struct Point3D {
    x: i32,
    y: i32,
    z: i32,
}

impl Point3D {
    fn new(x: i32, y: i32, z: i32) -> Self {
        Self { x, y, z }
    }
}

fn main() {
    let p = Point3D::new(1, 2, 3);
    println!("p = {:?}", p);
}
