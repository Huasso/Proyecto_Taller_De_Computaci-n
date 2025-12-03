import os
from flask import Flask, request, jsonify, render_template_string
from pymongo import MongoClient
import requests
import base64
from datetime import datetime
import json
import time
import hashlib
from bson.objectid import ObjectId
# Importar dotenv para cargar variables de entorno
from dotenv import load_dotenv

# Cargar las variables del archivo .env
load_dotenv()

app = Flask(__name__)

# --- 1. CONFIGURACIÓN ---
client = MongoClient('localhost', 27017)
db = client['fungi_project_db']
sensor_coll = db['telemetria']
img_coll = db['analisis_imagenes']
users_coll = db['usuarios']

# --- CREDENCIALES SEGURAS ---
# Ahora la clave se lee del sistema, no está escrita en el código
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not OPENROUTER_API_KEY:
    print("⚠️ ADVERTENCIA: No se encontró la API Key en el archivo .env")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELO_IA = "qwen/qwen2.5-vl-72b-instruct"

# --- FUNCIONES AUXILIARES ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- 2. DASHBOARD HTML CON LOGIN ---
HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FungiScan Pro | Panel de Control</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #e8f5e9; font-family: 'Segoe UI', sans-serif; }
        .login-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: #2e7d32; display: flex; justify-content: center; align-items: center; z-index: 1000; }
        .login-card { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 10px 25px rgba(0,0,0,0.2); width: 350px; text-align: center; }
        .dashboard-container { display: none; }
        .header-fungi { background: #388E3C; color: white; padding: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .card { border: none; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }
        .status-ok { color: #2e7d32; font-weight: bold; font-size: 1.2em; }
        .status-danger { color: #c62828; font-weight: bold; font-size: 1.2em; }
        .btn-logout { background: rgba(255,255,255,0.2); border: none; color: white; }
    </style>
</head>
<body>

    <!-- PANTALLA DE LOGIN -->
    <div id="loginScreen" class="login-overlay">
        <div class="login-card">
            <h2 class="text-success mb-4">🍄 FungiScan Web</h2>
            <input type="text" id="userWeb" class="form-control mb-3" placeholder="Usuario">
            <input type="password" id="passWeb" class="form-control mb-3" placeholder="Contraseña">
            <button onclick="doLogin()" class="btn btn-success w-100">Ingresar</button>
            <p id="loginError" class="text-danger mt-2 small"></p>
        </div>
    </div>

    <!-- PANTALLA DASHBOARD -->
    <div id="mainDashboard" class="dashboard-container">
        <nav class="navbar navbar-dark header-fungi justify-content-between">
            <div class="container-fluid">
                <span class="navbar-brand mb-0 h1">🌿 Monitor de Cultivos AI</span>
                <button onclick="doLogout()" class="btn btn-sm btn-logout">Cerrar Sesión</button>
            </div>
        </nav>

        <div class="container mt-4">
            <div class="row">
                <div class="col-md-8">
                    <div class="card h-100">
                        <div class="card-header bg-white fw-bold text-success">📉 Telemetría en Tiempo Real</div>
                        <div class="card-body">
                            <canvas id="sensorChart"></canvas>
                        </div>
                    </div>
                </div>

                <div class="col-md-4">
                    <div class="card bg-success text-white mb-3">
                        <div class="card-body text-center">
                            <h5>Temperatura</h5>
                            <h2 class="display-4 fw-bold"><span id="current-temp">--</span>°C</h2>
                        </div>
                    </div>
                    <div class="card bg-primary text-white mb-3">
                        <div class="card-body text-center">
                            <h5>Humedad</h5>
                            <h2 class="display-4 fw-bold"><span id="current-hum">--</span>%</h2>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header fw-bold">🤖 Último Diagnóstico</div>
                        <div class="card-body text-center">
                            <div id="ai-result">Esperando datos...</div>
                            <p id="ai-desc" class="text-muted small mt-2">...</p>
                            <small id="ai-date" class="text-secondary">--</small>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function doLogin() {
            const u = document.getElementById('userWeb').value;
            const p = document.getElementById('passWeb').value;
            
            fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: u, password: p})
            })
            .then(r => r.json())
            .then(data => {
                if(data.status === 'ok') {
                    localStorage.setItem('fungiUser', u);
                    showDashboard();
                } else {
                    document.getElementById('loginError').innerText = "Credenciales incorrectas";
                }
            });
        }

        function doLogout() {
            localStorage.removeItem('fungiUser');
            location.reload();
        }

        function showDashboard() {
            document.getElementById('loginScreen').style.display = 'none';
            document.getElementById('mainDashboard').style.display = 'block';
            startUpdates();
        }

        if(localStorage.getItem('fungiUser')) {
            showDashboard();
        }

        const ctx = document.getElementById('sensorChart').getContext('2d');
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    { label: 'Temp (°C)', borderColor: '#4CAF50', backgroundColor: 'rgba(76, 175, 80, 0.1)', fill: true, data: [] }, 
                    { label: 'Hum (%)', borderColor: '#2196F3', backgroundColor: 'rgba(33, 150, 243, 0.1)', fill: true, data: [] }
                ]
            }
        });

        function startUpdates() {
            setInterval(() => {
                fetch('/api/data').then(r => r.json()).then(data => {
                    if(data.telemetria.length > 0) {
                        const d = data.telemetria;
                        chart.data.labels = d.map(x => new Date(x.timestamp * 1000).toLocaleTimeString());
                        chart.data.datasets[0].data = d.map(x => x.temperatura);
                        chart.data.datasets[1].data = d.map(x => x.humedad);
                        chart.update();
                        
                        const last = d[d.length - 1];
                        document.getElementById('current-temp').innerText = last.temperatura;
                        document.getElementById('current-hum').innerText = last.humedad;
                    }
                    if(data.analisis) {
                        const ai = data.analisis;
                        const resElem = document.getElementById('ai-result');
                        resElem.innerHTML = ai.detectado ? "🚨 <b>HONGO DETECTADO</b>" : "✅ <b>PLANTA SANA</b>";
                        resElem.className = ai.detectado ? "status-danger" : "status-ok";
                        document.getElementById('ai-desc').innerText = ai.razonamiento;
                        document.getElementById('ai-date').innerText = ai.fecha_legible || new Date(ai.timestamp*1000).toLocaleString();
                    }
                });
            }, 3000);
        }
    </script>
</body>
</html>
"""

# --- 3. RUTAS API ---

@app.route('/')
def index():
    return render_template_string(HTML_DASHBOARD)

# Registro de Usuario
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        u, p = data.get('username'), data.get('password')
        if users_coll.find_one({"username": u}): return jsonify({"error": "Existe"}), 409
        users_coll.insert_one({"username": u, "password": hash_password(p)})
        return jsonify({"status": "ok"}), 201
    except: return jsonify({"error": "Error"}), 500

# Login de Usuario
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        user = users_coll.find_one({"username": data.get('username')})
        if user and user['password'] == hash_password(data.get('password')):
            return jsonify({"status": "ok", "token": user['username']}), 200
        return jsonify({"error": "Invalid"}), 401
    except: return jsonify({"error": "Error"}), 500

# Obtener Datos (Público para el Dashboard)
@app.route('/api/data', methods=['GET'])
def get_data():
    telemetria = list(sensor_coll.find({}, {'_id': 0}).sort('timestamp', -1).limit(20))
    analisis = img_coll.find_one({}, {'_id': 0}, sort=[('timestamp', -1)])
    telemetria.reverse()
    return jsonify({"telemetria": telemetria, "analisis": analisis})

# Recibir Datos Sensor ESP32
@app.route('/api/sensor', methods=['POST'])
def receive_sensor():
    try:
        data = request.json
        data['timestamp'] = time.time()
        sensor_coll.insert_one(data)
        return jsonify({"status": "ok"}), 200
    except: return jsonify({"error": "err"}), 500

# Analizar Imagen con IA (App Android)
@app.route('/api/analizar-imagen', methods=['POST'])
def analyze_image():
    try:
        username = request.form.get('username', 'anonimo')
        file = request.files['image']
        image_base64 = base64.b64encode(file.read()).decode('utf-8')
        
        print("🖼️ Analizando imagen...")
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "FungiScan"
        }
        
        # PROMPT EXPERTO AGRÓNOMO
        prompt = """
        Eres un fitopatólogo experto. Analiza esta imagen de planta.
        Responde ESTRÍCTAMENTE un JSON con este formato:
        {
            "detectado": boolean, 
            "razonamiento": "Nombre del hongo (si hay) y breve descripción de síntomas. Si está sana, indícalo.",
            "tipo_hongo": "Nombre o 'Ninguno'"
        }
        detectado=true si ves hongos o enfermedad.
        """

        payload = {
            "model": MODELO_IA,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ]
            }]
        }
        
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload)
        ai_res = response.json()
        
        if 'error' in ai_res: 
            print("Error IA:", ai_res)
            return jsonify(ai_res), 500
        
        try:
            content = ai_res['choices'][0]['message']['content']
            clean_json = content.replace("```json", "").replace("```", "").strip()
            ai_data = json.loads(clean_json)
        except: ai_data = {"detectado": False, "razonamiento": content}

        registro = {
            "timestamp": time.time(),
            "username": username,
            "detectado": ai_data.get('detectado', False),
            "razonamiento": ai_data.get('razonamiento', "Sin detalle"),
            "fecha_legible": datetime.now().strftime('%Y-%m-%d %H:%M')
        }
        
        img_coll.insert_one(registro)
        registro['_id'] = str(registro['_id'])
        
        return jsonify(registro), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Historial Filtrado por Usuario
@app.route('/api/historial-ia', methods=['GET'])
def get_history():
    try:
        u = request.args.get('username')
        # Filtra por usuario si se provee, sino trae todo
        query = {"username": u} if u else {}
        cursor = img_coll.find(query).sort('timestamp', -1).limit(20)
        
        lista = []
        for doc in cursor:
            doc['_id'] = str(doc['_id'])
            lista.append(doc)
        return jsonify(lista), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Servidor FungiScan Iniciado en Puerto 5000")
    app.run(host='0.0.0.0', port=5000)
