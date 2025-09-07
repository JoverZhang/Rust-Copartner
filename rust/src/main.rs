use clap::{Arg, Command};

fn main() {
    let matches = Command::new("rust-copartner")
        .version("0.1.0")
        .about("Rust code analysis tool for copartner")
        .subcommand(
            Command::new("parse")
                .about("Parse Rust code and extract information")
                .arg(
                    Arg::new("path")
                        .short('p')
                        .long("path")
                        .value_name("PATH")
                        .help("Path to Rust source file or directory")
                        .required(true),
                ),
        )
        .subcommand(
            Command::new("index")
                .about("Create index of code fragments")
                .arg(
                    Arg::new("project")
                        .short('p')
                        .long("project")
                        .value_name("PROJECT_PATH")
                        .help("Path to Rust project directory")
                        .required(true),
                ),
        )
        .get_matches();

    match matches.subcommand() {
        Some(("parse", sub_matches)) => {
            let path = sub_matches.get_one::<String>("path").unwrap();
            println!("Parsing Rust code at: {}", path);
            // TODO: Implement parsing logic
        }
        Some(("index", sub_matches)) => {
            let project = sub_matches.get_one::<String>("project").unwrap();
            println!("Creating index for project: {}", project);
            // TODO: Implement indexing logic
        }
        _ => {
            println!("No valid subcommand provided. Use --help for usage information.");
        }
    }
}