from git import Repo
import collections
import argparse
from fnmatch import fnmatch
from pathlib import PurePosixPath
from rich.progress import track
from rich import print
from rich.table import Table
from git.types import PathLike


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
        table["Fraction"].append(
            table["Total changed"][i] / total_changed if total_changed else float("NaN")
        )
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
        frac = total / total_changed if total_changed else float("NaN")
        table.add_row(
            author,
            f"{ins}",
            f"{dels}",
            f"{total}",
            f"{frac:.1%}",
        )

    print(table)


def print_stats_by_extension_and_author(repo_path, stats_by_ext):
    """Print breakdown of contributions by file extension and author."""
    # Calculate totals per extension
    ext_totals = collections.defaultdict(lambda: {"insertions": 0, "deletions": 0})
    for author_exts in stats_by_ext.values():
        for ext, counts in author_exts.items():
            ext_totals[ext]["insertions"] += counts["insertions"]
            ext_totals[ext]["deletions"] += counts["deletions"]

    total_changed = sum(
        ext_totals[ext]["insertions"] + ext_totals[ext]["deletions"]
        for ext in ext_totals
    )

    if total_changed == 0:
        return

    print()
    table = Table(title=f"Contribution by Extension and Author for {repo_path}")
    table.add_column("Extension", style="green", no_wrap=True)
    table.add_column("Author", style="cyan", no_wrap=True)
    table.add_column("Insertions", justify="right")
    table.add_column("Deletions", justify="right")
    table.add_column("Total Changed", justify="right")
    table.add_column("Fraction", justify="right")

    # Sort by extension, then by total changed descending
    for ext in sorted(
        ext_totals.keys(),
        key=lambda x: -(ext_totals[x]["insertions"] + ext_totals[x]["deletions"]),
    ):
        ext_display = ext or "(no extension)"
        # Get all authors for this extension, sorted by contribution
        authors_for_ext = sorted(
            [
                (
                    author,
                    stats_by_ext[author].get(ext, {"insertions": 0, "deletions": 0}),
                )
                for author in stats_by_ext.keys()
                if ext in stats_by_ext[author]
                and (
                    stats_by_ext[author][ext]["insertions"] > 0
                    or stats_by_ext[author][ext]["deletions"] > 0
                )
            ],
            key=lambda x: -(x[1]["insertions"] + x[1]["deletions"]),
        )

        for i, (author, counts) in enumerate(authors_for_ext):
            ins = counts["insertions"]
            dels = counts["deletions"]
            total = ins + dels
            frac = total / total_changed if total_changed else float("NaN")
            # Only show extension name in first row for readability
            ext_col = ext_display if i == 0 else ""
            table.add_row(
                ext_col,
                author,
                f"{ins}",
                f"{dels}",
                f"{total}",
                f"{frac:.1%}",
            )

    print(table)


def _is_excluded(
    file_path: PathLike, exclude_globs: list[str], exclude_names: set[str]
) -> bool:
    p = PurePosixPath(file_path)
    base = p.name
    if base in exclude_names:
        return True
    path_str = str(p)
    return any(fnmatch(path_str, pat) or fnmatch(base, pat) for pat in exclude_globs)


def _is_path_included(file_path: PathLike, path_filters: list[str]) -> bool:
    """Check if file_path is within one of the specified directories.
    If path_filters is empty, all paths are included.
    """
    if not path_filters:
        return True
    p = PurePosixPath(file_path)
    path_str = str(p)
    return any(path_str.startswith(pf.rstrip("/")) for pf in path_filters)


def _parse_semicolon_list(arg: str) -> list[str]:
    """Parse semicolon-separated argument into a list of stripped strings."""
    if not arg:
        return []
    return [p.strip() for p in arg.split(";") if p.strip()]


def main():
    parser = argparse.ArgumentParser(
        description="Show git contribution stats by author."
    )
    parser.add_argument("repo", nargs="+", help="One or more git repository paths.")
    parser.add_argument("-m", help="Output Markdown")
    parser.add_argument(
        "--exclude-glob",
        type=_parse_semicolon_list,
        default=[],
        help="Glob patterns to exclude (semicolon-separated), e.g. '*.json;*.csv' or 'docs/*'.",
    )
    parser.add_argument(
        "--exclude-name",
        type=_parse_semicolon_list,
        default=[],
        help="Exact file names to exclude (semicolon-separated), e.g. 'package-lock.json;poetry.lock'.",
    )
    parser.add_argument(
        "--path-filter",
        type=_parse_semicolon_list,
        default=[],
        help="Only count files within these directories (semicolon-separated), e.g. 'src/;backend/'.",
    )

    args = parser.parse_args()
    exclude_globs = args.exclude_glob
    exclude_names = set(args.exclude_name)
    path_filters = args.path_filter

    for repo_path in args.repo:
        repo = Repo(repo_path)
        stats = collections.defaultdict(lambda: {"insertions": 0, "deletions": 0})
        stats_by_ext = collections.defaultdict(
            lambda: collections.defaultdict(lambda: {"insertions": 0, "deletions": 0})
        )

        total_commits = int(repo.git.rev_list("--count", "HEAD", "--no-merges"))

        try:
            for commit in track(
                repo.iter_commits(no_merges=True),
                description=f"Processing {repo_path}",
                total=total_commits,
            ):
                author = commit.author.name or commit.author.email

                insertions = 0
                deletions = 0
                for file_path, fs in commit.stats.files.items():
                    if not _is_path_included(file_path, path_filters):
                        continue
                    if _is_excluded(file_path, exclude_globs, exclude_names):
                        continue

                    file_ins = fs.get("insertions", 0)
                    file_dels = fs.get("deletions", 0)
                    insertions += file_ins
                    deletions += file_dels

                    # Extract file extension
                    ext = PurePosixPath(file_path).suffix or ""
                    stats_by_ext[author][ext]["insertions"] += file_ins
                    stats_by_ext[author][ext]["deletions"] += file_dels

                stats[author]["insertions"] += insertions
                stats[author]["deletions"] += deletions
        except KeyboardInterrupt:
            print("\n**Interrupted by user, showing results so far...**\n")

        print_stats(repo_path, stats)
        print_stats_by_extension_and_author(repo_path, stats_by_ext)


if __name__ == "__main__":
    main()
