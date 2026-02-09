from git import Repo
import collections
import argparse
from rich.progress import track
from rich import print
from rich.table import Table


def compute_table(stats):
    table = {
        "Author": [],
        "Insertions": [],
        "Deletions": [],
        "Total changed": [],
        "Fraction": [],
    }

    for author, s in stats.items():
        ins = s["insertions"]
        dels = s["deletions"]
        total = ins + dels
        table["Author"].append(author)
        table["Insertions"].append(ins)
        table["Deletions"].append(dels)
        table["Total changed"].append(total)

    total_changed = sum(table["Total changed"])
    for i in range(len(table["Author"])):
        table["Fraction"].append(table["Total changed"][i] / total_changed)
    return table, total_changed


def print_stats(repo_path, stats):
    table, total_changed = compute_table(stats)

    table = Table(title=f"Contribution Stats for {repo_path}")
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
    parser.add_argument("-m", help="Output Markdown")

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
