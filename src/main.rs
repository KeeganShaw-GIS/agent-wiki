use agent_wiki::{commands, root};
use anyhow::Result;
use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(
    name = "agent-wiki",
    about = "Documentation wiki manager for LLM agents",
    version
)]
struct Cli {
    #[command(subcommand)]
    command: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// One-time setup — creates .agent-wiki/ as a nested git repo
    Init {
        #[arg(long, default_value = "CLAUDE.md", help = "Doc filename (e.g. CLAUDE.md, AGENTS.md)")]
        doc_filename: String,
        #[arg(long, help = "Skip absorbing existing doc files from the repo")]
        no_detect_target_docs: bool,
        #[arg(long, help = "Skip installing git hooks")]
        no_hooks: bool,
        #[arg(long, help = "Remote URL for the wiki git repo (for backup/recovery)")]
        wiki_remote: Option<String>,
    },
    /// Sync schema ↔ wiki docs ↔ target symlinks
    Push {
        #[arg(long, help = "Verify and repair broken symlinks")]
        verify: bool,
    },
    /// Absorb unmanaged doc files from the target repo into the wiki
    Pull {
        #[arg(long, default_value = "repo", value_parser = ["repo", "wiki", "skip"])]
        strategy: String,
    },
    /// Replace symlinks with real files, detaching from wiki
    Eject {
        #[arg(long, help = "Schema rel-path to eject (default: all)")]
        scope: Option<String>,
        #[arg(long, help = "Also remove .agent-wiki/ entirely (docs preserved in git history)")]
        purge: bool,
    },
    /// Log changed files that need doc updates (called by pre-commit hook)
    DetectDrift {
        #[arg(long)]
        staged: bool,
    },
    /// Show pending drift statistics
    Status {
        #[arg(long, help = "Scope: path, diff, staged, or git ref")]
        scope: Option<String>,
    },
    /// Manually clear one or all wiki status flags
    ClearFlags {
        #[arg(long, action = clap::ArgAction::Append, help = "Flag to clear (repeatable; omit to clear all)")]
        flag: Vec<String>,
    },
    /// Install git hooks and wrapper script in the target repo
    HookSetup {
        #[arg(long)]
        no_pre_commit: bool,
        #[arg(long)]
        no_post_checkout: bool,
    },
}

fn main() {
    let cli = Cli::parse();
    if let Err(e) = run(cli) {
        eprintln!("Error: {e:#}");
        std::process::exit(1);
    }
}

fn run(cli: Cli) -> Result<()> {
    match cli.command {
        Cmd::Init { doc_filename, no_detect_target_docs, no_hooks, wiki_remote } => {
            commands::init::run(commands::init::InitArgs {
                doc_filename,
                no_detect_target_docs,
                no_hooks,
                wiki_remote,
            })?;
        }
        Cmd::Push { verify } => {
            let ctx = root::find_wiki_ctx()?;
            commands::push::run(&ctx, verify)?;
        }
        Cmd::Pull { strategy } => {
            let ctx = root::find_wiki_ctx()?;
            commands::pull::run(&ctx, &strategy)?;
        }
        Cmd::Eject { scope, purge } => {
            let ctx = root::find_wiki_ctx()?;
            commands::eject::run(&ctx, scope.as_deref(), purge)?;
        }
        Cmd::DetectDrift { staged } => {
            let ctx = root::find_wiki_ctx()?;
            commands::detect_drift::run(&ctx, staged)?;
        }
        Cmd::Status { scope } => {
            let ctx = root::find_wiki_ctx()?;
            commands::status::run(&ctx, scope.as_deref())?;
        }
        Cmd::ClearFlags { flag } => {
            let ctx = root::find_wiki_ctx()?;
            commands::clear_flags::run(&ctx, &flag)?;
        }
        Cmd::HookSetup { no_pre_commit, no_post_checkout } => {
            let ctx = root::find_wiki_ctx()?;
            commands::hook_setup::run(&ctx, !no_pre_commit, !no_post_checkout)?;
        }
    }
    Ok(())
}
