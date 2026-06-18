import cv2
import threading
import time
import os
import json
from flask import Flask, Response, send_from_directory, stream_with_context, jsonify, request
from dotenv import load_dotenv

load_dotenv()

from neurodrive_pipeline import OdometriaVisual, telemetria_ext, ESCALA_MAQUETE, AsyncIPCamera

CAMERA_IP = os.getenv("CAMERA_IP")
WEB_PORT  = int(os.getenv("WEB_PORT", "5000"))

app = Flask(__name__, static_folder="web")

frame_atual = None
frame_lock  = threading.Lock()
odometria   = OdometriaVisual(escala=ESCALA_MAQUETE)

nova_fonte = None
async_cam = None

def camera_loop():
    global frame_atual, nova_fonte, async_cam
    
    video_source = f"http://{CAMERA_IP}/video" if CAMERA_IP else None
    print(f"[CAM] Conectando em: {video_source}")
    
    if video_source is None:
        async_cam = None
    elif str(video_source).startswith("http"):
        async_cam = AsyncIPCamera(video_source)
    else:
        async_cam = cv2.VideoCapture(video_source)
        async_cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    while True:
        if nova_fonte is not None:
            video_source = nova_fonte
            nova_fonte = None
            if async_cam is not None:
                if isinstance(async_cam, AsyncIPCamera):
                    async_cam.stop()
                else:
                    async_cam.release()
                
            print(f"[CAM] Mudando fonte para: {video_source}")
            if str(video_source).startswith("http"):
                async_cam = AsyncIPCamera(video_source)
            else:
                async_cam = cv2.VideoCapture(video_source)
                async_cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            continue

        if async_cam is None:
            import numpy as np
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            cv2.putText(frame, "COLOQUE O IP DA CAMERA NO DASHBOARD", (250, 360), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 2)
            time.sleep(0.5)
        elif isinstance(async_cam, AsyncIPCamera):
            # Zero Delay: Pega apenas o frame recém decodificado na memória
            frame = async_cam.get_frame()
            if frame is None:
                continue
        else:
            ret, frame = async_cam.read()
            if not ret:
                time.sleep(0.5)
                if nova_fonte is None:
                    async_cam.open(video_source)
                continue
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
            if frame.shape[1] != 1280 or frame.shape[0] != 720:
                frame = cv2.resize(frame, (1280, 720))

        # Optical flow ultraleve da V4.0
        processado = odometria.calcular_velocidade(frame)

        with frame_lock:
            frame_atual = processado

threading.Thread(target=camera_loop, daemon=True).start()

def gerar_mjpeg():
    # Loop agressivo para streaming MJPEG
    while True:
        with frame_lock:
            f = frame_atual
            
        if f is None:
            time.sleep(0.01)
            continue

        ok, jpeg = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            continue

        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
        time.sleep(1 / 45) # Permite ate 45fps pro client consumir fluido


@app.route("/video")
def video_feed():
    return Response(
        stream_with_context(gerar_mjpeg()),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


@app.route("/api/telemetria")
def telemetria_sse():
    def gerar():
        try:
            while True:
                sensor_ativo = (time.time() - telemetria_ext["ultima_att"]) < 2.0
                dados = {
                    "vel_inst":     round(odometria.velocidade_instantanea_kmh, 1),
                    "vel_media":    round(odometria.velocidade_media_kmh, 1),
                    "vel_max":      round(odometria.velocidade_maxima, 1),
                    "acel":         round(odometria.aceleracao_ms2, 2),
                    "modo":         odometria.modo,
                    "qualidade":    odometria.qualidade_rastreio,
                    "sensor_ativo": sensor_ativo,
                    "gps_kmh":      round(telemetria_ext["gps_speed_ms"] * 3.6, 1) if sensor_ativo else None,
                    "accel_x":      round(telemetria_ext["aceleracao_x"], 2) if sensor_ativo else None,
                    "accel_y":      round(telemetria_ext["aceleracao_y"], 2) if sensor_ativo else None,
                    "historico":    list(odometria.historico_grafico[-60:]),
                }
                yield f"data: {json.dumps(dados)}\n\n"
                time.sleep(0.1) # Resposta mais rápida da telemetria (10Hz)
        except GeneratorExit:
            pass

    return Response(
        stream_with_context(gerar()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/galeria")
def listar_galeria():
    pasta = os.path.join("web", "assets", "gallery")
    if not os.path.exists(pasta):
        return jsonify([])
    exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    arquivos = [f for f in os.listdir(pasta) if os.path.splitext(f)[1].lower() in exts]
    return jsonify(sorted(arquivos))


@app.route("/api/config_camera", methods=["POST"])
def config_camera():
    global nova_fonte
    dados = request.get_json()
    if dados and "url" in dados:
        url = dados["url"].strip()
        if url.endswith("/data"):
            url = url.replace("/data", "/video")
            
        if not url.startswith("http"):
            url = f"http://{url}"
            
        if url.count("/") == 2:
            url = f"{url}/video"
            
        nova_fonte = url
        return jsonify({"status": "ok", "url": url})
    return jsonify({"error": "invalid"}), 400


@app.route("/api/tecla", methods=["POST"])
def receber_tecla():
    dados = request.get_json()
    if dados and "tecla" in dados:
        tecla = dados["tecla"].lower()
        if len(tecla) == 1:
            odometria.processar_tecla(ord(tecla))
            return jsonify({"status": "ok"})
    return jsonify({"error": "invalid"}), 400


@app.route("/")
def index():
    return send_from_directory("web", "index.html")


@app.route("/<path:filename>")
def arquivos_estaticos(filename):
    return send_from_directory("web", filename)


if __name__ == "__main__":
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()
        
    sensor_port = os.getenv("SENSOR_SERVER_PORT", "8000")
    print(f"\n{'='*50}")
    print(f"  NEURODRIVE WEB DASHBOARD - ZERO DELAY")
    print(f"{'='*50}")
    print(f"  Local  -> http://localhost:{WEB_PORT}")
    print(f"  Rede   -> http://{local_ip}:{WEB_PORT}")
    print(f"\n  Sensor Logger -> http://{local_ip}:{sensor_port}/data")
    print(f"{'='*50}\n")
    
    # Roda o Flask sem cache, super rápido
    app.run(host="0.0.0.0", port=WEB_PORT, threaded=True)
