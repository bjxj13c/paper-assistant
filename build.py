"""
论文分析助手 - 一键打包构建脚本
================================
用法:
    python build.py              -> 打包为文件夹 (onedir)
    python build.py --onefile    -> 打包为单文件
    python build.py --installer  -> 打包 + 生成 NSIS 安装包
    python build.py --clean      -> 清理构建产物

要求:
    pip install pyinstaller
    安装包需要: NSIS (https://nsis.sourceforge.io)
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
SPEC = ROOT / "paper_assistant.spec"
APP_NAME = "PaperAssistant"
EXE_NAME = f"{APP_NAME}.exe"
NSIS_SCRIPT = ROOT / "installer.nsi"


def run(cmd, **kwargs):
    """运行命令并打印输出。"""
    print(f"  -> {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    return subprocess.run(cmd, check=True, **kwargs)


def clean():
    """清理构建产物。"""
    print("\n[CLEAN] 清理构建产物...")
    for d in [DIST, BUILD]:
        if d.exists():
            shutil.rmtree(d)
            print(f"  已删除: {d}")
    for pattern in ["*.spec.bak", "*.pyc"]:
        for f in ROOT.glob(pattern):
            f.unlink()
    # 删除 PyInstaller 缓存
    pycache = ROOT / "__pycache__"
    if pycache.exists():
        shutil.rmtree(pycache)
    print("[OK] 清理完成\n")


def check_dependencies():
    """检查打包依赖。"""
    print("[CHECK] 检查依赖...")
    try:
        import PyInstaller
        print(f"  PyInstaller {PyInstaller.__version__} [v]")
    except ImportError:
        print("  [x] PyInstaller 未安装，请运行: pip install pyinstaller")
        sys.exit(1)
    print()


def build_pyinstaller(onefile=False):
    """使用 PyInstaller 打包。"""
    check_dependencies()

    # 清理旧构建
    if DIST.exists():
        shutil.rmtree(DIST)
    if BUILD.exists():
        shutil.rmtree(BUILD)

    print(f"\n[BUILD] 开始打包 ({'单文件' if onefile else '文件夹'}模式)...")
    print("=" * 60)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(SPEC),
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--noconfirm",
        "--clean",
    ]
    if onefile:
        cmd.append("--onefile")

    run(cmd)

    # 验证输出（处理可能的中文目录名）
    cn_dir = DIST / "论文分析助手"
    en_dir = DIST / APP_NAME
    if cn_dir.exists() and not en_dir.exists():
        shutil.move(str(cn_dir), str(en_dir))
        print(f"  重命名: {cn_dir.name} -> {en_dir.name}")

    # 重命名 exe
    cn_exe = en_dir / "论文分析助手.exe"
    en_exe = en_dir / EXE_NAME
    if cn_exe.exists() and not en_exe.exists():
        shutil.move(str(cn_exe), str(en_exe))
        print(f"  重命名: {cn_exe.name} -> {en_exe.name}")

    if onefile:
        exe_path = DIST / EXE_NAME
    else:
        exe_path = en_dir / EXE_NAME

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n[OK] 打包成功!")
        print(f"   输出: {exe_path}")
        print(f"   大小: {size_mb:.1f} MB")
        if not onefile:
            folder_size = sum(f.stat().st_size for f in (DIST / APP_NAME).rglob("*")) / (1024 * 1024)
            print(f"   文件夹大小: {folder_size:.1f} MB")
        return exe_path
    else:
        print(f"\n[ERROR] 打包失败: 未找到 {exe_path}")
        print(f"   dist 目录内容: {list(DIST.rglob('*'))[:10]}")
        sys.exit(1)


def build_installer():
    """生成 NSIS 安装包。"""
    print("\n[BUILD] 生成 Windows 安装包...")

    if not NSIS_SCRIPT.exists():
        print(f"[ERROR] 未找到 NSIS 脚本: {NSIS_SCRIPT}")
        print("   请先运行 python build.py 生成 dist 文件夹")
        sys.exit(1)

    # 查找 NSIS
    nsis_paths = [
        r"C:\Program Files (x86)\NSIS\makensis.exe",
        r"C:\Program Files\NSIS\makensis.exe",
    ]
    makensis = None
    for p in nsis_paths:
        if Path(p).exists():
            makensis = p
            break

    if not makensis:
        # 尝试从 PATH 找
        which = shutil.which("makensis")
        if which:
            makensis = which

    if not makensis:
        print("\n[WARN]  未找到 NSIS (makensis.exe)")
        print("   请安装 NSIS: https://nsis.sourceforge.io/Download")
        print("   或使用 Inno Setup 等工具手动打包 dist 文件夹")
        print(f"\n   dist 文件夹位置: {DIST / APP_NAME}")
        return None

    print(f"  NSIS: {makensis}")

    # 删除之前的安装包
    old_installers = list(ROOT.glob("*.exe"))
    for f in old_installers:
        if "setup" in f.name.lower() or "install" in f.name.lower():
            f.unlink()

    run([makensis, str(NSIS_SCRIPT)])

    # 查找生成的安装包
    installer = list(ROOT.glob(f"{APP_NAME}*Setup*.exe"))
    if installer:
        size_mb = installer[0].stat().st_size / (1024 * 1024)
        print(f"\n[OK] 安装包生成成功!")
        print(f"   文件: {installer[0].name}")
        print(f"   大小: {size_mb:.1f} MB")
        return installer[0]
    else:
        print("\n[WARN]  未找到生成的安装包，请检查 NSIS 输出")
        return None


def main():
    parser = argparse.ArgumentParser(description="论文分析助手 - 一键打包")
    parser.add_argument("--onefile", action="store_true", help="打包为单文件 (启动较慢)")
    parser.add_argument("--installer", action="store_true", help="同时生成 NSIS 安装包")
    parser.add_argument("--clean", action="store_true", help="清理构建产物后退出")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("  [Paper] 论文分析助手 - 构建工具")
    print("=" * 60)

    if args.clean:
        clean()
        return

    # 1. PyInstaller 打包
    exe_path = build_pyinstaller(onefile=args.onefile)

    # 2. NSIS 安装包
    if args.installer:
        installer_path = build_installer()
        if installer_path:
            print("\n" + "=" * 60)
            print("  [DONE] 打包完成! 可分发文件:")
            print(f"  便携版: {exe_path.parent}")
            print(f"  安装包: {installer_path}")
            print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("  [DONE] 打包完成!")
        print(f"  输出目录: {exe_path.parent}")
        print(f"  直接运行: {exe_path}")
        print()
        print("  [TIP] 提示:")
        print(f"    python build.py --installer  生成安装包")
        print(f"    将 '{exe_path.parent.name}' 文件夹打包为 .zip 即可分发")
        print("=" * 60)

    print()


if __name__ == "__main__":
    main()
