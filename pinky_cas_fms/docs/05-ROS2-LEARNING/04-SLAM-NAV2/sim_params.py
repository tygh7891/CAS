"""새로 만든 단일 로봇 시뮬레이션 지도에 쓸 Nav2 설정 사본을 만든다."""

import argparse
from pathlib import Path

import yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    params = yaml.safe_load(args.source.read_text(encoding="utf-8"))
    for group in ("local_costmap", "global_costmap"):
        costmap = params[group][group]["ros__parameters"]
        # 다른 레이어와 필터는 그대로 둔다. X자 코스 전용 마스크만 분리한다.
        costmap["filters"] = [
            name for name in costmap.get("filters", []) if name != "keepout_filter"
        ]
    # 'x'는 새 파일만 만든다. 원본이나 기존 실습 사본을 덮어쓰지 않는다.
    with args.output.open("x", encoding="utf-8") as stream:
        yaml.safe_dump(params, stream, sort_keys=False, allow_unicode=True)
    print(args.output)


if __name__ == "__main__":
    main()
