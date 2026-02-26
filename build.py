#!/usr/bin/env python3
"""
Build script: minifica y obfusca JS/CSS para produccion.
Uso: python3 build.py
Requiere: npx (viene con Node.js)
"""

import subprocess
import os
import sys
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
DIST_DIR = os.path.join(STATIC_DIR, 'dist')

JS_SRC = os.path.join(STATIC_DIR, 'js', 'app.js')
CSS_SRC = os.path.join(STATIC_DIR, 'css', 'style.css')
JS_OUT = os.path.join(DIST_DIR, 'js', 'app.min.js')
CSS_OUT = os.path.join(DIST_DIR, 'css', 'style.min.css')


def ensure_dirs():
    os.makedirs(os.path.join(DIST_DIR, 'js'), exist_ok=True)
    os.makedirs(os.path.join(DIST_DIR, 'css'), exist_ok=True)


def minify_js():
    """Minifica JS con terser via npx"""
    print('[JS] Minificando app.js...')
    try:
        result = subprocess.run(
            ['npx', '--yes', 'terser', JS_SRC,
             '--compress', 'drop_console=true,passes=2',
             '--mangle', 'toplevel,reserved=[handleLogin,handleLogout,openSucursalModal,openGrupoModal,toggleAgrupacion,loadSupervisionAreas,handleNDAAccept]',
             '--output', JS_OUT],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            print(f'[JS] Error: {result.stderr}')
            return False
        src_size = os.path.getsize(JS_SRC)
        out_size = os.path.getsize(JS_OUT)
        ratio = round((1 - out_size / src_size) * 100, 1)
        print(f'[JS] {src_size:,} -> {out_size:,} bytes ({ratio}% reduccion)')
        return True
    except FileNotFoundError:
        print('[JS] npx no encontrado, copiando sin minificar')
        shutil.copy2(JS_SRC, JS_OUT)
        return True


def minify_css():
    """Minifica CSS con clean-css via npx"""
    print('[CSS] Minificando style.css...')
    try:
        result = subprocess.run(
            ['npx', '--yes', 'clean-css-cli', '-o', CSS_OUT, CSS_SRC],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            print(f'[CSS] Error: {result.stderr}')
            return False
        src_size = os.path.getsize(CSS_SRC)
        out_size = os.path.getsize(CSS_OUT)
        ratio = round((1 - out_size / src_size) * 100, 1)
        print(f'[CSS] {src_size:,} -> {out_size:,} bytes ({ratio}% reduccion)')
        return True
    except FileNotFoundError:
        print('[CSS] npx no encontrado, copiando sin minificar')
        shutil.copy2(CSS_SRC, CSS_OUT)
        return True


def main():
    print('=== EPL CAS 2026 - Build de Produccion ===\n')
    ensure_dirs()

    js_ok = minify_js()
    css_ok = minify_css()

    if js_ok and css_ok:
        print('\n[OK] Build completado. Archivos en static/dist/')
        print('     Para usar en produccion, set FLASK_ENV=production')
    else:
        print('\n[WARN] Build completado con errores')
        sys.exit(1)


if __name__ == '__main__':
    main()
