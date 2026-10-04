import subprocess

GIT = r"C:\Users\DELL\.workbuddy\binaries\PortableGit\versions\1.2.0\mingw64\bin\git.exe"


def run(*args):
    r = subprocess.run([GIT, *args], capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


print("1. 暂存并提交")
print(run("add", "."))
print(run("commit", "-m", "docs: 添加 CI 徽章与贡献指南"))

print("\n2. 推送")
out = run("push", "origin", "main")
print(out)

print("\n3. 验证远程提交")
print(run("log", "origin/main", "--oneline", "-3"))
