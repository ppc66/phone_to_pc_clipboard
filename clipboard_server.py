# -*- coding: utf-8 -*-
import os
import sys
import socket
import json
import threading
import webbrowser
from datetime import datetime

try:
    from flask import Flask, request, jsonify, render_template_string, send_file, make_response
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

PORT = 8080

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

@app.route("/", methods=["OPTIONS"])
@app.route("/clipboard", methods=["OPTIONS"])
@app.route("/upload", methods=["OPTIONS"])
@app.route("/files", methods=["OPTIONS"])
@app.route("/files/delete/<path:filename>", methods=["OPTIONS"])
def handle_options():
    return "", 204

CLIPBOARD_HISTORY = []
MAX_HISTORY = 50
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "clipboard_history.json")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
MAX_FILE_SIZE = 10 * 1024 * 1024

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def get_all_local_ips():
    ips = []
    hostname = socket.gethostname()
    try:
        addresses = socket.getaddrinfo(hostname, None, socket.AF_INET)
        for addr in addresses:
            ip = addr[4][0]
            if ip != "127.0.0.1" and ip not in ips:
                ips.append(ip)
    except:
        pass
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        main_ip = s.getsockname()[0]
        if main_ip not in ips:
            ips.insert(0, main_ip)
    except:
        pass
    finally:
        s.close()
    return ips

def generate_qr_code(url):
    if not HAS_QRCODE:
        return None
    try:
        qr = qrcode.QRCode(version=1, box_size=8, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        import io
        buf = io.BytesIO()
        img.save(buf)
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"[QR] 生成失败: {e}")
        return None

def save_history():
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(CLIPBOARD_HISTORY, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[History] 保存失败: {e}")

def load_history():
    global CLIPBOARD_HISTORY
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                CLIPBOARD_HISTORY = json.load(f)
            print(f"[History] 已加载 {len(CLIPBOARD_HISTORY)} 条历史记录")
        except Exception as e:
            print(f"[History] 加载失败: {e}")
            CLIPBOARD_HISTORY = []

def add_to_history(content):
    global CLIPBOARD_HISTORY
    item = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "content": content[:200] + "..." if len(content) > 200 else content
    }
    CLIPBOARD_HISTORY.insert(0, item)
    if len(CLIPBOARD_HISTORY) > MAX_HISTORY:
        CLIPBOARD_HISTORY.pop()
    save_history()

@app.route("/")
def index():
    local_ip = get_local_ip()
    service_url = f"http://{local_ip}:{PORT}"
    response = render_template_string(INDEX_HTML, 
                                  ip=local_ip, 
                                  port=PORT, 
                                  url=service_url)
    resp = make_response(response)
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route("/test", methods=["GET", "POST"])
def test_page():
    if request.method == "POST":
        content = request.data.decode("utf-8") if request.data else request.form.get("content", "")
        print(f"[DEBUG] POST 请求收到: {len(content)} 字符")
        if content:
            if HAS_PYPERCLIP:
                pyperclip.copy(content)
                add_to_history(content)
                return f"<html><body><h2>发送成功！</h2><p>内容已写入 Windows 剪贴板</p><p><a href='/test'>返回测试</a></p></body></html>"
            else:
                add_to_history(content)
                return f"<html><body><h2>接收成功！</h2><p>（未安装 pyperclip）</p><p><a href='/test'>返回测试</a></p></body></html>"
        return f"<html><body><h2>内容为空</h2><p><a href='/test'>返回测试</a></p></body></html>"
    return """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>测试页面</title>
<style>
body{font-family:sans-serif;padding:20px;max-width:400px;margin:0 auto}
textarea{width:100%;height:100px;padding:10px;margin:10px 0}
button{width:100%;padding:15px;font-size:16px;background:#667eea;color:white;border:none;border-radius:8px;cursor:pointer}
</style>
</head>
<body>
<h2>测试发送</h2>
<form action="/test" method="POST">
<textarea name="content" placeholder="输入内容..."></textarea>
<button type="submit">发送到电脑</button>
</form>
<p style="color:#666;font-size:12px;">这是一个纯表单测试，不使用 JavaScript</p>
</body>
</html>"""

@app.route("/qr")
def qr_code():
    qr_path = os.path.join(os.path.dirname(__file__), "service_qr.png")
    if os.path.exists(qr_path):
        return send_file(qr_path, mimetype='image/png')
    return jsonify({"ok": False, "error": "二维码未生成"}), 404

@app.route("/qr-image")
def qr_image():
    local_ip = get_local_ip()
    service_url = f"http://{local_ip}:{PORT}"
    if HAS_QRCODE:
        try:
            qr = qrcode.QRCode(version=1, box_size=8, border=4)
            qr.add_data(service_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            import io
            buf = io.BytesIO()
            img.save(buf)
            buf.seek(0)
            resp = make_response(send_file(buf, mimetype='image/png'))
            resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return resp
        except Exception as e:
            print(f"[QR] 生成失败: {e}")
    return jsonify({"ok": False, "error": "二维码生成失败"}), 500

@app.route("/clipboard", methods=["POST"])
def receive_clipboard():
    try:
        content = request.data.decode("utf-8") if request.data else ""
        if not content:
            return jsonify({"ok": False, "error": "内容为空"}), 400
        
        if HAS_PYPERCLIP:
            pyperclip.copy(content)
        
        add_to_history(content)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 已接收剪贴板内容: {content[:50]}")
        return jsonify({"ok": True, "message": "已写入Windows剪贴板"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/send", methods=["POST"])
def send_text():
    try:
        content = request.data.decode("utf-8") if request.data else ""
        if not content:
            return jsonify({"ok": False, "error": "内容为空"}), 400
        
        if HAS_PYPERCLIP:
            pyperclip.copy(content)
        
        add_to_history(content)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 已发送剪贴板内容: {content[:50]}")
        return jsonify({"ok": True, "message": "已写入Windows剪贴板"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/history")
def get_history():
    return jsonify({"history": CLIPBOARD_HISTORY})

@app.route("/history/clear", methods=["POST"])
def clear_history():
    global CLIPBOARD_HISTORY
    CLIPBOARD_HISTORY = []
    save_history()
    return jsonify({"ok": True, "message": "历史记录已清空"})

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "请选择要上传的文件"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"ok": False, "error": "文件名不能为空"}), 400
    
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    
    file_size = 0
    chunk = file.read(1024)
    while chunk:
        file_size += len(chunk)
        if file_size > MAX_FILE_SIZE:
            return jsonify({"ok": False, "error": f"文件大小超过限制 ({MAX_FILE_SIZE // 1024 // 1024}MB)"}), 400
        chunk = file.read(1024)
    
    file.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename, ext = os.path.splitext(file.filename)
    safe_filename = f"{filename}_{timestamp}{ext}"
    filepath = os.path.join(UPLOAD_DIR, safe_filename)
    
    try:
        file.save(filepath)
        add_to_history(f"上传文件: {file.filename} ({file_size} bytes)")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 已上传文件: {file.filename} -> {filepath}")
        return jsonify({
            "ok": True,
            "message": f"文件上传成功",
            "filename": file.filename,
            "size": file_size,
            "saved_as": safe_filename,
            "path": filepath
        })
    except Exception as e:
        return jsonify({"ok": False, "error": f"保存文件失败: {str(e)}"}), 500

@app.route("/files")
def list_files():
    try:
        if not os.path.exists(UPLOAD_DIR):
            return jsonify({"files": [], "count": 0})
        
        files = []
        for filename in os.listdir(UPLOAD_DIR):
            filepath = os.path.join(UPLOAD_DIR, filename)
            if os.path.isfile(filepath):
                files.append({
                    "filename": filename,
                    "size": os.path.getsize(filepath),
                    "modified": datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d %H:%M"),
                    "download_url": f"/files/download/{filename}"
                })
        
        files.sort(key=lambda x: x["modified"], reverse=True)
        return jsonify({"files": files, "count": len(files)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/files/download/<path:filename>")
def download_file(filename):
    try:
        filepath = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(filepath):
            return jsonify({"ok": False, "error": "文件不存在"}), 404
        
        return send_file(filepath, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/files/delete/<path:filename>", methods=["POST"])
def delete_file(filename):
    try:
        filepath = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(filepath):
            return jsonify({"ok": False, "error": "文件不存在"}), 404
        
        os.remove(filepath)
        add_to_history(f"删除文件: {filename}")
        return jsonify({"ok": True, "message": "文件已删除"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

INDEX_HTML = """<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>剪贴板同步</title>
<style>
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f5f5f5;min-height:100vh;padding:20px}
.container{max-width:480px;margin:0 auto}
.header{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border-radius:16px;padding:24px;text-align:center;margin-bottom:20px}
.header h1{margin:0;font-size:22px}
.header .status{margin-top:12px;font-size:14px;color:rgba(255,255,255,0.9)}
.qr-box{background:#fff;border-radius:12px;padding:20px;text-align:center;margin-bottom:20px;box-shadow:0 2px 10px rgba(0,0,0,0.05)}
.qr-box img{max-width:200px;border-radius:8px}
.qr-box p{color:#666;font-size:13px;margin-top:10px}
.qr-box button{background:#f0f0f0;border:none;padding:8px 16px;border-radius:6px;font-size:13px;color:#333;cursor:pointer;margin-top:10px}
.qr-box button:hover{background:#e0e0e0}
.card{background:#fff;border-radius:12px;padding:20px;margin-bottom:15px;box-shadow:0 2px 10px rgba(0,0,0,0.05)}
.card h3{margin:0 0 12px 0;font-size:16px;color:#333}
textarea{width:100%;height:100px;padding:12px;border:1px solid #ddd;border-radius:8px;font-size:14px;resize:none;outline:none;font-family:inherit}
textarea:focus{border-color:#667eea}
.btn{display:block;width:100%;padding:14px;background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border:none;border-radius:8px;font-size:16px;cursor:pointer;margin-top:12px}
.btn.secondary{background:#e5e7eb;color:#333}
.btn:active{transform:scale(0.98)}
.btn:disabled{opacity:0.6;cursor:not-allowed}
.msg{margin-top:10px;font-size:13px;text-align:center}
.msg.success{color:#10b981}
.msg.error{color:#ef4444}
.upload-area{border:2px dashed #22c55e;border-radius:8px;padding:30px;text-align:center;cursor:pointer}
.upload-area:hover{border-color:#16a34a;background:#f0fdf4}
.upload-area .icon{font-size:36px;margin-bottom:8px}
.upload-area .text{font-size:15px;color:#333}
.upload-area .hint{font-size:12px;color:#666;margin-top:4px}
input[type="file"]{display:none}
.progress{height:6px;background:#e5e7eb;border-radius:3px;margin-top:12px;overflow:hidden}
.progress-bar{height:100%;background:#667eea;width:0%;transition:width 0.3s}
.file-list{max-height:200px;overflow-y:auto}
.file-item{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid #f0f0f0}
.file-item:last-child{border-bottom:none}
.file-item .name{font-size:14px;color:#333}
.file-item .meta{font-size:12px;color:#888}
.file-item .actions{display:flex;gap:8px}
.file-item .actions a,.file-item .actions button{padding:4px 8px;font-size:12px;border:none;border-radius:4px;background:#f0f0f0;color:#333;text-decoration:none;cursor:pointer}
.history-list{max-height:150px;overflow-y:auto}
.history-item{padding:8px 0;border-bottom:1px solid #f0f0f0;font-size:13px}
.history-item .time{color:#888;font-size:11px}
.history-item .content{color:#333;margin-top:2px}
.empty{color:#888;font-size:13px;text-align:center;padding:15px}
.info{background:#f8f9fa;border-radius:8px;padding:12px;margin-bottom:15px;font-size:13px;color:#666;word-break:break-all}
</style>
</head><body>
<div class="container">
<div class="header">
<h1>剪贴板同步</h1>
<div class="status">服务运行中</div>
</div>

<div class="info">服务地址: <span id="serviceUrl">{{ url }}</span></div>

<div class="qr-box">
<img id="qrImage" src="/qr-image" alt="二维码">
<p>扫描二维码连接</p>
<button id="refreshBtn">刷新</button>
</div>

<div class="card">
<h3>发送文本到电脑</h3>
<textarea id="inputText" placeholder="输入或长按粘贴要发送的内容..."></textarea>
<button class="btn secondary" id="pasteBtn">粘贴剪贴板</button>
<button class="btn" id="sendBtn">发送到电脑</button>
<div class="msg" id="textMsg"></div>
</div>

<div class="card">
<h3>上传文件到电脑</h3>
<div class="upload-area" id="uploadArea">
<div class="icon">上传</div>
<div class="text">点击选择文件</div>
<div class="hint">支持图片、文档等，最大 10MB</div>
</div>
<input type="file" id="fileInput">
<div class="progress" id="uploadProgress" style="display:none"><div class="progress-bar" id="uploadBar"></div></div>
<div class="msg" id="uploadMsg"></div>
</div>

<div class="card">
<h3>已上传文件</h3>
<div id="fileList" class="file-list"></div>
</div>

<div class="card">
<h3>接收历史</h3>
<div id="historyList" class="history-list"></div>
</div>
</div>

<script>
function showMsg(id, text, type) {
    var el = document.getElementById(id);
    el.textContent = text;
    el.className = 'msg ' + type;
    setTimeout(function() { el.textContent = ''; el.className = 'msg'; }, 3000);
}

function pasteText() {
    var input = document.getElementById('inputText');
    input.focus();
    if (navigator.clipboard && navigator.clipboard.readText) {
        navigator.clipboard.readText().then(function(text) {
            input.value = text;
            showMsg('textMsg', '已粘贴', 'success');
        }).catch(function() {
            showMsg('textMsg', '长按输入框手动粘贴', 'error');
        });
    } else {
        showMsg('textMsg', '长按输入框手动粘贴', 'error');
    }
}

function sendText() {
    var input = document.getElementById('inputText');
    var content = input.value.trim();
    var btn = document.getElementById('sendBtn');
    
    if (!content) {
        showMsg('textMsg', '请输入内容', 'error');
        return;
    }
    
    btn.disabled = true;
    btn.textContent = '发送中...';
    
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/clipboard', true);
    xhr.setRequestHeader('Content-Type', 'text/plain;charset=utf-8');
    
    xhr.onload = function() {
        btn.disabled = false;
        btn.textContent = '发送到电脑';
        
        if (xhr.status === 200) {
            try {
                var result = JSON.parse(xhr.responseText);
                if (result.ok) {
                    showMsg('textMsg', '发送成功！', 'success');
                    input.value = '';
                } else {
                    showMsg('textMsg', '发送失败: ' + (result.error || '未知错误'), 'error');
                }
            } catch (e) {
                showMsg('textMsg', '解析错误: ' + e.message, 'error');
            }
        } else {
            showMsg('textMsg', 'HTTP错误: ' + xhr.status, 'error');
        }
    };
    
    xhr.onerror = function() {
        btn.disabled = false;
        btn.textContent = '发送到电脑';
        showMsg('textMsg', '网络错误: 无法连接服务器', 'error');
    };
    
    xhr.timeout = 10000;
    xhr.send(content);
}

function uploadFile(input) {
    var file = input.files[0];
    if (!file) return;
    
    var progress = document.getElementById('uploadProgress');
    var bar = document.getElementById('uploadBar');
    progress.style.display = 'block';
    bar.style.width = '0%';
    
    var formData = new FormData();
    formData.append('file', file);
    
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/upload', true);
    
    xhr.onload = function() {
        bar.style.width = '100%';
        
        if (xhr.status === 200) {
            try {
                var result = JSON.parse(xhr.responseText);
                if (result.ok) {
                    showMsg('uploadMsg', '文件上传成功', 'success');
                    loadFiles();
                    loadHistory();
                } else {
                    showMsg('uploadMsg', '上传失败: ' + (result.error || '未知错误'), 'error');
                }
            } catch (e) {
                showMsg('uploadMsg', '解析错误: ' + e.message, 'error');
            }
        } else {
            showMsg('uploadMsg', 'HTTP错误: ' + xhr.status, 'error');
        }
        
        setTimeout(function() { progress.style.display = 'none'; }, 500);
        input.value = '';
    };
    
    xhr.onerror = function() {
        progress.style.display = 'none';
        input.value = '';
        showMsg('uploadMsg', '网络错误: 无法连接服务器', 'error');
    };
    
    xhr.send(formData);
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1024 / 1024).toFixed(2) + ' MB';
}

function loadFiles() {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/files', true);
    
    xhr.onload = function() {
        if (xhr.status === 200) {
            try {
                var result = JSON.parse(xhr.responseText);
                var list = document.getElementById('fileList');
                
                if (!result.files || result.files.length === 0) {
                    list.innerHTML = '<div class="empty">暂无上传文件</div>';
                    return;
                }
                
                list.innerHTML = '';
                result.files.forEach(function(f) {
                    var div = document.createElement('div');
                    div.className = 'file-item';
                    
                    var nameDiv = document.createElement('div');
                    var nameSpan = document.createElement('div');
                    nameSpan.className = 'name';
                    nameSpan.textContent = f.filename;
                    var metaSpan = document.createElement('div');
                    metaSpan.className = 'meta';
                    metaSpan.textContent = formatSize(f.size) + ' · ' + f.modified;
                    nameDiv.appendChild(nameSpan);
                    nameDiv.appendChild(metaSpan);
                    
                    var actionsDiv = document.createElement('div');
                    actionsDiv.className = 'actions';
                    
                    var downloadLink = document.createElement('a');
                    downloadLink.href = f.download_url;
                    downloadLink.textContent = '下载';
                    
                    var deleteBtn = document.createElement('button');
                    deleteBtn.textContent = '删除';
                    deleteBtn.dataset.filename = f.filename;
                    deleteBtn.addEventListener('click', function() {
                        deleteFile(this.dataset.filename);
                    });
                    
                    actionsDiv.appendChild(downloadLink);
                    actionsDiv.appendChild(deleteBtn);
                    
                    div.appendChild(nameDiv);
                    div.appendChild(actionsDiv);
                    list.appendChild(div);
                });
            } catch (e) {
                console.error('解析文件列表失败:', e);
            }
        }
    };
    
    xhr.onerror = function() {
        console.error('加载文件列表失败');
    };
    
    xhr.send();
}

function deleteFile(name) {
    if (!confirm('确定删除？')) return;
    
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/files/delete/' + encodeURIComponent(name), true);
    
    xhr.onload = function() {
        if (xhr.status === 200) {
            try {
                var result = JSON.parse(xhr.responseText);
                if (result.ok) {
                    loadFiles();
                    loadHistory();
                    showMsg('textMsg', '文件已删除', 'success');
                }
            } catch (e) {
                console.error('解析失败:', e);
            }
        }
    };
    
    xhr.onerror = function() {
        console.error('删除失败');
    };
    
    xhr.send();
}

function loadHistory() {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/history', true);
    
    xhr.onload = function() {
        if (xhr.status === 200) {
            try {
                var result = JSON.parse(xhr.responseText);
                var list = document.getElementById('historyList');
                
                if (!result.history || result.history.length === 0) {
                    list.innerHTML = '<div class="empty">暂无历史记录</div>';
                    return;
                }
                
                list.innerHTML = '';
                result.history.slice(0, 10).forEach(function(item) {
                    var div = document.createElement('div');
                    div.className = 'history-item';
                    
                    var timeSpan = document.createElement('div');
                    timeSpan.className = 'time';
                    timeSpan.textContent = item.time;
                    
                    var contentSpan = document.createElement('div');
                    contentSpan.className = 'content';
                    contentSpan.textContent = item.content;
                    
                    div.appendChild(timeSpan);
                    div.appendChild(contentSpan);
                    list.appendChild(div);
                });
            } catch (e) {
                console.error('解析历史失败:', e);
            }
        }
    };
    
    xhr.onerror = function() {
        console.error('加载历史失败');
    };
    
    xhr.send();
}

function init() {
    document.getElementById('refreshBtn').addEventListener('click', function() {
        document.getElementById('qrImage').src = '/qr-image?' + Date.now();
    });
    
    document.getElementById('pasteBtn').addEventListener('click', pasteText);
    document.getElementById('sendBtn').addEventListener('click', sendText);
    
    document.getElementById('uploadArea').addEventListener('click', function() {
        document.getElementById('fileInput').click();
    });
    
    document.getElementById('fileInput').addEventListener('change', function() {
        uploadFile(this);
    });
    
    loadFiles();
    loadHistory();
}

document.addEventListener('DOMContentLoaded', init);
</script>
</body></html>"""

def check_dependencies():
    missing = []
    if not HAS_FLASK:
        missing.append("flask")
    if not HAS_PYPERCLIP:
        missing.append("pyperclip")
    if not HAS_QRCODE:
        missing.append("qrcode")
    if missing:
        print(f"[ERROR] 缺少依赖，请安装: pip install {' '.join(missing)}")
        return False
    return True

def start_server(port=8080):
    global PORT
    PORT = port
    load_history()
    local_ip = get_local_ip()
    all_ips = get_all_local_ips()
    service_url = f"http://{local_ip}:{PORT}"
    
    print("=" * 50)
    print("剪贴板同步服务")
    print("=" * 50)
    print(f"主服务地址: {service_url}")
    print(f"主 IP: {local_ip}")
    if len(all_ips) > 1:
        print("\n其他可用 IP 地址:")
        for ip in all_ips:
            if ip != local_ip:
                print(f"  - http://{ip}:{PORT}")
    print("=" * 50)
    print("提示：确保 iPhone 和电脑连接同一 Wi-Fi 网络")
    print("提示：如果主地址无法访问，请尝试其他 IP 地址")
    print("=" * 50)
    
    threading.Timer(1, lambda: webbrowser.open(service_url)).start()
    
    app.run(host="0.0.0.0", port=PORT, debug=False)

def print_usage():
    print("用法:")
    print("  python clipboard_server.py")
    print("  python clipboard_server.py -p <端口号>")
    print("  python clipboard_server.py --port <端口号>")
    print("  python clipboard_server.py <端口号>")
    print("")
    print("示例:")
    print("  python clipboard_server.py -p 8081")
    print("  python clipboard_server.py --port 9090")
    print("  python clipboard_server.py 8080")
    print("")
    print("默认端口: 8080")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='iPhone 剪贴板同步服务')
    parser.add_argument('-p', '--port', type=int, default=8080, help='服务端口号')
    args = parser.parse_args()
    
    if not check_dependencies():
        sys.exit(1)
    
    start_server(args.port)
