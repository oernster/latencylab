import sys
from pathlib import Path

EXCLUDED_DIRS = {"venv", ".venv", ".git", "__pycache__"}
INCLUDED_EXTENSIONS = {
    ".py",
    ".json",
    ".md",
    ".csv",
    ".yml",
    ".yaml",
    ".toml",
}

OUTPUT_FILE = "ALL_SOURCES.txt"


def should_exclude(path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.parts)


def print_progress(current, total, bar_width=40):
    progress = current / total
    filled = int(bar_width * progress)
    bar = "#" * filled + "-" * (bar_width - filled)
    sys.stdout.write(
        f"\r[{bar}] {progress * 100:6.2f}% ({current}/{total} files)"
    )
    sys.stdout.flush()


def main(src_dir: Path):
    files = sorted(
        p for p in src_dir.rglob("*")
        if (
            p.is_file()
            and p.suffix.lower() in INCLUDED_EXTENSIONS
            and not should_exclude(p)
        )
    )

    total_files = len(files)
    if total_files == 0:
        print("No matching source files found.")
        return

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        out.write(
            "# ============================================================\n"
            "# CONCATENATED SOURCE FILE\n"
            "# Includes: .py, .json, .md, .csv, .yml, .yaml, .toml\n"
            "# Each section is a file from the original directory tree\n"
            "# ============================================================\n\n"
        )

        for idx, path in enumerate(files, start=1):
            rel_path = path.relative_to(src_dir)

            out.write("\n")
            out.write("#" * 80 + "\n")
            out.write(f"# FILE: {rel_path}\n")
            out.write(f"# TYPE: {path.suffix}\n")
            out.write("#" * 80 + "\n\n")

            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = path.read_text(encoding="utf-8", errors="replace")

            out.write(content.rstrip())
            out.write("\n\n")

            print_progress(idx, total_files)

    print(f"\nDone. Wrote {total_files} files into {OUTPUT_FILE}")


if __name__ == "__main__":
    main(Path("."))
