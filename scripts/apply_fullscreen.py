from pathlib import Path
p = Path('android/app/src/main/java/ai/teable/albayda/court/preview/MainActivity.java')
s = p.read_text()
old = '''        Button configure = new Button(this);
        configure.setText("إعداد رابط الخادم");
        configure.setOnClickListener(v -> showError("أدخل رابط HTTPS للخادم."));
        linearLayout.addView(configure);
'''
assert s.count(old) == 1, 'Review changed source before patching'
g = Path('android/app/build.gradle')
t = g.read_text()
version = "        versionCode 5\n        versionName '1.3.1'"
assert t.count(version) == 1, 'Unexpected application version'
p.write_text(s.replace(old, ''))
g.write_text(t.replace(version, "        versionCode 6\n        versionName '1.3.2'"))
