import os
import sys
import subprocess
import shutil
import glob

# Ensure scripts folder is on sys.path so bundle_html can be imported
sys.path.insert(0, os.path.dirname(__file__))
import bundle_html


def find_compiler():
    # 1. Check in PATH
    # Prefer MinGW's g++ because the native GUI build uses MinGW-specific
    # flags such as -mwindows. A system LLVM clang++ may target MSVC instead.
    # Prefer MinGW's g++ because the native GUI build uses MinGW-specific flags such as -mwindows.
    for comp in ["g++", "clang++"]:
        p = shutil.which(comp)
        if p:
            return p
            
    # 2. Check the WinGet-installed WinLibs package. WinGet may install it
    # under the user's local package directory without adding it to PATH.

    # 2. Check the WinGet-installed WinLibs package
    local_app_data = os.environ.get("LOCALAPPDATA")
    winget_candidates = []
    if local_app_data:
        winget_bin = os.path.join(
            local_app_data,
            "Microsoft", "WinGet", "Packages",
            "BrechtSanders.WinLibs.MCF.UCRT_*", "mingw64", "bin"
        )
        winget_candidates.extend(glob.glob(os.path.join(winget_bin, "g++.exe")))
        winget_candidates.extend(glob.glob(os.path.join(winget_bin, "clang++.exe")))
    for c in winget_candidates:
        if os.path.exists(c):
            return c

    # 3. Check standard installation locations in C:\
    candidates = [
        r"C:\tools\llvm-mingw\bin\clang++.exe",
        r"C:\Program Files\LLVM\bin\clang++.exe",
        r"C:\Program Files (x86)\LLVM\bin\clang++.exe",
        r"C:\msys64\ucrt64\bin\g++.exe",
        r"C:\msys64\mingw64\bin\g++.exe",
        r"C:\tools\llvm\bin\clang++.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def build():
    compiler = find_compiler()
    if not compiler:
        print("[エラー] C++ コンパイラ (Clang++ または G++) が見つかりませんでした。")
        return False

    print(f"[発見] 使用コンパイラ: {compiler}")
    
    native_dir = os.path.join(os.path.dirname(__file__), "core", "native")
    engine_src = os.path.join(native_dir, "engine.cpp")
    cli_src = os.path.join(native_dir, "main_cli.cpp")
    webview_src = os.path.join(native_dir, "webview_main.cpp")
    resource_src = os.path.join(native_dir, "QuickDiskBench.rc")
    resource_obj = os.path.join(native_dir, "QuickDiskBench_res.o")

    script_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(script_dir, ".."))

    src_dir = os.path.join(repo_root, "src")
    engine_src = os.path.join(src_dir, "engine", "engine.cpp")
    cli_src = os.path.join(src_dir, "cli", "main_cli.cpp")
    gui_src = os.path.join(src_dir, "app", "main_gui.cpp")
    resource_src = os.path.join(src_dir, "app", "QuickDiskBench.rc")
    

    intermediate_dir = os.path.join(repo_root, "build", "intermediate")
    os.makedirs(intermediate_dir, exist_ok=True)
    resource_obj = os.path.join(intermediate_dir, "QuickDiskBench_res.o")

    webview_include = os.environ.get("WEBVIEW2_INCLUDE", r"C:\tools\webview2\build\native\include")
    if not os.path.isdir(webview_include):
        print(f"[エラー] WebView2 SDK headers not found: {webview_include}")
        return False
    
    dist_dir = os.path.join(os.path.dirname(__file__), "dist")
    binary_dir = os.path.join(dist_dir, "binary")
    os.makedirs(binary_dir, exist_ok=True)
    os.makedirs(os.path.join(binary_dir, "templates"), exist_ok=True)
    os.makedirs(os.path.join(binary_dir, "static", "css"), exist_ok=True)
    os.makedirs(os.path.join(binary_dir, "static", "js"), exist_ok=True)
    
    import bundle_html
    bundle_html.bundle(binary_dir)
    
    out_dll = os.path.join(native_dir, "engine_x64.dll")
    out_gui_exe = os.path.join(binary_dir, "QuickDiskBench.exe")
    out_cli_exe = os.path.join(binary_dir, "QuickDiskBench_cli.exe")

    dist_dir = os.path.join(repo_root, "dist")
    os.makedirs(dist_dir, exist_ok=True)

    # Compile the Windows application icon resource once and link it into the GUI.
    out_dll = os.path.join(dist_dir, "engine_x64.dll")
    out_gui_exe = os.path.join(dist_dir, "QuickDiskBench.exe")
    out_cli_exe = os.path.join(dist_dir, "QuickDiskBench_cli.exe")

    # 1. Bundle HTML into self-contained single-file HTML in build/intermediate
    print("\n[1/4] HTML/CSS/JS/画像を自己完結HTMLへバンドル中...")
    print("\n[1/5] HTML/CSS/JS/画像を自己完結HTMLへバンドル中...")
    bundled_html = bundle_html.bundle(intermediate_dir)
    if not os.path.exists(bundled_html):
        print("[エラー] 自己完結HTMLの生成に失敗しました。")
        return False

    out_dll = os.path.join(dist_dir, "engine_x64.dll")
    out_gui_exe = os.path.join(dist_dir, "QuickDiskBench.exe")
    out_cli_exe = os.path.join(dist_dir, "QuickDiskBench_cli.exe")

    # 2. Compile Windows application resource (icon, version info, embedded HTML)
    compiler_dir = os.path.dirname(compiler)
    windres = None
    for name in ("llvm-windres.exe", "windres.exe"):
        candidate = os.path.join(compiler_dir, name)
        if os.path.exists(candidate):
            windres = candidate
            break
    if not windres:
        windres = shutil.which("windres") or shutil.which("llvm-windres")
    if not windres:
        print("[エラー] Windows resource compiler (llvm-windres/windres) が見つかりませんでした。")
        return False
    cmd_res = [windres, resource_src, "-O", "coff", "-o", resource_obj]
    print(f"\n[0/3] Windows アイコンリソースをビルド中: {' '.join(cmd_res)}")
    res_res = subprocess.run(cmd_res, capture_output=True, text=True)

    app_dir = os.path.join(src_dir, "app")
    cmd_res = [
        windres,
        f"-I{app_dir}",
        f"-I{intermediate_dir}",
        f"-I{repo_root}",
        resource_src,
        "-O", "coff",
        "-o", resource_obj
    ]
    print(f"\n[2/4] リソース (アイコン・バージョン・埋め込みHTML) をコンパイル中: {' '.join(cmd_res)}")
    print(f"\n[2/5] リソース (アイコン・バージョン・埋め込みHTML) をコンパイル中: {' '.join(cmd_res)}")
    res_res = subprocess.run(cmd_res, capture_output=True, text=True, cwd=app_dir)
    if res_res.returncode != 0 or not os.path.exists(resource_obj):
        print("[失敗] アイコンリソースのビルドに失敗しました:")
        print("[失敗] リソースのビルドに失敗しました:")
        print(res_res.stderr)
        return False

    # 1. Build DLL
    # 3. Build DLL
    cmd_dll = [
        compiler,
        "-O3",
        "-shared",
        "-std=c++17",
        "-static",
        engine_src,
        "-o", out_dll,
        "-lkernel32"
    ]
    print(f"\n[1/3] DLL ビルド中: {' '.join(cmd_dll)}")
    print(f"\n[3/4] DLL ビルド中: {' '.join(cmd_dll)}")
    print(f"\n[3/5] DLL ビルド中: {' '.join(cmd_dll)}")
    res_dll = subprocess.run(cmd_dll, capture_output=True, text=True)
    if res_dll.returncode == 0 and os.path.exists(out_dll):
        print(f"[成功] C++ ネイティブ DLL を生成しました: {out_dll} ({os.path.getsize(out_dll)} bytes)")
        shutil.copy2(out_dll, os.path.join(binary_dir, "engine_x64.dll"))
    else:
        print("[失敗] DLL ビルドに失敗しました:")
        print(res_dll.stderr)
        return False

    # 2. Build 100% C++ Native WebView2 App (dist/QuickDiskBench.exe)
    # 4. Build 100% C++ Native WebView2 App (dist/QuickDiskBench.exe)
    cmd_gui = [
        compiler,
        "-O3",
        "-mwindows",
        "-std=c++17",
        "-static",
        f"-I{webview_include}",
        engine_src,
        webview_src,
        gui_src,
        resource_obj,
        "-o", out_gui_exe,
        "-lkernel32",
        "-luser32",
        "-lgdi32",
        "-ldwmapi",
        "-lole32",
        "-loleaut32",
        "-luuid",
        "-lcomctl32",
        "-lshell32"
    ]
    print(f"\n[2/3] 100% C++ ネイティブ GUI アプリ (dist/QuickDiskBench.exe) ビルド中: {' '.join(cmd_gui)}")
    print(f"\n[4/4] 100% C++ ネイティブ GUI アプリ (dist/QuickDiskBench.exe) ビルド中: {' '.join(cmd_gui)}")
    print(f"\n[4/5] 100% C++ ネイティブ GUI アプリ (dist/QuickDiskBench.exe) ビルド中: {' '.join(cmd_gui)}")
    res_gui = subprocess.run(cmd_gui, capture_output=True, text=True)
    if res_gui.returncode == 0 and os.path.exists(out_gui_exe):
        print(f"[成功] 100% C++ ネイティブ GUI アプリ を生成しました: {out_gui_exe} ({os.path.getsize(out_gui_exe)} bytes)")
    else:
        print("[失敗] アプリ ビルドに失敗しました:")
        print(res_gui.stderr)
        return False

    # 3. Build CLI Executable (dist/QuickDiskBench_cli.exe)
    # Build CLI Executable (dist/QuickDiskBench_cli.exe)
    # 5. Build CLI Executable (dist/QuickDiskBench_cli.exe)
    cmd_cli = [
        compiler,
        "-O3",
        "-std=c++17",
        "-static",
        engine_src,
        cli_src,
        "-o", out_cli_exe,
        "-lkernel32"
    ]
    print(f"\n[3/3] コマンドライン CLI 実行ファイル (dist/QuickDiskBench_cli.exe) ビルド中: {' '.join(cmd_cli)}")
    print(f"\n[CLI] コマンドライン CLI 実行ファイル (dist/QuickDiskBench_cli.exe) ビルド中: {' '.join(cmd_cli)}")
    print(f"\n[5/5] コマンドライン CLI 実行ファイル (dist/QuickDiskBench_cli.exe) ビルド中: {' '.join(cmd_cli)}")
    res_cli = subprocess.run(cmd_cli, capture_output=True, text=True)
    if res_cli.returncode == 0 and os.path.exists(out_cli_exe):
        print(f"[成功] コマンドライン CLI 実行ファイルを生成しました: {out_cli_exe} ({os.path.getsize(out_cli_exe)} bytes)")
    else:
        print("[失敗] CLI ビルドに失敗しました:")
        if res_cli.stdout:
            print(res_cli.stdout)
        if res_cli.stderr:
            print(res_cli.stderr)
        return False

    # 4. Copy required runtime DLL and UI assets to dist/
    # Prefer the loader shipped with the same WebView2 SDK as the headers.
    # This is required on GitHub Actions, where the SDK is downloaded to a
    # temporary directory instead of C:\tools\webview2.
    # Copy required runtime DLL and utility script to dist/
    wv_loader = os.environ.get("WEBVIEW2_LOADER")
    if not wv_loader:
        wv_loader = os.path.join(os.path.dirname(webview_include), "x64", "WebView2Loader.dll")
    if not os.path.exists(wv_loader):
        wv_loader = r"C:\tools\webview2\build\native\x64\WebView2Loader.dll"
    if os.path.exists(wv_loader):
        shutil.copy2(wv_loader, os.path.join(binary_dir, "WebView2Loader.dll"))
        shutil.copy2(wv_loader, os.path.join(dist_dir, "WebView2Loader.dll"))
        print(f"[コピー] WebView2Loader.dll を dist/ にコピーしました")

    shutil.copy2(os.path.join(os.path.dirname(__file__), "templates", "index.html"), os.path.join(binary_dir, "templates", "index.html"))
    shutil.copy2(os.path.join(os.path.dirname(__file__), "static", "css", "style.css"), os.path.join(binary_dir, "static", "css", "style.css"))
    shutil.copy2(os.path.join(os.path.dirname(__file__), "static", "js", "app.js"), os.path.join(binary_dir, "static", "js", "app.js"))
    shutil.copy2(os.path.join(os.path.dirname(__file__), "static", "js", "chart.min.js"), os.path.join(binary_dir, "static", "js", "chart.min.js"))
    shutil.copy2(os.path.join(os.path.dirname(__file__), "benchmark-all-drives.ps1"), os.path.join(binary_dir, "benchmark-all-drives.ps1"))
    ps_script = os.path.join(repo_root, "scripts", "benchmark-all-drives.ps1")
    if os.path.exists(ps_script):
        shutil.copy2(ps_script, os.path.join(dist_dir, "benchmark-all-drives.ps1"))
        print(f"[コピー] benchmark-all-drives.ps1 を dist/ にコピーしました")

    print(f"\n[完成] 配布用バイナリを dist/binary フォルダに生成完了: {binary_dir}")
    print(f"\n[完成] 配布用バイナリを dist/ フォルダに生成完了: {dist_dir}")
    return True


if __name__ == "__main__":
    success = build()
    sys.exit(0 if success else 1)
