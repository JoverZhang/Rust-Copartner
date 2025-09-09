// Performance analysis tool: combines complexity analysis with flamegraph
// This tool demonstrates how to combine complexity analysis results with performance analysis

use anyhow::{Context, Result};
use clap::Parser;
use rust_copartner::complexity_analyzer::{ComplexityAnalyzer, ComplexityRating};
use std::{fs, path::PathBuf, time::Instant};

#[derive(Parser)]
#[command(name = "performance-analyzer")]
#[command(about = "Analyze performance of functions based on complexity")]
struct Cli {
    /// Path to analyze
    #[arg(short, long)]
    path: PathBuf,
    
    /// Generate flamegraph for high complexity functions
    #[arg(long)]
    flamegraph: bool,
    
    /// Minimum complexity threshold for analysis
    #[arg(long, default_value = "5")]
    threshold: usize,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    
    println!("🔥 Performance Analysis Tool");
    println!("Analyzing: {}", cli.path.display());
    println!("Complexity threshold: {}", cli.threshold);
    println!();
    
    // Read and analyze file
    let content = fs::read_to_string(&cli.path)
        .with_context(|| format!("Failed to read file: {}", cli.path.display()))?;
    
    let start = Instant::now();
    let functions = ComplexityAnalyzer::analyze_file(&content)?;
    let analysis_time = start.elapsed();
    
    println!("📊 Analysis completed in {:?}", analysis_time);
    println!("Found {} functions", functions.len());
    println!();
    
    // Filter high complexity functions
    let high_complexity_functions: Vec<_> = functions.iter()
        .filter(|f| f.cyclomatic_complexity >= cli.threshold)
        .collect();
    
    if high_complexity_functions.is_empty() {
        println!("✅ No functions found above complexity threshold of {}", cli.threshold);
        return Ok(());
    }
    
    println!("⚠️  Found {} functions above complexity threshold:", high_complexity_functions.len());
    
    for func in &high_complexity_functions {
        print_performance_analysis(func);
    }
    
    if cli.flamegraph {
        println!();
        println!("🔥 Flamegraph Integration");
        show_flamegraph_commands(&high_complexity_functions);
    }
    
    // Generate performance recommendations
    println!();
    generate_performance_recommendations(&high_complexity_functions);
    
    Ok(())
}

fn print_performance_analysis(func: &rust_copartner::complexity_analyzer::FunctionComplexity) {
    println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    println!("🔍 Function: {}", func.name.to_uppercase());
    
    // Complexity analysis
    let complexity_emoji = match func.return_complexity {
        ComplexityRating::Low => "🟢",
        ComplexityRating::Medium => "🟡", 
        ComplexityRating::High => "🟠",
        ComplexityRating::VeryHigh => "🔴",
    };
    
    println!("   {} Complexity Rating: {:?}", complexity_emoji, func.return_complexity);
    println!("   📈 Cyclomatic: {} | Cognitive: {}", 
        func.cyclomatic_complexity, func.cognitive_complexity);
    
    // Performance impact factor analysis
    let performance_score = calculate_performance_impact(func);
    println!("   ⚡ Performance Impact Score: {}/100", performance_score);
    
    // Detailed analysis
    if func.details.loops > 0 {
        println!("   🔄 Contains {} loop(s) - Potential O(n) or higher complexity", func.details.loops);
    }
    
    if func.details.nested_functions > 0 {
        println!("   📦 {} nested function(s) - May affect stack usage", func.details.nested_functions);
    }
    
    if func.details.unsafe_blocks > 0 {
        println!("   ⚠️  {} unsafe block(s) - Requires careful performance verification", func.details.unsafe_blocks);
    }
    
    if func.details.max_nesting_depth > 3 {
        println!("   🏗️  Deep nesting ({}x) - May cause branch prediction issues", func.details.max_nesting_depth);
    }
    
    if func.details.function_calls > 10 {
        println!("   📞 High function call count ({}) - Consider call overhead", func.details.function_calls);
    }
    
    // Optimization suggestions
    print_optimization_suggestions(func);
    println!();
}

fn calculate_performance_impact(func: &rust_copartner::complexity_analyzer::FunctionComplexity) -> u32 {
    let mut score = 0;
    
    // Base complexity impact
    score += func.cyclomatic_complexity * 5;
    score += func.cognitive_complexity * 3;
    
    // Specific performance factors
    score += func.details.loops * 15;                    // Loops have significant performance impact
    score += func.details.max_nesting_depth * 8;         // Deep nesting affects branch prediction
    score += func.details.function_calls * 2;            // Function call overhead
    score += func.details.unsafe_blocks * 10;            // unsafe blocks require special attention
    score += func.parameter_count * 3;                   // Too many parameters affect stack usage
    
    // Limit to under 100
    score.min(100) as u32
}

fn print_optimization_suggestions(func: &rust_copartner::complexity_analyzer::FunctionComplexity) {
    let mut suggestions = Vec::new();
    
    if func.details.loops > 2 {
        suggestions.push("Consider vectorization or parallel processing for multiple loops");
    }
    
    if func.details.max_nesting_depth > 4 {
        suggestions.push("Refactor to reduce nesting - use early returns or helper functions");
    }
    
    if func.details.function_calls > 15 {
        suggestions.push("High function call overhead - consider inlining hot path functions");
    }
    
    if func.parameter_count > 5 {
        suggestions.push("Too many parameters - consider using structs to reduce stack pressure");
    }
    
    if func.cyclomatic_complexity > 15 {
        suggestions.push("Very high complexity - split into smaller, focused functions");
    }
    
    if !suggestions.is_empty() {
        println!("   💡 Optimization Suggestions:");
        for (i, suggestion) in suggestions.iter().enumerate() {
            println!("      {}. {}", i + 1, suggestion);
        }
    }
}

fn show_flamegraph_commands(functions: &[&rust_copartner::complexity_analyzer::FunctionComplexity]) {
    println!("To profile these high-complexity functions with flamegraph:");
    println!();
    
    // Basic flamegraph commands
    println!("1. 📊 Profile the entire application:");
    println!("   cargo flamegraph --bin complexity_cli -- stats --path .");
    println!();
    
    println!("2. 🎯 Profile specific functions (add this to your main.rs for testing):");
    println!("   ```rust");
    println!("   fn benchmark_high_complexity() {{");
    
    for func in functions.iter().take(3) {
        println!("       for _ in 0..1000 {{");
        println!("           {}(); // Call high complexity function", func.name);
        println!("       }}");
    }
    
    println!("   }}");
    println!("   ```");
    println!();
    
    println!("3. 🔧 Advanced flamegraph options:");
    println!("   cargo flamegraph --bin performance_analyzer --");
    println!("   cargo flamegraph --freq 997 --bin complexity_cli");  // Custom sampling frequency
    println!("   cargo flamegraph --min-width 0.01 --bin complexity_cli");  // Show more details
    println!();
    
    println!("4. 🌡️  Hot path analysis commands:");
    println!("   # Generate flamegraph focused on CPU-intensive operations");
    println!("   CARGO_PROFILE_RELEASE_DEBUG=true cargo flamegraph --release --bin complexity_cli");
    println!();
    
    // Specific analysis recommendations for functions
    println!("📋 Specific Analysis Recommendations:");
    for func in functions.iter().take(5) {
        let focus_areas = get_profiling_focus(func);
        println!("   • {}: {}", func.name, focus_areas);
    }
}

fn get_profiling_focus(func: &rust_copartner::complexity_analyzer::FunctionComplexity) -> String {
    let mut focus = Vec::new();
    
    if func.details.loops > 0 {
        focus.push("Loop optimization");
    }
    
    if func.details.function_calls > 10 {
        focus.push("Call overhead");
    }
    
    if func.details.unsafe_blocks > 0 {
        focus.push("Memory access patterns");
    }
    
    if func.details.max_nesting_depth > 4 {
        focus.push("Branch prediction");
    }
    
    if focus.is_empty() {
        "General performance profiling".to_string()
    } else {
        focus.join(", ")
    }
}

fn generate_performance_recommendations(functions: &[&rust_copartner::complexity_analyzer::FunctionComplexity]) {
    println!("🎯 Performance Optimization Strategy");
    println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    
    let total_score: u32 = functions.iter()
        .map(|f| calculate_performance_impact(f))
        .sum();
    
    let avg_score = total_score as f64 / functions.len() as f64;
    
    println!("📊 Overall Assessment:");
    println!("   • {} functions analyzed", functions.len());
    println!("   • Average performance impact: {:.1}/100", avg_score);
    
    if avg_score > 70.0 {
        println!("   🔥 HIGH PRIORITY: Critical performance bottlenecks detected!");
        println!("   💡 Recommended actions:");
        println!("      1. Profile with cargo flamegraph immediately");
        println!("      2. Focus on loop optimization and algorithm complexity");
        println!("      3. Consider refactoring the highest complexity functions");
    } else if avg_score > 40.0 {
        println!("   ⚠️  MEDIUM PRIORITY: Some performance concerns");
        println!("   💡 Recommended actions:");
        println!("      1. Monitor performance in production");
        println!("      2. Profile during load testing");
        println!("      3. Consider incremental optimizations");
    } else {
        println!("   ✅ LOW PRIORITY: Performance looks acceptable");
        println!("   💡 Recommended actions:");
        println!("      1. Maintain current code quality");
        println!("      2. Profile periodically as codebase grows");
    }
    
    println!();
    println!("🏆 Quick Wins (easiest optimizations):");
    
    let mut quick_wins = Vec::new();
    for func in functions.iter() {
        if func.parameter_count > 5 {
            quick_wins.push(format!("{}: Reduce parameter count", func.name));
        }
        if func.details.max_nesting_depth > 4 {
            quick_wins.push(format!("{}: Reduce nesting with early returns", func.name));
        }
    }
    
    if quick_wins.is_empty() {
        println!("   • No immediate quick wins identified - good code structure!");
    } else {
        for (i, win) in quick_wins.iter().take(5).enumerate() {
            println!("   {}. {}", i + 1, win);
        }
    }
}