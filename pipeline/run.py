#!/usr/bin/env python3
"""파이프라인 모듈 실행기. `python -I pipeline/run.py e1.build <인자...>` 처럼 쓴다.

-I(격리 모드)에서는 현재 디렉터리가 sys.path에 없어 패키지를 못 찾으므로 저장소 루트를 명시적으로 넣는다.
"""
import pathlib
import runpy
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
mod = sys.argv[1]
sys.argv = [f"pipeline/{mod.replace('.', '/')}.py"] + sys.argv[2:]
runpy.run_module(f"pipeline.{mod}", run_name="__main__", alter_sys=True)
