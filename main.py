
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import (
    MDFloatingActionButton,
    MDIconButton,
    MDFlatButton
)
from kivymd.uix.label import MDLabel, MDIcon
from kivymd.uix.card import MDCard
from kivymd.uix.spinner import MDSpinner

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.codeinput import CodeInput
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.utils import platform
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.graphics.texture import Texture

import os
import time
import threading
import json
import re
import urllib.request
import urllib.parse
import urllib.error


# ==================================================
# JAVASCRIPT LEXER
# ==================================================

try:
    from pygments.lexers import JavascriptLexer
    lexer = JavascriptLexer()
except:
    lexer = None


# ==================================================
# COLORS
# ==================================================

BG = (0.027, 0.032, 0.06, 1)
PANEL = (0.055, 0.065, 0.11, 1)
CARD = (0.085, 0.1, 0.155, 1)

GREEN = (0.0, 0.9, 0.55, 1)
PURPLE = (0.48, 0.3, 1, 1)

WHITE = (0.9, 0.94, 1, 1)
GREY = (0.48, 0.53, 0.63, 1)

RED = (1, 0.3, 0.3, 1)
AMBER = (1, 0.75, 0.2, 1)

KEYBOARD_RATIO = 0.40

SPEED_EVERY = 30

LIBS = {
    "react.js": "https://unpkg.com/react@18/umd/react.development.js",
    "react-dom.js": "https://unpkg.com/react-dom@18/umd/react-dom.development.js",
    "babel.js": "https://unpkg.com/@babel/standalone@7.29.0/babel.min.js",
    "ionicons.js": "https://unpkg.com/ionicons@7.1.0/dist/ionicons/ionicons.js",
    "ionicons.esm.js": "https://unpkg.com/ionicons@7.1.0/dist/ionicons/ionicons.esm.js",
}

BUILTIN_MODULES = {
    "react": "React",
    "react-dom": "ReactDOM",
    "react-native": "",
    "expo": "",
    "expo-status-bar": "",
    "expo-linear-gradient": "LinearGradient",
    "react-native-linear-gradient": "LinearGradient",
    "expo-av": "",
    "expo-video": "",
    "expo-image-picker": "ImagePicker",
    "expo-document-picker": "DocumentPicker",
    "expo-font": "Font",
    "expo-constants": "Constants",
    "expo-haptics": "Haptics",
    "expo-blur": "",
    "expo-splash-screen": "SplashScreen",
    "@expo/vector-icons": "",
    "react-native-vector-icons": "Icon",
    "@react-native-async-storage/async-storage": "AsyncStorage",
    "react-native-safe-area-context": ""
}

ICON_PACKAGES = (
    "@expo/vector-icons",
    "react-native-vector-icons"
)


def package_root(spec):

    parts = spec.split("/")

    if spec.startswith("@") and len(parts) >= 2:

        return parts[0] + "/" + parts[1]

    return parts[0]


def parse_import(statement):

    match = re.match(
        r"^import\s+(.*?)\s+from\s*['\"]([^'\"]+)['\"]",
        statement
    )

    if not match:
        return None

    clause = match.group(1).strip()

    module = match.group(2)

    if clause.startswith("type "):
        return None

    default = None

    namespace = None

    names = []

    brace = re.search(r"\{([^}]*)\}", clause)

    if brace:

        for part in brace.group(1).split(","):

            part = part.strip()

            if not part:
                continue

            pieces = re.split(r"\s+as\s+", part)

            names.append(
                (pieces[0].strip(), pieces[-1].strip())
            )

        clause = clause[:brace.start()] + clause[brace.end():]

    star = re.search(
        r"\*\s*as\s+([A-Za-z_$][\w$]*)",
        clause
    )

    if star:

        namespace = star.group(1)

        clause = clause.replace(star.group(0), "")

    rest = clause.replace(",", " ").split()

    if rest:

        default = rest[0]

    return default, namespace, names, module


def build_bindings(imports, versions):

    lines = []

    needed = {}

    missing = []

    q = json.dumps

    for statement in imports:

        parsed = parse_import(statement)

        if parsed is None:
            continue

        default, namespace, names, module = parsed

        if module.startswith(".") or module.startswith("/"):
            continue

        root = package_root(module)

        sub = module[len(root):]

        if root in BUILTIN_MODULES:

            if default:

                canon = BUILTIN_MODULES[root]

                if sub and root in ICON_PACKAGES:
                    canon = sub.split("/")[-1]

                if canon:

                    lines.append(
                        "const %s = (window[%s] !== undefined "
                        "? window[%s] : joscomMod(%s));" %
                        (default, q(canon), q(canon), q(root))
                    )

                else:

                    lines.append(
                        "const %s = joscomMod(%s);" %
                        (default, q(root))
                    )

            if namespace:

                lines.append(
                    "const %s = joscomMod(%s);" %
                    (namespace, q(root))
                )

            for original, local in names:

                lines.append(
                    "const %s = joscomPick(%s, %s);" %
                    (local, q(root), q(original))
                )

        elif root in versions:

            version = versions[root]

            url = "https://esm.sh/" + root

            if version:
                url += "@" + version

            url += sub + "?external=react,react-dom,react-native"

            needed[module] = url

            key = q(module)

            if default:

                lines.append(
                    "const %s = (__deps[%s].default !== undefined "
                    "? __deps[%s].default : __deps[%s]);" %
                    (default, key, key, key)
                )

            if namespace:

                lines.append(
                    "const %s = __deps[%s];" %
                    (namespace, key)
                )

            if names:

                parts = []

                for original, local in names:

                    if original == local:
                        parts.append(local)
                    else:
                        parts.append(original + ": " + local)

                lines.append(
                    "const { %s } = __deps[%s];" %
                    (", ".join(parts), key)
                )

        else:

            if root not in missing:
                missing.append(root)

    return lines, needed, missing


SPEED_URLS = [
    "https://speed.cloudflare.com/__down?bytes=1000000",
    "https://unpkg.com/react-dom@18/umd/react-dom.development.js"
]


# ==================================================
# SMALL DESIGN WIDGETS
# ==================================================

class GradientBar(Widget):

    def __init__(self, left=GREEN, right=PURPLE, **kwargs):

        super().__init__(**kwargs)

        texture = Texture.create(
            size=(2, 1),
            colorfmt="rgba"
        )

        data = bytes(
            [int(c * 255) for c in left] +
            [int(c * 255) for c in right]
        )

        texture.blit_buffer(
            data,
            colorfmt="rgba",
            bufferfmt="ubyte"
        )

        texture.mag_filter = "linear"

        with self.canvas:

            Color(1, 1, 1, 1)

            self.rect = Rectangle(
                texture=texture,
                pos=self.pos,
                size=self.size
            )

        self.bind(
            pos=self.update_rect,
            size=self.update_rect
        )

    def update_rect(self, *args):

        self.rect.pos = self.pos

        self.rect.size = self.size


class RoundBox(BoxLayout):

    def __init__(self, bg=CARD, radius=12, **kwargs):

        super().__init__(**kwargs)

        with self.canvas.before:

            Color(*bg)

            self.bg_rect = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(radius)]
            )

        self.bind(
            pos=self.update_bg,
            size=self.update_bg
        )

    def update_bg(self, *args):

        self.bg_rect.pos = self.pos

        self.bg_rect.size = self.size


class TapBox(ButtonBehavior, RoundBox):
    pass


class GradientBox(BoxLayout):

    def __init__(
        self,
        colors=(PANEL, BG),
        vertical=False,
        radius=0,
        **kwargs
    ):

        super().__init__(**kwargs)

        first = [int(c * 255) for c in colors[0]]

        second = [int(c * 255) for c in colors[1]]

        if vertical:

            texture = Texture.create(
                size=(1, 2),
                colorfmt="rgba"
            )

            data = bytes(second + first)

        else:

            texture = Texture.create(
                size=(2, 1),
                colorfmt="rgba"
            )

            data = bytes(first + second)

        texture.blit_buffer(
            data,
            colorfmt="rgba",
            bufferfmt="ubyte"
        )

        texture.mag_filter = "linear"

        with self.canvas.before:

            Color(1, 1, 1, 1)

            if radius:

                self.bg_rect = RoundedRectangle(
                    texture=texture,
                    pos=self.pos,
                    size=self.size,
                    radius=[dp(radius)]
                )

            else:

                self.bg_rect = Rectangle(
                    texture=texture,
                    pos=self.pos,
                    size=self.size
                )

        self.bind(
            pos=self.update_bg,
            size=self.update_bg
        )

    def update_bg(self, *args):

        self.bg_rect.pos = self.pos

        self.bg_rect.size = self.size


class GradientButton(ButtonBehavior, GradientBox):
    pass


class AxisScroll(ScrollView):

    def on_touch_down(self, touch):

        self.axis = None

        self.move_x = 0

        self.move_y = 0

        self.do_scroll_x = True

        self.do_scroll_y = True

        return super().on_touch_down(touch)

    def on_touch_move(self, touch):

        result = super().on_touch_move(touch)

        try:

            if (
                getattr(self, "axis", None) is None and
                touch is self._touch
            ):

                self.move_x += abs(touch.dx)

                self.move_y += abs(touch.dy)

                info = touch.ud.get(self._get_uid())

                if (
                    info is not None and
                    info.get("mode") == "scroll" and
                    self.move_x + self.move_y > dp(14)
                ):

                    if self.move_x > self.move_y:

                        self.axis = "x"

                        self.do_scroll_y = False

                    else:

                        self.axis = "y"

                        self.do_scroll_x = False

        except Exception:

            pass

        return result

    def on_touch_up(self, touch):

        result = super().on_touch_up(touch)

        locked = getattr(self, "axis", None)

        self.axis = None

        self.do_scroll_x = True

        self.do_scroll_y = True

        try:

            if locked == "x" and self.effect_y:

                self.effect_y.cancel()

            if locked == "y" and self.effect_x:

                self.effect_x.cancel()

        except Exception:

            pass

        return result


def show_android_keyboard():

    if platform != "android":
        return

    try:

        from jnius import autoclass

        SDLActivity = autoclass(
            "org.libsdl.app.SDLActivity"
        )

        SDLActivity.showTextInput(0, 0, 1, 1)

        return

    except Exception:

        pass

    try:

        from jnius import autoclass
        from android.runnable import run_on_ui_thread

        Activity = autoclass(
            "org.kivy.android.PythonActivity"
        )

        Context = autoclass(
            "android.content.Context"
        )

        @run_on_ui_thread
        def show():

            try:

                activity = Activity.mActivity

                manager = activity.getSystemService(
                    Context.INPUT_METHOD_SERVICE
                )

                view = activity.getCurrentFocus()

                if view is None:

                    view = activity.getWindow().getDecorView()

                manager.showSoftInput(view, 0)

            except Exception:

                pass

        show()

    except Exception:

        pass


# ==================================================
# SMART CODE EDITOR
# ==================================================

class SmartCodeInput(CodeInput):

    pairs = {
        "{": "}",
        "(": ")",
        "[": "]",
        "<": ">"
    }

    def insert_text(self, substring, from_undo=False):

        if from_undo:
            return super().insert_text(
                substring,
                from_undo
            )

        # Automatic closing symbols

        if substring in self.pairs:

            closing = self.pairs[substring]

            super().insert_text(
                substring + closing,
                from_undo
            )

            col, row = self.cursor

            self.cursor = (
                max(0, col - 1),
                row
            )

            return

        # Skip existing closing symbols

        if substring in self.pairs.values():

            col, row = self.cursor

            lines = self.text.split("\n")

            if row < len(lines):

                line = lines[row]

                if col < len(line) and line[col] == substring:

                    self.cursor = (
                        col + 1,
                        row
                    )

                    return

        super().insert_text(
            substring,
            from_undo
        )

    # SHOW KEYBOARD AGAIN ON TAP

    def on_touch_down(self, touch):

        self.tap_pos = touch.pos

        return super().on_touch_down(touch)

    def on_touch_up(self, touch):

        result = super().on_touch_up(touch)

        start = getattr(self, "tap_pos", None)

        if (
            platform == "android" and
            start is not None and
            self.focus and
            self.collide_point(*touch.pos) and
            abs(touch.x - start[0]) < dp(10) and
            abs(touch.y - start[1]) < dp(10)
        ):

            Clock.schedule_once(
                lambda dt: show_android_keyboard(),
                0.12
            )

        return result

    # AUTOMATIC INDENTATION

    def keyboard_on_key_down(
        self,
        window,
        keycode,
        text,
        modifiers
    ):

        key = keycode[1]

        if key in ("enter", "numpadenter"):

            col, row = self.cursor

            lines = self.text.split("\n")

            if row < len(lines):

                current_line = lines[row]

                indent = (
                    current_line[
                        :len(current_line) -
                        len(current_line.lstrip())
                    ]
                )

                before = current_line[:col].rstrip()

                after = current_line[col:].lstrip()

                opening = (
                    before.endswith("{") or
                    before.endswith("(") or
                    before.endswith("[")
                )

                matching = (
                    (before.endswith("{") and after.startswith("}")) or
                    (before.endswith("(") and after.startswith(")")) or
                    (before.endswith("[") and after.startswith("]"))
                )

                # Empty space between matching brackets

                if matching:

                    super().insert_text(
                        "\n" + indent + "    " +
                        "\n" + indent
                    )

                    self.cursor = (
                        len(indent) + 4,
                        row + 1
                    )

                    return True

                # Indent after opening brackets

                elif opening:

                    super().insert_text(
                        "\n" + indent + "    "
                    )

                    return True

                # Normal indentation

                else:

                    super().insert_text(
                        "\n" + indent
                    )

                    return True

        return super().keyboard_on_key_down(
            window,
            keycode,
            text,
            modifiers
        )


# ==================================================
# WEBVIEW PREVIEW
# ==================================================

class InsideWebView(BoxLayout):

    def __init__(self, **kwargs):

        super().__init__(**kwargs)

        self.orientation = "vertical"

        self.dialog = None
        self.webview = None
        self.activity = None
        self.back_event = None

        self.html_path = (
            "/storage/emulated/0/JoscomApp/preview.html"
        )

        self.info = Label(
            text="Ready to preview",
            color=GREEN,
            size_hint_y=None,
            height=dp(35),
            font_size=12
        )

        self.loading = Label(
            text="",
            color=(0, 0.8, 1, 1),
            size_hint_y=None,
            height=dp(35),
            font_size=14
        )

        self.add_widget(self.info)
        self.add_widget(self.loading)

    # --------------------------------------------------
    # CREATE HTML
    # --------------------------------------------------

    def create_html(self, rn_code):

        clean = ""

        imports = []

        statement = ""

        in_import = False

        for line in rn_code.split("\n"):

            stripped = line.strip()

            if in_import:

                clean += "\n"

                statement += " " + stripped

                if "'" in stripped or '"' in stripped:

                    in_import = False

                    imports.append(statement)

                continue

            if stripped.startswith("import "):

                clean += "\n"

                statement = stripped

                if "'" in stripped or '"' in stripped:

                    imports.append(statement)

                else:

                    in_import = True

                continue

            if stripped.startswith("export default"):

                line = line.replace(
                    "export default",
                    "",
                    1
                )

            elif stripped.startswith("export "):

                line = line.replace(
                    "export ",
                    "",
                    1
                )

            clean += line + "\n"

        extra = 0

        if not any(
            key in clean for key in (
                "function App",
                "const App",
                "class App",
                "let App",
                "var App",
                "AppRegistry",
                "registerRootComponent"
            )
        ):

            clean = (
                "function App() {\n"
                "return (\n" +
                clean +
                "\n);\n}"
            )

            extra = 2

        app = MDApp.get_running_app()

        versions = {}

        for dep in app.deps:

            versions[dep["name"]] = dep.get("version", "")

        bindings, needed, missing = build_bindings(
            imports,
            versions
        )

        html = r"""<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width, initial-scale=1, maximum-scale=1">

<script>

window.JOSCOM_OFFSET = __LINE_OFFSET__;

window.JOSCOM_DEPS = __DEPS_JSON__;

window.JOSCOM_MISSING = __MISSING_JSON__;

window.JOSCOM_WARNED = {};

window.joscomLast = '';

function joscomFix(text) {
    return String(text).replace(/\((\d+):(\d+)\)/g, function (m, l, c) {
        var n = parseInt(l, 10) - window.JOSCOM_OFFSET;
        if (n < 1) { return m; }
        return '(line ' + n + ', column ' + c + ')';
    });
}

function joscomFormat(args) {
    var list = Array.prototype.slice.call(args);
    var first = String(list[0]);
    var i = 1;
    first = first.replace(/%[sdfoOj]/g, function () {
        if (i < list.length) {
            var a = list[i++];
            return (a && a.message) ? a.message : String(a);
        }
        return '';
    });
    var rest = list.slice(i).map(function (a) {
        return (a && a.message) ? a.message : String(a);
    });
    return [first].concat(rest).join(' ');
}

window.joscomShowError = function (title, message, detail, warn) {
    try {
        var text = String(message);
        if (/\(\d+:\d+\)/.test(text)) { text = text.split('\n')[0]; }
        text = joscomFix(text);
        if (window.joscomLast === title + text) { return; }
        window.joscomLast = title + text;
        var box = document.getElementById('joscom-errors');
        if (!box) {
            box = document.createElement('div');
            box.id = 'joscom-errors';
            box.style.cssText = 'position:fixed;left:0;right:0;top:0;max-height:70%;overflow:auto;z-index:99999;background:#1c0a0e;border-bottom:2px solid #ff4d5e;padding:10px;font-family:monospace;font-size:12px;color:#ffd6da;';
            var head = document.createElement('div');
            head.style.cssText = 'display:flex;justify-content:space-between;margin-bottom:6px;color:#ff6b7a;font-weight:bold;font-size:13px;';
            var name = document.createElement('span');
            name.textContent = 'React Native Errors';
            var close = document.createElement('span');
            close.textContent = 'CLOSE';
            close.style.cssText = 'padding:0 8px;';
            close.onclick = function () {
                if (box.parentNode) { box.parentNode.removeChild(box); }
            };
            head.appendChild(name);
            head.appendChild(close);
            box.appendChild(head);
            (document.body || document.documentElement).appendChild(box);
        }
        var color = warn ? '#ffd166' : '#ff6b7a';
        var item = document.createElement('div');
        item.style.cssText = 'margin-bottom:8px;white-space:pre-wrap;word-break:break-word;border-left:3px solid ' + color + ';padding-left:8px;';
        var t = document.createElement('div');
        t.style.cssText = 'color:' + color + ';font-weight:bold;';
        t.textContent = title;
        var m = document.createElement('div');
        m.textContent = text;
        item.appendChild(t);
        item.appendChild(m);
        if (detail) {
            var d = document.createElement('div');
            d.style.cssText = 'color:#9aa4b8;margin-top:4px;';
            d.textContent = String(detail).split('\n').slice(0, 6).join('\n');
            item.appendChild(d);
        }
        box.appendChild(item);
    } catch (e) {}
};

window.onerror = function (message, source, line, col, error) {
    var text = String(message);
    if (error && error.message && text.indexOf(error.message) === -1) { text = error.message; }
    window.joscomShowError('Error', text, error && error.stack ? error.stack : '');
    return false;
};

window.addEventListener('unhandledrejection', function (e) {
    var r = e.reason;
    window.joscomShowError('Promise error', (r && r.message) ? r.message : String(r), r && r.stack ? r.stack : '');
});

(function () {
    var oe = console.error;
    var ow = console.warn;
    console.error = function () {
        try { window.joscomShowError('Error', joscomFormat(arguments)); } catch (e) {}
        oe.apply(console, arguments);
    };
    console.warn = function () {
        try {
            var text = joscomFormat(arguments);
            if (text.indexOf('in-browser Babel') === -1) {
                window.joscomShowError('Warning', text, '', true);
            }
        } catch (e) {}
        ow.apply(console, arguments);
    };
})();


window.joscomMod = function (root) {
    var m = window.__JOSCOM_MODULES__ && window.__JOSCOM_MODULES__[root];
    return m || {};
};

window.joscomPick = function (root, name) {
    var m = window.__JOSCOM_MODULES__ && window.__JOSCOM_MODULES__[root];
    if (m && m[name] !== undefined) { return m[name]; }
    if (window[name] !== undefined) { return window[name]; }
    var key = root + ':' + name;
    if (!window.JOSCOM_WARNED[key]) {
        window.JOSCOM_WARNED[key] = true;
        window.joscomShowError(
            'Not in preview',
            '"' + name + '" from "' + root + '" is not available in the preview yet.',
            '',
            true
        );
    }
    return undefined;
};

window.joscomImportMap = function () {
    try {
        if (!(window.HTMLScriptElement && HTMLScriptElement.supports && HTMLScriptElement.supports('importmap'))) {
            return;
        }
        var prefix = 'data:text/javascript;charset=utf-8,';
        var moduleOf = function (globalName, keys) {
            var code = 'export default window.' + globalName + ';';
            keys.forEach(function (k) {
                if (/^[A-Za-z_$][\w$]*$/.test(k) && k !== 'default' && k.indexOf('__') !== 0) {
                    code += 'export const ' + k + ' = window.' + globalName + '.' + k + ';';
                }
            });
            return prefix + encodeURIComponent(code);
        };
        var rn = window.__JOSCOM_MODULES__['react-native'];
        var rnCode = 'const m = window.__JOSCOM_MODULES__["react-native"]; export default m;';
        Object.keys(rn).forEach(function (k) {
            rnCode += 'export const ' + k + ' = m.' + k + ';';
        });
        var jsx = 'const R = window.React; export const Fragment = R.Fragment; ' +
            'export function jsx(t, p, k) { var props = Object.assign({}, p); ' +
            'if (k !== undefined) { props.key = k; } return R.createElement(t, props); } ' +
            'export const jsxs = jsx; export const jsxDEV = jsx;';
        var dom = moduleOf('ReactDOM', Object.keys(window.ReactDOM));
        var map = {
            imports: {
                'react': moduleOf('React', Object.keys(window.React)),
                'react-dom': dom,
                'react-dom/client': dom,
                'react-native': prefix + encodeURIComponent(rnCode),
                'react/jsx-runtime': prefix + encodeURIComponent(jsx),
                'react/jsx-dev-runtime': prefix + encodeURIComponent(jsx)
            }
        };
        var tag = document.createElement('script');
        tag.type = 'importmap';
        tag.textContent = JSON.stringify(map);
        document.head.appendChild(tag);
    } catch (e) {}
};

window.joscomLoadDeps = function (list) {
    window.JOSCOM_MISSING.forEach(function (name) {
        window.joscomShowError(
            'Missing dependency',
            'Package "' + name + '" is not added. Open Packages, add it, then run again.',
            '',
            true
        );
    });
    var out = {};
    if (!list || !list.length) { return Promise.resolve(out); }
    window.joscomImportMap();
    return Promise.all(list.map(function (item) {
        return import(item.url).then(function (mod) {
            out[item.name] = mod;
        }).catch(function (e) {
            throw new Error(
                'Could not load "' + item.name + '" from the internet. ' +
                ((e && e.message) ? e.message : String(e))
            );
        });
    })).then(function () { return out; });
};


</script>

<script src="__LIB_react.js__"></script>

<script src="__LIB_react-dom.js__"></script>

<script src="__LIB_babel.js__"></script>
<script type="module" src="__LIB_ionicons.esm.js__"></script>
<script nomodule src="__LIB_ionicons.js__"></script>

<script>

if (
    typeof React === 'undefined' ||
    typeof ReactDOM === 'undefined' ||
    typeof Babel === 'undefined'
) {
    window.joscomShowError(
        'Load error',
        'React or Babel could not load. Check your internet and run again.'
    );
}

</script>

<style>

* {
    box-sizing: border-box;
}

html, body {
    height: 100%;
}

body {
    margin: 0;
    padding: 15px;
    background: #090b13;
    color: white;
    font-family: sans-serif;
}

#root {
    display: flex;
    flex-direction: column;
    height: calc(100vh - 30px);
}

@keyframes joscomspin {
    to { transform: rotate(360deg); }
}

.joscom-btn {
    background: linear-gradient(135deg, #00d994, #6545ff);
    color: white;
    padding: 14px;
    border: none;
    border-radius: 12px;
    margin-top: 15px;
    width: 100%;
    font-size: 15px;
}

.joscom-input {
    padding: 13px;
    width: 100%;
    border-radius: 10px;
    border: 1px solid #03d9a0;
    margin-top: 12px;
    background: #171b2a;
    color: white;
    font-size: 16px;
}

</style>

</head>

<body>

<div id="root">

<p style="color:#00d994">
Preparing preview...
</p>

</div>

<script>

(function () {

  if (typeof React === 'undefined') { return; }

  var h = React.createElement;
  var W = window;

  W.global = W;
  W.__DEV__ = true;
  W.process = W.process || { env: { NODE_ENV: 'development' } };
  W.require = function () { return { uri: '' }; };

  ['useState', 'useEffect', 'useRef', 'useMemo', 'useCallback', 'useReducer',
   'useContext', 'useLayoutEffect', 'useImperativeHandle', 'useId',
   'createContext', 'createRef', 'Fragment', 'memo', 'forwardRef',
   'Children', 'cloneElement', 'isValidElement', 'Component',
   'PureComponent', 'StrictMode', 'Suspense', 'lazy'].forEach(function (k) {
    if (React[k] !== undefined) { W[k] = React[k]; }
  });

  function merge(style) {
    if (!style) { return {}; }
    if (Array.isArray(style)) {
      var acc = {};
      style.forEach(function (s) { Object.assign(acc, merge(s)); });
      return acc;
    }
    if (typeof style === 'object') { return Object.assign({}, style); }
    return {};
  }

  function convert(o, keep) {
    if (o.paddingHorizontal !== undefined) {
      o.paddingLeft = o.paddingHorizontal;
      o.paddingRight = o.paddingHorizontal;
      delete o.paddingHorizontal;
    }
    if (o.paddingVertical !== undefined) {
      o.paddingTop = o.paddingVertical;
      o.paddingBottom = o.paddingVertical;
      delete o.paddingVertical;
    }
    if (o.marginHorizontal !== undefined) {
      o.marginLeft = o.marginHorizontal;
      o.marginRight = o.marginHorizontal;
      delete o.marginHorizontal;
    }
    if (o.marginVertical !== undefined) {
      o.marginTop = o.marginVertical;
      o.marginBottom = o.marginVertical;
      delete o.marginVertical;
    }
    if (typeof o.lineHeight === 'number') { o.lineHeight = o.lineHeight + 'px'; }
    if (o.elevation) {
      o.boxShadow = '0px ' + o.elevation + 'px ' + (o.elevation * 2) + 'px rgba(0,0,0,0.35)';
    }
    delete o.elevation;
    if (o.shadowColor !== undefined || o.shadowRadius !== undefined || o.shadowOffset !== undefined) {
      var off = o.shadowOffset || { width: 0, height: 0 };
      o.boxShadow = off.width + 'px ' + off.height + 'px ' + (o.shadowRadius || 0) + 'px ' + (o.shadowColor || '#000');
    }
    delete o.shadowColor;
    delete o.shadowOffset;
    delete o.shadowOpacity;
    delete o.shadowRadius;
    delete o.textAlignVertical;
    delete o.includeFontPadding;
    if (!keep) { delete o.resizeMode; }
    var hasBorder = false;
    ['borderWidth', 'borderTopWidth', 'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth'].forEach(function (k) {
      if (o[k]) { hasBorder = true; }
    });
    if (hasBorder && !o.borderStyle) { o.borderStyle = 'solid'; }
    if (Array.isArray(o.transform)) {
      o.transform = o.transform.map(function (t) {
        var k = Object.keys(t)[0];
        var v = t[k];
        if (typeof v === 'number' && /translate/.test(k)) { v = v + 'px'; }
        else if (typeof v === 'number' && /rotate|skew/.test(k)) { v = v + 'deg'; }
        return k + '(' + v + ')';
      }).join(' ');
    }
    return o;
  }

  function flat(style, keep) { return convert(merge(style), keep); }

  var baseBox = { display: 'flex', flexDirection: 'column', position: 'relative', flexShrink: 0, boxSizing: 'border-box' };

  W.View = function View(props) {
    var s = Object.assign({}, baseBox, flat(props.style));
    if (props.pointerEvents === 'none') { s.pointerEvents = 'none'; }
    return h('div', { style: s, 'data-testid': props.testID }, props.children);
  };

  var TextContext = React.createContext(false);

  W.Text = function Text(props) {
    var nested = React.useContext(TextContext);
    var s = Object.assign({ margin: 0 }, flat(props.style));
    if (props.numberOfLines === 1) {
      s.whiteSpace = 'nowrap';
      s.overflow = 'hidden';
      s.textOverflow = 'ellipsis';
    } else if (props.numberOfLines > 1) {
      s.display = '-webkit-box';
      s.WebkitLineClamp = props.numberOfLines;
      s.WebkitBoxOrient = 'vertical';
      s.overflow = 'hidden';
    }
    if (props.onPress) { s.cursor = 'pointer'; }
    var click = props.onPress ? function () { props.onPress({ nativeEvent: {} }); } : undefined;
    return h(TextContext.Provider, { value: true },
      h(nested ? 'span' : 'div', { style: s, onClick: click }, props.children));
  };

  W.TextInput = function TextInput(props) {
    var common = {
      className: 'joscom-input',
      placeholder: props.placeholder,
      value: props.value,
      defaultValue: props.defaultValue,
      style: flat(props.style),
      disabled: props.editable === false,
      autoFocus: props.autoFocus,
      maxLength: props.maxLength,
      onFocus: props.onFocus,
      onBlur: props.onBlur,
      onChange: function (e) {
        if (props.onChangeText) { props.onChangeText(e.target.value); }
        if (props.onChange) { props.onChange({ nativeEvent: { text: e.target.value } }); }
      }
    };
    if (props.multiline) {
      common.rows = props.numberOfLines || 3;
      return h('textarea', common);
    }
    var type = 'text';
    var mode;
    var kt = props.keyboardType;
    if (props.secureTextEntry) { type = 'password'; }
    else if (kt === 'email-address') { type = 'email'; }
    else if (kt === 'phone-pad') { type = 'tel'; }
    else if (kt === 'numeric' || kt === 'number-pad') { mode = 'numeric'; }
    else if (kt === 'decimal-pad') { mode = 'decimal'; }
    common.type = type;
    common.inputMode = mode;
    common.onKeyDown = function (e) {
      if (e.key === 'Enter' && props.onSubmitEditing) {
        props.onSubmitEditing({ nativeEvent: { text: e.target.value } });
      }
    };
    return h('input', common);
  };

  function pressProps(setPressed, disabled, onPress) {
    return {
      onClick: function () { if (!disabled && onPress) { onPress({ nativeEvent: {} }); } },
      onMouseDown: function () { setPressed(true); },
      onMouseUp: function () { setPressed(false); },
      onMouseLeave: function () { setPressed(false); },
      onTouchStart: function () { setPressed(true); },
      onTouchEnd: function () { setPressed(false); },
      onTouchCancel: function () { setPressed(false); }
    };
  }

  W.Pressable = function Pressable(props) {
    var st = React.useState(false);
    var pressed = st[0];
    var resolved = typeof props.style === 'function' ? props.style({ pressed: pressed }) : props.style;
    var content = typeof props.children === 'function' ? props.children({ pressed: pressed }) : props.children;
    var s = flat(resolved);
    var handlers = pressProps(st[1], props.disabled, props.onPress);
    if (Object.keys(s).length === 0) {
      return h('button', Object.assign({
        className: 'joscom-btn',
        disabled: props.disabled,
        style: pressed ? { opacity: 0.8 } : undefined
      }, handlers), content);
    }
    var base = Object.assign({}, baseBox, {
      cursor: 'pointer', userSelect: 'none', opacity: props.disabled ? 0.5 : 1
    });
    return h('div', Object.assign({ role: 'button', style: Object.assign(base, s) }, handlers), content);
  };

  function makeTouchable(defaultActive) {
    return function Touchable(props) {
      var st = React.useState(false);
      var pressed = st[0];
      var active = props.activeOpacity !== undefined ? props.activeOpacity : defaultActive;
      var o = Object.assign({}, baseBox, { cursor: 'pointer', userSelect: 'none' }, flat(props.style));
      if (pressed) { o.opacity = active; }
      if (props.disabled) { o.opacity = 0.5; }
      return h('div', Object.assign({ role: 'button', style: o },
        pressProps(st[1], props.disabled, props.onPress)), props.children);
    };
  }

  W.TouchableOpacity = makeTouchable(0.2);
  W.TouchableHighlight = makeTouchable(0.85);
  W.TouchableWithoutFeedback = makeTouchable(1);
  W.TouchableNativeFeedback = makeTouchable(0.85);

  W.Button = function Button(props) {
    return h('button', {
      className: 'joscom-btn',
      disabled: props.disabled,
      style: props.color ? { background: props.color } : undefined,
      onClick: function () { if (props.onPress) { props.onPress({ nativeEvent: {} }); } }
    }, props.title);
  };

  W.ScrollView = function ScrollView(props) {
    var horizontal = !!props.horizontal;
    var outer = Object.assign({
      display: 'flex',
      flexDirection: horizontal ? 'row' : 'column',
      flexGrow: horizontal ? 0 : 1,
      flexShrink: 1,
      minHeight: 0,
      minWidth: 0,
      overflowX: horizontal ? 'auto' : 'hidden',
      overflowY: horizontal ? 'hidden' : 'auto',
      boxSizing: 'border-box',
      position: 'relative'
    }, flat(props.style));
    var inner = Object.assign({
      display: 'flex',
      flexDirection: horizontal ? 'row' : 'column',
      flexShrink: 0,
      boxSizing: 'border-box'
    }, flat(props.contentContainerStyle));
    return h('div', { style: outer }, h('div', { style: inner }, props.children));
  };

  function renderComp(c) {
    if (!c) { return null; }
    if (typeof c === 'function') { return h(c); }
    return c;
  }

  W.FlatList = function FlatList(props) {
    var data = props.data || [];
    var cols = props.numColumns || 1;
    var kids = [];
    var render = props.renderItem || function () { return null; };
    function keyOf(item, i) {
      if (props.keyExtractor) { return props.keyExtractor(item, i); }
      if (item && item.key !== undefined) { return item.key; }
      if (item && item.id !== undefined) { return item.id; }
      return i;
    }
    if (cols > 1) {
      for (var r = 0; r < data.length; r += cols) {
        var row = [];
        for (var c = r; c < r + cols; c++) {
          row.push(h(W.View, { key: c, style: { flex: 1 } },
            c < data.length ? render({ item: data[c], index: c, separators: {} }) : null));
        }
        kids.push(h(W.View, { key: 'row' + r, style: [{ flexDirection: 'row' }, props.columnWrapperStyle] }, row));
      }
    } else {
      data.forEach(function (item, i) {
        kids.push(h(React.Fragment, { key: keyOf(item, i) },
          render({ item: item, index: i, separators: {} }),
          (props.ItemSeparatorComponent && i < data.length - 1) ? renderComp(props.ItemSeparatorComponent) : null));
      });
    }
    if (data.length === 0 && props.ListEmptyComponent) {
      kids.push(h(React.Fragment, { key: 'empty' }, renderComp(props.ListEmptyComponent)));
    }
    return h(W.ScrollView, {
      horizontal: props.horizontal,
      style: props.style,
      contentContainerStyle: props.contentContainerStyle
    }, renderComp(props.ListHeaderComponent), kids, renderComp(props.ListFooterComponent));
  };

  W.SectionList = function SectionList(props) {
    var kids = [];
    (props.sections || []).forEach(function (section, si) {
      if (props.renderSectionHeader) {
        kids.push(h(React.Fragment, { key: 'h' + si }, props.renderSectionHeader({ section: section })));
      }
      (section.data || []).forEach(function (item, i) {
        var fn = section.renderItem || props.renderItem;
        kids.push(h(React.Fragment, { key: si + '-' + (props.keyExtractor ? props.keyExtractor(item, i) : i) },
          fn({ item: item, index: i, section: section })));
      });
    });
    return h(W.ScrollView, { style: props.style, contentContainerStyle: props.contentContainerStyle }, kids);
  };

  var fit = { cover: 'cover', contain: 'contain', stretch: 'fill', center: 'none', repeat: 'cover' };

  function uriOf(src) {
    if (src && src.uri) { return src.uri; }
    if (typeof src === 'string') { return src; }
    return '';
  }

  W.Image = function Image(props) {
    var s = flat(props.style, true);
    var mode = props.resizeMode || s.resizeMode || 'cover';
    delete s.resizeMode;
    var uri = uriOf(props.source);
    return h('img', {
      src: uri || undefined,
      alt: '',
      onLoad: props.onLoad,
      onError: props.onError,
      style: Object.assign({ display: 'block', objectFit: fit[mode] || 'cover', flexShrink: 0 }, s)
    });
  };

  W.ImageBackground = function ImageBackground(props) {
    var s = Object.assign({}, baseBox, {
      backgroundSize: props.resizeMode === 'contain' ? 'contain' : (props.resizeMode === 'stretch' ? '100% 100%' : 'cover'),
      backgroundPosition: 'center',
      backgroundRepeat: 'no-repeat'
    }, flat(props.style));
    var uri = uriOf(props.source);
    if (uri) { s.backgroundImage = 'url("' + uri + '")'; }
    return h('div', { style: s }, props.children);
  };

  W.SafeAreaView = W.View;
  W.KeyboardAvoidingView = W.View;
  W.StatusBar = function StatusBar() { return null; };
  W.SafeAreaProvider = function SafeAreaProvider(props) { return h(React.Fragment, null, props.children); };
  W.useSafeAreaInsets = function () { return { top: 0, right: 0, bottom: 0, left: 0 }; };

  W.ActivityIndicator = function ActivityIndicator(props) {
    if (props.animating === false) { return null; }
    var px = props.size === 'large' ? 36 : (typeof props.size === 'number' ? props.size : 20);
    return h('div', {
      style: Object.assign({
        width: px,
        height: px,
        borderRadius: '50%',
        border: '3px solid rgba(255,255,255,0.2)',
        borderTopColor: props.color || '#00d994',
        animation: 'joscomspin 0.8s linear infinite',
        flexShrink: 0
      }, flat(props.style))
    });
  };

  W.Switch = function Switch(props) {
    var on = !!props.value;
    var tc = props.trackColor || {};
    var track = on ? (tc.true || '#00d994') : (tc.false || '#555');
    return h('div', {
      onClick: function () { if (!props.disabled && props.onValueChange) { props.onValueChange(!on); } },
      style: {
        width: 46, height: 26, borderRadius: 13, background: track, padding: 3,
        display: 'flex', justifyContent: on ? 'flex-end' : 'flex-start',
        cursor: 'pointer', opacity: props.disabled ? 0.5 : 1, flexShrink: 0, boxSizing: 'border-box'
      }
    }, h('div', { style: { width: 20, height: 20, borderRadius: 10, background: props.thumbColor || '#fff' } }));
  };

  W.Modal = function Modal(props) {
    if (!props.visible) { return null; }
    return h('div', {
      style: {
        position: 'fixed', left: 0, top: 0, right: 0, bottom: 0, zIndex: 9000,
        display: 'flex', flexDirection: 'column',
        background: props.transparent ? 'transparent' : '#090b13'
      }
    }, props.children);
  };

  W.Alert = {
    alert: function (title, message, buttons) {
      var list = (buttons && buttons.length) ? buttons : [{ text: 'OK' }];
      var overlay = document.createElement('div');
      overlay.style.cssText = 'position:fixed;left:0;top:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:9500;display:flex;align-items:center;justify-content:center;';
      var card = document.createElement('div');
      card.style.cssText = 'background:#171b2a;border-radius:16px;padding:20px;width:80%;max-width:360px;color:white;font-family:sans-serif;';
      var t = document.createElement('div');
      t.style.cssText = 'font-size:18px;font-weight:bold;margin-bottom:8px;';
      t.textContent = title || '';
      var m = document.createElement('div');
      m.style.cssText = 'font-size:14px;color:#aab3c5;margin-bottom:16px;';
      m.textContent = message || '';
      var row = document.createElement('div');
      row.style.cssText = 'display:flex;justify-content:flex-end;';
      list.forEach(function (b) {
        var bt = document.createElement('div');
        bt.style.cssText = 'padding:8px 14px;color:#00d994;font-weight:bold;cursor:pointer;';
        bt.textContent = b.text || 'OK';
        bt.onclick = function () {
          if (overlay.parentNode) { overlay.parentNode.removeChild(overlay); }
          if (b.onPress) { b.onPress(); }
        };
        row.appendChild(bt);
      });
      card.appendChild(t);
      card.appendChild(m);
      card.appendChild(row);
      overlay.appendChild(card);
      document.body.appendChild(overlay);
    }
  };

  function winSize() {
    return { width: W.innerWidth, height: W.innerHeight, scale: W.devicePixelRatio || 1, fontScale: 1 };
  }

  W.Dimensions = {
    get: function () { return winSize(); },
    addEventListener: function (type, fn) {
      var f = function () { fn({ window: winSize(), screen: winSize() }); };
      W.addEventListener('resize', f);
      return { remove: function () { W.removeEventListener('resize', f); } };
    }
  };

  W.useWindowDimensions = function () {
    var st = React.useState(winSize());
    React.useEffect(function () {
      var f = function () { st[1](winSize()); };
      W.addEventListener('resize', f);
      return function () { W.removeEventListener('resize', f); };
    }, []);
    return st[0];
  };

  W.useColorScheme = function () { return 'dark'; };

  W.Platform = {
    OS: 'android',
    Version: 33,
    isTV: false,
    select: function (o) {
      if (o.android !== undefined) { return o.android; }
      if (o.native !== undefined) { return o.native; }
      return o.default;
    }
  };

  W.PixelRatio = {
    get: function () { return W.devicePixelRatio || 1; },
    roundToNearestPixel: function (n) { return Math.round(n); }
  };

  W.StyleSheet = {
    create: function (o) { return o; },
    flatten: function (s) { return merge(s); },
    compose: function (a, b) { return [a, b]; },
    hairlineWidth: 1,
    absoluteFill: { position: 'absolute', left: 0, right: 0, top: 0, bottom: 0 },
    absoluteFillObject: { position: 'absolute', left: 0, right: 0, top: 0, bottom: 0 }
  };

  W.Keyboard = {
    dismiss: function () { if (document.activeElement && document.activeElement.blur) { document.activeElement.blur(); } },
    addListener: function () { return { remove: function () {} }; }
  };
  W.Linking = {
    openURL: function (u) { W.open(u, '_blank'); return Promise.resolve(); },
    canOpenURL: function () { return Promise.resolve(true); }
  };
  W.Vibration = { vibrate: function () {}, cancel: function () {} };
  W.BackHandler = { addEventListener: function () { return { remove: function () {} }; }, exitApp: function () {} };
  W.LayoutAnimation = { configureNext: function () {}, Presets: {}, create: function () {} };
  W.NativeModules = {};
  W.Share = { share: function () { return Promise.resolve({}); } };
  W.AppRegistry = {
    registerComponent: function (name, getter) { W.__JOSCOM_APP__ = getter(); },
    runApplication: function () {}
  };

  var memoryStore = {};
  W.AsyncStorage = {
    getItem: function (k) {
      return new Promise(function (resolve) {
        try { resolve(W.localStorage.getItem(k)); }
        catch (e) { resolve(k in memoryStore ? memoryStore[k] : null); }
      });
    },
    setItem: function (k, v) {
      return new Promise(function (resolve) {
        try { W.localStorage.setItem(k, String(v)); } catch (e) { memoryStore[k] = String(v); }
        resolve();
      });
    },
    removeItem: function (k) {
      return new Promise(function (resolve) {
        try { W.localStorage.removeItem(k); } catch (e) { delete memoryStore[k]; }
        resolve();
      });
    },
    clear: function () {
      return new Promise(function (resolve) {
        try { W.localStorage.clear(); } catch (e) { memoryStore = {}; }
        resolve();
      });
    },
    getAllKeys: function () {
      return new Promise(function (resolve) {
        try {
          var keys = [];
          for (var i = 0; i < W.localStorage.length; i++) { keys.push(W.localStorage.key(i)); }
          resolve(keys);
        } catch (e) { resolve(Object.keys(memoryStore)); }
      });
    }
  };

  function makeIcon() {
    return function Icon(props) {
      var size = props.size || 24;
      var color = props.color || '#ffffff';
      return h('span', {
        style: Object.assign({
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          width: size, height: size, borderRadius: size / 4,
          border: '1.5px solid ' + color, color: color,
          fontSize: size * 0.5, fontWeight: 'bold', boxSizing: 'border-box', flexShrink: 0
        }, flat(props.style))
      }, String(props.name || '?').charAt(0).toUpperCase());
    };
  }

  ['Ionicons', 'MaterialIcons', 'MaterialCommunityIcons', 'FontAwesome', 'FontAwesome5',
   'AntDesign', 'Feather', 'Entypo', 'EvilIcons', 'Octicons', 'SimpleLineIcons',
   'Foundation', 'Fontisto', 'Icon'].forEach(function (n) { W[n] = makeIcon(); });

  function AnimatedValue(v) { this._v = v; this._l = []; }
  AnimatedValue.prototype.setValue = function (v) {
    this._v = v;
    this._l.slice().forEach(function (f) { f(v); });
  };
  AnimatedValue.prototype.addListener = function (f) { this._l.push(f); return f; };
  AnimatedValue.prototype.removeListener = function (f) {
    this._l = this._l.filter(function (x) { return x !== f; });
  };
  AnimatedValue.prototype.stopAnimation = function (cb) { if (cb) { cb(this._v); } };
  AnimatedValue.prototype.interpolate = function (cfg) {
    var parent = this;
    var derived = new AnimatedValue(0);
    function calc(x) {
      var inp = cfg.inputRange;
      var out = cfg.outputRange;
      var i = 1;
      while (i < inp.length - 1 && x > inp[i]) { i++; }
      var t = (x - inp[i - 1]) / (inp[i] - inp[i - 1]);
      if (cfg.extrapolate === 'clamp') { t = Math.max(0, Math.min(1, t)); }
      var a = out[i - 1];
      var b = out[i];
      if (typeof a === 'number') { return a + (b - a) * t; }
      var na = parseFloat(a);
      var nb = parseFloat(b);
      if (!isNaN(na) && !isNaN(nb) && /^-?[0-9.]/.test(String(a))) {
        return (na + (nb - na) * t) + String(a).replace(/^-?[0-9.]+/, '');
      }
      return t < 0.5 ? a : b;
    }
    derived._v = calc(parent._v);
    parent.addListener(function (v) { derived.setValue(calc(v)); });
    return derived;
  };

  var Easing = {
    linear: function (t) { return t; },
    ease: function (t) { return t * t * (3 - 2 * t); },
    quad: function (t) { return t * t; },
    cubic: function (t) { return t * t * t; },
    sin: function (t) { return 1 - Math.cos(t * Math.PI / 2); },
    in: function (f) { return f; },
    out: function (f) { return function (t) { return 1 - f(1 - t); }; },
    inOut: function (f) {
      return function (t) { return t < 0.5 ? f(2 * t) / 2 : 1 - f(2 * (1 - t)) / 2; };
    },
    bezier: function () { return function (t) { return t * t * (3 - 2 * t); }; }
  };
  W.Easing = Easing;

  function timing(value, cfg) {
    var origin = null;
    var stopped = false;
    return {
      start: function (cb) {
        if (origin === null) { origin = value._v; }
        stopped = false;
        var from = value._v;
        var to = cfg.toValue;
        var dur = cfg.duration !== undefined ? cfg.duration : 500;
        var ease = cfg.easing || Easing.ease;
        var startT = null;
        var step = function (now) {
          if (stopped) { return; }
          if (startT === null) { startT = now; }
          var t = dur === 0 ? 1 : Math.min(1, (now - startT) / dur);
          value.setValue(from + (to - from) * ease(t));
          if (t < 1) { requestAnimationFrame(step); }
          else if (cb) { cb({ finished: true }); }
        };
        setTimeout(function () { requestAnimationFrame(step); }, cfg.delay || 0);
      },
      stop: function () { stopped = true; },
      reset: function () { if (origin !== null) { value.setValue(origin); } }
    };
  }

  function spring(value, cfg) {
    return timing(value, { toValue: cfg.toValue, duration: 450, easing: Easing.out(Easing.cubic) });
  }

  function sequence(list) {
    return {
      start: function (cb) {
        var i = 0;
        var next = function () {
          if (i >= list.length) { if (cb) { cb({ finished: true }); } return; }
          list[i++].start(next);
        };
        next();
      },
      stop: function () { list.forEach(function (a) { if (a.stop) { a.stop(); } }); },
      reset: function () { list.forEach(function (a) { if (a.reset) { a.reset(); } }); }
    };
  }

  function parallel(list) {
    return {
      start: function (cb) {
        var done = 0;
        if (list.length === 0) { if (cb) { cb({ finished: true }); } return; }
        list.forEach(function (a) {
          a.start(function () { done++; if (done === list.length && cb) { cb({ finished: true }); } });
        });
      },
      stop: function () { list.forEach(function (a) { if (a.stop) { a.stop(); } }); },
      reset: function () { list.forEach(function (a) { if (a.reset) { a.reset(); } }); }
    };
  }

  function loop(anim, cfg) {
    var stopped = false;
    var iterations = (cfg && cfg.iterations !== undefined) ? cfg.iterations : -1;
    return {
      start: function (cb) {
        var count = 0;
        stopped = false;
        var run = function () {
          if (stopped || (iterations >= 0 && count >= iterations)) {
            if (cb) { cb({ finished: !stopped }); }
            return;
          }
          count++;
          if (count > 1 && anim.reset) { anim.reset(); }
          anim.start(function () { run(); });
        };
        run();
      },
      stop: function () { stopped = true; if (anim.stop) { anim.stop(); } },
      reset: function () { if (anim.reset) { anim.reset(); } }
    };
  }

  function delay(ms) {
    return {
      start: function (cb) { setTimeout(function () { if (cb) { cb({ finished: true }); } }, ms); },
      stop: function () {},
      reset: function () {}
    };
  }

  function resolveStyle(style, collect) {
    var s = merge(style);
    Object.keys(s).forEach(function (k) {
      var v = s[k];
      if (v instanceof AnimatedValue) {
        collect.push(v);
        s[k] = v._v;
      } else if (k === 'transform' && Array.isArray(v)) {
        s[k] = v.map(function (t) {
          var o = {};
          Object.keys(t).forEach(function (tk) {
            var tv = t[tk];
            if (tv instanceof AnimatedValue) { collect.push(tv); o[tk] = tv._v; }
            else { o[tk] = tv; }
          });
          return o;
        });
      }
    });
    return s;
  }

  function createAnimated(Comp) {
    return function AnimatedComponent(props) {
      var st = React.useState(0);
      var used = [];
      var style = resolveStyle(props.style, used);
      React.useEffect(function () {
        var f = function () { st[1](function (n) { return n + 1; }); };
        used.forEach(function (v) { v.addListener(f); });
        return function () { used.forEach(function (v) { v.removeListener(f); }); };
      });
      return h(Comp, Object.assign({}, props, { style: style }));
    };
  }

  W.Animated = {
    Value: AnimatedValue,
    timing: timing,
    spring: spring,
    sequence: sequence,
    parallel: parallel,
    loop: loop,
    delay: delay,
    stagger: function (time, list) {
      return parallel(list.map(function (a, i) { return sequence([delay(time * i), a]); }));
    },
    event: function () { return function () {}; },
    createAnimatedComponent: createAnimated,
    View: createAnimated(W.View),
    Text: createAnimated(W.Text),
    Image: createAnimated(W.Image),
    ScrollView: createAnimated(W.ScrollView)
  };

  W.LinearGradient = function LinearGradient(props) {
    function pt(p, d) {
      if (Array.isArray(p)) { return { x: p[0], y: p[1] }; }
      return p || d;
    }
    var colors = props.colors || ['#000000', '#ffffff'];
    var s = pt(props.start, { x: 0.5, y: 0 });
    var e = pt(props.end, { x: 0.5, y: 1 });
    var angle = Math.atan2(e.x - s.x, -(e.y - s.y)) * 180 / Math.PI;
    var stops = colors.map(function (c, i) {
      var loc = (props.locations && props.locations[i] !== undefined) ? ' ' + (props.locations[i] * 100) + '%' : '';
      return c + loc;
    }).join(', ');
    var style = Object.assign({}, baseBox, {
      backgroundImage: 'linear-gradient(' + angle + 'deg, ' + stops + ')'
    }, flat(props.style));
    return h('div', { style: style }, props.children);
  };

  W.BlurView = function BlurView(props) {
    var amount = (props.intensity !== undefined ? props.intensity : 50) / 5;
    var tint = props.tint === 'light' ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.35)';
    var style = Object.assign({}, baseBox, {
      backgroundColor: tint,
      backdropFilter: 'blur(' + amount + 'px)',
      WebkitBackdropFilter: 'blur(' + amount + 'px)'
    }, flat(props.style));
    return h('div', { style: style }, props.children);
  };

  var resolved = function (v) { return function () { return Promise.resolve(v); }; };

  W.Haptics = {
    impactAsync: resolved(), notificationAsync: resolved(), selectionAsync: resolved(),
    ImpactFeedbackStyle: { Light: 'light', Medium: 'medium', Heavy: 'heavy' },
    NotificationFeedbackType: { Success: 'success', Warning: 'warning', Error: 'error' }
  };

  W.Constants = {
    statusBarHeight: 0,
    deviceName: 'Joscom Preview',
    platform: { android: {} },
    expoConfig: {},
    manifest: {},
    default: undefined
  };

  W.Font = { loadAsync: resolved(), isLoaded: function () { return true; } };
  W.useFonts = function () { return [true, null]; };
  W.SplashScreen = { preventAutoHideAsync: resolved(), hideAsync: resolved() };
  W.registerRootComponent = function (Comp) { W.__JOSCOM_APP__ = Comp; };

  W.useEvent = function (player, name, initial) {
    var st = React.useState(initial);
    React.useEffect(function () {
      if (!player || !player.addListener) { return undefined; }
      var sub = player.addListener(name, function (payload) { st[1](payload); });
      return function () { if (sub && sub.remove) { sub.remove(); } };
    }, [player]);
    return st[0];
  };

  W.ResizeMode = { CONTAIN: 'contain', COVER: 'cover', STRETCH: 'stretch' };

  var videoFit = { contain: 'contain', cover: 'cover', stretch: 'fill' };

  function videoStatus(el, finished) {
    return {
      isLoaded: true,
      isPlaying: !el.paused && !el.ended,
      positionMillis: Math.round((el.currentTime || 0) * 1000),
      durationMillis: Math.round((el.duration || 0) * 1000),
      didJustFinish: !!finished,
      isBuffering: false,
      isMuted: el.muted,
      volume: el.volume,
      isLooping: el.loop,
      shouldPlay: !el.paused
    };
  }

  W.Video = React.forwardRef(function Video(props, ref) {
    var el = React.useRef(null);
    var uri = uriOf(props.source);
    React.useImperativeHandle(ref, function () {
      function get() { return el.current; }
      function done() { return Promise.resolve(get() ? videoStatus(get()) : {}); }
      return {
        playAsync: function () { if (get()) { get().play(); } return done(); },
        pauseAsync: function () { if (get()) { get().pause(); } return done(); },
        stopAsync: function () { if (get()) { get().pause(); get().currentTime = 0; } return done(); },
        replayAsync: function () { if (get()) { get().currentTime = 0; get().play(); } return done(); },
        setPositionAsync: function (ms) { if (get()) { get().currentTime = ms / 1000; } return done(); },
        setIsMutedAsync: function (v) { if (get()) { get().muted = !!v; } return done(); },
        setVolumeAsync: function (v) { if (get()) { get().volume = v; } return done(); },
        setIsLoopingAsync: function (v) { if (get()) { get().loop = !!v; } return done(); },
        getStatusAsync: done,
        setStatusAsync: function (s) {
          if (get()) {
            if (s.isMuted !== undefined) { get().muted = !!s.isMuted; }
            if (s.isLooping !== undefined) { get().loop = !!s.isLooping; }
            if (s.volume !== undefined) { get().volume = s.volume; }
            if (s.positionMillis !== undefined) { get().currentTime = s.positionMillis / 1000; }
            if (s.shouldPlay === true) { get().play(); }
            if (s.shouldPlay === false) { get().pause(); }
          }
          return done();
        },
        loadAsync: function (source, status) {
          if (get()) { get().src = uriOf(source); if (status && status.shouldPlay) { get().play(); } }
          return done();
        },
        unloadAsync: function () { if (get()) { get().pause(); } return done(); },
        presentFullscreenPlayerAsync: function () {
          if (get() && get().requestFullscreen) { get().requestFullscreen(); }
          return Promise.resolve();
        }
      };
    });
    function report(finished) {
      if (props.onPlaybackStatusUpdate && el.current) {
        props.onPlaybackStatusUpdate(videoStatus(el.current, finished));
      }
    }
    var style = Object.assign({
      display: 'block', backgroundColor: '#000', objectFit: videoFit[props.resizeMode] || 'contain', flexShrink: 0
    }, flat(props.style));
    return h('video', {
      ref: el,
      src: uri || undefined,
      controls: !!props.useNativeControls,
      autoPlay: !!props.shouldPlay,
      loop: !!props.isLooping,
      muted: !!props.isMuted,
      playsInline: true,
      style: style,
      onLoadedData: function () { if (props.onLoad && el.current) { props.onLoad(videoStatus(el.current)); } report(); },
      onTimeUpdate: function () { report(); },
      onPlay: function () { report(); },
      onPause: function () { report(); },
      onEnded: function () { report(true); },
      onError: function () { if (props.onError) { props.onError('Could not load the video'); } }
    });
  });

  W.Audio = {
    setAudioModeAsync: resolved(),
    requestPermissionsAsync: resolved({ status: 'granted', granted: true }),
    Sound: {
      createAsync: function (source, status) {
        var a = document.createElement('audio');
        a.src = uriOf(source);
        if (status && status.shouldPlay) { a.play(); }
        var sound = {
          playAsync: function () { a.play(); return Promise.resolve({ isLoaded: true, isPlaying: true }); },
          pauseAsync: function () { a.pause(); return Promise.resolve({ isLoaded: true, isPlaying: false }); },
          stopAsync: function () { a.pause(); a.currentTime = 0; return Promise.resolve({ isLoaded: true, isPlaying: false }); },
          setPositionAsync: function (ms) { a.currentTime = ms / 1000; return Promise.resolve({}); },
          unloadAsync: function () { a.pause(); return Promise.resolve({}); },
          setOnPlaybackStatusUpdate: function () {}
        };
        return Promise.resolve({ sound: sound, status: { isLoaded: true } });
      }
    }
  };

  W.useVideoPlayer = function (source, setup) {
    var ref = React.useRef(null);
    if (ref.current === null) {
      var listeners = {};
      var p = {
        source: source, _el: null, _wantPlay: false, _loop: false, _muted: false, _volume: 1,
        play: function () { p._wantPlay = true; if (p._el) { p._el.play(); } },
        pause: function () { p._wantPlay = false; if (p._el) { p._el.pause(); } },
        replace: function (s) { p.source = s; if (p._el) { p._el.src = uriOf(s); } },
        seekBy: function (sec) { if (p._el) { p._el.currentTime += sec; } },
        release: function () {},
        emit: function (name, payload) { (listeners[name] || []).slice().forEach(function (f) { f(payload); }); },
        addListener: function (name, f) {
          listeners[name] = listeners[name] || [];
          listeners[name].push(f);
          return { remove: function () { listeners[name] = listeners[name].filter(function (x) { return x !== f; }); } };
        }
      };
      Object.defineProperty(p, 'loop', { get: function () { return p._loop; }, set: function (v) { p._loop = !!v; if (p._el) { p._el.loop = !!v; } } });
      Object.defineProperty(p, 'muted', { get: function () { return p._muted; }, set: function (v) { p._muted = !!v; if (p._el) { p._el.muted = !!v; } } });
      Object.defineProperty(p, 'volume', { get: function () { return p._volume; }, set: function (v) { p._volume = v; if (p._el) { p._el.volume = v; } } });
      Object.defineProperty(p, 'currentTime', { get: function () { return p._el ? p._el.currentTime : 0; }, set: function (v) { if (p._el) { p._el.currentTime = v; } } });
      Object.defineProperty(p, 'duration', { get: function () { return p._el ? (p._el.duration || 0) : 0; } });
      Object.defineProperty(p, 'playing', { get: function () { return !!(p._el && !p._el.paused); } });
      ref.current = p;
      if (setup) { setup(p); }
    }
    return ref.current;
  };

  W.VideoView = function VideoView(props) {
    var p = props.player;
    var style = Object.assign({
      display: 'block', backgroundColor: '#000', objectFit: videoFit[props.contentFit === 'fill' ? 'stretch' : props.contentFit] || 'contain', flexShrink: 0
    }, flat(props.style));
    return h('video', {
      ref: function (el) {
        if (!p) { return; }
        p._el = el;
        if (el) {
          el.loop = !!p._loop;
          el.muted = !!p._muted;
          el.volume = p._volume;
          if (p._wantPlay) { el.play(); }
        }
      },
      src: uriOf(p && p.source) || undefined,
      controls: props.nativeControls !== false,
      playsInline: true,
      style: style,
      onPlay: function () { if (p) { p.emit('playingChange', { isPlaying: true }); } },
      onPause: function () { if (p) { p.emit('playingChange', { isPlaying: false }); } },
      onEnded: function () { if (p) { p.emit('playToEnd'); } }
    });
  };

  var SAMPLE_VIDEO = 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4';
  var SAMPLE_IMAGE = 'https://picsum.photos/600/400';

  function pickMedia(kind) {
    return new Promise(function (resolve) {
      var overlay = document.createElement('div');
      overlay.style.cssText = 'position:fixed;left:0;top:0;right:0;bottom:0;background:rgba(0,0,0,0.65);z-index:9600;display:flex;align-items:center;justify-content:center;';
      var card = document.createElement('div');
      card.style.cssText = 'background:#171b2a;border-radius:18px;padding:18px;width:88%;max-width:380px;color:white;font-family:sans-serif;';
      function line(text, css) {
        var d = document.createElement('div');
        d.style.cssText = css;
        d.textContent = text;
        return d;
      }
      function button(text, color, onClick) {
        var b = document.createElement('div');
        b.style.cssText = 'padding:12px;margin-top:8px;border-radius:12px;text-align:center;font-weight:bold;cursor:pointer;background:' + color + ';color:#06100c;';
        b.textContent = text;
        b.onclick = onClick;
        return b;
      }
      function finish(result) {
        if (overlay.parentNode) { overlay.parentNode.removeChild(overlay); }
        resolve(result);
      }
      function guess(uri) {
        if (/\.(mp4|webm|mov|m4v|ogv)(\?|$)/i.test(uri)) { return 'video'; }
        if (/\.(png|jpe?g|gif|webp)(\?|$)/i.test(uri)) { return 'image'; }
        return kind === 'video' ? 'video' : 'image';
      }
      function done(uri, type, extra) {
        var a = Object.assign({ uri: uri, type: type, width: 0, height: 0 }, extra || {});
        finish({ canceled: false, cancelled: false, uri: uri, assets: [a] });
      }
      var title = kind === 'video' ? 'Choose a video' : (kind === 'image' ? 'Choose an image' : 'Choose a file');
      card.appendChild(line(title, 'font-size:18px;font-weight:bold;margin-bottom:10px;'));
      var input = document.createElement('input');
      input.placeholder = 'Paste a link (https://...)';
      input.style.cssText = 'width:100%;padding:12px;border-radius:10px;border:1px solid #03d9a0;background:#0e1220;color:white;font-size:15px;';
      card.appendChild(input);
      card.appendChild(button('Use link', '#00d994', function () {
        if (input.value) { done(input.value, guess(input.value), { fileName: input.value.split('/').pop() }); }
      }));
      if (kind !== 'image') {
        card.appendChild(button('Use sample video', '#9d7bff', function () { done(SAMPLE_VIDEO, 'video', { fileName: 'flower.mp4' }); }));
      }
      if (kind !== 'video') {
        card.appendChild(button('Use sample image', '#9d7bff', function () { done(SAMPLE_IMAGE, 'image', { fileName: 'sample.jpg' }); }));
      }
      var file = document.createElement('input');
      file.type = 'file';
      file.accept = kind === 'video' ? 'video/*' : (kind === 'image' ? 'image/*' : '*/*');
      file.style.display = 'none';
      file.onchange = function () {
        var f = file.files && file.files[0];
        if (f) {
          var t = /^video/.test(f.type) ? 'video' : (/^image/.test(f.type) ? 'image' : 'file');
          done(URL.createObjectURL(f), t, { fileName: f.name, name: f.name, mimeType: f.type, size: f.size });
        }
      };
      card.appendChild(file);
      var browse = button('Browse files', '#2a3350', function () { file.click(); });
      browse.style.color = 'white';
      card.appendChild(browse);
      var cancel = button('Cancel', 'transparent', function () { finish({ canceled: true, cancelled: true, assets: null }); });
      cancel.style.color = '#ff6b7a';
      card.appendChild(cancel);
      overlay.appendChild(card);
      document.body.appendChild(overlay);
    });
  }

  function mediaKind(options) {
    var s = JSON.stringify((options && options.mediaTypes) || '');
    var video = /ideo/i.test(s);
    var image = /mage/i.test(s);
    if (video && !image) { return 'video'; }
    if (image && !video) { return 'image'; }
    return 'all';
  }

  var granted = { status: 'granted', granted: true, canAskAgain: true, expires: 'never' };

  W.ImagePicker = {
    launchImageLibraryAsync: function (o) { return pickMedia(mediaKind(o)); },
    launchCameraAsync: function (o) { return pickMedia(mediaKind(o)); },
    requestMediaLibraryPermissionsAsync: resolved(granted),
    requestCameraPermissionsAsync: resolved(granted),
    getMediaLibraryPermissionsAsync: resolved(granted),
    getCameraPermissionsAsync: resolved(granted),
    MediaTypeOptions: { All: 'All', Videos: 'Videos', Images: 'Images' },
    MediaType: { All: 'All', Videos: 'Videos', Images: 'Images' }
  };

  W.DocumentPicker = {
    getDocumentAsync: function () {
      return pickMedia('file').then(function (r) {
        if (r.canceled) { return { canceled: true, type: 'cancel', assets: null }; }
        var a = r.assets[0];
        a.name = a.name || a.fileName || 'file';
        return { canceled: false, type: 'success', assets: [a], uri: a.uri, name: a.name };
      });
    }
  };

  function pickNames(names) {
    var o = {};
    names.forEach(function (n) { if (W[n] !== undefined) { o[n] = W[n]; } });
    return o;
  }

  var rnNames = ['View', 'Text', 'TextInput', 'Pressable', 'TouchableOpacity', 'TouchableHighlight',
    'TouchableWithoutFeedback', 'TouchableNativeFeedback', 'Button', 'ScrollView', 'FlatList', 'SectionList',
    'Image', 'ImageBackground', 'SafeAreaView', 'KeyboardAvoidingView', 'StatusBar', 'ActivityIndicator',
    'Switch', 'Modal', 'Alert', 'Dimensions', 'useWindowDimensions', 'useColorScheme', 'Platform',
    'PixelRatio', 'StyleSheet', 'Keyboard', 'Linking', 'Vibration', 'BackHandler', 'LayoutAnimation',
    'NativeModules', 'Share', 'AppRegistry', 'Animated', 'Easing'];

  var iconNames = ['Ionicons', 'MaterialIcons', 'MaterialCommunityIcons', 'FontAwesome', 'FontAwesome5',
    'AntDesign', 'Feather', 'Entypo', 'EvilIcons', 'Octicons', 'SimpleLineIcons', 'Foundation', 'Fontisto', 'Icon'];

  W.__JOSCOM_MODULES__ = {
    'react': React,
    'react-dom': (typeof ReactDOM !== 'undefined') ? ReactDOM : {},
    'react-native': pickNames(rnNames),
    'expo': pickNames(['registerRootComponent', 'useEvent']),
    'expo-status-bar': pickNames(['StatusBar']),
    'expo-linear-gradient': pickNames(['LinearGradient']),
    'react-native-linear-gradient': pickNames(['LinearGradient']),
    'expo-av': pickNames(['Video', 'ResizeMode', 'Audio']),
    'expo-video': pickNames(['VideoView', 'useVideoPlayer']),
    'expo-image-picker': W.ImagePicker,
    'expo-document-picker': W.DocumentPicker,
    'expo-font': { useFonts: W.useFonts, loadAsync: W.Font.loadAsync, isLoaded: W.Font.isLoaded },
    'expo-constants': { default: W.Constants },
    'expo-haptics': W.Haptics,
    'expo-blur': pickNames(['BlurView']),
    'expo-splash-screen': W.SplashScreen,
    '@expo/vector-icons': pickNames(iconNames),
    'react-native-vector-icons': pickNames(iconNames),
    '@react-native-async-storage/async-storage': { default: W.AsyncStorage },
    'react-native-safe-area-context': pickNames(['SafeAreaView', 'SafeAreaProvider', 'useSafeAreaInsets'])
  };

  class ErrorBoundary extends React.Component {
    constructor(props) {
      super(props);
      this.state = { failed: false };
    }
    static getDerivedStateFromError() { return { failed: true }; }
    componentDidCatch(error, info) {
      W.joscomShowError('Render error',
        (error && error.message) ? error.message : String(error),
        info && info.componentStack);
    }
    render() { return this.state.failed ? null : this.props.children; }
  }
  W.ErrorBoundary = ErrorBoundary;

})();


</script>

<script type="text/babel">

joscomLoadDeps(window.JOSCOM_DEPS).then(function (__deps) {

try {

__IMPORT_BINDINGS__

__APP_CODE__

const Joscom_Root = (
    typeof App !== 'undefined' ? App : window.__JOSCOM_APP__
);

const root = ReactDOM.createRoot(
    document.getElementById('root')
);

root.render(
    <ErrorBoundary>
        <Joscom_Root />
    </ErrorBoundary>
);

} catch(e) {

document.getElementById('root').innerHTML = '';

window.joscomShowError(
    'Runtime error',
    (e && e.message) ? e.message : String(e),
    e && e.stack
);

}

}).catch(function (e) {

window.joscomShowError(
    'Dependency error',
    (e && e.message) ? e.message : String(e)
);

});

</script>

<script>

let startX = 0;

document.addEventListener("touchstart", function(e) {

    startX = e.touches[0].clientX;

}, {passive:true});

document.addEventListener("touchend", function(e) {

    let endX = e.changedTouches[0].clientX;

    let distance = endX - startX;

    if (distance < -85) {

        window.location.hash = "joscom-editor";

    }

}, {passive:true});

</script>

</body>

</html>
"""

        for name, url in LIBS.items():

            html = html.replace(
                "__LIB_" + name + "__",
                app.lib_url(name, url)
            )

        def as_js(value):

            return json.dumps(value).replace("</", "<\\/")

        html = html.replace(
            "__DEPS_JSON__",
            as_js(
                [
                    {"name": key, "url": value}
                    for key, value in needed.items()
                ]
            )
        )

        html = html.replace(
            "__MISSING_JSON__",
            as_js(missing)
        )

        html = html.replace(
            "__IMPORT_BINDINGS__",
            " ".join(bindings)
        )

        tag = '<script type="text/babel">'

        start = html.index(tag) + len(tag)

        offset = (
            html[start:html.index("__APP_CODE__")].count("\n") +
            extra
        )

        html = html.replace(
            "__LINE_OFFSET__",
            str(offset)
        )

        html = html.replace(
            "__APP_CODE__",
            clean
        )

        try:

            os.makedirs(
                "/storage/emulated/0/JoscomApp",
                exist_ok=True
            )

            with open(
                self.html_path,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(html)

            return self.html_path

        except:

            fallback = "preview.html"

            with open(
                fallback,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(html)

            return os.path.abspath(fallback)

    # --------------------------------------------------
    # LOAD PREVIEW
    # --------------------------------------------------

    def load(self, code):

        self.loading.text = "Preparing preview..."

        self.info.text = "Compiling React preview"

        path = self.create_html(code)

        if platform == "android":

            Clock.schedule_once(
                lambda dt: self.open_android_webview(path),
                0.3
            )

        else:

            import webbrowser

            webbrowser.open(
                "file://" + path
            )

            self.loading.text = ""

            self.info.text = "Preview opened in browser"

            MDApp.get_running_app().stop_editor_spinner()

    # --------------------------------------------------
    # ANDROID FULLSCREEN WEBVIEW
    # --------------------------------------------------

    def open_android_webview(self, path):

        try:

            from jnius import autoclass
            from android.runnable import run_on_ui_thread

            WebView = autoclass(
                "android.webkit.WebView"
            )

            WebViewClient = autoclass(
                "android.webkit.WebViewClient"
            )

            WebChromeClient = autoclass(
                "android.webkit.WebChromeClient"
            )

            Dialog = autoclass(
                "android.app.Dialog"
            )

            LayoutParams = autoclass(
                "android.view.ViewGroup$LayoutParams"
            )

            WindowManager = autoclass(
                "android.view.WindowManager$LayoutParams"
            )

            Activity = autoclass(
                "org.kivy.android.PythonActivity"
            )

            self.activity = Activity.mActivity

            @run_on_ui_thread
            def show():

                try:

                    self.close_preview()

                    dialog = Dialog(self.activity)

                    web = WebView(self.activity)

                    settings = web.getSettings()

                    settings.setJavaScriptEnabled(True)

                    settings.setDomStorageEnabled(True)

                    settings.setAllowFileAccess(True)

                    settings.setAllowFileAccessFromFileURLs(True)

                    settings.setAllowUniversalAccessFromFileURLs(True)

                    settings.setUseWideViewPort(True)

                    settings.setLoadWithOverviewMode(True)

                    web.setWebViewClient(
                        WebViewClient()
                    )

                    web.setWebChromeClient(
                        WebChromeClient()
                    )

                    web.loadUrl(
                        "file://" + path
                    )

                    dialog.setContentView(
                        web,
                        LayoutParams(-1, -1)
                    )

                    dialog.setCancelable(True)

                    dialog.show()

                    dialog.getWindow().setLayout(
                        -1,
                        -1
                    )

                    dialog.getWindow().setFlags(
                        WindowManager.FLAG_FULLSCREEN,
                        WindowManager.FLAG_FULLSCREEN
                    )

                    self.webview = web

                    self.dialog = dialog

                    self.loading.text = ""

                    self.info.text = (
                        "Preview running - Swipe left to return"
                    )

                    MDApp.get_running_app().stop_editor_spinner()

                    self.back_event = Clock.schedule_interval(
                        self.check_swipe_back,
                        0.25
                    )

                except Exception as e:

                    self.loading.text = ""

                    self.info.text = "Preview error: " + str(e)

                    MDApp.get_running_app().stop_editor_spinner()

            show()

        except Exception as e:

            self.loading.text = ""

            self.info.text = "WebView error: " + str(e)

            MDApp.get_running_app().stop_editor_spinner()

    # --------------------------------------------------
    # SWIPE BACK
    # --------------------------------------------------

    def check_swipe_back(self, dt):

        try:

            if not self.webview:
                return False

            current_url = str(
                self.webview.getUrl()
            )

            if "joscom-editor" in current_url:

                self.close_preview()

                return False

        except:
            pass

        return True

    # --------------------------------------------------
    # CLOSE PREVIEW
    # --------------------------------------------------

    def close_preview(self):

        try:

            if self.back_event:

                self.back_event.cancel()

                self.back_event = None

        except:
            pass

        try:

            if self.dialog:

                self.dialog.dismiss()

        except:
            pass

        self.dialog = None
        self.webview = None

        self.info.text = "Editor ready"

        self.loading.text = ""


# ==================================================
# EDITOR SCREEN
# ==================================================

class EditorScreen(Screen):

    def on_touch_move(self, touch):

        if self.name == "preview" and touch.dx < -60:

            self.manager.current = "editor"

            return True

        return super().on_touch_move(touch)


# ==================================================
# MAIN APPLICATION
# ==================================================

class JoscomFinal(MDApp):

    def build(self):

        self.theme_cls.theme_style = "Dark"

        self.theme_cls.primary_palette = "DeepPurple"

        Window.clearcolor = BG

        Window.softinput_mode = ""

        self.file_path = os.path.join(
            self.get_folder(),
            "App.js"
        )

        self.libs_dir = os.path.join(
            os.path.dirname(self.file_path),
            "libs"
        )

        self.deps_path = os.path.join(
            os.path.dirname(self.file_path),
            "dependencies.json"
        )

        self.deps = self.load_deps()

        self.editor = None

        self.connection = False

        self.net_busy = False

        self.last_mbps = None

        self.last_speed_time = 0

        self.kb_space = 0

        self.native_ok = False

        self.full_height = Window.height

        self.sm = ScreenManager()

        Window.bind(
            on_keyboard=self.on_back
        )

        self.editor_screen = EditorScreen(
            name="editor"
        )

        self.build_editor()

        self.preview_screen = Screen(
            name="preview"
        )

        self.preview = InsideWebView()

        self.preview_screen.add_widget(
            self.preview
        )

        self.files_screen = Screen(
            name="files"
        )

        self.build_files()

        self.deps_screen = Screen(
            name="deps"
        )

        self.build_deps()

        self.sm.add_widget(
            self.editor_screen
        )

        self.sm.add_widget(
            self.preview_screen
        )

        self.sm.add_widget(
            self.files_screen
        )

        self.sm.add_widget(
            self.deps_screen
        )

        Clock.schedule_once(
            self.update_initial_numbers,
            0.5
        )

        Clock.schedule_once(
            self.check_connection,
            1
        )

        Clock.schedule_interval(
            self.check_connection,
            15
        )

        return self.sm

    # ==================================================
    # EDITOR DESIGN
    # ==================================================

    def build_editor(self):

        main = MDBoxLayout(
            orientation="vertical",
            md_bg_color=BG
        )

        # TOP TOOLBAR

        top = GradientBox(
            colors=(
                (0.13, 0.09, 0.27, 1),
                (0.03, 0.07, 0.11, 1)
            ),
            orientation="horizontal",
            size_hint_y=None,
            height=dp(64),
            padding=[dp(12), dp(8)],
            spacing=dp(10)
        )

        logo = GradientBox(
            colors=(GREEN, PURPLE),
            radius=14,
            size_hint=(None, None),
            size=(dp(46), dp(46)),
            pos_hint={"center_y": 0.5}
        )

        logo_center = AnchorLayout()

        logo_center.add_widget(
            MDIcon(
                icon="code-braces",
                theme_text_color="Custom",
                text_color=(0.02, 0.05, 0.09, 1),
                halign="center"
            )
        )

        logo.add_widget(logo_center)

        top.add_widget(logo)

        title_box = MDBoxLayout(
            orientation="vertical",
            spacing=0
        )

        title_box.add_widget(
            MDLabel(
                text="JOSCOM STUDIO",
                bold=True,
                font_style="Subtitle1",
                theme_text_color="Custom",
                text_color=WHITE
            )
        )

        title_box.add_widget(
            MDLabel(
                text="React Native Editor",
                font_style="Caption",
                theme_text_color="Custom",
                text_color=GREY
            )
        )

        top.add_widget(title_box)

        self.editor_spinner = MDSpinner(
            size_hint=(None, None),
            size=(dp(23), dp(23)),
            active=False,
            color=GREEN,
            line_width=dp(2),
            pos_hint={"center_y": 0.5}
        )

        top.add_widget(
            self.editor_spinner
        )

        net_box = TapBox(
            bg=CARD,
            radius=14,
            orientation="horizontal",
            size_hint=(None, None),
            size=(dp(88), dp(32)),
            padding=[dp(5), 0, dp(5), 0],
            pos_hint={"center_y": 0.5}
        )

        self.net_icon = MDIcon(
            icon="wifi",
            theme_text_color="Custom",
            text_color=GREY,
            halign="center",
            size_hint_x=None,
            width=dp(24),
            pos_hint={"center_y": 0.5}
        )

        self.net = MDLabel(
            text="Checking",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=GREY,
            halign="left"
        )

        net_box.add_widget(self.net_icon)

        net_box.add_widget(self.net)

        net_box.bind(
            on_release=self.test_speed_now
        )

        top.add_widget(net_box)

        self.main_box = main

        main.add_widget(top)

        main.add_widget(
            GradientBar(
                size_hint_y=None,
                height=dp(2)
            )
        )

        # FILE TAB

        tab = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(38),
            padding=[dp(10), 0],
            spacing=dp(5),
            md_bg_color=(0.045, 0.05, 0.085, 1)
        )

        tab.add_widget(
            MDIconButton(
                icon="language-javascript",
                size_hint_x=None,
                width=dp(32),
                theme_text_color="Custom",
                text_color=(1, 0.8, 0.2, 1)
            )
        )

        self.tab_label = MDLabel(
            text=os.path.basename(self.file_path),
            font_style="Caption",
            theme_text_color="Custom",
            text_color=WHITE
        )

        tab.add_widget(self.tab_label)

        tab.add_widget(
            MDIcon(
                icon="circle-medium",
                halign="right",
                theme_text_color="Custom",
                text_color=GREEN,
                size_hint_x=None,
                width=dp(25)
            )
        )

        main.add_widget(tab)

        # ==================================================
        # SYMBOL TOOLBAR
        # ==================================================

        symbol_scroll = ScrollView(
            size_hint_y=None,
            height=dp(48),
            do_scroll_y=False,
            do_scroll_x=True,
            bar_width=0,
            scroll_type=["content"]
        )

        symbol_bar = MDBoxLayout(
            orientation="horizontal",
            size_hint_x=None,
            width=dp(610),
            spacing=dp(3),
            padding=[dp(5), dp(3)],
            md_bg_color=(0.07, 0.085, 0.14, 1)
        )

        symbols = [
            "</>",
            "{}",
            "()",
            "[]",
            "<>",
            "=>",
            ";",
            "=",
            "'",
            '"',
            ".",
            ",",
            "&&",
            "||"
        ]

        for symbol in symbols:

            chip = TapBox(
                bg=CARD,
                radius=10,
                size_hint=(None, None),
                size=(dp(46), dp(34)),
                pos_hint={"center_y": 0.5}
            )

            chip.add_widget(
                Label(
                    text=symbol,
                    color=GREEN,
                    bold=True,
                    font_size=dp(14)
                )
            )

            chip.bind(
                on_release=lambda instance, s=symbol:
                self.insert_symbol(s)
            )

            symbol_bar.add_widget(chip)

        symbol_bar.width = dp(len(symbols) * 49 + 10)

        symbol_scroll.add_widget(
            symbol_bar
        )

        main.add_widget(symbol_scroll)

        # ==================================================
        # EDIT TOOLBAR
        # ==================================================

        tools_bar = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            spacing=dp(3),
            padding=[dp(5), dp(3)],
            md_bg_color=(0.06, 0.07, 0.115, 1)
        )

        tools = [
            ("keyboard-close", "keyboard"),
            ("select-all", "select"),
            ("content-copy", "copy"),
            ("content-cut", "cut"),
            ("content-paste", "paste"),
            ("undo", "undo"),
            ("redo", "redo")
        ]

        for icon, action in tools:

            tool_chip = TapBox(
                bg=CARD,
                radius=10,
                size_hint=(1, None),
                height=dp(34),
                pos_hint={"center_y": 0.5}
            )

            tool_center = AnchorLayout()

            tool_center.add_widget(
                MDIcon(
                    icon=icon,
                    theme_text_color="Custom",
                    text_color=(0.72, 0.62, 1, 1),
                    halign="center"
                )
            )

            tool_chip.add_widget(tool_center)

            tool_chip.bind(
                on_release=lambda instance, a=action:
                self.edit_action(a)
            )

            tools_bar.add_widget(tool_chip)

        main.add_widget(tools_bar)

        # ==================================================
        # SMOOTH CODE SCROLL AREA
        # ==================================================

        self.code_scroll = AxisScroll(
            do_scroll_x=True,
            do_scroll_y=True,
            scroll_timeout=250,
            scroll_distance=dp(8),
            bar_width=dp(3),
            bar_color=GREEN,
            bar_inactive_color=(0.3, 0.35, 0.45, 0.3),
            scroll_type=["bars", "content"],
            effect_cls="ScrollEffect"
        )

        self.code_area = MDBoxLayout(
            orientation="horizontal",
            size_hint=(None, None),
            width=dp(300),
            height=dp(400),
            spacing=0,
            md_bg_color=(0.055, 0.06, 0.095, 1)
        )

        # LINE NUMBERS

        self.line_label = Label(
            text="1",
            size_hint=(None, None),
            width=dp(43),
            height=dp(400),
            font_name="data/fonts/RobotoMono-Regular.ttf",
            font_size=dp(13),
            color=(0.42, 0.5, 0.65, 1),
            halign="right",
            valign="top",
            text_size=(dp(43), dp(400)),
            padding=[dp(5), dp(10)]
        )

        # DEFAULT CODE

        default_code = """function App() {
  const [name, setName] = React.useState('Joscom');
  const [count, setCount] = React.useState(0);

  return (
    <View style={{flex:1, padding:20, backgroundColor:'#0a0a0f'}}>
      <Text style={{fontSize:28, color:'#03DAC6', fontWeight:'bold'}}>
        Joscom Pro Max
      </Text>

      <Text style={{color:'#888', marginTop:8}}>
        Welcome to Joscom Studio
      </Text>

      <TextInput
        placeholder="Type your name"
        value={name}
        onChangeText={setName}
      />

      <Pressable onPress={() => setCount(count+1)}>
        <Text>Count {count} - {name}</Text>
      </Pressable>
    </View>
  );
}"""

        # CODE INPUT

        self.editor = SmartCodeInput(
            lexer=lexer,
            font_size=dp(13),
            background_color=(0.055, 0.06, 0.095, 1),
            foreground_color=(0.87, 0.92, 1, 1),
            cursor_color=GREEN,
            selection_color=(0.3, 0.3, 0.6, 0.5),
            size_hint=(None, None),
            width=dp(300),
            height=dp(400),
            padding=[dp(10), dp(10)],
            text=default_code,
            tab_width=4,
            multiline=True,
            do_wrap=False,
            unfocus_on_touch=False
        )

        self.editor.bind(
            text=self.update_numbers
        )

        self.editor.bind(
            cursor=self.follow_cursor
        )

        self.editor.bind(
            focus=self.on_editor_focus
        )

        self.code_area.add_widget(
            self.editor
        )

        self.code_scroll.bind(
            width=self.on_h_width
        )

        self.code_scroll.bind(
            scroll_y=self.sync_gutter
        )

        self.code_scroll.add_widget(
            self.code_area
        )

        code_holder = BoxLayout(
            padding=[dp(8), dp(6), dp(8), dp(6)]
        )

        code_border = GradientBox(
            colors=(
                (0.0, 0.9, 0.55, 0.6),
                (0.48, 0.3, 1, 0.6)
            ),
            radius=12,
            padding=dp(1.5)
        )

        code_inner = RoundBox(
            bg=(0.055, 0.06, 0.095, 1),
            radius=11,
            padding=dp(3)
        )

        self.gutter_scroll = ScrollView(
            size_hint=(None, 1),
            width=dp(43),
            do_scroll_x=False,
            do_scroll_y=False,
            bar_width=0
        )

        self.gutter_scroll.add_widget(
            self.line_label
        )

        code_inner.add_widget(
            self.gutter_scroll
        )

        code_inner.add_widget(
            self.code_scroll
        )

        code_border.add_widget(code_inner)

        code_holder.add_widget(code_border)

        main.add_widget(code_holder)

        # ==================================================
        # STATUS BAR
        # ==================================================

        status = MDBoxLayout(
            size_hint_y=None,
            height=dp(28),
            padding=[dp(10), 0],
            md_bg_color=PANEL
        )

        self.status_text = MDLabel(
            text="JavaScript | Ready",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=GREY
        )

        status.add_widget(
            self.status_text
        )

        status.add_widget(
            MDLabel(
                text="Joscom",
                font_style="Caption",
                theme_text_color="Custom",
                text_color=GREEN,
                halign="right"
            )
        )

        main.add_widget(
            GradientBar(
                size_hint_y=None,
                height=dp(1.5)
            )
        )

        main.add_widget(status)

        # ==================================================
        # ACTION BAR
        # ==================================================

        action_bar = GradientBox(
            colors=(
                (0.07, 0.08, 0.14, 1),
                (0.035, 0.04, 0.075, 1)
            ),
            vertical=True,
            orientation="horizontal",
            size_hint_y=None,
            height=dp(64),
            padding=[dp(8), dp(6)],
            spacing=dp(6)
        )

        def make_action(icon, label, color, callback):

            button = TapBox(
                bg=CARD,
                radius=14,
                orientation="vertical",
                padding=[0, dp(4), 0, dp(3)]
            )

            icon_box = AnchorLayout(
                size_hint_y=0.62
            )

            icon_box.add_widget(
                MDIcon(
                    icon=icon,
                    theme_text_color="Custom",
                    text_color=color,
                    halign="center"
                )
            )

            button.add_widget(icon_box)

            button.add_widget(
                Label(
                    text=label,
                    font_size=dp(10),
                    color=GREY,
                    size_hint_y=0.38
                )
            )

            button.bind(on_release=callback)

            return button

        action_bar.add_widget(
            make_action(
                "folder-outline",
                "Files",
                WHITE,
                lambda x: self.open_files()
            )
        )

        action_bar.add_widget(
            make_action(
                "package-variant-closed",
                "Packages",
                (1, 0.8, 0.3, 1),
                lambda x: self.open_deps()
            )
        )

        action_bar.add_widget(
            make_action(
                "content-save-outline",
                "Save",
                (0.35, 0.65, 1, 1),
                self.save_code
            )
        )

        action_bar.add_widget(
            make_action(
                "eye-outline",
                "Preview",
                (0.72, 0.62, 1, 1),
                lambda x: self.show_preview()
            )
        )

        run_button = GradientButton(
            colors=(GREEN, (0.1, 0.75, 0.95, 1)),
            radius=14,
            orientation="horizontal",
            size_hint_x=1.5,
            padding=[dp(6), 0],
            spacing=dp(2)
        )

        run_icon_box = AnchorLayout(
            size_hint_x=0.4
        )

        run_icon_box.add_widget(
            MDIcon(
                icon="play",
                theme_text_color="Custom",
                text_color=(0.02, 0.07, 0.07, 1),
                halign="center"
            )
        )

        run_button.add_widget(run_icon_box)

        run_button.add_widget(
            Label(
                text="RUN",
                bold=True,
                font_size=dp(15),
                color=(0.02, 0.07, 0.07, 1),
                size_hint_x=0.6
            )
        )

        run_button.bind(on_release=self.run_code)

        action_bar.add_widget(run_button)

        main.add_widget(action_bar)

        root = FloatLayout()

        self.root_box = root

        root.add_widget(main)

        self.editor_screen.add_widget(root)

    # ==================================================
    # SYMBOL INSERTION
    # ==================================================

    def insert_symbol(self, symbol):

        if not self.editor:
            return

        if symbol == "</>":

            self.editor.insert_text("</")

        elif symbol == "{}":

            self.editor.insert_text("{")

        elif symbol == "()":

            self.editor.insert_text("(")

        elif symbol == "[]":

            self.editor.insert_text("[")

        elif symbol == "<>":

            self.editor.insert_text("<")

        else:

            self.editor.insert_text(symbol)

        self.editor.focus = True

    # ==================================================
    # LINE NUMBERS
    # ==================================================

    def follow_cursor(self, instance, value):

        Clock.schedule_once(
            self.move_to_cursor,
            0.15
        )

    def move_to_cursor(self, dt):

        self.scroll_cursor_y()

        self.scroll_cursor_x()

    def sync_gutter(self, instance, value):

        gutter = getattr(self, "gutter_scroll", None)

        if gutter is not None:

            gutter.scroll_y = value

    def on_h_width(self, instance, value):

        self.update_numbers(
            self.editor,
            self.editor.text
        )

    def scroll_cursor_x(self):

        hs = self.code_scroll

        scrollable = self.code_area.width - hs.width

        if scrollable <= 0:
            return

        char_w = self.editor.font_size * 0.6

        left = (
            self.editor.padding[0] +
            self.editor.cursor_col * char_w
        )

        right = left + char_w

        view_left = hs.scroll_x * scrollable

        view_right = view_left + hs.width

        margin = dp(30)

        if left < view_left + margin:
            new_left = left - margin

        elif right > view_right - margin:
            new_left = right + margin - hs.width

        else:
            return

        hs.scroll_x = max(
            0,
            min(1, new_left / scrollable)
        )

    def scroll_cursor_y(self):

        sv = self.code_scroll

        scrollable = self.code_area.height - sv.height

        if scrollable <= 0:
            return

        line_h = (
            self.editor.line_height +
            self.editor.line_spacing
        )

        top = (
            self.editor.padding[1] +
            self.editor.cursor_row * line_h
        )

        bottom = top + line_h

        view_top = (1 - sv.scroll_y) * scrollable

        view_bottom = view_top + sv.height

        if top < view_top:
            new_top = top

        elif bottom > view_bottom:
            new_top = bottom - sv.height

        else:
            return

        sv.scroll_y = max(
            0,
            min(1, 1 - new_top / scrollable)
        )

    def update_initial_numbers(self, dt):

        if self.editor:

            self.update_numbers(
                self.editor,
                self.editor.text
            )

    def update_numbers(self, instance, text):

        lines = text.split("\n")

        count = len(lines)

        self.line_label.text = "\n".join(
            str(i)
            for i in range(1, count + 1)
        )

        # Update height automatically

        new_height = max(
            dp(400),
            count * dp(22) + dp(25)
        )

        self.editor.height = new_height

        self.line_label.height = new_height

        self.line_label.text_size = (
            dp(43),
            new_height
        )

        self.code_area.height = new_height

        longest = max(
            len(line.expandtabs(4))
            for line in lines
        )

        char_w = self.editor.font_size * 0.6

        text_w = (
            longest * char_w +
            self.editor.padding[0] * 2 +
            dp(60)
        )

        self.editor.width = max(
            self.code_scroll.width,
            text_w
        )

        self.code_area.width = self.editor.width

        self.gutter_scroll.scroll_y = self.code_scroll.scroll_y

        self.line_label.texture_update()

        self.status_text.text = (
            f"JavaScript | {count} Lines"
        )

    # ==================================================
    # EDIT BUTTONS
    # ==================================================

    def flash_status(self, text):

        self.status_text.text = text

        Clock.schedule_once(
            lambda dt: setattr(
                self.status_text,
                "text",
                "JavaScript | Ready"
            ),
            2
        )

    def edit_action(self, action):

        editor = self.editor

        if action == "keyboard":

            editor.focus = False

            return

        if action == "select":

            editor.select_all()

            message = "All selected"

        elif action == "copy":

            if editor.selection_text:

                editor.copy()

                message = "Copied"

            else:

                editor.copy(editor.text)

                message = "Copied all code"

        elif action == "cut":

            if editor.selection_text:

                editor.cut()

                message = "Cut"

            else:

                message = "Select some text first"

        elif action == "paste":

            editor.paste()

            message = "Pasted"

        elif action == "undo":

            editor.do_undo()

            message = "Undo"

        else:

            editor.do_redo()

            message = "Redo"

        self.flash_status(message)

    # ==================================================
    # KEYBOARD SPACE
    # ==================================================

    def on_editor_focus(self, instance, focused):

        Clock.unschedule(self.hide_keyboard_space)

        Clock.unschedule(self.apply_keyboard)

        if focused:

            if self.kb_space == 0:

                self.full_height = Window.height

            Clock.schedule_once(
                lambda dt: show_android_keyboard(),
                0.1
            )

            Clock.schedule_once(
                self.apply_keyboard,
                0.2
            )

            Clock.schedule_interval(
                self.apply_keyboard,
                0.5
            )

        else:

            Clock.schedule_once(
                self.hide_keyboard_space,
                0.3
            )

    def hide_keyboard_space(self, dt):

        self.set_keyboard_space(0)

    def apply_keyboard(self, dt):

        if not self.editor.focus:
            return

        height = self.get_keyboard_height()

        if abs(height - self.kb_space) > 2:

            self.set_keyboard_space(height)

    def get_keyboard_height(self):

        if platform != "android":
            return 0

        if Window.height < self.full_height - dp(100):
            return 0

        if Window.keyboard_height > 0:
            return Window.keyboard_height

        native = self.android_keyboard_height()

        if native is not None:

            if native > 0:

                self.native_ok = True

                return native

            if self.native_ok:

                return 0

        return Window.height * KEYBOARD_RATIO

    def android_keyboard_height(self):

        try:

            from jnius import autoclass

            Activity = autoclass(
                "org.kivy.android.PythonActivity"
            )

            decor = (
                Activity.mActivity
                .getWindow()
                .getDecorView()
            )

            version = autoclass(
                "android.os.Build$VERSION"
            ).SDK_INT

            if version >= 30:

                insets = decor.getRootWindowInsets()

                if insets is not None:

                    ime = autoclass(
                        "android.view.WindowInsets$Type"
                    ).ime()

                    return int(
                        insets.getInsets(ime).bottom
                    )

            Rect = autoclass("android.graphics.Rect")

            rect = Rect()

            decor.getWindowVisibleDisplayFrame(rect)

            full = decor.getRootView().getHeight()

            gap = full - rect.bottom

            if gap > full * 0.15:
                return int(gap)

            return 0

        except Exception:

            return None

    def set_keyboard_space(self, height):

        self.kb_space = height

        self.main_box.padding = [0, 0, 0, height]

        Clock.schedule_once(
            self.move_to_cursor,
            0.15
        )

    # ==================================================
    # LOADING SPINNER
    # ==================================================

    def stop_editor_spinner(self, *args):

        if hasattr(self, "editor_spinner"):

            self.editor_spinner.active = False

    # ==================================================
    # INTERNET CONNECTION
    # ==================================================

    def check_connection(self, dt):

        if self.net_busy:
            return

        self.net_busy = True

        def check():

            online = False

            mbps = None

            try:

                request = urllib.request.Request(
                    "https://www.google.com/generate_204",
                    headers={
                        "User-Agent": "JoscomStudio"
                    }
                )

                urllib.request.urlopen(
                    request,
                    timeout=4
                )

                online = True

            except:

                online = False

            if (
                online and
                time.time() - self.last_speed_time >= SPEED_EVERY
            ):

                mbps = self.measure_speed()

                self.last_speed_time = time.time()

            self.net_busy = False

            Clock.schedule_once(
                lambda d: self.set_connection(online, mbps),
                0
            )

        threading.Thread(
            target=check,
            daemon=True
        ).start()

    def measure_speed(self):

        for url in SPEED_URLS:

            try:

                request = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0"
                    }
                )

                response = urllib.request.urlopen(
                    request,
                    timeout=8
                )

                response.read(65536)

                total = 0

                start = time.time()

                while True:

                    chunk = response.read(65536)

                    if not chunk:
                        break

                    total += len(chunk)

                    if time.time() - start > 6:
                        break

                seconds = time.time() - start

                response.close()

                if total > 30000 and seconds > 0:

                    return total * 8 / seconds / 1000000

            except Exception:

                pass

        return None

    def test_speed_now(self, *args):

        if self.net_busy:
            return

        self.last_speed_time = 0

        self.net.text = "Testing"

        self.net.text_color = GREY

        self.net_icon.text_color = GREY

        self.check_connection(0)

    def set_connection(self, online, mbps=None):

        self.connection = online

        if not online:

            self.last_mbps = None

            self.net.text = "Offline"

            self.net.text_color = RED

            self.net_icon.icon = "wifi-off"

            self.net_icon.text_color = RED

            return

        if mbps is not None:

            self.last_mbps = mbps

        mbps = self.last_mbps

        if mbps is None:

            text = "Online"

            color = GREEN

            icon = "wifi"

        else:

            if mbps >= 1:

                text = f"{mbps:.1f} Mbps"

            else:

                text = f"{mbps * 1000:.0f} Kbps"

            if mbps >= 10:

                icon = "wifi-strength-4"

                color = GREEN

            elif mbps >= 5:

                icon = "wifi-strength-3"

                color = GREEN

            elif mbps >= 1:

                icon = "wifi-strength-2"

                color = AMBER

            else:

                icon = "wifi-strength-1"

                color = RED

        self.net.text = text

        self.net.text_color = color

        self.net_icon.icon = icon

        self.net_icon.text_color = color

    # ==================================================
    # SAVE CODE
    # ==================================================

    def get_folder(self):

        folder = "/storage/emulated/0/JoscomApp"

        try:

            os.makedirs(folder, exist_ok=True)

            test = os.path.join(folder, ".joscom_test")

            with open(test, "w") as f:
                f.write("1")

            os.remove(test)

            return folder

        except:

            return self.user_data_dir

    def save_code(self, *args):

        if not self.editor:
            return

        name = os.path.basename(self.file_path)

        try:

            os.makedirs(
                os.path.dirname(self.file_path),
                exist_ok=True
            )

            with open(
                self.file_path,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
                    self.editor.text
                )

        except Exception:

            try:

                os.makedirs(
                    self.user_data_dir,
                    exist_ok=True
                )

                self.file_path = os.path.join(
                    self.user_data_dir,
                    name
                )

                with open(
                    self.file_path,
                    "w",
                    encoding="utf-8"
                ) as f:

                    f.write(
                        self.editor.text
                    )

            except Exception as e:

                self.status_text.text = (
                    "Save failed: " + str(e)
                )

                return

        if self.file_path.startswith("/storage"):
            where = "JoscomApp"
        else:
            where = "app storage"

        self.status_text.text = (
            name + " saved to " + where
        )

        Clock.schedule_once(
            lambda dt: setattr(
                self.status_text,
                "text",
                "JavaScript | Ready"
            ),
            2
        )

    # ==================================================
    # OPEN CODE
    # ==================================================

    def open_code(self, *args):

        if not self.editor:
            return

        try:

            if os.path.exists(self.file_path):

                with open(
                    self.file_path,
                    "r",
                    encoding="utf-8"
                ) as f:

                    self.editor.text = f.read()

                self.status_text.text = (
                    os.path.basename(self.file_path) +
                    " opened"
                )

            else:

                self.status_text.text = (
                    os.path.basename(self.file_path) +
                    " not found"
                )

        except Exception as e:

            self.status_text.text = (
                "Open failed: " + str(e)
            )

    def open_file(self, path, *args):

        try:

            with open(
                path,
                "r",
                encoding="utf-8"
            ) as f:

                text = f.read()

        except Exception as e:

            self.status_text.text = (
                "Open failed: " + str(e)
            )

            return

        self.file_path = path

        self.editor.text = text

        self.tab_label.text = os.path.basename(path)

        self.go_editor()

        self.status_text.text = (
            os.path.basename(path) + " opened"
        )

        Clock.schedule_once(
            lambda dt: setattr(
                self.status_text,
                "text",
                "JavaScript | Ready"
            ),
            2
        )

    def new_file(self, *args):

        folder = self.get_folder()

        number = 1

        while os.path.exists(
            os.path.join(
                folder,
                "Project" + str(number) + ".js"
            )
        ):

            number += 1

        self.file_path = os.path.join(
            folder,
            "Project" + str(number) + ".js"
        )

        self.editor.text = (
            "function App() {\n"
            "  return (\n"
            "    <View style={{flex:1, padding:20}}>\n"
            "      <Text>Hello Joscom</Text>\n"
            "    </View>\n"
            "  );\n"
            "}"
        )

        self.tab_label.text = os.path.basename(
            self.file_path
        )

        self.save_code()

        self.go_editor()

    # ==================================================
    # PREVIEW
    # ==================================================

    def show_preview(self):

        if not self.editor:
            return

        self.editor.focus = False

        self.editor_spinner.active = True

        self.status_text.text = (
            "Preparing preview..."
        )

        self.save_code()

        self.preview.loading.text = (
            "Loading React preview..."
        )

        self.preview.load(
            self.editor.text
        )

    def run_code(self, *args):

        if not self.editor:
            return

        self.save_code()

        self.show_preview()

    # ==================================================
    # FILES SCREEN
    # ==================================================

    # ==================================================
    # PACKAGES (DEPENDENCIES) SCREEN
    # ==================================================

    def load_deps(self):

        try:

            with open(
                self.deps_path,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

            result = []

            for item in data:

                if isinstance(item, dict) and item.get("name"):

                    item.setdefault("version", "")

                    result.append(item)

            return result

        except Exception:

            return []

    def save_deps(self):

        try:

            with open(
                self.deps_path,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(self.deps, f)

        except Exception:

            try:

                self.deps_path = os.path.join(
                    self.user_data_dir,
                    "dependencies.json"
                )

                with open(
                    self.deps_path,
                    "w",
                    encoding="utf-8"
                ) as f:

                    json.dump(self.deps, f)

            except Exception:

                pass

    def open_deps(self):

        self.editor.focus = False

        self.refresh_deps()

        self.sm.current = "deps"

    def build_deps(self):

        main = MDBoxLayout(
            orientation="vertical",
            md_bg_color=BG
        )

        top = GradientBox(
            colors=(
                (0.13, 0.09, 0.27, 1),
                (0.03, 0.07, 0.11, 1)
            ),
            orientation="horizontal",
            size_hint_y=None,
            height=dp(64),
            padding=dp(8),
            spacing=dp(6)
        )

        back = MDIconButton(
            icon="arrow-left",
            theme_text_color="Custom",
            text_color=WHITE
        )

        back.bind(
            on_release=lambda x: self.go_editor()
        )

        top.add_widget(back)

        titles = MDBoxLayout(
            orientation="vertical",
            spacing=0
        )

        titles.add_widget(
            MDLabel(
                text="Packages",
                bold=True,
                font_style="Subtitle1",
                theme_text_color="Custom",
                text_color=WHITE
            )
        )

        titles.add_widget(
            MDLabel(
                text="Added here, loaded from the internet",
                font_style="Caption",
                theme_text_color="Custom",
                text_color=GREY
            )
        )

        top.add_widget(titles)

        main.add_widget(top)

        main.add_widget(
            GradientBar(
                size_hint_y=None,
                height=dp(2)
            )
        )

        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(66),
            padding=[dp(12), dp(10)],
            spacing=dp(8)
        )

        input_box = RoundBox(
            bg=CARD,
            radius=12,
            padding=[dp(4), 0]
        )

        self.dep_input = TextInput(
            hint_text="package name, like lodash or dayjs@1.11.10",
            multiline=False,
            write_tab=False,
            background_normal="",
            background_active="",
            background_color=(0, 0, 0, 0),
            foreground_color=WHITE,
            hint_text_color=GREY,
            cursor_color=GREEN,
            padding=[dp(10), dp(13), dp(10), dp(10)],
            font_size=dp(14)
        )

        self.dep_input.bind(
            on_text_validate=lambda x: self.add_dependency()
        )

        input_box.add_widget(self.dep_input)

        row.add_widget(input_box)

        add_button = GradientButton(
            colors=(GREEN, PURPLE),
            radius=12,
            size_hint=(None, 1),
            width=dp(72)
        )

        add_button.add_widget(
            Label(
                text="ADD",
                bold=True,
                font_size=dp(14),
                color=(0.02, 0.07, 0.07, 1)
            )
        )

        add_button.bind(
            on_release=lambda x: self.add_dependency()
        )

        row.add_widget(add_button)

        main.add_widget(row)

        self.dep_status = Label(
            text="Type a package name and tap ADD.",
            color=GREY,
            font_size=dp(12),
            size_hint_y=None,
            height=dp(26),
            halign="left",
            padding_x=dp(14)
        )

        self.dep_status.bind(
            width=lambda i, w: setattr(i, "text_size", (w, None))
        )

        main.add_widget(self.dep_status)

        scroll = ScrollView(
            do_scroll_x=False,
            bar_width=dp(3),
            bar_color=GREEN
        )

        self.deps_list = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=dp(15),
            spacing=dp(10)
        )

        self.deps_list.bind(
            minimum_height=self.deps_list.setter("height")
        )

        scroll.add_widget(self.deps_list)

        main.add_widget(scroll)

        self.deps_screen.add_widget(main)

    def refresh_deps(self):

        self.deps_list.clear_widgets()

        if not self.deps:

            self.deps_list.add_widget(
                MDLabel(
                    text="No packages added yet.",
                    halign="center",
                    size_hint_y=None,
                    height=dp(50),
                    theme_text_color="Custom",
                    text_color=GREY
                )
            )

        for dep in self.deps:

            self.deps_list.add_widget(
                self.make_dep_row(dep)
            )

        card = RoundBox(
            bg=CARD,
            radius=14,
            size_hint_y=None,
            padding=dp(12)
        )

        info = Label(
            text=(
                "Already included, no need to add: react, "
                "react-native, expo-linear-gradient, expo-video, "
                "expo-av, expo-image-picker, expo-document-picker, "
                "expo-status-bar, expo-font, expo-constants, "
                "expo-haptics, expo-blur, expo-splash-screen, expo, "
                "@expo/vector-icons, react-native-vector-icons, "
                "@react-native-async-storage/async-storage, "
                "react-native-safe-area-context.\n\n"
                "Any other package you add here loads from the "
                "internet when you press Run."
            ),
            color=GREY,
            font_size=dp(12),
            size_hint_y=None,
            halign="left",
            valign="top"
        )

        info.bind(
            width=lambda i, w: setattr(i, "text_size", (w, None))
        )

        info.bind(
            texture_size=lambda i, size: setattr(i, "height", size[1])
        )

        info.bind(
            height=lambda i, h: setattr(card, "height", h + dp(24))
        )

        card.add_widget(info)

        self.deps_list.add_widget(card)

    def make_dep_row(self, dep):

        row = RoundBox(
            bg=CARD,
            radius=14,
            orientation="horizontal",
            size_hint_y=None,
            height=dp(66),
            padding=[dp(8), dp(4)],
            spacing=dp(6)
        )

        icon = MDIconButton(
            icon="package-variant-closed",
            theme_text_color="Custom",
            text_color=(1, 0.8, 0.3, 1)
        )

        texts = MDBoxLayout(
            orientation="vertical",
            spacing=0
        )

        texts.add_widget(
            MDLabel(
                text=dep["name"],
                bold=True,
                theme_text_color="Custom",
                text_color=WHITE
            )
        )

        texts.add_widget(
            MDLabel(
                text="version " + str(dep.get("version", "")),
                font_style="Caption",
                theme_text_color="Custom",
                text_color=GREY
            )
        )

        remove = MDIconButton(
            icon="delete-outline",
            theme_text_color="Custom",
            text_color=RED
        )

        remove.bind(
            on_release=lambda x, n=dep["name"]: self.remove_dependency(n)
        )

        row.add_widget(icon)

        row.add_widget(texts)

        row.add_widget(remove)

        return row

    def dep_message(self, text, color=GREY):

        self.dep_status.text = text

        self.dep_status.color = color

    def add_dependency(self, *args):

        text = self.dep_input.text.strip()

        if not text:
            return

        if text.startswith("@"):

            name_part, sep, version = text[1:].partition("@")

            name = "@" + name_part

        else:

            name, sep, version = text.partition("@")

        name = name.lower()

        name_ok = re.match(
            r"^(@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*$",
            name
        )

        version_ok = (
            not version or
            re.match(r"^[A-Za-z0-9._-]+$", version)
        )

        if not name_ok or not version_ok:

            self.dep_message(
                "That does not look right. Example: lodash or dayjs@1.11.10",
                RED
            )

            return

        self.dep_message(
            "Checking " + name + " on npm...",
            AMBER
        )

        def work():

            wanted = version or "latest"

            url = (
                "https://registry.npmjs.org/" +
                name.replace("/", "%2F") + "/" +
                urllib.parse.quote(wanted)
            )

            try:

                request = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "JoscomStudio",
                        "Accept": "application/json"
                    }
                )

                data = json.loads(
                    urllib.request.urlopen(
                        request,
                        timeout=12
                    ).read().decode("utf-8")
                )

                resolved = data.get("version") or wanted

                Clock.schedule_once(
                    lambda dt: self.dep_added(name, resolved),
                    0
                )

            except urllib.error.HTTPError as error:

                if error.code == 404:

                    message = (
                        "Not found on npm: " + name +
                        ("@" + version if version else "")
                    )

                else:

                    message = "npm error " + str(error.code)

                Clock.schedule_once(
                    lambda dt: self.dep_message(message, RED),
                    0
                )

            except Exception:

                Clock.schedule_once(
                    lambda dt: self.dep_message(
                        "No internet. Could not check the package.",
                        RED
                    ),
                    0
                )

        threading.Thread(
            target=work,
            daemon=True
        ).start()

    def dep_added(self, name, version):

        self.deps = [
            d for d in self.deps if d["name"] != name
        ]

        self.deps.append(
            {"name": name, "version": version}
        )

        self.save_deps()

        self.dep_input.text = ""

        self.refresh_deps()

        self.dep_message(
            "Added " + name + "@" + version +
            ". It loads from the internet when you press Run.",
            GREEN
        )

    def remove_dependency(self, name):

        self.deps = [
            d for d in self.deps if d["name"] != name
        ]

        self.save_deps()

        self.refresh_deps()

        self.dep_message("Removed " + name)

    def build_files(self):

        main = MDBoxLayout(
            orientation="vertical",
            md_bg_color=BG
        )

        top = GradientBox(
            colors=(
                (0.13, 0.09, 0.27, 1),
                (0.03, 0.07, 0.11, 1)
            ),
            orientation="horizontal",
            size_hint_y=None,
            height=dp(64),
            padding=dp(8)
        )

        back = MDIconButton(
            icon="arrow-left",
            theme_text_color="Custom",
            text_color=WHITE
        )

        back.bind(
            on_release=lambda x: self.go_editor()
        )

        top.add_widget(back)

        top.add_widget(
            MDLabel(
                text="Project Files",
                bold=True,
                theme_text_color="Custom",
                text_color=WHITE
            )
        )

        main.add_widget(top)

        main.add_widget(
            GradientBar(
                size_hint_y=None,
                height=dp(2)
            )
        )

        scroll = ScrollView(
            do_scroll_x=False,
            bar_width=dp(3),
            bar_color=GREEN
        )

        self.files_list = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=dp(15),
            spacing=dp(10)
        )

        self.files_list.bind(
            minimum_height=self.files_list.setter("height")
        )

        scroll.add_widget(self.files_list)

        main.add_widget(scroll)

        root = FloatLayout()

        root.add_widget(main)

        fab_new = MDFloatingActionButton(
            icon="plus",
            md_bg_color=GREEN,
            icon_color=(0.02, 0.08, 0.07, 1),
            size_hint=(None, None),
            size=(dp(58), dp(58)),
            pos_hint={"right": 0.95, "y": 0.035},
            elevation=8
        )

        fab_new.bind(
            on_release=self.new_file
        )

        root.add_widget(fab_new)

        self.files_screen.add_widget(root)

    def refresh_files(self):

        self.files_list.clear_widgets()

        folders = [
            "/storage/emulated/0/JoscomApp",
            self.user_data_dir
        ]

        items = []

        seen = set()

        for folder in folders:

            try:

                for name in os.listdir(folder):

                    if not name.lower().endswith(
                        (".js", ".jsx")
                    ):
                        continue

                    path = os.path.join(folder, name)

                    if path in seen:
                        continue

                    if not os.path.isfile(path):
                        continue

                    seen.add(path)

                    items.append(
                        (os.path.getmtime(path), path)
                    )

            except Exception:

                pass

        items.sort(reverse=True)

        if not items:

            self.files_list.add_widget(
                MDLabel(
                    text="No saved files yet. Tap + to make one.",
                    halign="center",
                    size_hint_y=None,
                    height=dp(60),
                    theme_text_color="Custom",
                    text_color=GREY
                )
            )

        for modified, path in items:

            self.files_list.add_widget(
                self.make_file_row(path, modified)
            )

    def make_file_row(self, path, modified):

        name = os.path.basename(path)

        size = os.path.getsize(path) / 1024

        when = time.strftime(
            "%d %b %Y  %H:%M",
            time.localtime(modified)
        )

        if path == self.file_path:
            name_color = GREEN
        else:
            name_color = WHITE

        row = TapBox(
            bg=CARD,
            radius=14,
            orientation="horizontal",
            size_hint_y=None,
            height=dp(68),
            padding=[dp(8), dp(4)],
            spacing=dp(6)
        )

        icon = MDIconButton(
            icon="language-javascript",
            theme_text_color="Custom",
            text_color=(1, 0.8, 0.2, 1)
        )

        texts = MDBoxLayout(
            orientation="vertical",
            spacing=0
        )

        texts.add_widget(
            MDLabel(
                text=name,
                bold=True,
                theme_text_color="Custom",
                text_color=name_color
            )
        )

        texts.add_widget(
            MDLabel(
                text=f"{size:.1f} KB   |   {when}",
                font_style="Caption",
                theme_text_color="Custom",
                text_color=GREY
            )
        )

        open_button = MDIconButton(
            icon="folder-open",
            theme_text_color="Custom",
            text_color=GREEN
        )

        icon.bind(
            on_release=lambda x, p=path: self.open_file(p)
        )

        open_button.bind(
            on_release=lambda x, p=path: self.open_file(p)
        )

        row.bind(
            on_release=lambda x, p=path: self.open_file(p)
        )

        row.add_widget(icon)

        row.add_widget(texts)

        row.add_widget(open_button)

        return row

    def open_files(self):

        self.editor.focus = False

        self.refresh_files()

        self.sm.current = "files"

    # ==================================================
    # NAVIGATION
    # ==================================================

    def go_editor(self, *args):

        self.preview.close_preview()

        self.sm.current = "editor"

        Animation(
            opacity=1,
            duration=0.2
        ).start(self.editor_screen)

    def on_back(self, window, key, *args):

        # Android Back button

        if key in (27, 1001):

            if self.preview.dialog:

                self.preview.close_preview()

                return True

            if self.sm.current in ("files", "deps"):

                self.go_editor()

                return True

            if self.sm.current == "preview":

                self.go_editor()

                return True

        # Volume buttons
        # Android key 24 = Volume Up
        # Android key 25 = Volume Down

        if key in (24, 25):

            if self.preview.dialog:

                self.preview.close_preview()

                return True

        return False

    # ==================================================
    # APPLICATION LIFECYCLE
    # ==================================================

    def lib_url(self, name, url):

        path = os.path.join(self.libs_dir, name)

        try:

            if (
                os.path.exists(path) and
                os.path.getsize(path) > 10000
            ):

                return "file://" + path

        except Exception:

            pass

        return url

    def download_libs(self):

        def work():

            try:

                os.makedirs(
                    self.libs_dir,
                    exist_ok=True
                )

            except Exception:

                return

            for name, url in LIBS.items():

                path = os.path.join(self.libs_dir, name)

                try:

                    if (
                        os.path.exists(path) and
                        os.path.getsize(path) > 10000
                    ):
                        continue

                    request = urllib.request.Request(
                        url,
                        headers={
                            "User-Agent": "Mozilla/5.0"
                        }
                    )

                    data = urllib.request.urlopen(
                        request,
                        timeout=40
                    ).read()

                    if len(data) > 10000:

                        with open(path + ".tmp", "wb") as f:

                            f.write(data)

                        os.replace(path + ".tmp", path)

                except Exception:

                    pass

        threading.Thread(
            target=work,
            daemon=True
        ).start()

    def on_start(self):

        Clock.schedule_once(
            lambda dt: self.download_libs(),
            3
        )

        if platform == "android":

            try:

                from android.permissions import (
                    request_permissions,
                    Permission
                )

                request_permissions([
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.WRITE_EXTERNAL_STORAGE
                ])

            except Exception:

                pass

    def on_pause(self):

        return True

    def on_stop(self):

        try:

            self.preview.close_preview()

        except:

            pass


# ==================================================
# START APPLICATION
# ==================================================

JoscomFinal().run()
