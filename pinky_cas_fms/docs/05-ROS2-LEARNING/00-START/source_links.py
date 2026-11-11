"""강의 원본을 읽기 전용으로 찾고, 필요할 때 로컬 HTML 링크 목록을 만든다."""

import argparse
import hashlib
from html import escape
import json
from pathlib import Path
import tempfile
import webbrowser


DEFAULT_ROOT = Path.home() / "Developer/Projects/PhysicalAI/dev_ws"
MANIFEST = Path(__file__).with_name("sources.json")


def source_path(root, entry):
    # 자료별 경로는 상대 경로다. 각 팀원의 원본 폴더는 --root로 지정한다.
    return root / entry["path"]


def check_sources(root, entries):
    expected = {entry["path"] for entry in entries}
    folders = {Path(path).parent for path in expected}
    actual = {
        path.relative_to(root).as_posix()
        for folder in folders
        for path in (root / folder).glob("*.html")
        if path.is_file()
    }
    differences = expected ^ actual
    for path in sorted(differences):
        print(f"목록 불일치: {path}")
    matched = 0
    for entry in entries:
        path = source_path(root, entry)
        if not path.is_file():
            continue
        # 큰 HTML은 통째로 메모리에 올리지 않고 파일 스트림으로 해시를 계산한다.
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest == entry["sha256"]:
            matched += 1
        else:
            print(f"해시 불일치: {entry['path']}")
    print(f"원본 SHA-256 일치: {matched}/{len(entries)}")
    return matched == len(entries) and not differences


def write_local_index(root, entries):
    rows = []
    for entry in entries:
        path = source_path(root, entry)
        label = escape(f"{entry['id']} · {entry['title']}")
        if path.is_file():
            target = escape(path.resolve().as_uri(), quote=True)
            rows.append(f'<li><a href="{target}">{label}</a></li>')
        else:
            rows.append(f"<li>{label} · 원본 경로 확인 필요</li>")
    # 생성물은 시스템 임시 경로에 두고 원본이나 저장소에 쓰지 않는다.
    folder = Path(tempfile.mkdtemp(prefix="cas-lecture-links-"))
    index = folder / "lectures.html"
    index.write_text(
        '<!doctype html><html lang="ko"><meta charset="utf-8">'
        "<title>CAS 학습용 강의 원본 링크</title>"
        "<h1>SeSAC 강의 원본 링크</h1><ul>"
        + "\n".join(rows)
        + "</ul></html>\n",
        encoding="utf-8",
    )
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--open", metavar="ID", help="예: ROS2-02")
    mode.add_argument("--html", action="store_true", help="로컬 링크 목록 생성")
    mode.add_argument("--check", action="store_true", help="HTML 목록과 해시 검증")
    args = parser.parse_args()
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    root = args.root.expanduser()
    if args.check:
        return 0 if check_sources(root, entries) else 1
    if args.html:
        print(write_local_index(root, entries))
        return 0

    entry = next((row for row in entries if row["id"] == args.open.upper()), None)
    if entry is None:
        parser.error(f"알 수 없는 강의 ID: {args.open}")
    path = source_path(root, entry)
    if not path.is_file():
        parser.error(f"원본 파일을 찾을 수 없습니다: {path}")
    print(path)
    return 0 if webbrowser.open(path.resolve().as_uri()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
