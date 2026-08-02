from pathlib import Path
print(__file__)
print(Path(__file__))
print(Path(__file__).resolve())
print("parents________")
print("===========>",Path(__file__).resolve().parents[2])
print(Path(__file__).resolve().parents[3])