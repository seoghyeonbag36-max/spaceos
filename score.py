"""SpaceOS 거점 점수 실측 실행 (간편 런처).

cmd에서 `-m` 없이 실행:
    cd C:\\Users\\USER\\Documents\\Claude\\Projects\\SpaceOS
    python score.py
"""
import os
import sys

# 이 파일이 있는 폴더(repo 루트)를 import 경로에 추가 → data 패키지 인식
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.run_collection import main

if __name__ == "__main__":
    main()
