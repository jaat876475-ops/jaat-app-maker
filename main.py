from flask import Flask, request, render_template_string, send_file
from io import BytesIO
from html import escape
import secrets

app = Flask(__name__)
GENERATED_FILES = {}

PAGE = r"""
<!doctype html>
<html lang="hi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Jaat App Maker</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0c1224;color:#f4f6ff;font-family:Arial,sans-serif}
main{max-width:850px;margin:auto;padding:20px 14px}
.panel{background:#151e35;border:1px solid #2b3959;border-radius:16px;padding:18px;margin:16px 0}
h1 span{color:#67e8c5}
label{display:block;margin:12px 0 6px;font-weight:bold}
input,textarea,select{width:100%;padding:12px;border-radius:9px;border:1px solid #354666;background:#0c1429;color:white;font:inherit}
textarea{min-height:110px}
button,.download{padding:12px 14px;border:0;border-radius:9px;cursor:pointer;font-weight:bold;text-decoration:none;display:inline-block}
.primary{background:#67e8c5;color:#071a18;width:100%;margin-top:14px}
.chip{background:#263452;color:white;margin:5px 4px 0 0}
.download{background:#67e8c5;color:#071a18}
.preview{background:#fff;color:#18233b;padding:16px;border-radius:12px}
.small{font-size:12px;color:#b6c2dc}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#090f1f;color:#dce8ff;padding:12px;border-radius:9px;max-height:300px;overflow:auto}
</style>
</head>
<body>
<main>
<div><b>🟩 Jaat App Maker</b><h1>हिंदी निर्देश से <span>ऐप बनाएँ</span></h1>
<p class="small">अपना ऐप विचार लिखें। उपलब्ध प्रकारों के अनुसार एक चलने वाला HTML ऐप तैयार होगा।</p></div>
<section class="panel">
<form method="post">
<label>भाषा / Language</label>
<select name="language">
<option value="hi" {% if language == 'hi' %}selected{% endif %}>हिंदी</option>
<option value="en" {% if language == 'en' %}selected{% endif %}>English</option>
</select>
<label>ऐप का नाम</label>
<input name="app_name" maxlength="60" value="{{ app_name }}" required>
<label>ऐप का विचार / निर्देश</label>
<textarea id="idea" name="idea" maxlength="2000" required>{{ idea }}</textarea>
<button class="chip" type="button" onclick="document.getElementById('idea').value='एक ऑनलाइन दुकान बनाओ जिसमें सामान, कीमत और कार्ट में जोड़ने का बटन हो।'">दुकान</button>
<button class="chip" type="button" onclick="document.getElementById('idea').value='एक स्कूल ऐप बनाओ जिसमें विद्यार्थी और कक्षा जोड़ी जा सके।'">स्कूल</button>
<button class="chip" type="button" onclick="document.getElementById('idea').value='एक कैलकुलेटर बनाओ जो जोड़ घटाव गुणा भाग करे।'">कैलकुलेटर</button>
<button class="chip" type="button" onclick="document.getElementById('idea').value='एक टास्क लिस्ट बनाओ जिसमें काम जोड़ सकूँ और टिक कर सकूँ।'">टास्क लिस्ट</button>
<button class="chip" type="button" onclick="document.getElementById('idea').value='एक नोट्स ऐप बनाओ जिसमें नोट लिख सकूँ।'">नोट्स</button>
<button class="chip" type="button" onclick="document.getElementById('idea').value='एक काउंटर बनाओ जिसमें संख्या बढ़ा और घटा सकूँ।'">काउंटर</button>
<button class="primary" type="submit">✦ ऐप बनाएँ</button>
</form>
<p class="small">यह संस्करण बिना API key के नियम-आधारित है; अभी AI सेवा कनेक्ट नहीं है।</p>
</section>
{% if generated %}
<section class="panel">
<h2>ऐप प्रीव्यू</h2>
<div class="preview"><h2>{{ title }}</h2><p>{{ description }}</p><p>ऐप का प्रकार: <b>{{ kind }}</b></p><p>पूरा इंटरैक्टिव ऐप डाउनलोड की गई HTML फ़ाइल में चलेगा।</p></div>
<p><a class="download" href="/download/{{ token }}">HTML डाउनलोड करें</a></p>
<h3>HTML कोड</h3><pre>{{ generated }}</pre>
</section>
{% endif %}
</main>
</body>
</html>
"""

def detect_kind(idea):
    """सबसे विशिष्ट संकेत पहले जाँचें, ताकि टास्क लिस्ट को कैलकुलेटर न समझे।"""
    s = idea.casefold()
    rules = [
        ("shop", ["दुकान", "सामान", "खरीदारी", "कार्ट", "कीमत", "ऑनलाइन स्टोर", "online shop", "online store", "shopping cart", "cart", "products", "product"]),
        ("school", ["स्कूल", "विद्यार्थी", "छात्र", "कक्षा", "school", "student", "classroom"]),
        ("todo", ["टास्क लिस्ट", "काम की सूची", "काम जोड़", "कार्य सूची", "todo", "to-do", "task list", "tasks", "checklist"]),
        ("notes", ["नोट्स", "नोट लिख", "notes", "notepad", "memo"]),
        ("calculator", ["कैलकुलेटर", "गणना", "जोड़ घटाव", "गुणा भाग", "calculator", "calculate"]),
        ("counter", ["काउंटर", "गिनती", "counter", "count"])
    ]
    for kind, terms in rules:
        if any(term in s for term in terms):
            return kind
    return "general"

def build_app(app_name, idea, language):
    kind = detect_kind(idea)
    safe_name = escape(app_name)
    safe_idea = escape(idea)
    titles = {
        "shop": "ऑनलाइन दुकान",
        "school": "स्कूल डैशबोर्ड",
        "todo": "मेरी टास्क लिस्ट",
        "notes": "मेरे नोट्स",
        "calculator": "कैलकुलेटर",
        "counter": "गिनती काउंटर",
        "general": app_name
    }
    title = escape(titles[kind])
    css = """
    body{font-family:Arial,sans-serif;max-width:850px;margin:20px auto;padding:16px;background:#f2f5fb;color:#172033}
    main{background:white;padding:20px;border-radius:15px;border:1px solid #dde3ee}
    button,input,textarea{font:inherit;padding:10px;border-radius:8px;border:1px solid #d0d8e8;margin:4px}
    button{background:#4f65e9;color:white;cursor:pointer}
    .card{padding:12px;border:1px solid #e0e5ef;border-radius:10px;margin:10px 0}
    .row{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}
    """
    if kind == "shop":
        body = """
        <h2>हमारी ऑनलाइन दुकान में आपका स्वागत है</h2>
        <div class="row">
          <div class="card"><h3>शानदार स्मार्टफोन</h3><p>कीमत: ₹15,000</p><button onclick="addToCart('शानदार स्मार्टफोन',15000)">कार्ट में जोड़ें</button></div>
          <div class="card"><h3>वायरलेस हेडफ़ोन</h3><p>कीमत: ₹2,500</p><button onclick="addToCart('वायरलेस हेडफ़ोन',2500)">कार्ट में जोड़ें</button></div>
          <div class="card"><h3>फिटनेस स्मार्टवॉच</h3><p>कीमत: ₹4,000</p><button onclick="addToCart('फिटनेस स्मार्टवॉच',4000)">कार्ट में जोड़ें</button></div>
        </div>
        <h2>आपकी कार्ट 🛒</h2><div id="cart-items">कार्ट अभी खाली है।</div>
        <h3>कुल कीमत: ₹<span id="cart-total">0</span></h3>
        <script>
        const cart = [];
        function addToCart(name, price) {
          const item = cart.find(x => x.name === name);
          if (item) item.quantity += 1;
          else cart.push({name:name, price:price, quantity:1});
          updateCart();
        }
        function updateCart() {
          const box = document.getElementById('cart-items');
          box.replaceChildren();
          let total = 0;
          cart.forEach(item => {
            const row = document.createElement('p');
            const amount = item.price * item.quantity;
            total += amount;
            row.textContent = item.name + ' (x' + item.quantity + ') — ₹' + amount.toLocaleString('en-IN');
            box.appendChild(row);
          });
          if (!cart.length) box.textContent = 'कार्ट अभी खाली है।';
          document.getElementById('cart-total').textContent = total.toLocaleString('en-IN');
        }
        </script>
        """
    elif kind == "todo":
        body = """
        <h2>काम जोड़ें</h2><div class="row"><input id="task" placeholder="नया काम"><button onclick="addTask()">जोड़ें</button></div><ul id="tasks"></ul>
        <script>
        function addTask(){
          const input=document.getElementById('task'), value=input.value.trim();
          if(!value)return;
          const li=document.createElement('li'), cb=document.createElement('input'), text=document.createElement('span'), del=document.createElement('button');
          cb.type='checkbox'; text.textContent=value; del.textContent='हटाएँ';
          cb.onchange=()=>text.style.textDecoration=cb.checked?'line-through':'none';
          del.onclick=()=>li.remove(); li.append(cb,text,del); document.getElementById('tasks').append(li); input.value='';
        }
        </script>
        """
    elif kind == "calculator":
        body = """
        <h2>कैलकुलेटर</h2><div class="row"><input id="a" type="number" placeholder="पहली संख्या"><input id="b" type="number" placeholder="दूसरी संख्या"></div>
        <div class="row"><button onclick="calc('+')">+</button><button onclick="calc('-')">−</button><button onclick="calc('*')">×</button><button onclick="calc('/')">÷</button></div><p id="result">परिणाम यहाँ दिखेगा</p>
        <script>
        function calc(op){
          const a=Number(document.getElementById('a').value), b=Number(document.getElementById('b').value);
          let result;
          if(op==='/' && b===0) result='शून्य से भाग नहीं कर सकते';
          else result=op==='+'?a+b:op==='-'?a-b:op==='*'?a*b:a/b;
          document.getElementById('result').textContent='परिणाम: '+result;
        }
        </script>
        """
    elif kind == "notes":
        body = """
        <h2>नोट लिखें</h2><textarea id="note" placeholder="अपना नोट" style="width:95%;min-height:90px"></textarea><p><button onclick="saveNote()">नोट जोड़ें</button></p><div id="notes"></div>
        <script>
        function saveNote(){const input=document.getElementById('note'), value=input.value.trim();if(!value)return;const card=document.createElement('div');card.className='card';card.textContent=value;document.getElementById('notes').prepend(card);input.value='';}
        </script>
        """
    elif kind == "counter":
        body = """
        <h2 id="number">0</h2><button onclick="change(-1)">−</button><button onclick="change(1)">+</button><button onclick="change(0,true)">रीसेट</button>
        <script>let count=0;function change(n,reset){count=reset?0:count+n;document.getElementById('number').textContent=count;}</script>
        """
    elif kind == "school":
        body = """
        <h2>विद्यार्थी जोड़ें</h2><div class="row"><input id="student" placeholder="विद्यार्थी का नाम"><input id="grade" placeholder="कक्षा"><button onclick="addStudent()">जोड़ें</button></div><ul id="students"></ul>
        <script>
        function addStudent(){const n=document.getElementById('student'),g=document.getElementById('grade');if(!n.value.trim())return;const li=document.createElement('li');li.textContent=n.value+' — कक्षा '+g.value;document.getElementById('students').append(li);n.value='';g.value='';}
        </script>
        """
    else:
        body = "<p>यह ऐप आपके दिए गए निर्देश के लिए शुरुआती पेज है:</p><div class='card'>" + safe_idea + "</div><p>अभी समर्थित प्रकार: दुकान, स्कूल, टास्क लिस्ट, नोट्स, कैलकुलेटर और काउंटर।</p>"

    html = (
        '<!doctype html><html lang="' + ('hi' if language == 'hi' else 'en') + '"><head>'
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>' + safe_name + '</title><style>' + css + '</style></head><body><main>'
        '<h1>' + title + '</h1><p>आपके ऐप में स्वागत है!</p><p><b>आपका निर्देश:</b> ' + safe_idea + '</p>'
        + body + '<hr><small>Jaat App Maker से बनाया गया</small></main></body></html>'
    )
    return kind, titles[kind], html

@app.route("/", methods=["GET", "POST"])
def home():
    language = "hi"
    app_name = "मेरी दुकान"
    idea = "एक ऑनलाइन दुकान बनाओ जिसमें सामान, कीमत और कार्ट में जोड़ने का बटन हो।"
    generated = ""
    kind = ""
    title = ""
    token = ""
    if request.method == "POST":
        language = request.form.get("language", "hi")
        if language not in ("hi", "en"):
            language = "hi"
        app_name = request.form.get("app_name", "मेरा ऐप").strip()[:60] or "मेरा ऐप"
        idea = request.form.get("idea", "").strip()[:2000] or "एक सरल ऐप बनाओ।"
        kind, title, generated = build_app(app_name, idea, language)
        token = secrets.token_urlsafe(12)
        GENERATED_FILES[token] = generated
    return render_template_string(
        PAGE, language=language, app_name=app_name, idea=idea,
        generated=generated, kind=kind, title=title,
        description=idea, token=token
    )

@app.route("/download/<token>")
def download(token):
    content = GENERATED_FILES.get(token)
    if content is None:
        return "डाउनलोड लिंक उपलब्ध नहीं है। कृपया ऐप फिर से बनाएँ।", 404
    return send_file(
        BytesIO(content.encode("utf-8")),
        mimetype="text/html",
        as_attachment=True,
        download_name="jaat_generated_app.html"
    )

if __name__ == "__main__":
    print("Jaat App Maker चालू है: http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
