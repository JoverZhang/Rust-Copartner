// Demonstration tool for code generation using quote crate
// This tool shows how to generate new Rust code using AST analysis results

use anyhow::{Context, Result};
use clap::Parser;
use proc_macro2::TokenStream;
use quote::quote;
use rust_copartner::complexity_analyzer::{ComplexityAnalyzer, FunctionComplexity};
use std::{fs, path::PathBuf};

#[derive(Parser)]
#[command(name = "code-generator")]
#[command(about = "Generate Rust code based on complexity analysis")]
struct Cli {
    /// Path to the Rust file to analyze
    #[arg(short, long)]
    input: PathBuf,

    /// Output file for generated code
    #[arg(short, long)]
    output: PathBuf,

    /// Type of code to generate
    #[arg(short, long, value_enum)]
    generate: GenerationType,
}

#[derive(clap::ValueEnum, Clone)]
enum GenerationType {
    /// Generate unit tests for functions
    Tests,
    /// Generate benchmark code
    Benchmarks,
    /// Generate documentation stubs
    Docs,
    /// Generate complexity reports as code
    Reports,
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    println!(
        "🚀 Generating {} for: {}",
        match cli.generate {
            GenerationType::Tests => "unit tests",
            GenerationType::Benchmarks => "benchmarks",
            GenerationType::Docs => "documentation",
            GenerationType::Reports => "complexity reports",
        },
        cli.input.display()
    );

    let content = fs::read_to_string(&cli.input)
        .with_context(|| format!("Failed to read file: {}", cli.input.display()))?;

    let functions = ComplexityAnalyzer::analyze_file(&content)?;

    if functions.is_empty() {
        println!("No functions found to generate code for.");
        return Ok(());
    }

    let generated_code = match cli.generate {
        GenerationType::Tests => generate_tests(&functions)?,
        GenerationType::Benchmarks => generate_benchmarks(&functions)?,
        GenerationType::Docs => generate_docs(&functions)?,
        GenerationType::Reports => generate_reports(&functions)?,
    };

    fs::write(&cli.output, generated_code.to_string())
        .with_context(|| format!("Failed to write to: {}", cli.output.display()))?;

    println!("✅ Generated code written to: {}", cli.output.display());
    println!("📊 Processed {} functions", functions.len());

    Ok(())
}

fn generate_tests(functions: &[FunctionComplexity]) -> Result<TokenStream> {
    let mut test_functions = Vec::new();

    for func in functions {
        let func_name = &func.name;
        let test_name = format!("test_{}", func_name);
        let test_ident = syn::Ident::new(&test_name, proc_macro2::Span::call_site());
        let func_ident = syn::Ident::new(func_name, proc_macro2::Span::call_site());

        let complexity_comment = format!(
            "Test for {} (complexity: {})",
            func_name, func.cyclomatic_complexity
        );

        let test_fn = if func.parameter_count == 0 {
            quote! {
                #[test]
                fn #test_ident() {
                    // #complexity_comment
                    // TODO: Add proper test implementation
                    // Function has no parameters, test direct call
                    let result = #func_ident();
                    // Add assertions here based on expected behavior
                }
            }
        } else {
            quote! {
                #[test]
                fn #test_ident() {
                    // #complexity_comment
                    // TODO: Add proper test implementation with parameters
                    // Function has #(func.parameter_count) parameter(s)
                    // Create appropriate test inputs and verify outputs
                }
            }
        };

        test_functions.push(test_fn);
    }

    let generated = quote! {
        #[cfg(test)]
        mod generated_tests {
            use super::*;

            // Generated tests for complexity analysis
            // Total functions analyzed: #(functions.len())

            #(#test_functions)*
        }
    };

    Ok(generated)
}

fn generate_benchmarks(functions: &[FunctionComplexity]) -> Result<TokenStream> {
    let mut benchmark_functions = Vec::new();

    for func in functions {
        let func_name = &func.name;
        let bench_name = format!("bench_{}", func_name);
        let bench_ident = syn::Ident::new(&bench_name, proc_macro2::Span::call_site());
        let func_ident = syn::Ident::new(func_name, proc_macro2::Span::call_site());

        let complexity_comment = format!(
            "Benchmark for {} (cyclomatic: {}, cognitive: {})",
            func_name, func.cyclomatic_complexity, func.cognitive_complexity
        );

        let bench_fn = quote! {
            #[bench]
            fn #bench_ident(b: &mut Bencher) {
                // #complexity_comment
                b.iter(|| {
                    // TODO: Add appropriate benchmark setup
                    // High complexity functions may need performance monitoring
                    #func_ident(/* add parameters as needed */)
                });
            }
        };

        benchmark_functions.push(bench_fn);
    }

    let generated = quote! {
        #![feature(test)]
        extern crate test;
        use test::Bencher;

        // Generated benchmarks for complexity analysis
        // Functions with high complexity should be monitored for performance

        #(#benchmark_functions)*
    };

    Ok(generated)
}

fn generate_docs(functions: &[FunctionComplexity]) -> Result<TokenStream> {
    let mut doc_items = Vec::new();

    for func in functions {
        let func_name = &func.name;
        let rating = &func.return_complexity;

        let doc_comment = format!(
            r#"
# Function: {}

## Complexity Analysis
- **Cyclomatic Complexity**: {}
- **Cognitive Complexity**: {}
- **Parameters**: {}
- **Rating**: {:?}
- **Max Nesting Depth**: {}

## Details
- If statements: {}
- Match arms: {}
- Loops: {}
- Function calls: {}
- Unsafe blocks: {}

## Recommendations
{}
"#,
            func_name,
            func.cyclomatic_complexity,
            func.cognitive_complexity,
            func.parameter_count,
            rating,
            func.details.max_nesting_depth,
            func.details.if_statements,
            func.details.match_arms,
            func.details.loops,
            func.details.function_calls,
            func.details.unsafe_blocks,
            get_complexity_recommendations(func)
        );

        doc_items.push(doc_comment);
    }

    let all_docs = doc_items.join("\n---\n");

    let generated = quote! {
        //! # Complexity Analysis Documentation
        //!
        //! This documentation was automatically generated from complexity analysis.
        //!
        #![doc = #all_docs]
    };

    Ok(generated)
}

fn generate_reports(functions: &[FunctionComplexity]) -> Result<TokenStream> {
    let total_functions = functions.len();
    let high_complexity_count = functions
        .iter()
        .filter(|f| {
            matches!(
                f.return_complexity,
                rust_copartner::complexity_analyzer::ComplexityRating::High
                    | rust_copartner::complexity_analyzer::ComplexityRating::VeryHigh
            )
        })
        .count();

    let avg_cyclomatic: f64 = if total_functions > 0 {
        functions
            .iter()
            .map(|f| f.cyclomatic_complexity)
            .sum::<usize>() as f64
            / total_functions as f64
    } else {
        0.0
    };

    let generated = quote! {
        //! # Complexity Analysis Report
        //!
        //! Generated automatically from AST analysis.

        use std::collections::HashMap;

        /// Complexity analysis results structure
        #[derive(Debug, Clone)]
        pub struct ComplexityReport {
            pub total_functions: usize,
            pub high_complexity_functions: usize,
            pub average_cyclomatic_complexity: f64,
            pub function_details: HashMap<String, FunctionMetrics>,
        }

        #[derive(Debug, Clone)]
        pub struct FunctionMetrics {
            pub cyclomatic_complexity: usize,
            pub cognitive_complexity: usize,
            pub parameter_count: usize,
            pub unsafe_blocks: usize,
        }

        impl ComplexityReport {
            /// Get the pre-computed analysis report
            pub fn get_analysis() -> Self {
                let mut function_details = HashMap::new();

                // Insert function metrics
                // TODO: Add actual function data here

                Self {
                    total_functions: #total_functions,
                    high_complexity_functions: #high_complexity_count,
                    average_cyclomatic_complexity: #avg_cyclomatic,
                    function_details,
                }
            }

            /// Check if codebase has acceptable complexity levels
            pub fn is_healthy(&self) -> bool {
                self.average_cyclomatic_complexity <= 5.0 &&
                (self.high_complexity_functions as f64 / self.total_functions as f64) < 0.2
            }
        }
    };

    Ok(generated)
}

fn get_complexity_recommendations(func: &FunctionComplexity) -> String {
    let mut recommendations = Vec::new();

    if func.cyclomatic_complexity > 10 {
        recommendations.push("Consider breaking this function into smaller functions");
    }

    if func.details.max_nesting_depth > 4 {
        recommendations.push("Reduce nesting depth using early returns or helper functions");
    }

    if func.details.unsafe_blocks > 0 {
        recommendations.push("Review unsafe code blocks for safety guarantees");
    }

    if func.parameter_count > 5 {
        recommendations.push("Consider using a struct to group related parameters");
    }

    if func.details.function_calls > 10 {
        recommendations.push("High number of function calls may indicate doing too much");
    }

    if recommendations.is_empty() {
        "Function complexity is within acceptable limits".to_string()
    } else {
        recommendations.join("; ")
    }
}
