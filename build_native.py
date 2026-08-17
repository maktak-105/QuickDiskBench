import os
import sys
import subprocess
import shutil

def find_compiler():
    # 1. Check in PATH
    # Prefer MinGW's g++ because the native GUI build uses MinGW-specific
    # flags such as -mwindows. A system LLVM clang++ may target MSVC instead.
    for comp in ["g++", "clang++"]:
        p = shutil.which(comp)
        if p:
            return p
            
    # 2. Check standard installation locations in C:\
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

    # Compile the Windows application icon resource once and link it into the GUI.
    windres = os.path.join(os.path.dirname(compiler), "llvm-windres.exe")
    if not os.path.exists(windres):
        windres = shutil.which("windres") or shutil.which("llvm-windres")
    if not windres:
        print("[エラー] Windows resource compiler (llvm-windres/windres) が見つかりませんでした。")
        return False
    cmd_res = [windres, resource_src, "-O", "coff", "-o", resource_obj]
    print(f"\n[0/3] Windows アイコンリソースをビルド中: {' '.join(cmd_res)}")
    res_res = subprocess.run(cmd_res, capture_output=True, text=True)
    if res_res.returncode != 0 or not os.path.exists(resource_obj):
        print("[失敗] アイコンリソースのビルドに失敗しました:")
        print(res_res.stderr)
        return False

    # 1. Build DLL
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
    res_dll = subprocess.run(cmd_dll, capture_output=True, text=True)
    if res_dll.returncode == 0 and os.path.exists(out_dll):
        print(f"[成功] C++ ネイティブ DLL を生成しました: {out_dll} ({os.path.getsize(out_dll)} bytes)")
        shutil.copy2(out_dll, os.path.join(binary_dir, "engine_x64.dll"))
    else:
        print("[失敗] DLL ビルドに失敗しました:")
        print(res_dll.stderr)
        return False

    # 2. Build 100% C++ Native WebView2 App (dist/QuickDiskBench.exe)
    cmd_gui = [
        compiler,
        "-O3",
        "-mwindows",
        "-std=c++17",
        "-static",
        f"-I{webview_include}",
        engine_src,
        webview_src,
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
    res_gui = subprocess.run(cmd_gui, capture_output=True, text=True)
    if res_gui.returncode == 0 and os.path.exists(out_gui_exe):
        print(f"[成功] 100% C++ ネイティブ GUI アプリ を生成しました: {out_gui_exe} ({os.path.getsize(out_gui_exe)} bytes)")
    else:
        print("[失敗] アプリ ビルドに失敗しました:")
        print(res_gui.stderr)
        return False

    # 3. Build CLI Executable (dist/QuickDiskBench_cli.exe)
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
    res_cli = subprocess.run(cmd_cli, capture_output=True, text=True)
    if res_cli.returncode == 0 and os.path.exists(out_cli_exe):
        print(f"[成功] コマンドライン CLI 実行ファイルを生成しました: {out_cli_exe} ({os.path.getsize(out_cli_exe)} bytes)")

    # 4. Copy required runtime DLL and UI assets to dist/
    wv_loader = r"C:\tools\webview2\build\native\x64\WebView2Loader.dll"
    if os.path.exists(wv_loader):
        shutil.copy2(wv_loader, os.path.join(binary_dir, "WebView2Loader.dll"))

    shutil.copy2(os.path.join(os.path.dirname(__file__), "templates", "index.html"), os.path.join(binary_dir, "templates", "index.html"))
    shutil.copy2(os.path.join(os.path.dirname(__file__), "static", "css", "style.css"), os.path.join(binary_dir, "static", "css", "style.css"))
    shutil.copy2(os.path.join(os.path.dirname(__file__), "static", "js", "app.js"), os.path.join(binary_dir, "static", "js", "app.js"))
    shutil.copy2(os.path.join(os.path.dirname(__file__), "static", "js", "chart.min.js"), os.path.join(binary_dir, "static", "js", "chart.min.js"))
    shutil.copy2(os.path.join(os.path.dirname(__file__), "benchmark-all-drives.ps1"), os.path.join(binary_dir, "benchmark-all-drives.ps1"))

    print(f"\n[完成] 配布用バイナリを dist/binary フォルダに生成完了: {binary_dir}")
    return True

if __name__ == "__main__":
    success = build()
    sys.exit(0 if success else 1)
