import cv2
import numpy as np
import time
import math
import os
import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv

load_dotenv()
SENSOR_SERVER_PORT = int(os.getenv("SENSOR_SERVER_PORT", "8000"))

# Variaveis globais para telemetria externa (Sensor Logger)
telemetria_ext = {
    "aceleracao_x": 0.0,
    "aceleracao_y": 0.0,
    "aceleracao_z": 0.0,
    "gps_speed_ms": 0.0,
    "ultima_att": 0.0
}

class SensorLoggerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                payload = data.get("payload", [])
                for p in payload:
                    name = p.get("name")
                    vals = p.get("values", {})
                    if name == "accelerometer" or name == "gravity":
                        telemetria_ext["aceleracao_x"] = vals.get("x", 0.0)
                        telemetria_ext["aceleracao_y"] = vals.get("y", 0.0)
                        telemetria_ext["aceleracao_z"] = vals.get("z", 0.0)
                        telemetria_ext["ultima_att"] = time.time()
                    elif name == "location":
                        telemetria_ext["gps_speed_ms"] = vals.get("speed", 0.0)
                        telemetria_ext["ultima_att"] = time.time()
            except Exception:
                pass
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass # Silencia logs para nao poluir o terminal

def iniciar_servidor_sensores():
    server = HTTPServer(('0.0.0.0', SENSOR_SERVER_PORT), SensorLoggerHandler)
    server.serve_forever()

threading.Thread(target=iniciar_servidor_sensores, daemon=True).start()

# ==============================================================================
#  CLASSE ASYNC IP CAMERA (Processamento Assíncrono para Mitigação de Latência)
# ==============================================================================
class AsyncIPCamera:
    def __init__(self, url):
        self.url = url
        self.frame = None
        self.running = True
        self.lock = threading.Lock()
        self.new_frame_event = threading.Event()
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def _capture_loop(self):
        import urllib.request
        import socket
        
        # Solicitação de frames discretos (snapshot) em vez de stream contínuo.
        # Esta abordagem previne o enfileiramento de pacotes (buffer TCP),
        # garantindo que o algoritmo de visão processe apenas o estado atual (latência mitigada).
        is_ipwebcam = self.url.endswith("/video")
        shot_url = self.url.replace("/video", "/shot.jpg") if is_ipwebcam else self.url
        
        socket.setdefaulttimeout(1.0)
        
        while self.running:
            try:
                # Usar urllib pura para evitar ModuleNotFoundError no Windows
                req = urllib.request.Request(shot_url)
                req.add_header('Connection', 'close') # Nao segurar sockets pendentes
                
                with urllib.request.urlopen(req, timeout=0.8) as response:
                    img_array = np.frombuffer(response.read(), dtype=np.uint8)
                    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                    
                    if frame is not None:
                        frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
                        if frame.shape[1] != 1280 or frame.shape[0] != 720:
                            frame = cv2.resize(frame, (1280, 720))
                        
                        with self.lock:
                            self.frame = frame
                        self.new_frame_event.set()
                
                # Pausa para controle de fluxo (prevenção de negação de serviço no dispositivo móvel)
                time.sleep(0.015)
            except Exception as e:
                # Tratamento de exceção de rede
                print(f"[AsyncIPCamera] Oscilação de rede detectada, reconectando... ({e})")
                time.sleep(0.1) # Intervalo de segurança (backoff)

    def get_frame(self):
        if self.new_frame_event.wait(timeout=1.0):
            self.new_frame_event.clear()
            with self.lock:
                return self.frame.copy() if self.frame is not None else None
        return None

    def stop(self):
        self.running = False

# ==============================================================================
#  CLASSE ODOMETRIA VISUAL (Análise Cinemática e Vetorial)
# ==============================================================================

ARQUIVO_CALIBRACAO   = "calibracao_neurodrive.json"
VEL_MAX_CARRINHO_KMH = 30.0   # Velocidade máxima real do carrinho (spec fabricante)
ESCALA_MAQUETE       = 30.0   # Escala 1:30 (escala real medida)

class OdometriaVisual:
    def __init__(self, escala=ESCALA_MAQUETE):
        self.frame_cinza_anterior  = None
        self.pontos_rastreados     = None
        self.ultimo_tempo          = time.time()

        # Física / velocidade
        self.velocidade_instantanea_kmh = 0.0
        self.velocidade_media_kmh       = 0.0
        self.aceleracao_ms2             = 0.0
        self.velocidade_maxima          = 0.0
        self.qualidade_rastreio         = 0

        # Históricos
        self.historico_recente     = []
        self.historico_grafico     = []
        self.soma_velocidades_curso = 0.0
        self.qtd_medicoes_curso    = 0

        self.escala = escala

        # Calibração — carrega do disco se existir
        self.fator_px_mm                = None
        self.flow_maximo_observado_pxs  = None
        self._carregar_calibracao()

        # Estado da calibração interativa
        self.calibrando              = False
        self.calib_pixels_acumulados = 0.0
        self.calib_frames            = 0
        self.calib_tempo_inicio      = 0.0

        # Variaveis para o modo LISTRAS
        self.distancia_listras_m = 1.0
        self.ultimo_tempo_listra = None
        self.faixa_passando      = False
        
        self.ia_ativada = True # Controle de performance

        # Modo de operação e Layout
        self.modo = "real" if self.fator_px_mm is not None else "simulado"
        self.layout = "velocimetro"
        self.tempo_demo = 0.0

        print(f"\n[NEURODRIVE] Iniciando — modo: {self.modo.upper()}")
        if self.fator_px_mm:
            print(f"[NEURODRIVE] Calibração: 1 px = {self.fator_px_mm:.4f} mm real")
        else:
            print("[NEURODRIVE] Sem calibração. Pressione [C] para calibrar ou [S] para modo simulado.")

    def _carregar_calibracao(self):
        if os.path.exists(ARQUIVO_CALIBRACAO):
            try:
                with open(ARQUIVO_CALIBRACAO) as f:
                    d = json.load(f)
                self.fator_px_mm               = d.get("fator_px_mm")
                self.flow_maximo_observado_pxs = d.get("flow_maximo_pxs")
            except Exception as e:
                print(f"[CALIB] Erro ao carregar: {e}")

    def _salvar_calibracao(self):
        try:
            d = {}
            if os.path.exists(ARQUIVO_CALIBRACAO):
                with open(ARQUIVO_CALIBRACAO) as f:
                    d = json.load(f)
            if self.fator_px_mm is not None:
                d["fator_px_mm"] = self.fator_px_mm
            if self.flow_maximo_observado_pxs is not None:
                d["flow_maximo_pxs"] = self.flow_maximo_observado_pxs
            with open(ARQUIVO_CALIBRACAO, "w") as f:
                json.dump(d, f, indent=2)
        except Exception as e:
            pass

    def processar_tecla(self, tecla):
        if tecla in (ord('c'), ord('C')):
            self._toggle_calibracao()
        elif tecla in (ord('s'), ord('S')):
            self._toggle_modo()
        elif tecla in (ord('r'), ord('R')):
            self._resetar_estatisticas()
        elif tecla in (ord('l'), ord('L')):
            self._toggle_layout()
        elif tecla in (ord('i'), ord('I')):
            self.ia_ativada = not self.ia_ativada
            print(f"[IA] {'ATIVADA' if self.ia_ativada else 'DESATIVADA'} - ZERO DELAY")

    def _toggle_layout(self):
        self.layout = "cyber" if self.layout == "velocimetro" else "velocimetro"

    def _toggle_calibracao(self):
        if not self.calibrando:
            self.calibrando              = True
            self.calib_pixels_acumulados = 0.0
            self.calib_frames            = 0
            self.calib_tempo_inicio      = time.time()
        else:
            self.calibrando   = False
            tempo_total       = time.time() - self.calib_tempo_inicio
            if self.calib_pixels_acumulados > 10:
                self.fator_px_mm = 1000.0 / self.calib_pixels_acumulados
                self._salvar_calibracao()
                self.modo = "real"

    def _toggle_modo(self):
        modos = ["real", "sensor", "listras", "demo", "simulado"]
        idx = modos.index(self.modo) if self.modo in modos else 0
        self.modo = modos[(idx + 1) % len(modos)]

    def _resetar_estatisticas(self):
        self.velocidade_maxima      = 0.0
        self.velocidade_media_kmh   = 0.0
        self.soma_velocidades_curso = 0.0
        self.qtd_medicoes_curso     = 0
        self.historico_grafico.clear()
        self.historico_recente.clear()

    # ──────────────────────────────────────────────────────────────────
    #  CÁLCULO DO FLUXO ÓPTICO (Algoritmo de Lucas-Kanade)
    # ──────────────────────────────────────────────────────────────────
    def _extrair_flow(self, frame_cinza_atual, frame_debug):
        # Redução de dimensionalidade (downscale) para otimização da carga de processamento matricial.
        SCALE_FACTOR = 0.5 
        
        h_orig, w_orig = frame_cinza_atual.shape
        h_small, w_small = int(h_orig * SCALE_FACTOR), int(w_orig * SCALE_FACTOR)
        
        frame_cinza_small = cv2.resize(frame_cinza_atual, (w_small, h_small), interpolation=cv2.INTER_LINEAR)

        mascara = np.zeros_like(frame_cinza_small)
        pts_small = np.array([[
            [int(w_small * 0.05), int(h_small * 0.75)],
            [int(w_small * 0.25), int(h_small * 0.50)],
            [int(w_small * 0.75), int(h_small * 0.50)],
            [int(w_small * 0.95), int(h_small * 0.75)],
        ]], dtype=np.int32)
        cv2.fillPoly(mascara, pts_small, 255)
        
        # Polígono apenas visualizado na alta qualidade
        pts_orig = (pts_small / SCALE_FACTOR).astype(np.int32)
        cv2.polylines(frame_debug, pts_orig, True, (0, 255, 255), 1)

        if self.frame_cinza_anterior is None or self.pontos_rastreados is None or len(self.pontos_rastreados) < 15:
            self.frame_cinza_anterior = frame_cinza_small
            self.pontos_rastreados = cv2.goodFeaturesToTrack(
                frame_cinza_small, mask=mascara, maxCorners=100, qualityLevel=0.1, minDistance=10, blockSize=7)
            return None, 0

        # Resolução numérica e rastreamento iterativo dos vetores no espaço transformado.
        pontos_novos, status, _ = cv2.calcOpticalFlowPyrLK(
            self.frame_cinza_anterior, frame_cinza_small,
            self.pontos_rastreados, None,
            winSize=(15, 15), maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))

        mediana_px = None
        n_bons = 0

        if pontos_novos is not None:
            bons_novos = pontos_novos[status == 1]
            bons_antigos = self.pontos_rastreados[status == 1]
            n_bons = len(bons_novos)
            self.qualidade_rastreio = n_bons

            distancias = []
            deslocamentos_y = []
            for novo, antigo in zip(bons_novos, bons_antigos):
                a, b = novo.ravel()
                c, d = antigo.ravel()
                dist = float(np.sqrt((a - c) ** 2 + (b - d) ** 2))
                dy = b - d
                
                # Renderiza debug convertido
                a_orig, b_orig = a / SCALE_FACTOR, b / SCALE_FACTOR
                c_orig, d_orig = c / SCALE_FACTOR, d / SCALE_FACTOR
                
                cv2.circle(frame_debug, (int(a_orig), int(b_orig)), 3, (255, 255, 0), -1)
                cv2.line(frame_debug, (int(a_orig), int(b_orig)), (int(c_orig), int(d_orig)), (150, 150, 0), 1)
                
                if dist < (80 * SCALE_FACTOR):
                    distancias.append(dist)
                    deslocamentos_y.append(dy)

            if distancias:
                mediana_px_small = float(np.median(distancias))
                mediana_dy_small = float(np.median(deslocamentos_y))
                if mediana_dy_small < 0:
                    mediana_px_small = -mediana_px_small
                mediana_px = mediana_px_small / SCALE_FACTOR

            self.frame_cinza_anterior = frame_cinza_small.copy()
            if n_bons < 20:
                self.pontos_rastreados = cv2.goodFeaturesToTrack(
                    frame_cinza_small, mask=mascara, maxCorners=100, qualityLevel=0.1, minDistance=10, blockSize=7)
            else:
                self.pontos_rastreados = bons_novos.reshape(-1, 1, 2)

        return mediana_px, n_bons

    # ──────────────────────────────────────────────────────────────────
    #  RENDERIZAÇÃO DO PAINEL HUD (Modelagem de Regiões de Interesse)
    # ──────────────────────────────────────────────────────────────────
    def _desenhar_grafico(self, frame, x, y, larg, alt):
        roi = frame[y:y+alt, x:x+larg]
        blk = np.zeros_like(roi)
        cv2.addWeighted(blk, 0.4, roi, 0.6, 0, roi)
        
        cv2.putText(frame, "HISTORICO (KM/H)", (x + 10, y + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        if len(self.historico_grafico) < 2:
            return
            
        dados = [abs(v) for v in self.historico_grafico[-(larg - 20):]]
        max_v = max(VEL_MAX_CARRINHO_KMH * self.escala, max(dados) if dados else VEL_MAX_CARRINHO_KMH * self.escala)
        
        pts = []
        for i in range(len(dados)):
            xi = x + 10 + i
            yi = y + alt - 10 - int((dados[i] / max_v) * (alt - 40))
            pts.append((xi, yi))
        
        for i in range(1, len(pts)):
            intens = min(255, int((dados[i] / max_v) * 255))
            cv2.line(frame, pts[i-1], pts[i], (255, 255 - intens, intens), 2)

    def desenhar_painel(self, frame):
        H, W = frame.shape[:2]
        
        # ---------------------------------------------------------
        # BARRA SUPERIOR OTIMIZADA POR ROI
        # ---------------------------------------------------------
        roi_sup = frame[0:40, 0:W]
        blk_sup = np.zeros_like(roi_sup)
        cv2.addWeighted(blk_sup, 0.5, roi_sup, 0.5, 0, roi_sup)
        
        # ---------------------------------------------------------
        # PAINEL LATERAL OTIMIZADO POR ROI
        # ---------------------------------------------------------
        dx, dy = W - 280, 50
        roi_lat = frame[dy:dy+220, dx:dx+270]
        blk_lat = np.zeros_like(roi_lat)
        cv2.addWeighted(blk_lat, 0.5, roi_lat, 0.5, 0, roi_lat)

        # Textos da barra superior
        cv2.putText(frame, f"NEURODRIVE OS v4.0 ZERO-DELAY | 1:{int(self.escala)}",
                    (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        if self.calibrando:
            cor_badge = (0, 50, 255)
            txt_badge = f">> CALIBRANDO: {self.calib_pixels_acumulados:.0f} px <<"
        elif self.modo == "simulado":
            cor_badge = (255, 255, 255)
            txt_badge = f"MODO SIMULADO | [S]"
        elif self.modo == "sensor":
            cor_badge = (0, 255, 255)
            txt_badge = f"MODO SENSOR CELULAR | [S]"
        elif self.modo == "listras":
            cor_badge = (0, 255, 0)
            txt_badge = f"RASTREIO DE LISTRAS (1m) | [S]"
        elif self.modo == "demo":
            cor_badge = (255, 0, 0)
            txt_badge = f"MODO DEMO (AUTOMATICO) | [S]"
        else:
            cor_badge = (255, 255, 255)
            txt_badge = f"REAL CALIBRADO | [S]"
            
        cv2.putText(frame, txt_badge, (400, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cor_badge, 1)

        cor_s  = (255, 255, 0) if self.qualidade_rastreio > 30 else \
                 (0, 165, 255) if self.qualidade_rastreio > 10 else (0, 0, 255)
        txt_s  = "OTIMO" if self.qualidade_rastreio > 30 else \
                 "MEDIO" if self.qualidade_rastreio > 10 else "FRACO"
        cv2.putText(frame, f"SENS: {txt_s} ({self.qualidade_rastreio})",
                    (W - 250, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_s, 2)

        # ---------------------------------------------------------
        # VELOCIMETRO OU HUD CYBER
        # ---------------------------------------------------------
        if self.layout == "velocimetro":
            cx, cy = 180, H - 150
            raio_ext = 110
            raio_int = 70
            mv = 80 
            
            vd_real = self.velocidade_instantanea_kmh
            vd_abs = abs(vd_real)
            vd = min(vd_abs, mv)
            
            roi_vel = frame[cy-raio_ext-10 : cy+raio_ext+10, cx-raio_ext-10 : cx+raio_ext+10]
            blk_vel = np.zeros_like(roi_vel)
            
            mascara_circ = np.zeros((roi_vel.shape[0], roi_vel.shape[1]), dtype=np.uint8)
            cv2.circle(mascara_circ, (raio_ext+10, raio_ext+10), raio_ext+10, 255, -1)
            for ch in range(3):
                roi_vel[:,:,ch] = np.where(mascara_circ == 255, roi_vel[:,:,ch]//2, roi_vel[:,:,ch])
            
            cv2.circle(frame, (cx, cy), raio_ext, (255, 255, 255), 2)
    
            ang_inicio, ang_fim = 150, 390
            faixa_ang = ang_fim - ang_inicio
            
            for v in range(0, mv + 1, 5):
                prop = v / mv
                ang_rad = math.radians(ang_inicio + (prop * faixa_ang))
                cor_tick = (255, 0, 255) if v >= mv * 0.8 else (255, 255, 255)
                
                if v % 20 == 0:
                    x1 = int(cx + (raio_ext) * math.cos(ang_rad))
                    y1 = int(cy + (raio_ext) * math.sin(ang_rad))
                    x2 = int(cx + (raio_int) * math.cos(ang_rad))
                    y2 = int(cy + (raio_int) * math.sin(ang_rad))
                    cv2.line(frame, (x1, y1), (x2, y2), cor_tick, 3)
                    
                    xt = int(cx + (raio_int - 20) * math.cos(ang_rad))
                    yt = int(cy + (raio_int - 20) * math.sin(ang_rad))
                    (tw, th), _ = cv2.getTextSize(str(v), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                    cv2.putText(frame, str(v), (xt - tw//2, yt + th//2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cor_tick, 1)
                else:
                    x1 = int(cx + (raio_ext) * math.cos(ang_rad))
                    y1 = int(cy + (raio_ext) * math.sin(ang_rad))
                    x2 = int(cx + (raio_int + 15) * math.cos(ang_rad))
                    y2 = int(cy + (raio_int + 15) * math.sin(ang_rad))
                    cv2.line(frame, (x1, y1), (x2, y2), cor_tick, 1)
    
            prop_vd = vd / mv
            ang_vd = ang_inicio + (prop_vd * faixa_ang)
            cor_v  = (255, 255, 0) if prop_vd < 0.8 else (255, 0, 255)
            if vd_real < -0.5:
                cor_v = (0, 165, 255)
            
            cv2.ellipse(frame, (cx, cy), (raio_ext - 3, raio_ext - 3), 0, ang_inicio, ang_vd, cor_v, 6)
            
            texto_vd = f"{int(vd_abs):02d}"
            (tw, th), _ = cv2.getTextSize(texto_vd, cv2.FONT_HERSHEY_DUPLEX, 2.5, 4)
            cv2.putText(frame, texto_vd, (cx - tw//2, cy + th//2 - 10), cv2.FONT_HERSHEY_DUPLEX, 2.5, (255, 255, 255), 4)
            
            marcha = "R" if vd_real < -0.5 else "D"
            cv2.putText(frame, marcha, (cx - 10, cy + 30), cv2.FONT_HERSHEY_DUPLEX, 0.8, cor_v, 2)
            cv2.putText(frame, "km/h", (cx - 20, cy + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            
            px_ag = int(cx + (raio_int - 20) * math.cos(math.radians(ang_vd)))
            py_ag = int(cy + (raio_int - 20) * math.sin(math.radians(ang_vd)))
            cv2.line(frame, (cx, cy), (px_ag, py_ag), cor_v, 3)
            cv2.circle(frame, (cx, cy), 6, (255, 255, 255), -1)

        elif self.layout == "cyber":
            cx, cy = W // 2, H // 2
            cv2.circle(frame, (cx, cy), 40, (0, 255, 0), 1)
            cv2.line(frame, (cx - 60, cy), (cx - 20, cy), (0, 255, 0), 2)
            cv2.line(frame, (cx + 20, cy), (cx + 60, cy), (0, 255, 0), 2)
            cv2.line(frame, (cx, cy - 60), (cx, cy - 20), (0, 255, 0), 2)
            cv2.line(frame, (cx, cy + 20), (cx, cy + 60), (0, 255, 0), 2)
            cv2.circle(frame, (cx, cy), 2, (0, 0, 255), -1)
            
            cv2.rectangle(frame, (cx - 150, cy - 100), (cx - 120, cy - 70), (0, 255, 255), 2)
            cv2.rectangle(frame, (cx + 120, cy + 70), (cx + 150, cy + 100), (0, 255, 255), 2)
            
            g_cx, g_cy = 180, H - 150
            g_raio = 90
            
            cv2.circle(frame, (g_cx, g_cy), g_raio, (255, 255, 255), 1)
            cv2.circle(frame, (g_cx, g_cy), g_raio // 2, (100, 100, 100), 1)
            cv2.line(frame, (g_cx - g_raio, g_cy), (g_cx + g_raio, g_cy), (100, 100, 100), 1)
            cv2.line(frame, (g_cx, g_cy - g_raio), (g_cx, g_cy + g_raio), (100, 100, 100), 1)
            
            accel_long = self.aceleracao_ms2 / 9.8 
            accel_lat = telemetria_ext.get("aceleracao_x", 0.0) / 9.8 if self.modo == "sensor" else math.sin(time.time() * 2) * 0.2
            
            px = int(g_cx + (max(-1.5, min(1.5, accel_lat)) / 1.5) * g_raio)
            py = int(g_cy - (max(-1.5, min(1.5, accel_long)) / 1.5) * g_raio) 
            
            cv2.circle(frame, (px, py), 8, (0, 255, 255), -1)
            cv2.putText(frame, "G-METER", (g_cx - 30, g_cy + g_raio + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.putText(frame, f"G: {abs(accel_long):.2f}", (g_cx - 20, g_cy - g_raio - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # ---------------------------------------------------------
        # PAINEL DE DADOS DE CORRIDA
        # ---------------------------------------------------------
        cv2.putText(frame, "TELEMETRIA", (dx + 15, dy + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        cv2.putText(frame, f"MEDIA:  {self.velocidade_media_kmh:.1f} km/h", (dx + 15, dy + 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(frame, f"MAXIMA: {self.velocidade_maxima:.1f} km/h", (dx + 15, dy + 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 1)
        
        cor_a = (255, 255, 0) if self.aceleracao_ms2 >= 0 else (255, 0, 255)
        cv2.putText(frame, f"ACEL:   {self.aceleracao_ms2:+.2f} m/s2", (dx + 15, dy + 135), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_a, 2)
                    
        if time.time() - telemetria_ext["ultima_att"] < 2.0:
            gps_kmh = telemetria_ext["gps_speed_ms"] * 3.6
            accel_y = telemetria_ext["aceleracao_y"]
            cv2.line(frame, (dx + 10, dy + 150), (dx + 260, dy + 150), (100, 100, 100), 1)
            cv2.putText(frame, "SENSOR CELULAR", (dx + 15, dy + 170), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            cv2.putText(frame, f"GPS:   {gps_kmh:.1f} km/h", (dx + 15, dy + 195), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.putText(frame, f"ACCEL: {accel_y:+.2f} m/s2", (dx + 15, dy + 215), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        cv2.putText(frame, "[C] Calib  [S] Modo  [L] Layout  [I] IA ON/OFF  [R] Reset  [Q] Sair",
                    (10, H - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)

        gx, gy = W - 280, 280
        self._desenhar_grafico(frame, gx, gy, 270, 140)

        return frame

    def calcular_velocidade(self, frame):
        tempo_atual  = time.time()
        delta_tempo  = tempo_atual - self.ultimo_tempo
        frame_debug  = frame.copy()
        
        if getattr(self, 'ia_ativada', True) == False:
            self.velocidade_instantanea_kmh = 0.0
            self.aceleracao_ms2 = 0.0
            self.ultimo_tempo = tempo_atual
            return self.desenhar_painel(frame_debug)

        frame_cinza_atual = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if self.modo == "demo":
            self.tempo_demo += delta_tempo
            ciclo = (self.tempo_demo % 12.0) / 12.0
            accel_falsa = 5.0 if ciclo < 0.4 else (0.0 if ciclo < 0.6 else (-6.0 if ciclo < 0.9 else 0.0))
                
            self.velocidade_instantanea_kmh = max(0.0, min(120.0, self.velocidade_instantanea_kmh + accel_falsa * delta_tempo * 3.6))
            self.aceleracao_ms2 = accel_falsa * self.escala
            self.ultimo_tempo = tempo_atual
            
            self.historico_recente.append(self.velocidade_instantanea_kmh)
            if len(self.historico_recente) > 10: self.historico_recente.pop(0)
            
            self.soma_velocidades_curso += self.velocidade_instantanea_kmh
            self.qtd_medicoes_curso += 1
            self.velocidade_media_kmh = self.soma_velocidades_curso / self.qtd_medicoes_curso
            
            if self.velocidade_instantanea_kmh > self.velocidade_maxima:
                self.velocidade_maxima = self.velocidade_instantanea_kmh
                
            self.historico_grafico.append(self.velocidade_instantanea_kmh)
            if len(self.historico_grafico) > 300: self.historico_grafico.pop(0)
            
            return self.desenhar_painel(frame_debug)

        mediana_px, _ = self._extrair_flow(frame_cinza_atual, frame_debug)

        if self.modo not in ["sensor", "listras"] and (mediana_px is None or delta_tempo < 0.02):
            if abs(self.velocidade_instantanea_kmh) > 0.5:
                self.velocidade_instantanea_kmh *= 0.85
                self.historico_recente = [self.velocidade_instantanea_kmh] * max(1, len(self.historico_recente))
            else:
                self.velocidade_instantanea_kmh = 0.0
                
            self.aceleracao_ms2 = 0.0
            self.ultimo_tempo = tempo_atual
            return self.desenhar_painel(frame_debug)

        if self.calibrando:
            self.calib_pixels_acumulados += abs(mediana_px)
            self.calib_frames += 1
            cv2.putText(frame_debug, f"CALIBRANDO... {self.calib_pixels_acumulados:.0f} px | [C] finalizar",
                        (20, frame_debug.shape[0] // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        velocidade_fisica_kmh = 0.0
        mediana_px_abs = abs(mediana_px) if mediana_px is not None else 0.0
        sinal = -1 if (mediana_px is not None and mediana_px < 0) else 1
        
        if self.modo == "listras":
            hsv = cv2.cvtColor(frame_debug, cv2.COLOR_BGR2HSV)
            mask_white = cv2.inRange(hsv, np.array([0, 0, 150]), np.array([180, 50, 255]))
            mask_yellow = cv2.inRange(hsv, np.array([15, 100, 100]), np.array([40, 255, 255]))
            mask = cv2.bitwise_or(mask_white, mask_yellow)
            
            H_frame = frame_debug.shape[0]
            linha_deteccao = H_frame - 150
            mask[:linha_deteccao - 100, :] = 0 
            
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.line(frame_debug, (0, linha_deteccao), (frame_debug.shape[1], linha_deteccao), (0, 0, 255), 2)
            
            faixa_cruzando = False
            for cnt in contours:
                if cv2.contourArea(cnt) > 2000:
                    x, y, w, h = cv2.boundingRect(cnt)
                    if y < linha_deteccao < y + h:
                        faixa_cruzando = True
                        cv2.rectangle(frame_debug, (x, y), (x+w, y+h), (0, 255, 0), 4)
                        break
                        
            if faixa_cruzando and not self.faixa_passando:
                self.faixa_passando = True
                if self.ultimo_tempo_listra is not None:
                    dt_listra = tempo_atual - self.ultimo_tempo_listra
                    if dt_listra > 0.3:
                        vel_ms = self.distancia_listras_m / dt_listra
                        velocidade_fisica_kmh = vel_ms * 3.6
                self.ultimo_tempo_listra = tempo_atual
            elif not faixa_cruzando:
                self.faixa_passando = False
                
            if self.ultimo_tempo_listra is None:
                velocidade_fisica_kmh = 0.0
            else:
                dt_listra = tempo_atual - self.ultimo_tempo_listra
                if dt_listra > 2.0:
                    velocidade_fisica_kmh = (self.velocidade_instantanea_kmh / self.escala) * 0.95
                elif velocidade_fisica_kmh == 0.0:
                    velocidade_fisica_kmh = self.velocidade_instantanea_kmh / self.escala
                    
            velocidade_fisica_kmh = min(max(velocidade_fisica_kmh, 0.0), VEL_MAX_CARRINHO_KMH)

        elif self.modo == "sensor":
            gps_kmh = telemetria_ext["gps_speed_ms"] * 3.6
            accel_y = telemetria_ext["aceleracao_y"]
            
            if gps_kmh > 1.0:
                velocidade_fisica_kmh = gps_kmh
            else:
                if abs(accel_y) < 0.3:
                    velocidade_fisica_kmh = (self.velocidade_instantanea_kmh / self.escala) * 0.92
                else:
                    vel_ms = accel_y * delta_tempo
                    velocidade_fisica_kmh = (self.velocidade_instantanea_kmh / self.escala) + (vel_ms * 3.6)
            
            velocidade_fisica_kmh = min(max(velocidade_fisica_kmh, -VEL_MAX_CARRINHO_KMH), VEL_MAX_CARRINHO_KMH)

        elif self.modo == "real" and self.fator_px_mm is not None:
            if mediana_px_abs >= 0.3:
                desl_mm = mediana_px_abs * self.fator_px_mm
                velocidade_fisica_kmh = min(((desl_mm / 1000.0) / delta_tempo) * 3.6, VEL_MAX_CARRINHO_KMH) * sinal
        else:
            if mediana_px_abs >= 0.3:
                flow_pxs = mediana_px_abs / delta_tempo
                if self.flow_maximo_observado_pxs is None or flow_pxs > self.flow_maximo_observado_pxs:
                    self.flow_maximo_observado_pxs = flow_pxs
                    self._salvar_calibracao()
                proporcao = min(flow_pxs / self.flow_maximo_observado_pxs, 1.0)
                velocidade_fisica_kmh = (proporcao ** 0.75) * VEL_MAX_CARRINHO_KMH * sinal

        velocidade_kmh = velocidade_fisica_kmh * self.escala

        vel_anterior = self.velocidade_instantanea_kmh
        delta_v_aparente = abs(velocidade_kmh - vel_anterior) / max(delta_tempo, 0.001)
        if delta_v_aparente > 150.0 and abs(velocidade_kmh) > 2.0:
            velocidade_kmh = vel_anterior * 0.75 + velocidade_kmh * 0.25

        self.historico_recente.append(velocidade_kmh)
        if len(self.historico_recente) > 10:
            self.historico_recente.pop(0)
        self.velocidade_instantanea_kmh = sum(self.historico_recente) / len(self.historico_recente)

        delta_v_ms = (self.velocidade_instantanea_kmh - vel_anterior) / 3.6
        accel_crua = delta_v_ms / max(delta_tempo, 0.001)
        if abs(self.velocidade_instantanea_kmh) < 2.0:
            self.aceleracao_ms2 = 0.0
        else:
            self.aceleracao_ms2 = self.aceleracao_ms2 * 0.7 + accel_crua * 0.3

        if self.velocidade_instantanea_kmh > self.velocidade_maxima:
            self.velocidade_maxima = self.velocidade_instantanea_kmh
        self.soma_velocidades_curso += self.velocidade_instantanea_kmh
        self.qtd_medicoes_curso += 1
        self.velocidade_media_kmh = self.soma_velocidades_curso / self.qtd_medicoes_curso
        self.historico_grafico.append(self.velocidade_instantanea_kmh)
        if len(self.historico_grafico) > 300:
            self.historico_grafico.pop(0)

        self.ultimo_tempo = tempo_atual
        return self.desenhar_painel(frame_debug)

# ==============================================================================
#  LOOP PRINCIPAL (Standalone)
# ==============================================================================
if __name__ == "__main__":
    camera_ip = os.getenv("CAMERA_IP")
    video_source = f"http://{camera_ip}/video" if camera_ip else None
    print(f"[CAM] Fonte: {video_source}")

    if video_source is None:
        print("[IP WEBCAM] Aguardando IP. Use o Web Dashboard ou defina no .env.")
        cap = None
    elif str(video_source).startswith("http"):
        print("[IP WEBCAM] Usando AsyncIPCamera (Zero Delay Mode)...")
        cap = AsyncIPCamera(video_source)
    else:
        cap = cv2.VideoCapture(video_source)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    odometria = OdometriaVisual(escala=ESCALA_MAQUETE)
    cv2.namedWindow("Visao do Piloto - Neurodrive", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Visao do Piloto - Neurodrive", 1280, 720)

    print("\n[OK] Câmera conectada (Zero Delay Edition)!")
    try:
        while True:
            if cap is None:
                frame = np.zeros((720, 1280, 3), dtype=np.uint8)
                cv2.putText(frame, "AGUARDANDO CAMERA...", (400, 360), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 2)
                time.sleep(0.5)
            elif isinstance(cap, AsyncIPCamera):
                frame = cap.get_frame()
                if frame is None:
                    time.sleep(0.01)
                    continue
            else:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.5)
                    continue
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
                if frame.shape[1] != 1280 or frame.shape[0] != 720:
                    frame = cv2.resize(frame, (1280, 720))

            frame_out = odometria.calcular_velocidade(frame)
            cv2.imshow("Visao do Piloto - Neurodrive", frame_out)

            tecla = cv2.waitKey(1) & 0xFF
            if tecla in (ord('q'), ord('Q')):
                break
            odometria.processar_tecla(tecla)
    except KeyboardInterrupt:
        pass
    finally:
        odometria._salvar_calibracao()
        if isinstance(cap, AsyncIPCamera):
            cap.stop()
        else:
            cap.release()
        cv2.destroyAllWindows()
        print("[FIM] Neurodrive encerrado.")
