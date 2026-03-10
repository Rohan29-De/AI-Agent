#!/usr/bin/env python3
"""
OpenClaw-inspired Autonomous Internet Exploration Agent
Researches founders and CEOs using LLM + web scraping.

Usage:
    python main.py "Elon Musk"
    python main.py "Sam Altman" --iterations 5
    python main.py "Jensen Huang" --resume
"""

import argparse
import sys
import os

from rich.console import Console
from agent import ResearchAgent
from output.formatter import save_json, save_markdown, print_report_summary

console = Console()


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous founder/CEO research agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "Elon Musk"
  python main.py "Sam Altman" --iterations 5
  python main.py "Sundar Pichai" --resume --output-dir results
        """
    )
    
    parser.add_argument(
        "target",
        type=str,
        help="Name of the founder or CEO to research"
    )
    parser.add_argument(
        "--iterations", "-i",
        type=int,
        default=3,
        help="Max research iterations (default: 3). More = deeper research."
    )
    parser.add_argument(
        "--urls-per-iter", "-u",
        type=int,
        default=4,
        help="Max URLs to scrape per iteration (default: 4)"
    )
    parser.add_argument(
        "--resume", "-r",
        action="store_true",
        help="Resume from previous session if available"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="output",
        help="Output directory (default: output/)"
    )
    parser.add_argument(
        "--no-markdown",
        action="store_true",
        help="Skip markdown report generation"
    )

    args = parser.parse_args()

    # Validate env
    if not os.environ.get("GROQ_API_KEY"):
        # Try loading .env manually
        if os.path.exists(".env"):
            from dotenv import load_dotenv
            load_dotenv()
        
        if not os.environ.get("GROQ_API_KEY"):
            console.print("[bold red]ERROR:[/bold red] GROQ_API_KEY not found.")
            console.print("Create a .env file with: GROQ_API_KEY=your_key_here")
            sys.exit(1)

    target = args.target.strip()
    
    console.print(f"\n[bold]🔍 Research target:[/bold] [cyan]{target}[/cyan]")
    
    try:
        # Run the agent
        agent = ResearchAgent(
            target=target,
            max_iterations=args.iterations,
            max_urls_per_iter=args.urls_per_iter,
            resume=args.resume
        )
        
        report = agent.run()

        if "error" in report:
            console.print(f"[red]Report compilation error: {report['error']}[/red]")
            console.print("[dim]Raw LLM output saved to debug.txt[/dim]")
            with open("debug.txt", "w") as f:
                f.write(str(report.get("raw", "")))
            sys.exit(1)

        # Print summary
        print_report_summary(report)

        # Save outputs
        json_path = save_json(report, target, args.output_dir)
        console.print(f"\n[green]✓ JSON report saved:[/green] {json_path}")

        if not args.no_markdown:
            md_path = save_markdown(report, target, args.output_dir)
            console.print(f"[green]✓ Markdown report saved:[/green] {md_path}")

        console.print(f"\n[bold green]✨ Research complete![/bold green]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Saving progress...[/yellow]")
        agent.memory.save()
        console.print("[dim]Session saved. Resume with --resume flag.[/dim]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Fatal error:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()