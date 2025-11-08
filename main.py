from git import Repo
import collections
import argparse
from rich.progress import track
from rich import print
from rich.table import Table


def print_stats(repo_path, stats):
    # Compute total change across all authors
    total_changed = sum(v["insertions"] + v["deletions"] for v in stats.values())

    table = Table(title=f"[bold]Contribution Stats for {repo_path}[/bold]")
    table.add_column("Author", style="cyan", no_wrap=True)
    table.add_column("Insertions", justify="right")
    table.add_column("Deletions", justify="right")
    table.add_column("Total Changed", justify="right")
    table.add_column("Fraction", justify="right")

    for author, s in sorted(
        stats.items(), key=lambda x: -(x[1]["insertions"] + x[1]["deletions"])
    ):
        ins = s["insertions"]
        dels = s["deletions"]
        total = ins + dels
        frac = total / total_changed if total_changed else 0.0
        table.add_row(
            author,
            f"{ins}",
            f"{dels}",
            f"{total}",
            f"{frac:.1%}",
        )

    print(table)


def main():
    parser = argparse.ArgumentParser(
        description="Show git contribution stats by author."
    )
    parser.add_argument("repo", nargs="+", help="One or more git repository paths.")

    args = parser.parse_args()

    for repo_path in args.repo:
        repo = Repo(repo_path)
        stats = collections.defaultdict(lambda: {"insertions": 0, "deletions": 0})

        total_commits = int(repo.git.rev_list("--count", "HEAD", "--no-merges"))

        for commit in track(
            repo.iter_commits(no_merges=True),
            description=f"Processing {repo_path}",
            total=total_commits,
        ):
            author = commit.author.name or commit.author.email
            s = commit.stats.total
            stats[author]["insertions"] += s.get("insertions", 0)
            stats[author]["deletions"] += s.get("deletions", 0)

        print_stats(repo_path, stats)


if __name__ == "__main__":
    main()
