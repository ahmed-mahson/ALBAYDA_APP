from pathlib import Path
import subprocess

p = Path('android/app/src/main/java/ai/teable/albayda/court/preview/MainActivity.java')
assert subprocess.check_output(['git', 'hash-object', str(p)], text=True).strip() == '42930471a216fd19e451938e347c24099b66bbda', 'Source changed; review before applying'
s = p.read_text()
changes = [
    ('        enterFullscreen();\n        final LinearLayout linearLayout = new LinearLayout(this);', '        final LinearLayout linearLayout = new LinearLayout(this);'),
    ('        setContentView(linearLayout);', '        setContentView(linearLayout);\n        linearLayout.post(this::enterFullscreen);'),
    ('        if (Build.VERSION.SDK_INT >= 30) {\n            WindowInsetsController insetsController = getWindow().getInsetsController();', "        // getDecorView initializes PhoneWindow's decor; getInsetsController alone does not.\n        View decor = getWindow().getDecorView();\n        if (Build.VERSION.SDK_INT >= 30) {\n            WindowInsetsController insetsController = decor.getWindowInsetsController();"),
    ('        getWindow().getDecorView().setSystemUiVisibility(4358);', '        decor.setSystemUiVisibility(4358);'),
]
for old, new in changes:
    assert s.count(old) == 1
    s = s.replace(old, new)
g = Path('android/app/build.gradle')
t = g.read_text()
old = "        versionCode 4\n        versionName '1.3.0'"
assert t.count(old) == 1
p.write_text(s)
g.write_text(t.replace(old, "        versionCode 5\n        versionName '1.3.1'"))
