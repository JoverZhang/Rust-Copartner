use anyhow::{Context, Result};
use clap::Parser;
use rust_copartner::analyzer::{analyze_project, write_ndjson, AnalyzeConfig};
use std::fs::File;
use std::io::{self, BufWriter};
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(name = "project_analyzer", version, about = "Scan Rust sources and emit NDJSON metadata")] 
struct Cli {
    /// Root directory of Rust sources
    #[arg(long, value_name = "dir")]
    path: PathBuf,

    /// Repository identifier
    #[arg(long, value_name = "string")]
    repo_id: String,

    /// Output file for NDJSON (default stdout)
    #[arg(long, value_name = "file")]
    out: Option<PathBuf>,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let cfg = AnalyzeConfig { path: cli.path.clone(), repo_id: cli.repo_id.clone() };
    let records = analyze_project(&cfg)?;

    match cli.out {
        Some(p) => {
            let f = File::create(&p).with_context(|| format!("Failed to create {}", p.display()))?;
            write_ndjson(&records, &mut BufWriter::new(f))?;
        }
        None => {
            let mut out = io::stdout().lock();
            write_ndjson(&records, &mut out)?;
        }
    }
    Ok(())
}
