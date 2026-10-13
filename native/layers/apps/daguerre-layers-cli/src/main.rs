// Modified for Daguerre: incorporated engine, own identity and historical import.
#![deny(clippy::unwrap_used, clippy::expect_used, clippy::panic, clippy::unimplemented, clippy::todo, clippy::unreachable)]

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let code = daguerre_layers_cli::run(&args, &mut std::io::stdout(), &mut std::io::stderr());
    std::process::exit(code);
}
