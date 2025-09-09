// Test sample file: contains functions with different complexities

fn simple_function(x: i32) -> i32 {
    x + 1
}

fn medium_complexity(numbers: Vec<i32>) -> i32 {
    let mut sum = 0;
    for i in 0..numbers.len() {
        if numbers[i] > 0 {
            sum += numbers[i];
        } else {
            sum -= numbers[i];
        }
    }
    sum
}

fn high_complexity(data: Vec<Vec<i32>>) -> Vec<i32> {
    let mut result = Vec::new();
    
    for row in data.iter() {
        for &value in row {
            match value {
                0 => {
                    if result.is_empty() {
                        result.push(0);
                    } else {
                        for i in 0..result.len() {
                            if result[i] == 0 {
                                result[i] = 1;
                                break;
                            }
                        }
                    }
                }
                1..=10 => {
                    let mut found = false;
                    for &existing in &result {
                        if existing == value {
                            found = true;
                            break;
                        }
                    }
                    if !found {
                        result.push(value);
                    }
                }
                11..=100 => {
                    while result.len() < value as usize {
                        result.push(result.len() as i32);
                    }
                    if let Some(last) = result.last_mut() {
                        *last *= 2;
                    }
                }
                _ => {
                    loop {
                        if result.is_empty() {
                            result.push(value % 10);
                            break;
                        }
                        let sum: i32 = result.iter().sum();
                        if sum > value {
                            break;
                        }
                        result.push(sum % 7);
                        if result.len() > 100 {
                            break;
                        }
                    }
                }
            }
        }
    }
    
    result
}