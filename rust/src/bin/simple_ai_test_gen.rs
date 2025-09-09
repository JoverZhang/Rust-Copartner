// Simplified AI test generator - direct use of reqwest to call OpenRouter API
// Avoids complexity of async-openai library, uses native HTTP calls

use anyhow::{Context, Result};
use clap::Parser;
use colored::*;
use rust_copartner::complexity_analyzer::{ComplexityAnalyzer, ComplexityRating, FunctionComplexity};
use dotenv::dotenv;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::{env, fs, path::PathBuf};

#[derive(Parser)]
#[command(name = "simple-ai-test-gen")]
#[command(about = "Simple AI-powered unit test generator using direct HTTP calls")]
struct Cli {
    /// Rust source file to analyze and generate tests for
    #[arg(short, long)]
    file: PathBuf,

    /// Output file for generated tests
    #[arg(short, long, default_value = "tests/generated_tests.rs")]
    output: PathBuf,

    /// Minimum complexity threshold for AI test generation
    #[arg(long, default_value = "3")]
    min_complexity: usize,

    /// Dry run - show what would be generated without calling API
    #[arg(long)]
    dry_run: bool,

    /// Verbose output
    #[arg(short, long)]
    verbose: bool,
}

#[derive(Debug, Serialize)]
struct OpenRouterRequest {
    model: String,
    messages: Vec<Message>,
    temperature: f64,
    max_tokens: u32,
}

#[derive(Debug, Serialize)]
struct Message {
    role: String,
    content: String,
}

#[derive(Debug, Deserialize)]
struct OpenRouterResponse {
    choices: Vec<Choice>,
}

#[derive(Debug, Deserialize)]
struct Choice {
    message: ResponseMessage,
}

#[derive(Debug, Deserialize)]
struct ResponseMessage {
    content: String,
}

#[derive(Debug)]
struct GeneratedTestSuite {
    function_name: String,
    test_code: String,
    test_count: usize,
}

#[tokio::main]
async fn main() -> Result<()> {
    dotenv().ok();
    let cli = Cli::parse();

    println!("{}", "🤖 Simple AI Test Generator".bright_cyan().bold());
    println!("Analyzing: {}", cli.file.display().to_string().bright_yellow());
    println!();

    // Check environment variables
    let api_key = env::var("OPENROUTER_API_KEY")
        .context("OPENROUTER_API_KEY environment variable is required")?;
    let base_url = env::var("OPENROUTER_BASE_URL")
        .unwrap_or_else(|_| "https://openrouter.ai/api/v1".to_string());
    let model = env::var("OPENROUTER_MODEL")
        .unwrap_or_else(|_| "deepseek/deepseek-r1:free".to_string());

    if cli.verbose {
        println!("🔧 Configuration:");
        println!("   API Base: {}", base_url.bright_blue());
        println!("   Model: {}", model.bright_green());
        println!();
    }

    // Read and analyze source file
    let source_code = fs::read_to_string(&cli.file)
        .with_context(|| format!("Failed to read file: {}", cli.file.display()))?;

    let functions = ComplexityAnalyzer::analyze_file(&source_code)
        .context("Failed to analyze source code")?;

    // Filter functions that need AI-generated tests
    let target_functions: Vec<_> = functions
        .iter()
        .filter(|f| f.cyclomatic_complexity >= cli.min_complexity)
        .collect();

    if target_functions.is_empty() {
        println!(
            "{}",
            "No functions found above complexity threshold. Consider lowering --min-complexity."
                .yellow()
        );
        return Ok(());
    }

    println!(
        "📊 Found {} functions requiring AI-generated tests:",
        target_functions.len().to_string().bright_green()
    );

    for func in &target_functions {
        print_function_summary(func);
    }

    if cli.dry_run {
        println!("\n{}", "🏃 Dry run mode - skipping API calls".bright_blue());
        show_generation_plan(&target_functions);
        return Ok(());
    }

    // Create HTTP client
    let client = Client::new();

    // Generate test suites
    let mut all_tests = Vec::new();
    for (index, func) in target_functions.iter().enumerate() {
        println!(
            "\n{} Generating tests for: {} ({}/{})...",
            "🤖".bright_green(),
            func.name.bright_cyan(),
            index + 1,
            target_functions.len()
        );

        match generate_test_for_function(&client, &api_key, &base_url, &model, func, &source_code)
            .await
        {
            Ok(test_suite) => {
                println!(
                    "   ✅ Generated {} test cases",
                    test_suite.test_count.to_string().bright_green()
                );
                if cli.verbose {
                    println!("   📝 Generated code preview:");
                    let preview = test_suite
                        .test_code
                        .lines()
                        .take(3)
                        .collect::<Vec<_>>()
                        .join("\n");
                    println!("      {}", preview.dimmed());
                }
                all_tests.push(test_suite);
            }
            Err(e) => {
                println!("   ❌ Failed: {}", e.to_string().bright_red());
            }
        }

        // Add delay to avoid API rate limits
        tokio::time::sleep(tokio::time::Duration::from_millis(1000)).await;
    }

    if !all_tests.is_empty() {
        save_generated_tests(&all_tests, &cli.output, &cli.file).await?;
        println!(
            "\n{} Tests saved to: {}",
            "🎉".bright_green(),
            cli.output.display().to_string().bright_cyan()
        );
        
        let total_tests: usize = all_tests.iter().map(|t| t.test_count).sum();
        println!(
            "📊 Summary: {} test functions generated for {} source functions",
            total_tests.to_string().bright_yellow(),
            all_tests.len().to_string().bright_cyan()
        );
    }

    Ok(())
}

fn print_function_summary(func: &FunctionComplexity) {
    let complexity_color = match func.return_complexity {
        ComplexityRating::Low => "🟢",
        ComplexityRating::Medium => "🟡",
        ComplexityRating::High => "🟠",
        ComplexityRating::VeryHigh => "🔴",
    };

    println!(
        "   {} {} (CC: {}, Lines: ~{})",
        complexity_color,
        func.name.bright_white(),
        func.cyclomatic_complexity.to_string().bright_cyan(),
        func.parameter_count * 5  // Estimate line count
    );
}

fn show_generation_plan(functions: &[&FunctionComplexity]) {
    println!("\n📋 Test Generation Plan:");
    
    let estimated_cost = functions.len() as f64 * 0.003; // About $0.003 per function
    println!("💰 Estimated cost: ${:.4}", estimated_cost);
    
    println!("\n📝 Test types to generate:");
    println!("   • Basic functionality tests");
    println!("   • Edge case tests");
    println!("   • Error condition tests");
    println!("   • Parameter validation tests");
}

async fn generate_test_for_function(
    client: &Client,
    api_key: &str,
    base_url: &str,
    model: &str,
    func: &FunctionComplexity,
    source_code: &str,
) -> Result<GeneratedTestSuite> {
    let function_code = extract_function_code(source_code, func)?;

    let system_prompt = format!(
        r#"You are an expert Rust developer. Generate comprehensive unit tests for the given Rust function.

Requirements:
1. Use standard Rust testing conventions with #[test] attribute
2. Generate 3-5 test functions covering different scenarios
3. Include edge cases and error conditions where applicable
4. Use descriptive test names like test_function_name_scenario()
5. Use appropriate assert macros (assert_eq!, assert!, etc.)
6. Return ONLY the test code, properly formatted and ready to compile

Function Analysis:
- Complexity: {} (Cyclomatic: {})
- Parameters: {}
- Analysis: Function has {} loops, {} max nesting depth"#,
        format!("{:?}", func.return_complexity),
        func.cyclomatic_complexity,
        func.parameter_count,
        func.details.loops,
        func.details.max_nesting_depth
    );

    let user_prompt = format!(
        r#"Generate comprehensive unit tests for this Rust function:

```rust
{}
```

Please generate multiple test cases covering:
1. Normal operation
2. Edge cases (empty inputs, boundary values)
3. Error conditions (if applicable)
4. Different parameter combinations

Return only the Rust test code with #[test] functions."#,
        function_code
    );

    let request = OpenRouterRequest {
        model: model.to_string(),
        messages: vec![
            Message {
                role: "system".to_string(),
                content: system_prompt,
            },
            Message {
                role: "user".to_string(),
                content: user_prompt,
            },
        ],
        temperature: 0.3,
        max_tokens: 2000,
    };

    let response = client
        .post(&format!("{}/chat/completions", base_url))
        .header("Authorization", &format!("Bearer {}", api_key))
        .header("Content-Type", "application/json")
        .header("HTTP-Referer", "https://github.com/corust-ai/interview-prep")
        .header("X-Title", "Rust AI Test Generator")
        .json(&request)
        .send()
        .await
        .context("Failed to send request to OpenRouter")?;

    if !response.status().is_success() {
        let status = response.status();
        let text = response.text().await.unwrap_or_default();
        return Err(anyhow::anyhow!("API request failed with status {}: {}", status, text));
    }

    let api_response: OpenRouterResponse = response
        .json()
        .await
        .context("Failed to parse response from OpenRouter")?;

    let test_code = api_response
        .choices
        .first()
        .context("No choices in API response")?
        .message
        .content
        .clone();

    let test_count = test_code.matches("#[test]").count();

    Ok(GeneratedTestSuite {
        function_name: func.name.clone(),
        test_code,
        test_count,
    })
}

fn extract_function_code(source_code: &str, func: &FunctionComplexity) -> Result<String> {
    let lines: Vec<&str> = source_code.lines().collect();
    
    // Find function definition
    for (i, line) in lines.iter().enumerate() {
        if line.contains(&format!("fn {}", func.name)) 
            || line.contains(&format!("pub fn {}", func.name))
            || line.contains(&format!("async fn {}", func.name)) {
            
            // Extract from function start to matching brace end
            let mut brace_count = 0;
            let mut function_lines = Vec::new();
            let mut in_function = false;
            
            for line in &lines[i..] {
                function_lines.push(*line);
                
                for ch in line.chars() {
                    match ch {
                        '{' => {
                            brace_count += 1;
                            in_function = true;
                        },
                        '}' => {
                            brace_count -= 1;
                            if in_function && brace_count == 0 {
                                return Ok(function_lines.join("\n"));
                            }
                        },
                        _ => {}
                    }
                }
            }
            break;
        }
    }
    
    Err(anyhow::anyhow!("Could not extract function code for {}", func.name))
}

async fn save_generated_tests(
    test_suites: &[GeneratedTestSuite],
    output_path: &PathBuf,
    source_file: &PathBuf,
) -> Result<()> {
    // Ensure output directory exists
    if let Some(parent) = output_path.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("Failed to create directory: {}", parent.display()))?;
    }

    let mut full_content = String::new();
    
    // File header
    full_content.push_str(&format!(
        r#"//! AI-Generated Unit Tests
//! Source: {}
//! Generated: {}
//! 
//! This file contains automatically generated unit tests.
//! Review and modify as needed before using in production.

// Import the module being tested
use super::*;

"#,
        source_file.display(),
        chrono::Utc::now().format("%Y-%m-%d %H:%M:%S UTC")
    ));

    // Add all generated tests
    for (index, test_suite) in test_suites.iter().enumerate() {
        full_content.push_str(&format!(
            "// ========================================\n// Tests for function: {} ({} test functions)\n// ========================================\n\n",
            test_suite.function_name,
            test_suite.test_count
        ));
        
        // Clean and format test code
        let cleaned_code = clean_generated_code(&test_suite.test_code);
        full_content.push_str(&cleaned_code);
        
        if index < test_suites.len() - 1 {
            full_content.push_str("\n\n");
        }
    }

    fs::write(output_path, full_content)
        .with_context(|| format!("Failed to write tests to: {}", output_path.display()))?;

    Ok(())
}

fn clean_generated_code(code: &str) -> String {
    // Remove possible markdown code block markers
    let cleaned = code
        .replace("```rust", "")
        .replace("```", "")
        .trim()
        .to_string();
    
    // Ensure code ends with newline
    if !cleaned.ends_with('\n') {
        format!("{}\n", cleaned)
    } else {
        cleaned
    }
}