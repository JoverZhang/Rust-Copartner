use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use colored::*;
use rust_copartner::complexity_analyzer::{
    ComplexityAnalyzer, ComplexityRating, FunctionComplexity,
};
use std::{fs, path::PathBuf};
use walkdir::WalkDir;

#[derive(Parser)]
#[command(name = "complexity-analyzer")]
#[command(about = "A CLI tool to analyze Rust function complexity")]
#[command(version = "1.0")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Analyze a single file
    File {
        /// Path to the Rust file
        #[arg(short, long)]
        path: PathBuf,

        /// Show detailed breakdown
        #[arg(short, long)]
        detailed: bool,

        /// Filter by complexity threshold
        #[arg(long)]
        threshold: Option<usize>,
    },
    /// Analyze all Rust files in a directory
    Dir {
        /// Directory path
        #[arg(short, long)]
        path: PathBuf,

        /// Include subdirectories
        #[arg(short, long)]
        recursive: bool,

        /// Show only high complexity functions
        #[arg(long)]
        high_only: bool,

        /// Export results to JSON
        #[arg(long)]
        export: Option<PathBuf>,
    },
    /// Show complexity statistics
    Stats {
        /// Directory path
        #[arg(short, long)]
        path: PathBuf,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Commands::File {
            path,
            detailed,
            threshold,
        } => {
            analyze_single_file(path, detailed, threshold)?;
        }
        Commands::Dir {
            path,
            recursive,
            high_only,
            export,
        } => {
            analyze_directory(path, recursive, high_only, export)?;
        }
        Commands::Stats { path } => {
            show_statistics(path)?;
        }
    }

    Ok(())
}

fn analyze_single_file(path: PathBuf, detailed: bool, threshold: Option<usize>) -> Result<()> {
    println!(
        "{}",
        format!("Analyzing file: {}", path.display()).bold().blue()
    );

    let content = fs::read_to_string(&path)
        .with_context(|| format!("Failed to read file: {}", path.display()))?;

    let functions = ComplexityAnalyzer::analyze_file(&content)?;

    if functions.is_empty() {
        println!("{}", "No functions found in the file.".yellow());
        return Ok(());
    }

    for func in &functions {
        if let Some(thresh) = threshold {
            if func.cyclomatic_complexity < thresh {
                continue;
            }
        }

        print_function_complexity(func, detailed);
        println!();
    }

    println!(
        "{}",
        format!("Total functions analyzed: {}", functions.len()).green()
    );
    Ok(())
}

fn analyze_directory(
    path: PathBuf,
    recursive: bool,
    high_only: bool,
    export: Option<PathBuf>,
) -> Result<()> {
    println!(
        "{}",
        format!("Analyzing directory: {}", path.display())
            .bold()
            .blue()
    );

    let mut all_functions = Vec::new();
    let mut file_count = 0;

    let walker = if recursive {
        WalkDir::new(&path).follow_links(true)
    } else {
        WalkDir::new(&path).max_depth(1)
    };

    for entry in walker {
        let entry = entry.context("Failed to read directory entry")?;
        let path = entry.path();

        if path.extension().map_or(false, |ext| ext == "rs") {
            let content = match fs::read_to_string(path) {
                Ok(content) => content,
                Err(_) => continue,
            };

            match ComplexityAnalyzer::analyze_file(&content) {
                Ok(functions) => {
                    println!("  📁 {}: {} functions", path.display(), functions.len());
                    all_functions.extend(functions);
                    file_count += 1;
                }
                Err(e) => {
                    println!("  ⚠️  Failed to analyze {}: {}", path.display(), e);
                }
            }
        }
    }

    // Filter and sort results
    if high_only {
        all_functions.retain(|f| {
            matches!(
                f.return_complexity,
                ComplexityRating::High | ComplexityRating::VeryHigh
            )
        });
    }

    all_functions.sort_by(|a, b| b.cyclomatic_complexity.cmp(&a.cyclomatic_complexity));

    println!("\n{}", "=== Analysis Results ===".bold().green());

    for func in &all_functions {
        print_function_complexity(func, false);
        println!();
    }

    // Export if requested
    if let Some(export_path) = export {
        export_to_json(&all_functions, export_path)?;
    }

    println!(
        "{}",
        format!(
            "Files processed: {}, Functions found: {}",
            file_count,
            all_functions.len()
        )
        .green()
    );
    Ok(())
}

fn show_statistics(path: PathBuf) -> Result<()> {
    println!(
        "{}",
        format!("Generating statistics for: {}", path.display())
            .bold()
            .blue()
    );

    let mut all_functions = Vec::new();

    for entry in WalkDir::new(&path).follow_links(true) {
        let entry = entry.context("Failed to read directory entry")?;
        let path = entry.path();

        if path.extension().map_or(false, |ext| ext == "rs") {
            let content = match fs::read_to_string(path) {
                Ok(content) => content,
                Err(_) => continue,
            };

            if let Ok(functions) = ComplexityAnalyzer::analyze_file(&content) {
                all_functions.extend(functions);
            }
        }
    }

    if all_functions.is_empty() {
        println!("{}", "No functions found.".yellow());
        return Ok(());
    }

    // Calculate statistics
    let total = all_functions.len();
    let low = all_functions
        .iter()
        .filter(|f| f.return_complexity == ComplexityRating::Low)
        .count();
    let medium = all_functions
        .iter()
        .filter(|f| f.return_complexity == ComplexityRating::Medium)
        .count();
    let high = all_functions
        .iter()
        .filter(|f| f.return_complexity == ComplexityRating::High)
        .count();
    let very_high = all_functions
        .iter()
        .filter(|f| f.return_complexity == ComplexityRating::VeryHigh)
        .count();

    let avg_cyclomatic: f64 = all_functions
        .iter()
        .map(|f| f.cyclomatic_complexity)
        .sum::<usize>() as f64
        / total as f64;
    let avg_cognitive: f64 = all_functions
        .iter()
        .map(|f| f.cognitive_complexity)
        .sum::<usize>() as f64
        / total as f64;

    println!("\n{}", "=== Complexity Statistics ===".bold().green());
    println!("Total functions: {}", total.to_string().bold());
    println!(
        "Average Cyclomatic Complexity: {:.2}",
        format!("{:.2}", avg_cyclomatic).yellow()
    );
    println!(
        "Average Cognitive Complexity: {:.2}",
        format!("{:.2}", avg_cognitive).yellow()
    );
    println!();

    println!("{}", "Complexity Distribution:".bold());
    println!(
        "  {} Low:       {} ({:.1}%)",
        "🟢".green(),
        low,
        (low as f64 / total as f64) * 100.0
    );
    println!(
        "  {} Medium:    {} ({:.1}%)",
        "🟡".yellow(),
        medium,
        (medium as f64 / total as f64) * 100.0
    );
    println!(
        "  {} High:      {} ({:.1}%)",
        "🟠".red(),
        high,
        (high as f64 / total as f64) * 100.0
    );
    println!(
        "  {} Very High: {} ({:.1}%)",
        "🔴".red(),
        very_high,
        (very_high as f64 / total as f64) * 100.0
    );

    // Show most complex functions
    all_functions.sort_by(|a, b| b.cyclomatic_complexity.cmp(&a.cyclomatic_complexity));
    println!("\n{}", "Top 5 Most Complex Functions:".bold().red());
    for func in all_functions.iter().take(5) {
        println!(
            "  {} (complexity: {})",
            func.name.bright_white(),
            func.cyclomatic_complexity.to_string().red()
        );
    }

    Ok(())
}

fn print_function_complexity(func: &FunctionComplexity, detailed: bool) {
    let color = match func.return_complexity {
        ComplexityRating::Low => "green",
        ComplexityRating::Medium => "yellow",
        ComplexityRating::High => "red",
        ComplexityRating::VeryHigh => "bright_red",
    };

    println!("{} {}", "Function:".bold(), func.name.color(color).bold());

    println!(
        "  {} {}",
        "Cyclomatic Complexity:".bright_blue(),
        func.cyclomatic_complexity
    );
    println!(
        "  {} {}",
        "Cognitive Complexity:".bright_blue(),
        func.cognitive_complexity
    );
    println!("  {} {}", "Parameters:".bright_blue(), func.parameter_count);
    println!(
        "  {} {}",
        "Rating:".bright_blue(),
        format!("{}", func.return_complexity).color(color)
    );

    if detailed {
        println!("  {} {}", "Details:".bright_cyan().bold(), "");
        println!("    If statements: {}", func.details.if_statements);
        println!("    Match arms: {}", func.details.match_arms);
        println!("    Loops: {}", func.details.loops);
        println!("    Function calls: {}", func.details.function_calls);
        println!("    Max nesting depth: {}", func.details.max_nesting_depth);

        // Advanced analysis data
        println!("    Unsafe blocks: {}", func.details.unsafe_blocks);
        println!(
            "    Generic parameters: {}",
            func.details.generic_parameters
        );

        if !func.details.function_call_chain.is_empty() {
            println!(
                "    Function call chain: [{}]",
                func.details.function_call_chain.join(", ")
            );
        }

        if !func.details.macro_invocations.is_empty() {
            println!(
                "    Macro invocations: [{}]",
                func.details.macro_invocations.join(", ")
            );
        }

        if !func.details.module_dependencies.is_empty() {
            println!(
                "    Module dependencies: [{}]",
                func.details
                    .module_dependencies
                    .iter()
                    .take(5) // Limit display count
                    .cloned()
                    .collect::<Vec<_>>()
                    .join(", ")
            );
        }
    }
}

fn export_to_json(functions: &[FunctionComplexity], path: PathBuf) -> Result<()> {
    use std::io::Write;

    let mut file = fs::File::create(&path)
        .with_context(|| format!("Failed to create export file: {}", path.display()))?;

    writeln!(file, "[")?;

    for (i, func) in functions.iter().enumerate() {
        let comma = if i == functions.len() - 1 { "" } else { "," };
        writeln!(file, "  {{")?;
        writeln!(file, "    \"name\": \"{}\",", func.name)?;
        writeln!(
            file,
            "    \"cyclomatic_complexity\": {},",
            func.cyclomatic_complexity
        )?;
        writeln!(
            file,
            "    \"cognitive_complexity\": {},",
            func.cognitive_complexity
        )?;
        writeln!(file, "    \"parameter_count\": {},", func.parameter_count)?;
        // Advanced analysis data
        writeln!(
            file,
            "    \"unsafe_blocks\": {},",
            func.details.unsafe_blocks
        )?;
        writeln!(
            file,
            "    \"generic_parameters\": {},",
            func.details.generic_parameters
        )?;
        if !func.details.function_call_chain.is_empty() {
            writeln!(
                file,
                "    \"function_call_chain\": \"{}\",",
                func.details.function_call_chain.join(", ")
            )?;
        }
        if !func.details.macro_invocations.is_empty() {
            writeln!(
                file,
                "    \"macro_invocations\": \"{}\",",
                func.details.macro_invocations.join(", ")
            )?;
        }
        if !func.details.module_dependencies.is_empty() {
            writeln!(
                file,
                "    \"module_dependencies\": \"{}\",",
                func.details.module_dependencies.join(", ")
            )?;
        }
        writeln!(file, "    \"rating\": \"{}\"", func.return_complexity)?;
        writeln!(file, "  }}{}", comma)?;
    }

    writeln!(file, "]")?;

    println!(
        "{}",
        format!("Results exported to: {}", path.display()).green()
    );
    Ok(())
}
